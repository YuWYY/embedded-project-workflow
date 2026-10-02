"""Original MPSoC case runner; existing export never reapplies prepare.tcl.

Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
import zipfile

PACKAGE = Path(__file__).resolve().parents[1]
UTILITY = PACKAGE.parent / 'controlled-project/scripts/run_clock.py'
spec = importlib.util.spec_from_file_location('epw_clock_helpers', UTILITY)
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
OWNER = '.soc-handoff-owner.json'


def mutate_once(path, original, replacement):
    source=path.read_text(encoding='utf-8')
    if original==replacement or source.count(original)!=1:
        raise ValueError('Negative injection requires exactly one matching original expression')
    changed=source.replace(original,replacement)
    if source==changed:
        raise ValueError('Negative injection made no change')
    path.write_text(changed,encoding='utf-8')


def check_xsa(path):
    """Product integrity only; address semantics belong to the independent checker."""
    try:
        with zipfile.ZipFile(path) as archive:
            names=archive.namelist()
            if len(names)!=len(set(names)) or archive.testzip() is not None:
                raise ValueError('Duplicate XSA members or corrupt member CRC')
            if not isinstance(json.loads(archive.read('xsa.json')),dict):
                raise ValueError('XSA metadata is not an object')
            definition=ET.fromstring(archive.read('hwdef.xml'))
            top=[e.get('Name') for e in definition.findall('.//File')
                 if e.get('Type')=='HW_HANDOFF' and e.get('BD_TYPE')=='DEFAULT_BD']
            if len(top)!=1 or not top[0] or top[0] not in names:
                raise ValueError('XSA must declare one existing DEFAULT_BD HWH')
            handoff=ET.fromstring(archive.read(top[0]))
            if not handoff.findall('.//MODULE'):
                raise ValueError('Declared top HWH has no hardware modules')
            if any(name.lower().endswith('.bit') for name in names):
                raise ValueError('This offline case must not export a bitstream')
            return {'sha256':helpers.sha(path),'declared_top_hwh':top[0],
                    'top_hwh_sha256':hashlib.sha256(archive.read(top[0])).hexdigest()}
    except (OSError,KeyError,ValueError,ET.ParseError,zipfile.BadZipFile) as error:
        raise RuntimeError(f'Invalid current XSA product: {error}') from error


def check_sdt(path):
    """Require a nonempty current top and readable in-tree include closure."""
    root=unlinked(path.parent)
    try:
        path=unlinked(path)
        first=path.read_text(encoding='utf-8')
        if '/dts-v1/;' not in first or not re.search(r'^\s*#include\s+"pl\.dtsi"',first,re.M):
            raise ValueError('Missing DTS header or generated PL include')
        pending=[path]; checked={}
        while pending:
            current=unlinked(pending.pop())
            if not current.is_relative_to(root):
                raise ValueError('SDT include escapes the current output')
            name=str(current.relative_to(root)).replace('\\','/')
            if name in checked:
                continue
            text=current.read_text(encoding='utf-8')
            if not text.strip():
                raise ValueError(f'Empty SDT product: {name}')
            checked[name]=helpers.sha(current)
            for include in re.findall(r'^\s*(?:#include|/include/)\s*["<]([^">]+)[">]',text,re.M):
                pending.append(current.parent/include)
        return checked
    except (OSError,ValueError,UnicodeError) as error:
        raise RuntimeError(f'Invalid current SDT products: {error}') from error


class ParameterError(ValueError):
    pass


def unlinked(path):
    """Check lexical ancestors before resolve; reject junctions as well as symlinks."""
    path = Path(os.path.abspath(path))
    for current in [*reversed(path.parents), path]:
        if current.exists() or current.is_symlink():
            info = current.lstat()
            if current.is_symlink() or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ParameterError(f'Linked path is unsupported: {current}')
    return path.resolve()


def checked_tree(root):
    pending=[root]
    while pending:
        directory=pending.pop()
        for path in directory.iterdir():
            unlinked(path)
            if path.is_dir():
                pending.append(path)


def project_inputs(project):
    """Allow only the isolated example and internal current project sources."""
    project=unlinked(project)
    owned=project.parent.parent
    marker=owned/OWNER
    if not marker.is_file() or json.loads(marker.read_text()) .get('format')!='epw-soc-handoff/1':
        raise ParameterError('Existing export requires this example ownership marker')
    if project.name!='soc_handoff.xpr' or project.parent.name!='project':
        raise ParameterError('Unsupported project layout')
    checked_tree(owned)
    refs={str(project):helpers.sha(project)}
    replacements={'$PPRDIR':str(project.parent), '$PSRCDIR':str(project.parent/'soc_handoff.srcs'),
                  '$PGENDIR':str(project.parent/'soc_handoff.gen'),
                  '$PRUNDIR':str(project.parent/'soc_handoff.runs'),
                  '$PCACHEDIR':str(project.parent/'soc_handoff.cache'),
                  '$PIPUSERFILESDIR':str(project.parent/'soc_handoff.ip_user_files')}
    tree=ET.parse(project)
    for option in tree.findall('.//Option'):
        name=option.get('Name','').lower()
        if ('tcl.pre' in name or 'tcl.post' in name) and option.get('Val','').strip():
            raise ParameterError('Custom build hooks are outside this narrow runner')
        if option.get('Name') in ('IPRepoPaths','VerilogIncludeDirs') and option.get('Val','').strip():
            raise ParameterError('Additional source/include repositories are outside this narrow runner')
        # Vivado stores outputs in both options and Run/FileSet attributes.
        value=option.get('Val','')
        if ('dir' in name or 'path' in name or name=='ipoutputrepo') and value:
            for token,replacement in replacements.items():
                value=value.replace(token,replacement)
            if '$' in value or not unlinked(project.parent/value).is_relative_to(owned):
                raise ParameterError(f'External or unsupported project directory option: {name}')
    for element in tree.iter():
        for name,value in element.attrib.items():
            if name.lower().endswith('dir') and value:
                for token,replacement in replacements.items():
                    value=value.replace(token,replacement)
                if '$' in value or not unlinked(project.parent/value).is_relative_to(owned):
                    raise ParameterError(f'External or unsupported project output directory: {name}')
    for element in tree.findall('.//File'):
        raw=element.get('Path','')
        for name,value in replacements.items():
            raw=raw.replace(name,value)
        if '$' in raw:
            raise ParameterError(f'Unsupported source path variable: {raw}')
        path=unlinked(project.parent/raw)
        if not path.is_relative_to(owned) or not path.is_file():
            raise ParameterError(f'Source outside this isolated project or missing: {path}')
        refs[str(path)]=helpers.sha(path)
    expected=owned/'sources/counter32.v'
    if str(expected) not in refs:
        raise ParameterError('Expected the isolated counter32 source')
    return refs


def check_source_retention(project, before, after):
    """Preserve user HDL/constraints; record this case's tool-managed wrapper separately."""
    generated = str(unlinked(project.parent/'soc_handoff.gen/sources_1/bd/system/hdl/system_wrapper.v'))
    user_sources = {}
    for path, digest in before.items():
        if Path(path).suffix.lower() not in ('.v', '.sv', '.vhd', '.vhdl', '.xdc'):
            continue
        if path == generated:
            continue
        if path not in after or after[path] != digest or helpers.sha(Path(path)) != digest:
            raise RuntimeError(f'Current user source changed or lost its project reference: {path}')
        user_sources[path] = digest
    changes = []
    if generated in before and generated not in after:
        raise RuntimeError(f'Tool-managed wrapper lost its project reference: {generated}')
    if before.get(generated) != after.get(generated):
        changes.append({'path': generated, 'owner': 'Vivado make_wrapper for this case',
                        'before_sha256': before.get(generated), 'after_sha256': after.get(generated)})
    return {'user_sources': user_sources, 'generated_wrapper_changes': changes}


