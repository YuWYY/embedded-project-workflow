#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
"""Rebuild the two-screen ownership trial using a local TouchGFX installation.

No downloads, installer actions, target build, flash, or simulator GUI launch.
All generated/vendor material stays in the explicitly supplied empty build root.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hashes(root):
    return {p.relative_to(root).as_posix(): digest(p)
            for p in sorted(root.rglob('*')) if p.is_file()}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def positive_timeout(value):
    try:
        seconds = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError('timeout must be a positive finite number')
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError('timeout must be a positive finite number')
    return seconds


def write_json(path, value):
    """Publish only complete JSON, with the temporary file on the same volume."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                         dir=path.parent, prefix=path.name+'.',
                                         suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def hidden_process_options():
    if os.name != 'nt':
        return {}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {'startupinfo': startup, 'creationflags': subprocess.CREATE_NO_WINDOW}


def stop_owned_process(proc):
    """Never search by executable name or act on a saved/stale process ID."""
    cleanup = {'pid': proc.pid, 'status': 'NOT_NEEDED', 'tree_kill_returncode': None}
    if proc.poll() is not None:
        return cleanup
    cleanup['status'] = 'INCOMPLETE'
    if os.name == 'nt':
        try:
            taskkill = Path(os.environ['SystemRoot'])/'System32/taskkill.exe'
            killed = subprocess.run([str(taskkill), '/PID', str(proc.pid), '/T', '/F'],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=10, **hidden_process_options())
            cleanup['tree_kill_returncode'] = killed.returncode
        except (KeyError, OSError, subprocess.TimeoutExpired) as error:
            cleanup['tree_kill_error'] = str(error)
    # One five-second budget covers the parent wait and direct-kill fallback.
    deadline = time.monotonic() + 5
    try:
        if cleanup['tree_kill_returncode'] == 0:
            proc.wait(timeout=max(0.001, deadline-time.monotonic()))
            cleanup['status'] = 'COMPLETE'
            return cleanup
        if proc.poll() is None:
            proc.kill()
            cleanup['direct_kill'] = True
        proc.wait(timeout=max(0.001, deadline-time.monotonic()))
    except (OSError, subprocess.TimeoutExpired) as error:
        cleanup['wait_error'] = str(error)
        if proc.poll() is None:
            try:
                proc.kill()
                cleanup['direct_kill'] = True
            except OSError as kill_error:
                cleanup['direct_kill_error'] = str(kill_error)
    # Killing the parent alone cannot establish that descendants were cleaned up.
    return cleanup


class Trial:
    """Small local journal; the example remains a single-file entry point."""
    def __init__(self, path, names, timeout, env):
        self.path, self.timeout, self.env = path, timeout, env
        self.results = {'status': 'RUNNING', 'timeout_seconds': timeout, 'stages': [
            {'name': name, 'status': 'NOT_RUN', 'timeout_seconds': timeout, 'returncode': None} for name in names]}
        self.current = None
        self.phase = 'checkpoint'
        self.checkpoint()

    def checkpoint(self):
        previous = self.phase
        self.phase = 'checkpoint'
        write_json(self.path, self.results)
        self.phase = previous

    def fail(self, error):
        kind = ('interrupt' if isinstance(error, KeyboardInterrupt) else
                'timeout' if isinstance(error, subprocess.TimeoutExpired) else
                'launch' if self.phase == 'launch' else
                'io' if isinstance(error, OSError) else
                'parse' if isinstance(error, (ValueError, KeyError, TypeError)) else 'semantic')
        status = {'interrupt': 'INTERRUPTED', 'timeout': 'TIMEOUT'}.get(kind, 'FAIL')
        failure = {'kind': kind, 'phase': self.phase,
                   'stage': self.current['name'] if self.current is not None else None,
                   'message': str(error) or type(error).__name__}
        self.results.update(status='FAIL', failure=failure)
        if self.current is not None:
            self.current.update(status=status, failure=failure)
        return 130 if kind == 'interrupt' else 1

    @contextmanager
    def stage(self, name):
        self.current = next(item for item in self.results['stages'] if item['name'] == name)
        self.current['status'] = 'RUNNING'
        self.phase = 'prepare'
        start = time.monotonic()
        try:
            self.checkpoint()
            yield self.current
            self.current['status'] = 'PASS'
            self.current['seconds'] = round(time.monotonic()-start, 3)
            self.checkpoint()
        except BaseException as error:
            self.current['seconds'] = round(time.monotonic()-start, 3)
            self.fail(error)
            raise

    def run(self, command, cwd, log, expected=0):
        stage = self.current
        stage.update(command=[str(x) for x in command], log=str(log), returncode=None)
        self.checkpoint()
        self.phase = 'log-open'
        with log.open('wb') as stream:
            self.phase = 'launch'
            proc = subprocess.Popen(stage['command'], cwd=cwd, env=self.env, stdin=subprocess.DEVNULL, stdout=stream,
                                    stderr=subprocess.STDOUT, **hidden_process_options())
            stage['pid'] = proc.pid
            self.phase = 'wait'
            try:
                stage['returncode'] = proc.wait(timeout=self.timeout)
            except (Exception, KeyboardInterrupt):
                stage['cleanup'] = stop_owned_process(proc)
                stage['returncode'] = proc.poll()
                raise
        self.phase = 'postcheck'
        require(stage['returncode'] == expected,
                stage['name'] + ': unexpected exit code; inspect ' + str(log))
        return log.read_text(encoding='utf-8', errors='replace')

    def finish(self):
        require(all(s['status'] == 'PASS' for s in self.results['stages']),
                'Cannot pass with unfinished stages')
        self.results['status'] = 'PASS'
        self.checkpoint()


