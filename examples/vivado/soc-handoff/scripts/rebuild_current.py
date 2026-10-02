"""Reconstruct this narrow case from the current XPR/BD/RTL in an empty directory.

Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT
The saved BD remains the maintenance source. No initial-design Tcl is executed.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import uuid
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('current_case_runner', HERE / 'run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def semantic_bd(path):
    """Compare all saved design data except locations and validation bookkeeping."""
    design = json.loads(path.read_text(encoding='utf-8'))['design']
    design['design_info'].pop('gen_directory', None)
    design['design_info'].pop('validated', None)
    for component in design.get('components', {}).values():
        component.pop('xci_path', None)
    return design


def differences(left, right, prefix=''):
    if type(left) is not type(right):
        return [dict(path=prefix, before=left, after=right)]
    if isinstance(left, dict):
        found = []
        for key in sorted(left.keys() | right.keys()):
            if key not in left or key not in right:
                found.append(dict(path=prefix+'/'+key, before=left.get(key), after=right.get(key)))
            else:
                found.extend(differences(left[key], right[key], prefix+'/'+key))
        return found
    return [] if left == right else [dict(path=prefix, before=left, after=right)]


def read_case(project):
    if not project.is_file():
        raise runner.ParameterError('The supplied current .xpr does not exist')
    try:
        refs = runner.project_inputs(project)
        tree = ET.parse(project)
    except ET.ParseError as error:
        raise runner.ParameterError(f'Invalid current XPR: {error}') from error
    config = {p.get('Name'): p.get('Val') for p in tree.findall('./Configuration/Option')}
    for key in ('Part', 'BoardPart', 'DefaultLib'):
        if not (config.get(key) or '').strip():
            raise runner.ParameterError(f'Missing current project property: {key}')
    fileset = tree.find('./FileSets/FileSet[@Name="sources_1"]')
    if fileset is None:
        raise runner.ParameterError('Missing sources_1 fileset')
    options = {p.get('Name'): p.get('Val') for p in fileset.findall('./Config/Option')}
    for name, value in options.items():
        lowered = name.lower()
        if value and any(token in lowered for token in ('define', 'generic', 'include', 'verilog', 'vhdl')):
            raise runner.ParameterError(f'Custom compile setting requires an explicit adapter: {name}')
    if options.get('TopLib', 'xil_defaultlib') != 'xil_defaultlib':
        raise runner.ParameterError('A custom top library requires an explicit adapter')
    if options.get('TopModule') != 'system_wrapper' or options.get('DesignMode') != 'RTL':
        raise runner.ParameterError('Only the current system_wrapper RTL case is supported')
    if config.get('DefaultLib') != 'xil_defaultlib':
        raise runner.ParameterError('Additional HDL library configuration is unsupported')
    if tree.findall('./FileSets/FileSet[@Name="constrs_1"]/File'):
        raise runner.ParameterError('Additional user constraints require an explicit adapter')
    if tree.findall('./FileSets/FileSet[@Name="sim_1"]/File'):
        raise runner.ParameterError('Additional simulation sources require an explicit adapter')
    source_root = project.parent.parent
    managed_wrapper = project.parent/'soc_handoff.gen/sources_1/bd/system/hdl/system_wrapper.v'
    for source in fileset.findall('./File'):
        attributes = source.findall('./FileInfo/Attr')
        used_in = {a.get('Val') for a in attributes if a.get('Name') == 'UsedIn'}
        if used_in != {'synthesis', 'implementation', 'simulation'}:
            raise runner.ParameterError('Custom source usage requires an explicit adapter')
        for attribute in attributes:
            name, value = attribute.get('Name'), attribute.get('Val', '')
            if name == 'UsedIn':
                continue
            if name in ('ImportPath', 'ImportTime'):
                continue  # Native import provenance, not an active source/compile override.
            if name == 'AutoDisabled' and source.get('Path', '').lower().endswith('.bd'):
                continue  # Native empty-BD dependency bookkeeping; retained via import.
            if name == 'Library' and value == 'xil_defaultlib':
                continue
            if value:
                raise runner.ParameterError(f'Explicit per-file setting requires an adapter: {name}')
    bds = []
    for raw in refs:
        path = Path(raw)
        if path.suffix.lower() == '.bd':
            design = json.loads(path.read_text(encoding='utf-8'))['design']
            name = design['design_info']['name']
            if name != path.stem or not name.replace('_', '').isalnum():
                raise runner.ParameterError('Unsupported BD identity')
            if name != 'system' and design.get('design_tree'):
                raise runner.ParameterError('Only empty additional BDs are supported')
            bds.append(path)
        elif path.suffix.lower() in ('.v', '.sv', '.vhd', '.vhdl', '.xdc'):
            if path != source_root/'sources/counter32.v' and path != managed_wrapper:
                raise runner.ParameterError('Additional user HDL requires an explicit adapter')
    if [p.stem for p in bds].count('system') != 1:
        raise runner.ParameterError('Expected exactly one current system.bd')
    return refs, config, options, bds


def effective_xci(bd):
    design = json.loads(bd.read_text(encoding='utf-8'))['design']
    result, hashes = {}, {}
    for instance, component in design.get('components', {}).items():
        name = component['xci_name']
        path = runner.unlinked(bd.parent/'ip'/name/(name+'.xci'))
        if not path.is_relative_to(bd.parent) or not path.is_file():
            raise RuntimeError(f'Missing current native XCI: {instance}')
        data = json.loads(path.read_text(encoding='utf-8'))['ip_inst']
        if not isinstance(data['parameters'].get('component_parameters'), dict):
            raise RuntimeError(f'Missing required XCI component parameter map: {instance}')
        if 'model_parameters' not in data['parameters'] and (
                instance != 'counter32_0' or data['component_reference'] != 'xilinx.com:module_ref:counter32:1.0'):
            raise RuntimeError(f'Missing required native IP model parameter map: {instance}')
        result[instance] = dict(component_reference=data['component_reference'],
            ip_revision=data['ip_revision'], parameters={
                kind: {key: [entry.get('value') for entry in values]
                       for key, values in data['parameters'].get(kind, {}).items()}
                for kind in ('component_parameters', 'model_parameters')})
        hashes[str(path)] = runner.helpers.sha(path)
    return result, hashes


def effective_hwh(xsa):
    identity = runner.check_xsa(xsa)
    with zipfile.ZipFile(xsa) as archive:
        document = ET.fromstring(archive.read(identity['declared_top_hwh']))
    modules = {}
    for module in document.findall('.//MODULE'):
        name = module.get('INSTANCE')
        if not name or name in modules:
            raise RuntimeError('Duplicate or missing native HWH instance')
        params = {}
        for parameter in module.findall('./PARAMETERS/PARAMETER'):
            key = parameter.get('NAME')
            if not key or key in params:
                raise RuntimeError('Duplicate or missing HWH parameter')
            params[key] = parameter.get('VALUE')
        memory_ranges = sorted((entry.attrib for entry in module.findall('.//MEMRANGE')),
                               key=lambda item: json.dumps(item, sort_keys=True))
        modules[name] = dict(attributes=module.attrib, parameters=params, memory_ranges=memory_ranges)
    return modules, identity


def verify_gpio_address(bd, hardware):
    design = json.loads(bd.read_text(encoding='utf-8'))['design']
    segment = design['addressing']['/zynq_ultra_ps_e_0']['address_spaces']['Data']['segments']['SEG_axi_gpio_0_Reg']
    if segment['address_block'] != '/axi_gpio_0/S_AXI/Reg':
        raise RuntimeError('Unsupported source GPIO address path')
    base = int(segment['offset'], 0)
    raw = segment['range'].upper()
    size = int(raw[:-1], 0)*1024 if raw.endswith('K') else int(raw, 0)
    mapped = [entry for entry in hardware['zynq_ultra_ps_e_0']['memory_ranges']
              if entry.get('INSTANCE') == 'axi_gpio_0' and entry.get('SLAVEBUSINTERFACE') == 'S_AXI'
              and entry.get('ADDRESSBLOCK') == 'Reg']
    if (len(mapped) != 1 or mapped[0].get('MASTERBUSINTERFACE') != 'M_AXI_HPM0_FPD'
            or int(mapped[0]['BASEVALUE'], 0) != base
            or int(mapped[0]['HIGHVALUE'], 0)+1 != base+size):
        raise RuntimeError('Reference/current BD and XSA GPIO handoff disagree')


def resolve_native_expansions(raw_differences, before_xci, after_xci, before_hwh, after_hwh):
    """Explain explicit native expansions only with complete effective agreement."""
    if differences(before_xci, after_xci) or differences(before_hwh, after_hwh):
        raise RuntimeError('Native effective configuration differs')
    explained = []
    for difference in raw_differences:
        parts = difference['path'].split('/')
        if (len(parts) != 5 or parts[1] != 'components' or parts[3] != 'parameters'
                or difference['before'] is not None or not isinstance(difference['after'], dict)
                or set(difference['after']) != {'value'}):
            raise RuntimeError(f'Unexplained saved BD difference: {difference["path"]}')
        instance, parameter = parts[2], parts[4]
        value = difference['after']['value']
        if (instance, parameter, value) != ('zynq_ultra_ps_e_0', 'PSU_MIO_22_INPUT_TYPE', 'cmos'):
            raise RuntimeError(f'Unreviewed native expansion: {difference["path"]}')
        expected = before_xci.get(instance, {}).get('parameters', {}).get('component_parameters', {}).get(parameter)
        hardware = before_hwh.get(instance, {}).get('parameters', {}).get(parameter)
        if expected != [value] or hardware != value:
            raise RuntimeError(f'No matching native evidence for expansion: {difference["path"]}')
        explained.append(dict(**difference, effective_value=value,
            reason='B and C complete XCI component/model values and HWH module attributes/parameters agree'))
    return explained


def post_validate(args):
    """Read actual finished artifacts; preserve the original run record unchanged."""
    root = runner.unlinked(args.output)
    source = runner.unlinked(args.project)
    reference = runner.unlinked(args.reference_project)
    reference_xsa = runner.unlinked(args.reference_xsa)
    report_name = getattr(args, 'post_report_name', 'post-validation.json')
    if not re.fullmatch(r'post-validation(?:-[A-Za-z0-9_-]+)?\.json', report_name):
        raise runner.ParameterError('Post report name must be post-validation[-suffix].json')
    result = root/report_name
    if result.exists():
        raise runner.ParameterError('Post-validation record already exists; preserve it')
    native_file = root/'result.json'
    native = json.loads(native_file.read_text(encoding='utf-8'))
    summary = dict(status='running', phase='initialize', failure_phase=None,
        native_result_sha256=runner.helpers.sha(native_file),
        original_native_overall_status=native['status'], original_native_error=native.get('error'),
        native_script_sha256=native.get('copied_input_sha256', {}),
        post_validator_sha256=runner.helpers.sha(Path(__file__)),
        source_project=str(source), reference_project=str(reference),
        reference_xsa=str(reference_xsa), cross_artifact_semantics='NOT_RUN; independent checker required',
        software_platform='NOT_RUN', bsp='NOT_RUN', a53_application_build='NOT_RUN',
        hardware='NOT_RUN', implementation='NOT_RUN', bitstream='NOT_RUN')
    runner.helpers.write_json(result, summary)
    try:
        summary['phase'] = 'native_provenance'
        if (len(native['stages']) != 3
                or set(s['name'] for s in native['stages']) != {'import_current', 'export', 'sdt'}
                or any(s['status'] != 'pass' or s['returncode'] != 0 for s in native['stages'])):
            raise RuntimeError('All three original native stages must have passed')
        if Path(native['source_project']) != source:
            raise RuntimeError('Native source identity differs')
        source_refs, source_config, source_options, source_bds = read_case(source)
        rebuilt = root/'project/soc_handoff.xpr'
        rebuilt_refs, rebuilt_config, rebuilt_options, rebuilt_bds = read_case(rebuilt)
        reference_refs, reference_config, reference_options, reference_bds = read_case(reference)
        if native['input_sha256'] != source_refs:
            raise RuntimeError('Native input identity map is incomplete or changed')
        for raw, digest in native['input_sha256'].items():
            if runner.helpers.sha(Path(raw)) != digest:
                raise RuntimeError(f'Original native input changed: {raw}')
        expected_copies = {'scripts/'+name for name in
            ('rebuild_current.py', 'rebuild_current.tcl', 'export.tcl', 'sdt.tcl')}
        expected_copies.add('sources/counter32.v')
        expected_copies.update('input_bd/'+p.stem+'/'+p.name for p in source_bds)
        if set(native['copied_input_sha256']) != expected_copies:
            raise RuntimeError('Native copied-input identity map is incomplete')
        for relative, digest in native['copied_input_sha256'].items():
            if runner.helpers.sha(root/relative) != digest:
                raise RuntimeError(f'Copied native input changed: {relative}')
        for key in ('Part', 'BoardPart', 'DefaultLib'):
            if len({config[key] for config in (source_config, rebuilt_config, reference_config)}) != 1:
                raise RuntimeError(f'Project property differs: {key}')
        if len({options['TopModule'] for options in (source_options, rebuilt_options, reference_options)}) != 1:
            raise RuntimeError('Top differs')
        counter = source_refs[str(source.parent.parent/'sources/counter32.v')]
        if any(runner.helpers.sha(p) != counter for p in
               (root/'sources/counter32.v', reference.parent.parent/'sources/counter32.v')):
            raise RuntimeError('Original counter implementation differs')
        reference_record = json.loads((reference_xsa.parent/'result.json').read_text(encoding='utf-8'))
        if Path(reference_record['project']) != reference:
            raise RuntimeError('Reference native project identity differs')
        if (len(reference_record['stages']) != 2
                or {s['name'] for s in reference_record['stages']} != {'export', 'sdt'}
                or any(s['status'] != 'pass' or s['returncode'] != 0 for s in reference_record['stages'])):
            raise RuntimeError('Reference native stages did not pass')
        if reference_record['xsa_integrity']['sha256'] != runner.helpers.sha(reference_xsa):
            raise RuntimeError('Reference XSA identity differs')
        if reference_record['current_input_sha256'] != reference_refs:
            raise RuntimeError('Reference current-input identity map is incomplete or changed')
        for raw, digest in reference_record['current_input_sha256'].items():
            if runner.helpers.sha(Path(raw)) != digest:
                raise RuntimeError(f'Reference native source changed: {raw}')
        by_name = lambda paths: {p.stem: p for p in paths}
        originals, actuals, references = map(by_name, (source_bds, rebuilt_bds, reference_bds))
        if set(originals) != set(actuals) or set(originals) != set(references):
            raise RuntimeError('Saved BD set differs')
        summary['phase'] = 'full_effective_configuration'
        raw_differences = {}
        for name, path in originals.items():
            if differences(semantic_bd(path), semantic_bd(references[name])):
                raise RuntimeError('Reference saved BD is not the same current input')
            raw_differences[name] = differences(semantic_bd(path), semantic_bd(actuals[name]))
        summary['raw_bd_differences'] = raw_differences
        if any(value for name, value in raw_differences.items() if name != 'system'):
            raise RuntimeError('An additional saved BD differs')
        before_xci, before_xci_hashes = effective_xci(references['system'])
        after_xci, after_xci_hashes = effective_xci(actuals['system'])
        before_hwh, before_xsa_id = effective_hwh(reference_xsa)
        after_hwh, after_xsa_id = effective_hwh(root/'hardware.xsa')
        if after_xsa_id != native['xsa_integrity']:
            raise RuntimeError('Current XSA is not the recorded native product')
        verify_gpio_address(references['system'], before_hwh)
        verify_gpio_address(actuals['system'], after_hwh)
        summary['effective_xci_differences'] = differences(before_xci, after_xci)
        summary['effective_hwh_differences'] = differences(before_hwh, after_hwh)
        summary['explained_native_expansions'] = resolve_native_expansions(
            [item for values in raw_differences.values() for item in values],
            before_xci, after_xci, before_hwh, after_hwh)
        summary['xci_input_sha256'] = dict(**before_xci_hashes, **after_xci_hashes)
        summary['xsa_identities'] = dict(reference=before_xsa_id, rebuilt=after_xsa_id)
        summary['sdt_product_sha256'] = runner.check_sdt(root/'sdt/system-top.dts')
        if summary['sdt_product_sha256'] != native['sdt_product_sha256']:
            raise RuntimeError('Current SDT is not the recorded native product')
        summary['project_input_sha256'] = dict(source=source_refs, reference=reference_refs, rebuilt=rebuilt_refs)
        summary['source_file_attributes'] = {
            name: [dict(path=f.get('Path'), attributes=[a.attrib for a in f.findall('./FileInfo/Attr')])
                   for f in ET.parse(path).findall('./FileSets/FileSet[@Name="sources_1"]/File')]
            for name, path in [('source', source), ('reference', reference), ('rebuilt', rebuilt)]}
        summary['user_rtl_retention'] = 'pass'
        summary['raw_bd_equal'] = not any(raw_differences.values())
        summary['effective_configuration_equal'] = True
        summary['status'] = 'pass'
        summary['phase'] = 'finished'
    except (Exception, KeyboardInterrupt) as error:
        summary.update(status='fail', failure_phase=summary['phase'], error=f'{type(error).__name__}: {error}')
        if isinstance(error, runner.ParameterError):
            raise RuntimeError(f'Post-validation rejected current artifacts: {error}') from error
        raise
    finally:
        runner.helpers.write_json(result, summary)
    return result


def run(args):
    root = runner.unlinked(args.output)
    project = runner.unlinked(args.project)
    executable = runner.unlinked(args.vivado)
    if not project.is_file():
        raise runner.ParameterError('The supplied current .xpr does not exist')
    try:
        str(root).encode('ascii')
    except UnicodeError as error:
        raise runner.ParameterError('Output needs an ASCII path') from error
    if root.exists() and any(root.iterdir()):
        raise runner.ParameterError('Reconstruction output must be new or empty')
    install = executable.parent.parent
    if install.name.lower() == 'vivado':
        install = install.parent
    protected = [project.parent.parent, runner.PACKAGE.parent, install]
    if any(root.is_relative_to(p) or p.is_relative_to(root) for p in protected):
        raise runner.ParameterError('Output must be separate from source, project and installation')
    if os.name != 'nt' or not executable.is_file():
        raise runner.ParameterError('An installed Windows Vivado is required')
    refs, config, options, bds = read_case(project)
    runner.checked_tree(HERE)
    stages = ['import_current', 'export', 'sdt']
    summary = dict(status='running', phase='initialize', failure_phase=None,
        source_project=str(project), input_sha256=refs, current_input_sha256={},
        stages=[dict(name=n, status='NOT_RUN', returncode=None) for n in stages],
        configuration_source='current saved BD; no prepare.tcl',
        source_configuration=dict(part=config['Part'], board_part=config['BoardPart'],
            top=options['TopModule'], default_lib=config['DefaultLib']),
        preserved_bds=[p.name for p in bds], bd_semantics='NOT_RUN',
        user_rtl_retention='NOT_RUN', artifact_generation='NOT_RUN',
        cross_artifact_semantics='NOT_RUN; independent BD/XSA/SDT check required',
        software_platform='NOT_RUN', bsp='NOT_RUN', a53_application_build='NOT_RUN',
        implementation='NOT_RUN', bitstream='NOT_RUN', hardware='NOT_RUN')
    root.mkdir(parents=True, exist_ok=True)
    result = root/'result.json'
    runner.helpers.write_json(result, summary)  # No native launch before this succeeds.

    def save(phase):
        summary['phase'] = phase
        runner.helpers.write_json(result, summary)

    def stage(name, binary, argv):
        save(name)
        index = stages.index(name)
        report = root/'reports'/name
        summary['stages'][index].update(status='running', report=str(report))
        runner.helpers.write_json(result, summary)
        try:
            observed = runner.native(binary, argv, root, report, args.timeout)
        except (Exception, KeyboardInterrupt) as error:
            try:
                observed = json.loads((report/'result.json').read_text())
            except (OSError, ValueError):
                observed = {}
            summary['stages'][index].update(observed)
            summary['stages'][index].update(status='UNCONFIRMED',
                reporting_error=str(error), process_cleanup_complete=False)
            raise
        summary['stages'][index] = dict(name=name, **observed)
        runner.helpers.write_json(result, summary)
        if observed['interrupted']:
            raise KeyboardInterrupt('Native wait interrupted')
        if observed['status'] != 'pass':
            raise RuntimeError(f'{name} failed; inspect {report}')
        print(f'{name}: pass (native returncode={observed["returncode"]})', flush=True)

    try:
        save('copy_current_inputs')
        (root/'scripts').mkdir()
        for name in ('rebuild_current.py', 'rebuild_current.tcl', 'export.tcl', 'sdt.tcl'):
            shutil.copy2(HERE/name, root/'scripts'/name)
        (root/'sources').mkdir()
        shutil.copy2(project.parent.parent/'sources/counter32.v', root/'sources/counter32.v')
        for path in bds:
            target = root/'input_bd'/path.stem/path.name
            target.parent.mkdir(parents=True)
            shutil.copy2(path, target)
        summary['copied_input_sha256'] = {
            p.relative_to(root).as_posix(): runner.helpers.sha(p)
            for directory in ('scripts', 'sources', 'input_bd')
            for p in (root/directory).rglob('*') if p.is_file()}
        summary['runner_sha256'] = runner.helpers.sha(HERE/'run.py')
        summary['helper_sha256'] = runner.helpers.sha(runner.UTILITY)
        runner.helpers.write_json(root/runner.OWNER,
            dict(format='epw-soc-handoff/1', owner_id=uuid.uuid4().hex))
        save('inputs_fixed')
        stage('import_current', executable,
            ['-mode', 'batch', '-notrace', '-source', root/'scripts/rebuild_current.tcl',
             '-tclargs', root, config['Part'], config['BoardPart'], options['TopModule'],
             *(p.stem for p in bds)])
        rebuilt = root/'project/soc_handoff.xpr'
        stage('export', executable,
            ['-mode', 'batch', '-notrace', '-source', root/'scripts/export.tcl',
             '-tclargs', rebuilt, root])
        save('xsa_products')
        summary['xsa_integrity'] = runner.check_xsa(root/'hardware.xsa')
        stage('sdt', executable.parent/'sdtgen.bat',
            [root/'scripts/sdt.tcl', root/'hardware.xsa', root/'sdt'])
        save('sdt_products')
        summary['sdt_product_sha256'] = runner.check_sdt(root/'sdt/system-top.dts')
        summary['artifact_generation'] = 'pass'
        save('semantic_and_retention_checks')
        rebuilt_refs, rebuilt_config, rebuilt_options, rebuilt_bds = read_case(rebuilt)
        summary['current_input_sha256'] = rebuilt_refs
        if any(config[key] != rebuilt_config.get(key) for key in ('Part', 'BoardPart', 'DefaultLib')):
            raise RuntimeError('Recreated project configuration differs')
        if rebuilt_options['TopModule'] != options['TopModule']:
            raise RuntimeError('Recreated top differs')
        actual = {p.stem: p for p in rebuilt_bds}
        if set(actual) != {p.stem for p in bds}:
            raise RuntimeError('Additional saved BDs were not retained')
        summary['bd_comparison'] = {}
        for source in bds:
            diff = differences(semantic_bd(source), semantic_bd(actual[source.stem]))
            summary['bd_comparison'][source.stem] = dict(
                source_sha256=runner.helpers.sha(source),
                rebuilt_sha256=runner.helpers.sha(actual[source.stem]), differences=diff)
        if any(item['differences'] for item in summary['bd_comparison'].values()):
            raise RuntimeError('Saved BD semantic differences require diagnosis')
        summary['bd_semantics'] = 'pass'
        for raw, digest in refs.items():
            if runner.helpers.sha(Path(raw)) != digest:
                raise RuntimeError(f'Original source changed: {raw}')
        for relative, digest in summary['copied_input_sha256'].items():
            if runner.helpers.sha(root/relative) != digest:
                raise RuntimeError(f'Copied input changed: {relative}')
        if runner.helpers.sha(root/'sources/counter32.v') != refs[str(project.parent.parent/'sources/counter32.v')]:
            raise RuntimeError('Original counter source was not preserved')
        summary['user_rtl_retention'] = 'pass'
        summary['status'] = 'pass'
        save('finished')
    except (Exception, KeyboardInterrupt) as error:
        summary.update(status='fail', failure_phase=summary['phase'],
            interrupted=isinstance(error, KeyboardInterrupt), error=f'{type(error).__name__}: {error}')
        if isinstance(error, runner.ParameterError):
            raise RuntimeError(f'Execution-stage verification rejected current artifacts: {error}') from error
        raise
    finally:
        summary['process_cleanup_complete'] = all(
            item.get('process_cleanup_complete', True) for item in summary['stages'])
        runner.helpers.write_json(result, summary)
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--vivado', type=Path, required=True)
    parser.add_argument('--timeout', type=runner.helpers.positive_timeout, default=900.0)
    parser.add_argument('--post-validate', action='store_true',
        help='Read finished native results and write a separate post-validation record')
    parser.add_argument('--reference-project', type=Path)
    parser.add_argument('--reference-xsa', type=Path)
    parser.add_argument('--post-report-name', default='post-validation.json',
        help='New post-validation[-suffix].json filename; never overwrite a previous record')
    args = parser.parse_args()
    try:
        if args.post_validate:
            if not args.reference_project or not args.reference_xsa:
                raise runner.ParameterError('Post-validation requires a native reference project and XSA')
            print(post_validate(args))
        else:
            if args.reference_project or args.reference_xsa:
                raise runner.ParameterError('Reference arguments are only for post-validation')
            if args.post_report_name != 'post-validation.json':
                raise runner.ParameterError('A post report name is only for post-validation')
            print(run(args))
        return 0
    except KeyboardInterrupt:
        return 130
    except runner.ParameterError as error:
        print(f'ParameterError: {error}', file=sys.stderr)
        return 2
    except (ValueError, RuntimeError, OSError) as error:
        print(f'{type(error).__name__}: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