def native(executable, arguments, directory, report, timeout, expected_success=True):
    """Run one real process, preserving launch/wait/validation failures atomically."""
    directory.mkdir(parents=True, exist_ok=True)
    report.mkdir(parents=True, exist_ok=False)
    record = dict(status='running', phase='initialize', failure_phase=None,
                  failure_type=None, command=[str(executable), *map(str, arguments)],
                  cwd=str(directory), returncode=None, pid=None,
                  timeout_seconds=timeout, timed_out=False, interrupted=False,
                  cleanup=None, diagnostics=[], expected_success=expected_success,
                  utility_sha256=helpers.sha(UTILITY))
    result = report / 'result.json'
    started = time.monotonic()
    process = None
    def save(phase):
        record['phase'] = phase
        helpers.write_json(result, record)
    try:
        save('initialize')
        with (report / 'stdout.log').open('wb') as output:
            save('launch')
            process = subprocess.Popen(record['command'], cwd=directory,
                    stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                    startupinfo=helpers.hidden_startup(),
                    creationflags=subprocess.CREATE_NEW_CONSOLE)
            record['pid'] = process.pid
            save('wait')
            record['returncode'] = process.wait(timeout=timeout)
        save('validate_exit')
        if expected_success and record['returncode'] != 0:
            raise RuntimeError('Native process failed')
        if not expected_success and record['returncode'] == 0:
            raise RuntimeError('Negative native process unexpectedly passed')
        record['status'] = 'pass'
    except (Exception, KeyboardInterrupt) as error:
        record.update(status='fail', failure_phase=record['phase'],
                      failure_type=type(error).__name__,
                      timed_out=isinstance(error, subprocess.TimeoutExpired),
                      interrupted=isinstance(error, KeyboardInterrupt))
        record['diagnostics'].append(str(error))
        if process is not None:
            # A launcher that exited during failure leaves descendant state unknown.
            # The shared helper records that uncertainty without killing unrelated PIDs.
            record['cleanup'] = helpers.cleanup_owned_process(process)
            record['returncode'] = process.returncode
    record['elapsed_seconds'] = round(time.monotonic()-started, 3)
    record['process_cleanup_complete'] = (record['cleanup'] is None or record['cleanup']['complete'])
    save('finished')
    return record