STAGES = ('prepare-inputs', 'tool-version', 'create-local', 'configure-local',
          'generate-before-user-code', 'install-user-code', 'compile-original-user-design',
          'edit-user-design', 'generate-user-rename-and-move',
          'compile-stale-reference-expected-failure', 'adapt-user-code',
          'compile-adapted-user-code', 'generate-retention', 'compile-retention',
          'compile-production-model-test', 'production-model-pass',
          'production-model-negative-control', 'source-integrity')


def validate_model_negative(output):
    require(re.search(r'^FAIL: startup\s*$', output, re.M) is not None,
            'Expected model startup negative-control diagnostic was not observed')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--touchgfx-root', type=Path, required=True)
    parser.add_argument('--build-root', type=Path, required=True)
    parser.add_argument('--timeout', type=positive_timeout, default=300)
    args = parser.parse_args(argv)
    source = Path(__file__).resolve().parent
    install = args.touchgfx_root.resolve()
    build = args.build_root.resolve()
    if os.name != 'nt':
        parser.error('This verified entry point uses the Windows TouchGFX package.')
    if source == build or source in build.parents:
        parser.error('Choose an empty build directory outside this source package.')
    if build.exists() and (not build.is_dir() or any(build.iterdir())):
        parser.error('Build root must be empty.')
    tgfx = install / 'designer/tgfx.exe'
    cxx = install / 'env/MinGW/bin/g++.exe'
    for path in (tgfx, cxx, install/'app/packages/BlankUI-2.0.0.tpa',
                 install/'app/packages/Simulator-2.0.0.tpa'):
        if not path.is_file():
            parser.error('Missing local dependency: ' + str(path))
    trial = None
    try:
        build.mkdir(parents=True, exist_ok=True)
        logs = build/'logs'
        env = os.environ.copy()
        env.update(TEMP=str(build/'tmp'), TMP=str(build/'tmp'), PYTHONUTF8='1')
        env['PATH'] = os.pathsep.join(str(install/p) for p in
            ('env/MinGW/bin', 'env/MinGW/msys/1.0/bin', 'touchgfx/framework/tools')) + os.pathsep + env.get('PATH', '')
        trial = Trial(build/'results.json', STAGES, args.timeout, env)

        def run(name, cmd, cwd, expected=0):
            return trial.run(cmd, cwd, logs/(name+'.log'), expected)

        with trial.stage('prepare-inputs'):
            before = tree_hashes(source)
            (build/'tmp').mkdir()
            logs.mkdir()
        with trial.stage('tool-version'):
            version = run('tool-version', [tgfx, 'version'], build).strip()
            require(version == '4.26.1', 'This fixture is validated with TouchGFX 4.26.1.')
            trial.results['tool_version'] = version
        with trial.stage('create-local'):
            run('create-local', [tgfx, 'new', '--ui='+str(install/'app/packages/BlankUI-2.0.0.tpa'),
                '--at='+str(install/'app/packages/Simulator-2.0.0.tpa'), '--out='+str(build/'work'),
                '--prj=HumanControl'], build)
            project = build/'work/HumanControl'
            project_file = project/'HumanControl.touchgfx'
            require(project_file.is_file() and (project/'application.config').is_file(),
                    'Local project creation did not produce the expected configuration files')
        with trial.stage('configure-local'):
            config = json.loads(project_file.read_text(encoding='utf-8-sig'))
            app = config['Application']
            app['SelectedColorDepth'] = 16
            app['StartupScreenName'] = 'Dashboard'
            app['Screens'] = json.loads((source/'ui-before.json').read_text(encoding='utf-8'))
            project_file.write_text(json.dumps(config, indent=2)+'\n', encoding='utf-8')
            resource_config = project/'application.config'
            resources = json.loads(resource_config.read_text(encoding='utf-8-sig'))
            resources['text_configuration']['framebuffer_bpp'] = '16'
            resources['image_configuration']['opaque_image_format'] = 'RGB565'
            resource_config.write_text(json.dumps(resources, indent=2)+'\n', encoding='utf-8')
            shutil.copyfile(source/'texts.xml', project/'assets/texts/texts.xml')

        def generate(label):
            output = run(label, [tgfx, 'generate', '-p', project_file, '-v'], project)
            require('Generation & Update complete' in output, label + ': completion not reported')
            require((project/'generated/gui_generated/include/gui_generated/dashboard_screen/DashboardViewBase.hpp').is_file(),
                    'Missing generated Dashboard base class')

        def compile_simulator(label, expected=0):
            output = run(label, [tgfx, 'compile', '-p', project_file, '-s', '-v'], project, expected)
            if expected == 0:
                require('Compilation Succeded' in output and (project/'build/bin/simulator.exe').is_file(),
                        label + ': simulator build not demonstrated')
            return output

        with trial.stage('generate-before-user-code'):
            generate('generate-before-user-code')
        with trial.stage('install-user-code'):
            for path in (source/'user').rglob('*'):
                if not path.is_file():
                    continue
                dest = project/path.relative_to(source/'user')
                dest.parent.mkdir(parents=True, exist_ok=True)
                text = path.read_text(encoding='utf-8')
                if path.name == 'DashboardView.cpp':
                    text = text.replace('sampleValue', 'counterValue').replace('SAMPLEVALUE_SIZE', 'COUNTERVALUE_SIZE')
                dest.write_text(text, encoding='utf-8')
        with trial.stage('compile-original-user-design'):
            compile_simulator('compile-original-user-design')
            original_gui = tree_hashes(project/'gui')
        with trial.stage('edit-user-design'):
            app['Screens'] = json.loads((source/'ui-after.json').read_text(encoding='utf-8'))
            project_file.write_text(json.dumps(config, indent=2)+'\n', encoding='utf-8')
            expected_user_source = digest(project_file)
        with trial.stage('generate-user-rename-and-move'):
            generate('generate-user-rename-and-move')
            require(tree_hashes(project/'gui') == original_gui, 'Regeneration changed existing user code')
            generated = (project/'generated/gui_generated/src/dashboard_screen/DashboardViewBase.cpp').read_text()
            require('sampleValue.setPosition(40, 80, 300, 36)' in generated,
                    'Generated layout does not implement the user source change')
        with trial.stage('compile-stale-reference-expected-failure'):
            failed = compile_simulator('compile-stale-reference-expected-failure', expected=2)
            require('counterValueBuffer' in failed and 'not declared' in failed,
                    'Expected stale-reference failure was not observed')
        with trial.stage('adapt-user-code'):
            target = project/'gui/src/dashboard_screen/DashboardView.cpp'
            target.write_bytes((source/'user/gui/src/dashboard_screen/DashboardView.cpp').read_bytes())
            require(digest(project_file) == expected_user_source, 'User design source was altered by adaptation')
        with trial.stage('compile-adapted-user-code'):
            compile_simulator('compile-adapted-user-code')
            final_gui = tree_hashes(project/'gui')
        with trial.stage('generate-retention'):
            generate('generate-retention')
            require(tree_hashes(project/'gui') == final_gui, 'Second regeneration changed user implementation')
            require(digest(project_file) == expected_user_source, 'Retention generation changed the user source')
        with trial.stage('compile-retention'):
            compile_simulator('compile-retention')
        test_exe = build/'model_test.exe'
        with trial.stage('compile-production-model-test'):
            run('compile-production-model-test', [cxx, '-std=c++11', '-O2', '-Wall', '-Wextra', '-Werror',
                '-I'+str(project/'gui/include'), project/'gui/src/model/Model.cpp',
                source/'tests/model_test.cpp', '-static', '-o', test_exe], build)
            require(test_exe.is_file(), 'Model compiler did not produce the test executable')
        with trial.stage('production-model-pass'):
            run('production-model-pass', [test_exe], build)
        with trial.stage('production-model-negative-control'):
            output = run('production-model-negative-control', [test_exe, '--inject-extra-period'], build, expected=1)
            validate_model_negative(output)
        with trial.stage('source-integrity'):
            require(tree_hashes(source) == before, 'Source package changed during rebuild')
            trial.results.update(user_source_preserved=True,
                user_code_preserved_by_regeneration=True, model_test='PASS', negative_control='EXPECTED_FAILURE',
                simulator_build='PASS', gui_launch='NOT_RUN', gui_interaction='NOT_RUN',
                target_build='NOT_RUN', hardware='NOT_RUN', source_unchanged=True,
                simulator_sha256=digest(project/'build/bin/simulator.exe'))
        trial.finish()
        print('PASS: source configuration, generated interface, user adaptation, model tests, simulator build')
        return 0
    except (Exception, KeyboardInterrupt) as error:
        code = 130 if isinstance(error, KeyboardInterrupt) else 1
        if trial is not None:
            code = trial.fail(error)
            try:
                trial.checkpoint()
            except OSError as write_error:
                print('FAIL: cannot persist final checkpoint: ' + str(write_error), file=sys.stderr)
        print('FAIL: ' + (str(error) or type(error).__name__), file=sys.stderr)
        return code


if __name__ == '__main__':
    sys.exit(main())
