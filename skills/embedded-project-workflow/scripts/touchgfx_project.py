#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
"""Inspect/generate/build an existing Windows TouchGFX 4.26.1 Simulator project.

No project creation, screen replacement, user-code installation, GUI launch or
hardware operation. Build includes a fresh generation and clean simulator build.
Reports must be a new directory outside the project and tool installation,
on the same volume as the project so prior derived outputs can be archived.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET


class ProjectError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ProjectError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def positive_timeout(value):
    try:
        seconds = float(value)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError('timeout must be a positive finite number')
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError('timeout must be a positive finite number')
    return seconds


def write_json(path, value):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name+'.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def no_links(path):
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            require(not item.is_symlink() and not (getattr(item.lstat(), 'st_file_attributes', 0) & 0x400),
                    'Links/reparse points are unsupported: '+str(item))


def checked_tree(project):
    no_links(project)
    for root, dirs, files in os.walk(project, followlinks=False):
        for name in dirs + files:
            item = Path(root)/name
            no_links(item)
            require(not any(c in name for c in '$`;&|<>\r\n'), 'Unsupported shell-sensitive filename: '+str(item))
            if item.is_file():
                require(item.stat().st_nlink == 1, 'Hard-linked files are unsupported: '+str(item))


def hashes(root, exclusions=()):
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            if not any(relative == x or relative.startswith(x+'/') for x in exclusions):
                result[relative] = sha(path)
    return result


COMMANDS = {
    'GenerateAssetsCommand': 'make -f simulator/gcc/Makefile assets -j8',
    'PostGenerateCommand': 'touchgfx update_project --project-file=simulator/msvs/Application.vcxproj',
    'CompileSimulatorCommand': 'make -f simulator/gcc/Makefile -j8',
    'RunSimulatorCommand': 'build\\bin\\simulator.exe',
    'CompileTargetCommand': '', 'FlashTargetCommand': '',
}
# ST 4.26.1 generated GCC makefile, checked from an actual native generation.
GENERATED_MAKE_SHA = 'd1ac809157ac4958e115cafb7ef6bbdb6d4e103b953026487f7c5b5b593f0f2f'
SIMULATOR_MAKE_SHA = '839e1423880741708e9ac098304fdbaa337f4150eba0e2bd4b0484630f474b12'
IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def load_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate JSON key: '+key)
            result[key] = value
        return result
    return json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=unique)


def inspect_project(project, install):
    require(project.is_dir(), 'Existing project directory is required')
    require(not any(c in str(project) for c in ' $`;&|<>\r\n"'), 'Unsupported project path characters')
    require(not project.is_relative_to(install) and not install.is_relative_to(project), 'Project/tool roots must be disjoint')
    checked_tree(project)
    no_links(install)
    configs = list(project.glob('*.touchgfx'))
    require(len(configs) == 1, 'Expected exactly one .touchgfx file in project root')
    config = configs[0]
    data = load_json(config)
    app = data['Application']
    require(data['Version'] == '4.26.1', 'Only TouchGFX 4.26.1 is supported')
    for key, expected in {'ApplicationTemplateName':'Simulator', 'ApplicationTemplateVersion':'2.0.0',
                          'UIPath':'.', 'TouchGfxPath':'touchgfx'}.items():
        require(app.get(key) == expected, 'Unsupported '+key)
    for key, expected in COMMANDS.items():
        require(app.get(key) == expected, 'Unsupported command/hook: '+key)
    for key in app:
        require(not ('command' in key.lower() and key not in COMMANDS), 'Unknown command field: '+key)
    screens = app['Screens']
    names = [s['Name'] for s in screens]
    require(names and len(names) == len(set(names)) and all(IDENT.fullmatch(n) for n in names), 'Invalid screen names')
    require(app['StartupScreenName'] in names, 'Startup screen is absent')
    for screen in screens:
        for component in screen.get('Components', []):
            require(IDENT.fullmatch(component['Name']), 'Unsupported component name')
        for interaction in screen.get('Interactions', []):
            action = interaction['Action']
            if action['Type'] == 'ActionGotoScreen':
                require(action['ActionComponent'] in names, 'Navigation references an absent screen')
    def local_paths(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str) and any(k in key.lower() for k in ('path', 'filename', 'directory')):
                    normalized = value.replace('\\', '/')
                    require(not normalized.startswith('/') and ':' not in normalized and '..' not in normalized.split('/'),
                            'External path in configuration: '+key)
                local_paths(value)
        elif isinstance(obj, list):
            for value in obj:
                local_paths(value)
    local_paths(data)
    resources = load_json(project/'application.config')
    local_paths(resources)
    require(app['SelectedColorDepth'] == 16 and resources['text_configuration']['framebuffer_bpp'] == '16'
            and resources['image_configuration']['opaque_image_format'] == 'RGB565', 'Only RGB565 is currently supported')
    if (project/'target.config').exists():
        target = load_json(project/'target.config')
        require(target == {'target_configuration': {'touchgfx_path':'touchgfx', 'additional_features':['VectorFonts']}},
                'Unsupported target configuration')
    if (project/'simulator/gcc/Makefile').exists():
        # Source makefiles are never executed until their known profile is verified.
        require(sha(project/'simulator/gcc/Makefile') == SIMULATOR_MAKE_SHA,
                'Simulator Makefile differs from the verified native 4.26.1 wrapper')
    if (project/'config/gcc/app.mk').exists():
        assignments = {}
        for line in (project/'config/gcc/app.mk').read_text(encoding='utf-8-sig').splitlines():
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            match = re.fullmatch(r'([a-z_]+)\s*:=\s*([^\r\n]*)', line)
            require(match is not None and match[1] not in assignments, 'Unsupported GCC config statement')
            assignments[match[1]] = match[2].strip()
        require(set(assignments) == {'touchgfx_path','touchgfx_env','user_cflags'} and
                assignments['touchgfx_path'] == 'touchgfx' and assignments['user_cflags'] == '-DUSE_BPP=16',
                'Unsupported GCC build configuration')
        require(not any(c in assignments['touchgfx_env'] for c in '$`;&|<>\r\n"'), 'Unsafe environment path')
        require((project/assignments['touchgfx_env']).resolve() == install/'env', 'GCC environment must reference supplied install')
    texts = (project/'assets/texts/texts.xml').read_text(encoding='utf-8-sig')
    require('<!DOCTYPE' not in texts and '<!ENTITY' not in texts, 'External XML entities are unsupported')
    for typography in ET.fromstring(texts).iter('Typography'):
        font = typography.get('Font', '')
        require(font and Path(font).name == font and not any(c in font for c in ':\\/$`;&|<>'), 'Unsupported font path')
        # Native first generation may populate a system font into assets/fonts.
        # Only a basename is accepted; font material is not copied by this runner.
    # Local framework contains executable conversion scripts: it must match the installation.
    for path in (project/'touchgfx').rglob('*'):
        if path.is_file():
            reference = install/'touchgfx'/path.relative_to(project/'touchgfx')
            require(reference.is_file() and sha(path) == sha(reference), 'Local framework differs from installation: '+str(path))
    if (project/'touchgfx').exists():
        require((project/'touchgfx/framework/tools/textconvert/main.rb').is_file(), 'Missing local TouchGFX framework')
    for tool in ('designer/tgfx.exe', 'env/MinGW/bin/g++.exe'):
        require((install/tool).is_file(), 'Missing local tool: '+tool)
    return {'project':str(project), 'project_file':str(config), 'profile':'windows-touchgfx-4.26.1-simulator-2.0.0-rgb565',
            'resolution':app['Resolution'], 'startup_screen':app['StartupScreenName'], 'screens':names,
            'source_hashes':hashes(project, ('generated','build','simulator/msvs','touchgfx')),
            'tool_sha256':sha(install/'designer/tgfx.exe')}


def hidden_process_options():
    return {'creationflags':subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session':True}


def stop_owned_process(proc):
    cleanup = {'pid':proc.pid, 'status':'NOT_NEEDED', 'tree_kill_returncode':None}
    if proc.poll() is not None:
        return cleanup
    cleanup['status'] = 'INCOMPLETE'
    try:
        if os.name == 'nt':
            killed = subprocess.run([str(Path(os.environ['SystemRoot'])/'System32/taskkill.exe'),
                                     '/PID',str(proc.pid),'/T','/F'], stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=10, **hidden_process_options())
            cleanup['tree_kill_returncode'] = killed.returncode
        else:
            import signal
            os.killpg(proc.pid, signal.SIGKILL)
            cleanup['tree_kill_returncode'] = 0
        proc.wait(timeout=5)
        if cleanup['tree_kill_returncode'] == 0:
            cleanup['status'] = 'COMPLETE'
    except (OSError, KeyError, subprocess.TimeoutExpired) as error:
        cleanup['error'] = str(error)
    if proc.poll() is None:
        try:
            proc.kill()
            proc.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired) as error:
            cleanup['direct_kill_error'] = str(error)
    return cleanup


class Journal:
    def __init__(self, reports, stages, timeout, env):
        self.reports, self.timeout, self.env = reports, timeout, env
        self.current, self.phase = None, 'checkpoint'
        self.result = {'status':'RUNNING', 'timeout_seconds':timeout, 'stages':[
            {'name':name,'status':'NOT_RUN','returncode':None} for name in stages]}
        self.checkpoint()

    def checkpoint(self):
        write_json(self.reports/'results.json', self.result)

    def fail(self, error):
        kind = ('interrupt' if isinstance(error, KeyboardInterrupt) else
                'timeout' if isinstance(error, subprocess.TimeoutExpired) else
                'launch' if self.phase == 'launch' else 'io' if isinstance(error, OSError) else
                'parse' if isinstance(error, (ValueError, KeyError, TypeError, ET.ParseError)) else 'semantic')
        failure = {'kind':kind,'phase':self.phase,'stage':self.current['name'] if self.current else None,
                   'message':str(error) or type(error).__name__}
        self.result.update(status='FAIL', failure=failure)
        if self.current:
            self.current.update(status={'timeout':'TIMEOUT','interrupt':'INTERRUPTED'}.get(kind,'FAIL'),failure=failure)
        return 130 if kind == 'interrupt' else 1

    @contextmanager
    def stage(self, name):
        self.current = next(s for s in self.result['stages'] if s['name'] == name)
        self.current['status'] = 'RUNNING'
        self.phase = 'prepare'
        started = time.monotonic()
        try:
            self.checkpoint()
            yield self.current
            self.current.update(status='PASS',seconds=round(time.monotonic()-started,3))
            self.checkpoint()
        except BaseException as error:
            self.current['seconds'] = round(time.monotonic()-started,3)
            self.fail(error)
            raise

    def run(self, command, cwd):
        log = self.reports/(self.current['name']+'.log')
        self.current.update(command=[str(x) for x in command],cwd=str(cwd),log=str(log))
        self.checkpoint()
        self.phase = 'log-open'
        with log.open('wb') as stream:
            self.phase = 'launch'
            proc = subprocess.Popen(self.current['command'],cwd=cwd,env=self.env,stdin=subprocess.DEVNULL,
                                    stdout=stream,stderr=subprocess.STDOUT,**hidden_process_options())
            self.current['pid'] = proc.pid
            try:
                self.phase = 'wait'
                self.checkpoint()
                self.current['returncode'] = proc.wait(timeout=self.timeout)
            except (Exception, KeyboardInterrupt):
                self.current['cleanup'] = stop_owned_process(proc)
                self.current['returncode'] = proc.poll()
                raise
        self.phase = 'postcheck'
        require(self.current['returncode'] == 0, 'Child exited '+str(self.current['returncode'])+'; see '+str(log))
        return log.read_text(encoding='utf-8',errors='replace')


def environment(install, reports):
    env = {k:v for k,v in os.environ.items() if k.upper() in {
        'SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','NUMBER_OF_PROCESSORS','PROCESSOR_ARCHITECTURE',
        'USERPROFILE','APPDATA','LOCALAPPDATA','PROGRAMDATA','OS'}}
    env.update(TEMP=str(reports/'tmp'),TMP=str(reports/'tmp'),PYTHONUTF8='1')
    env['PATH'] = os.pathsep.join(str(install/p) for p in (
        'env/MinGW/bin','env/MinGW/msys/1.0/bin','touchgfx/framework/tools'))
    system_root = os.environ.get('SystemRoot')
    require(bool(system_root), 'Windows SystemRoot is required')
    env['PATH'] += os.pathsep + str(Path(system_root)/'System32')
    return env


def protected_changes(project, before):
    return [name for name, identity in before.items() if not (project/name).is_file() or sha(project/name) != identity]


def volume_id(path):
    """Use an existing ancestor without creating the requested report directory."""
    ancestor = path
    while not ancestor.exists():
        require(ancestor.parent != ancestor, 'Cannot identify filesystem volume')
        ancestor = ancestor.parent
    return ancestor.stat().st_dev


def execute(args):
    no_links(args.project)
    no_links(args.touchgfx_root)
    project, install = args.project.resolve(), args.touchgfx_root.resolve()
    if args.command == 'inspect':
        result = inspect_project(project, install)
        result['status'] = 'INSPECTED_READ_ONLY'
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    require(os.name == 'nt', 'Native execution is supported on Windows only')
    require(args.reports is not None, '--reports is required for generate/build')
    no_links(args.reports)
    reports = args.reports.resolve()
    require(not reports.exists(), 'Reports directory must be new')
    for root in (project, install):
        require(not reports.is_relative_to(root) and not root.is_relative_to(reports), 'Reports/project/install roots must be disjoint')
    require(volume_id(project) == volume_id(reports), 'Reports must be on the same volume as the project')
    reports.mkdir(parents=True)
    journal = Journal(reports, ['inspect','tool-version','generate'] + (['build'] if args.command == 'build' else []) + ['source-integrity'], args.timeout, environment(install,reports))
    before = None
    try:
        (reports/'tmp').mkdir()
        with journal.stage('inspect'):
            info = inspect_project(project, install)
            before = info['source_hashes']
            journal.result['input'] = info
            write_json(reports/'source-before.json',before)
        tgfx = install/'designer/tgfx.exe'
        with journal.stage('tool-version'):
            require(journal.run([tgfx,'version'],reports).strip() == '4.26.1','Installed tool version is unsupported')
        def unchanged():
            changes = protected_changes(project,before)
            require(not changes, 'Protected source/config changed: '+', '.join(changes))
        with journal.stage('generate') as stage:
            unchanged()
            # Preserve stale generated material outside the project before invoking native tooling.
            # This both removes untrusted derived makefiles and makes fresh outputs mandatory.
            for name in ('generated','build'):
                target = project/name
                if target.exists():
                    require(target.resolve().is_relative_to(project) and target.is_dir(), 'Unsafe derived directory')
                    target.rename(reports/('previous-'+name))
            stage['discarded_stale_outputs'] = True
            output = journal.run([tgfx,'generate','-p',info['project_file'],'-v'],project)
            require('Generation & Update complete' in output, 'Generation completion marker is missing')
            require(sha(project/'generated/simulator/gcc/Makefile') == GENERATED_MAKE_SHA,'Unexpected generated Makefile')
            for name in info['screens']:
                require((project/f'generated/gui_generated/include/gui_generated/{name.lower()}_screen/{name}ViewBase.hpp').is_file(),
                        'Missing freshly generated screen: '+name)
            unchanged()
            inspect_project(project, install)
            journal.result['generated_hashes'] = hashes(project/'generated')
        if args.command == 'build':
            with journal.stage('build'):
                unchanged()
                output = journal.run([tgfx,'compile','-p',info['project_file'],'-s','-v'],project)
                product = project/'build/bin/simulator.exe'
                require('Compilation Succeded' in output and product.is_file() and product.stat().st_size > 0,
                        'Fresh simulator build was not demonstrated')
                journal.result['simulator_sha256'] = sha(product)
        with journal.stage('source-integrity'):
            unchanged()
            after = hashes(project,('generated','build','simulator/msvs','touchgfx'))
            write_json(reports/'source-after.json',after)
            journal.result.update(source_preserved=True,added_source_files=sorted(set(after)-set(before)),
                                  gui_launch='NOT_RUN',gui_interaction='NOT_RUN',target_build='NOT_RUN',hardware='NOT_RUN')
        require(all(s['status'] == 'PASS' for s in journal.result['stages']), 'Unfinished stages')
        journal.result['status'] = 'PASS'
        journal.checkpoint()
        print('PASS: '+args.command+' existing project; evidence '+str(reports/'results.json'))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        code = journal.fail(error)
        if before is not None:
            try:
                journal.result['protected_source_changes'] = protected_changes(project,before)
            except OSError as check_error:
                journal.result['source_check_error'] = str(check_error)
        try:
            journal.checkpoint()
        except OSError as write_error:
            print('FAIL: final checkpoint could not be written: '+str(write_error),file=sys.stderr)
        print('FAIL: '+(str(error) or type(error).__name__),file=sys.stderr)
        return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('inspect','generate','build'))
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--touchgfx-root',type=Path,required=True)
    parser.add_argument('--reports',type=Path)
    parser.add_argument('--timeout',type=positive_timeout,default=300)
    args = parser.parse_args(argv)
    try:
        return execute(args)
    except (Exception, KeyboardInterrupt) as error:
        print('FAIL: '+(str(error) or type(error).__name__),file=sys.stderr)
        return 130 if isinstance(error,KeyboardInterrupt) else 1


if __name__ == '__main__':
    sys.exit(main())