def run(args):
    root = unlinked(args.output)
    try:
        str(root).encode('ascii')
    except UnicodeError as error:
        raise ParameterError('Output needs an ASCII path') from error
    if root.exists() and any(root.iterdir()):
        raise ParameterError('Output must be a new or empty ASCII directory')
    if root.is_relative_to(PACKAGE.parent) or PACKAGE.is_relative_to(root):
        raise ParameterError('Output must be separate from and not an ancestor of the source package')
    executable = unlinked(args.vivado)
    if os.name != 'nt' or not executable.is_file():
        raise ParameterError('Windows and an existing Vivado installation required')
    install=executable.parent.parent
    if install.name.lower()=='vivado':
        install=install.parent
    if root.is_relative_to(install) or install.is_relative_to(root):
        raise ParameterError('Output must be separate from the tool installation')
    project = unlinked(args.project) if args.project else None
    if project and not project.is_file():
        raise ParameterError('The supplied current .xpr does not exist')
    if args.command == 'export' and (not project or not project.is_file()):
        raise ParameterError('Export requires the current .xpr')
    if args.command not in ('export','address-overlap') and project:
        raise ParameterError('--project is accepted only by export or an isolated overlap copy')
    if project and (root.is_relative_to(project.parent.parent) or project.parent.parent.is_relative_to(root)):
        raise ParameterError('Current project and new output must be separate')
    before=project_inputs(project) if project else {}
    for folder in ('scripts','sources'):
        checked_tree(PACKAGE/folder)
    plans={'prepare':['prepare','export','sdt'], 'export':['export','sdt'],
           'address-unassigned':['prepare','unassigned'], 'address-overlap':['prepare','overlap']}
    planned=plans.get(args.command,['simulate'])
    if args.command=='address-overlap' and project:
        planned=['overlap']
    summary = dict(command=args.command, status='running', phase='initialize', failure_phase=None,
        stages=[dict(name=name,status='NOT_RUN',returncode=None) for name in planned],
        coverage='offline only; no implementation, bitstream, processor build, or hardware',
        source_sha256={}, input_sha256=before, project=str(project) if project else None,
        artifact_generation='NOT_RUN', cross_artifact_semantics='NOT_RUN; use independent checker',
        process_cleanup_complete=None)
    root.mkdir(parents=True, exist_ok=True)
    helpers.write_json(root/'result.json',summary)
    def phase(name):
        summary['phase']=name
        helpers.write_json(root/'result.json',summary)
    def stage(name, script, arguments, expected_success=True, binary=None):
        phase(name)
        report=root/'reports'/name
        slot=planned.index(name)
        summary['stages'][slot].update(status='running', report=str(report),returncode=None)
        helpers.write_json(root/'result.json',summary)
        if binary is None:
            argv=['-mode','batch','-notrace','-source',root/'scripts'/script,'-tclargs',*arguments]
        else:
            argv=[root/'scripts'/script,*arguments]
        try:
            record=native(binary or executable, argv, root, report, args.timeout, expected_success)
        except (Exception,KeyboardInterrupt) as error:
            # Preserve that execution started even if native's final atomic save failed.
            try:
                observed=json.loads((report/'result.json').read_text())
            except (OSError,ValueError):
                observed={}
            summary['stages'][slot].update(observed)
            summary['stages'][slot].update(status='UNCONFIRMED',
                reporting_error=f'{type(error).__name__}: {error}',process_cleanup_complete=False)
            raise
        summary['stages'][slot]={'name':name, **record}
        helpers.write_json(root/'result.json',summary)
        if record['interrupted']:
            raise KeyboardInterrupt('Native wait interrupted')
        if record['status']!='pass':
            raise RuntimeError(f'{name} failed: {report}')
        print(f'{name}: pass (native returncode={record["returncode"]})', flush=True)
    try:
        phase('copy_inputs')
        shutil.copytree(PACKAGE / 'scripts', root / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(PACKAGE / 'sources', root / 'sources')
        if args.command == 'sim-missing-clear':
            p=root/'sources/counter32.v'
            mutate_once(p,"    else if (control[1]) count <= 32'd0;\n", '')
        if args.command == 'sim-missing-pause':
            p=root/'sources/counter32.v'
            mutate_once(p,'else if (control[0]) count <=', 'else count <=')
        summary['source_sha256']={str(p.relative_to(root)).replace('\\','/'):helpers.sha(p)
            for folder in ('scripts','sources') for p in sorted((root/folder).rglob('*')) if p.is_file()}
        if args.command in ('prepare','address-unassigned','address-overlap'):
            helpers.write_json(root/OWNER,dict(format='epw-soc-handoff/1',owner_id=uuid.uuid4().hex))
        if args.command=='address-overlap' and project:
            phase('copy_current_project_for_negative')
            shutil.copytree(project.parent,root/'project')
            shutil.copy2(project.parent.parent/'sources/counter32.v',root/'sources/counter32.v')
            project=root/'project/soc_handoff.xpr'
            project_inputs(project)
            summary['project']=str(project)
            summary['source_sha256']['sources/counter32.v']=helpers.sha(root/'sources/counter32.v')
        elif args.command in ('prepare','address-unassigned','address-overlap'):
            stage('prepare','prepare.tcl',[root/'sources',root])
            project=root/'project/soc_handoff.xpr'
            summary['project']=str(project)
        if args.command == 'address-overlap':
            stage('overlap','overlap.tcl',[project],expected_success=False)
            log=(root/'reports/overlap/stdout.log').read_text(errors='replace')
            if ('NEGATIVE_OVERLAP_GPIO_READY' not in log or 'Native address assignment unexpectedly accepted' in log
                or not re.search(r'(?:ERROR|CRITICAL WARNING): \[BD [^\]]+\].*(?:overlap|conflict)',log,re.I)):
                raise RuntimeError('Address negative did not fail with native overlap/conflict diagnostic')
        elif args.command == 'address-unassigned':
            stage('unassigned','unassigned.tcl',[project],expected_success=False)
            log=(root/'reports/unassigned/stdout.log').read_text(errors='replace')
            if ('NEGATIVE_UNASSIGNED_GPIO_READY' not in log or 'Native validate unexpectedly accepted' in log
                or not re.search(r'(?:ERROR|CRITICAL WARNING): \[BD [^\]]+\].*(?:not assigned|unassigned|unmapped)',log,re.I)):
                raise RuntimeError('Address negative did not fail in native validate')
        elif args.command in ('prepare','export'):
            stage('export','export.tcl',[project,root])
            phase('export_products')
            summary['xsa_integrity']=check_xsa(root/'hardware.xsa')
            sdt=executable.parent/'sdtgen.bat'
            stage('sdt','sdt.tcl',[root/'hardware.xsa',root/'sdt'],binary=sdt)
            phase('sdt_products')
            summary['sdt_product_sha256']=check_sdt(root/'sdt/system-top.dts')
            summary['artifact_generation']='pass'
        else:
            negative=args.command!='sim'
            stage('simulate','simulate.tcl',[root/'sources',root],expected_success=not negative)
            if negative:
                logs=list((root/'simulation').rglob('simulate.log'))
                reason='CLEAR_DOMINANCE' if args.command=='sim-missing-clear' else 'PAUSE_HOLD'
                text=logs[0].read_text(errors='replace') if len(logs)==1 else ''
                if (not re.search(r'COUNTER_ASSERT '+reason+r' expected=[0-9a-fA-F]+ actual=[0-9a-fA-F]+',text)
                    or 'COUNTER_ASSERT timeout' in text):
                    raise RuntimeError('Negative failed without the expected counter assertion')
            elif not (root/'counter_result.txt').read_text().startswith('PASS checks=18'):
                raise RuntimeError('Counter business marker missing')
        phase('source_retention')
        for relative,digest in summary['source_sha256'].items():
            if helpers.sha(root/relative)!=digest:
                raise RuntimeError(f'Copied input changed during native processing: {relative}')
        if project:
            summary['current_input_sha256']=project_inputs(project)
            summary['source_retention']=check_source_retention(project,before,summary['current_input_sha256'])
        summary['status']='pass'
    except (Exception, KeyboardInterrupt) as error:
        summary.update(status='fail', failure_phase=summary['phase'], interrupted=isinstance(error,KeyboardInterrupt),
                       error=f'{type(error).__name__}: {error}')
        raise
    finally:
        summary['process_cleanup_complete']=all(x.get('process_cleanup_complete',True) for x in summary['stages'])
        helpers.write_json(root/'result.json',summary)
    return root


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','export','sim','sim-missing-clear','sim-missing-pause','address-unassigned','address-overlap'))
    parser.add_argument('--vivado',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--project',type=Path)
    parser.add_argument('--timeout',type=helpers.positive_timeout,default=900.0)
    args=parser.parse_args()
    try:
        print(run(args))
        return 0
    except KeyboardInterrupt:
        return 130
    except ParameterError as error:
        print(f'ParameterError: {error}',file=sys.stderr)
        return 2
    except (ValueError,UnicodeError,RuntimeError,OSError) as error:
        print(f'{type(error).__name__}: {error}',file=sys.stderr)
        return 1

if __name__=='__main__':
    raise SystemExit(main())
