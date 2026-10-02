"""Run one isolated Clocking Wizard generation, simulation and synthesis stage.

Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT
"""

import argparse
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
import uuid


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


CLOCK_SOURCES = ('clock.xdc', 'clock_top.sv', 'tb_clock.sv')
OWNER_FILE = '.controlled-clock-project.json'
OWNER_FORMAT = 'embedded-project-workflow/controlled-clock'
EVIDENCE_FILES = (
    'utilization.rpt', 'clocks.rpt', 'timing_synth.rpt', 'cdc.rpt',
    'check_timing.rpt', 'ip_properties.txt', 'tool_version.txt', 'completed.txt',
    'p/c.sim/sim_1/behav/xsim/clock_result.txt',
    'p/c.sim/sim_1/behav/xsim/simulate.log',
)


def inventory(package, source_root=None):
    source_root = source_root or package / 'sources'
    found = {str(p.relative_to(package)).replace('\\', '/'): sha(p)
             for folder in ('config', 'scripts')
             for p in sorted((package / folder).rglob('*'))
             if p.is_file() and '__pycache__' not in p.parts}
    found.update({'sources/' + name: sha(source_root / name) for name in CLOCK_SOURCES})
    return found


def checked_target(path, root):
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'Write target escapes the isolated build root: {path}')


def write_json(path, obj, root=None):
    """Validate, verify and atomically replace a JSON file in its own directory."""
    root = root or path.parent
    temporary = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
    checked_target(path, root)
    checked_target(temporary, root)
    try:
        with temporary.open('x', encoding='utf-8') as output:
            output.write(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
            output.flush()
        if json.loads(temporary.read_text(encoding='utf-8')) != obj:
            raise OSError('Temporary JSON verification failed')
        checked_target(path, root)
        checked_target(temporary, root)
        temporary.replace(path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def source_copy_plan(package, shared_sources, root):
    """List the exact directories/files to copy, including individual targets."""
    directories = [root / 'sources']
    files = [(shared_sources / name, root / 'sources' / name) for name in CLOCK_SOURCES]
    for folder in ('scripts', 'config'):
        source_dir = package / folder
        directories.append(root / folder)
        for source in sorted(source_dir.rglob('*')):
            if '__pycache__' in source.relative_to(source_dir).parts:
                continue
            target = root / source.relative_to(package)
            if source.is_dir():
                directories.append(target)
            elif source.is_file():
                files.append((source, target))
    return directories, files


def check_write_targets(root, work, evidence, directories, files):
    """Reject linked destinations outside this root before the first write."""
    targets = [root, work, root / OWNER_FILE, evidence,
               evidence / 'result.json', evidence / 'stdout.log',
               evidence / 'clock-config.tcl', *directories,
               *(destination for _, destination in files)]
    for target in targets:
        if not target.resolve().is_relative_to(root):
            raise ValueError(f'Write target escapes the isolated build root: {target}')
    # This runner owns the small build tree. Reject external links anywhere in
    # it, including native-tool outputs, without traversing an external target.
    pending = [root] if root.exists() else []
    visited = set()
    while pending:
        directory = pending.pop()
        resolved = directory.resolve()
        if resolved in visited:
            continue
        visited.add(resolved)
        for child in directory.iterdir():
            if not child.resolve().is_relative_to(root):
                raise ValueError(f'Build tree link escapes the isolated build root: {child}')
            if child.is_dir():
                pending.append(child)
    checked_artifact_paths(root, work, evidence)


def checked_artifact_paths(root, work, evidence):
    """Resolve every known artifact before moving or collecting any of them."""
    root = root.resolve()
    paths = [(relative, work / relative, evidence / Path(relative).name,
              evidence / 'preexisting-artifacts' / relative)
             for relative in EVIDENCE_FILES]
    for relative, source, destination, archived in paths:
        if any(not path.resolve().is_relative_to(root)
               for path in (source, destination, archived)):
            raise ValueError(f'Artifact path escapes the isolated build root: {relative}')
        if source.exists() and not source.is_file():
            raise ValueError(f'Expected a generated evidence file: {relative}')
    return paths


def archive_preexisting_artifacts(root, work, evidence, archived_files=None):
    paths = checked_artifact_paths(root, work, evidence)
    if any(archived.exists() for _, _, _, archived in paths):
        raise ValueError('Preexisting artifact archive already contains evidence')
    archived_files = [] if archived_files is None else archived_files
    for relative, source, _, archived in paths:
        if source.is_file():
            archived.parent.mkdir(parents=True, exist_ok=True)
            source.replace(archived)
            archived_files.append(relative)
    return archived_files


def collect_current_artifacts(root, work, evidence, collected=None):
    collected = [] if collected is None else collected
    errors = []
    for relative in EVIDENCE_FILES:
        source, destination = work / relative, evidence / Path(relative).name
        try:
            checked_target(source, root)
            checked_target(destination, root)
            if source.exists() and not source.is_file():
                raise ValueError(f'Expected a generated evidence file: {relative}')
            if source.is_file():
                shutil.copy2(source, destination)
                collected.append(relative)
        except (OSError, RuntimeError, ValueError) as error:
            errors.append(f'{relative}: {error}')
    if errors:
        raise OSError('; '.join(errors))
    return collected


def output_frequency(config):
    # This is the fixed, original example's one-line setting, not a Tcl parser.
    values = re.findall(r'^\s*set output_mhz ([0-9]+(?:\.[0-9]+)?)\s*$',
                        config.read_text(encoding='utf-8'), re.MULTILINE)
    if len(values) != 1 or not 100 <= float(values[0]) <= 125:
        raise ValueError('Expected one literal output_mhz setting in the agreed 100-125 MHz range')
    return float(values[0])


def matching_results(completion, simulation, mhz):
    match = re.fullmatch(r'CLOCK_COMPLETE mhz=([0-9]+(?:\.[0-9]+)?) synth_status=synth_design Complete!', completion)
    return bool(match and float(match[1]) == mhz and
                simulation == f'PASS samples=400 resets=2 expected_ns={1000.0 / mhz:.3f}')


def existing_owner(root):
    marker = json.loads((root / OWNER_FILE).read_text(encoding='utf-8'))
    if marker.get('format') != OWNER_FORMAT or marker.get('version') != 1:
        raise ValueError('Ownership marker format/version does not identify this example')
    owner_id = marker.get('owner_id', '')
    if not isinstance(owner_id, str) or not re.fullmatch(r'[0-9a-f]{32}', owner_id):
        raise ValueError('Ownership marker has no valid owner id')
    stage = marker.get('last_successful_stage', '')
    if not isinstance(stage, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', stage):
        raise ValueError('Ownership marker has no successful stage evidence')
    evidence = root / 'stage-results' / stage
    result = json.loads((evidence / 'result.json').read_text(encoding='utf-8'))
    config = evidence / 'clock-config.tcl'
    mhz = output_frequency(config)
    if (result.get('owner_id') != owner_id or result.get('stage') != stage
            or result.get('status') != 'pass' or result.get('returncode') != 0
            or Path(result.get('build_root', '')).resolve() != root
            or result.get('source_sha256', {}).get('config/clock-config.tcl') != sha(config)
            or not matching_results(result.get('completion', ''), result.get('simulation', ''), mhz)):
        raise ValueError('Ownership marker does not match successful stage evidence')
    if not (root / 'clock/p/c.xpr').is_file():
        raise ValueError('Owned clock project is missing')
    return marker


def positive_timeout(value):
    try:
        seconds = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError('Timeout must be a positive finite number') from error
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError('Timeout must be a positive finite number')
    return seconds


def hidden_startup():
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    return startup


def cleanup_owned_process(process):
    """Only taskkill the still-live PID from our own Popen, never by image name."""
    cleanup = {'attempted': False, 'complete': False, 'pid': process.pid,
               'taskkill_returncode': None, 'diagnostics': []}
    helper = None
    try:
        if process.poll() is not None:
            cleanup['diagnostics'].append('Owned launcher already exited; descendant state is unknown')
            return cleanup
        # Resolve a fixed Windows utility path; do not use PATH or a shell.
        taskkill = str(Path(os.environ['SystemRoot']) / 'System32/taskkill.exe')
        command = [taskkill, '/PID', str(process.pid), '/T', '/F']
        cleanup.update(attempted=True, command=command)
        helper = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  startupinfo=hidden_startup(),
                                  creationflags=subprocess.CREATE_NEW_CONSOLE)
        try:
            cleanup['taskkill_returncode'] = helper.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cleanup['diagnostics'].append('taskkill exceeded its 10 second limit')
            helper.kill()  # This is our cleanup helper, not a process-name search.
            try:
                helper.wait(timeout=0)
            except subprocess.TimeoutExpired:
                cleanup['diagnostics'].append('Cleanup helper has not yet exited')
    except (KeyError, OSError, ValueError, KeyboardInterrupt) as error:
        cleanup['diagnostics'].append(f'{type(error).__name__}: {error}')
        if helper is not None and helper.poll() is None:
            try:
                helper.kill()
            except OSError as stop_error:
                cleanup['diagnostics'].append(f'Cleanup helper stop failed: {stop_error}')
    try:
        process.wait(timeout=5)
    except (subprocess.TimeoutExpired, OSError, KeyboardInterrupt) as error:
        cleanup['diagnostics'].append(f'Owned launcher did not finish cleanup: {type(error).__name__}: {error}')
    cleanup['complete'] = (cleanup['taskkill_returncode'] == 0 and
                           process.returncode is not None and not cleanup['diagnostics'])
    return cleanup


def save_record(path, record, root):
    write_json(path, record, root)
    if json.loads(path.read_text(encoding='utf-8')) != record:
        raise OSError('Saved result verification failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vivado', help='Existing Vivado executable; otherwise resolve Windows vivado.bat/exe from PATH')
    parser.add_argument('--build-root')
    parser.add_argument('--regenerate', action='store_true')
    parser.add_argument('--stage', required=True)
    parser.add_argument('--timeout', type=positive_timeout, default=900.0,
                        help='Positive finite wall-clock seconds per Vivado process (default: 900)')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.stage):
        parser.error('Stage name must use ASCII letters, digits, hyphens or underscores')
    package = Path(__file__).resolve().parents[1]
    shared_sources = package.parent / 'sources'
    selected = args.vivado or shutil.which('vivado.bat') or shutil.which('vivado.exe')
    if not selected:
        parser.error('Provide --vivado or put the Windows Vivado launcher on PATH')
    executable = Path(selected).resolve()
    if os.name != 'nt' or not executable.is_file():
        parser.error('This trial requires Windows and an existing Vivado executable')
    if args.regenerate and not args.build_root:
        parser.error('Regeneration needs the previous build root')
    root = (Path(args.build_root).resolve() if args.build_root else
            Path(tempfile.mkdtemp(prefix='skill-v02-clock-')).resolve())
    try:
        str(root).encode('ascii')
    except UnicodeEncodeError:
        parser.error('Use --build-root with a new ASCII path outside the source package')
    if root.is_relative_to(package.parent):
        parser.error('Build root must be outside the Vivado source package')
    try:
        requested_mhz = output_frequency(package / 'config/clock-config.tcl')
    except (OSError, ValueError) as error:
        parser.error(str(error))
    work = root / 'clock'
    if args.regenerate:
        try:
            owner = existing_owner(root)
        except (OSError, ValueError, TypeError, KeyError) as error:
            parser.error(f'Regeneration requires this example ownership marker and successful evidence: {error}')
    elif root.exists() and any(root.iterdir()):
        parser.error('Initial build needs a new or empty directory')
    else:
        owner = {'format': OWNER_FORMAT, 'version': 1, 'owner_id': uuid.uuid4().hex,
                 'last_successful_stage': None}
    evidence = root / 'stage-results' / args.stage
    if evidence.exists():
        parser.error('Stage evidence already exists; choose a new stage name')
    try:
        copy_directories, copy_files = source_copy_plan(package, shared_sources, root)
        check_write_targets(root, work, evidence, copy_directories, copy_files)
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    marker = work / 'completed.txt'
    sim = work / 'p/c.sim/sim_1/behav/xsim/clock_result.txt'
    command = [str(executable), '-mode', 'batch', '-notrace', '-source',
               str(root / 'scripts/clock.tcl'), '-tclargs', str(root / 'sources')]
    if args.regenerate:
        command.append('regenerate')
    started = time.monotonic()
    record = {'stage': args.stage, 'command': command, 'cwd': str(work),
              'build_root': str(root), 'source_sha256': {},
              'owner_id': owner['owner_id'], 'requested_output_mhz': requested_mhz,
              'expected_period_ns': 1000.0 / requested_mhz,
              'removed_old_result_files': [], 'archived_preexisting_artifacts': [],
              'collected_current_artifacts': [], 'returncode': None, 'pid': None,
              'sources_unchanged': None, 'completion': '', 'simulation': '',
              'timeout_seconds': args.timeout, 'timed_out': False, 'interrupted': False,
              'phase': 'initialize', 'failure_phase': None, 'failure_type': None,
              'diagnostics': [], 'cleanup': None,
              'process_io': 'DEVNULL stdin, file stdout/stderr, hidden new console',
              'status': 'running', 'coverage': 'IP generation, XSim, IP/top synthesis only'}
    result_path = evidence / 'result.json'
    process = None
    initial = None

    def failure(phase, error, kind=None):
        if isinstance(error, KeyboardInterrupt):
            record['interrupted'] = True
        if record['failure_phase'] is None:
            record['failure_phase'] = phase
            record['failure_type'] = kind or (
                'timeout' if isinstance(error, subprocess.TimeoutExpired) else
                'interrupted' if isinstance(error, KeyboardInterrupt) else
                'launch_error' if phase == 'launch' else
                'io_error' if isinstance(error, OSError) else 'runtime_error')
        record['diagnostics'].append(f'{phase}: {type(error).__name__}: {error}')
        record['status'] = 'fail'

    def checkpoint(phase):
        record['phase'] = phase
        save_record(result_path, record, root)

    try:
        root.mkdir(parents=True, exist_ok=True)
        evidence.mkdir(parents=True)
        # Persist the production record before source copying, owner writes or archive moves.
        checkpoint('initialize')
        work.mkdir(exist_ok=True)
        if not args.regenerate:
            checkpoint('initialize_owner')
            write_json(root / OWNER_FILE, owner, root)
        checkpoint('inventory')
        initial = inventory(package, shared_sources)
        record['source_sha256'] = initial
        checkpoint('copy_sources')
        for directory in copy_directories:
            checked_target(directory, root)
            directory.mkdir(parents=True, exist_ok=True)
        for source, destination in copy_files:
            checked_target(destination, root)
            shutil.copy2(source, destination)
        checked_target(evidence / 'clock-config.tcl', root)
        shutil.copy2(package / 'config/clock-config.tcl', evidence / 'clock-config.tcl')
        checkpoint('archive_preexisting_artifacts')
        archive_preexisting_artifacts(root, work, evidence, record['archived_preexisting_artifacts'])
        record['removed_old_result_files'] = [Path(relative).name
            for relative in record['archived_preexisting_artifacts']
            if Path(relative).name in ('completed.txt', 'clock_result.txt')]
        checkpoint('launch')
        print('Build directory:', root, flush=True)
        checked_target(evidence / 'stdout.log', root)
        with (evidence / 'stdout.log').open('w', encoding='utf-8') as output:
            process = subprocess.Popen(command, cwd=work, stdin=subprocess.DEVNULL,
                                       stdout=output, stderr=subprocess.STDOUT,
                                       startupinfo=hidden_startup(),
                                       creationflags=subprocess.CREATE_NEW_CONSOLE)
            record['pid'] = process.pid
            checkpoint('running')
            record['returncode'] = process.wait(timeout=args.timeout)
    except subprocess.TimeoutExpired as error:
        record['timed_out'] = True
        failure(record['phase'], error)
    except KeyboardInterrupt as error:
        record['interrupted'] = True
        failure(record['phase'], error)
    except Exception as error:
        failure(record['phase'], error)
    finally:
        if process is not None:
            if record['failure_phase'] is not None:
                record['cleanup'] = cleanup_owned_process(process)
            record['returncode'] = process.returncode

    record['removed_old_result_files'] = [Path(relative).name
        for relative in record['archived_preexisting_artifacts']
        if Path(relative).name in ('completed.txt', 'clock_result.txt')]

    # An archive/copy failure cannot turn untouched previous-stage files into current evidence.
    if process is not None:
        for field, path in (('completion', marker), ('simulation', sim)):
            try:
                checked_target(path, root)
                record[field] = path.read_text(encoding='utf-8').strip() if path.exists() else ''
            except (Exception, KeyboardInterrupt) as error:
                failure('read_' + field, error)
        try:
            collect_current_artifacts(root, work, evidence, record['collected_current_artifacts'])
        except Exception as error:
            failure('collect_current_artifacts', error)
        except KeyboardInterrupt as error:
            record['interrupted'] = True
            failure('collect_current_artifacts', error)
    if initial is not None:
        try:
            record['sources_unchanged'] = (initial == inventory(package, shared_sources) == inventory(root))
        except (Exception, KeyboardInterrupt) as error:
            failure('verify_sources', error)
    if record['failure_phase'] is None:
        if (record['returncode'] == 0 and record['sources_unchanged'] and
                matching_results(record['completion'], record['simulation'], requested_mhz)):
            record['status'] = 'pass'
        else:
            kind = ('nonzero_exit' if record['returncode'] != 0 else
                    'source_integrity' if not record['sources_unchanged'] else 'evidence_mismatch')
            failure('verify_results', RuntimeError('Tool exit, source integrity or completion/simulation evidence failed'), kind)
    record.update(phase='complete', elapsed_seconds=round(time.monotonic() - started, 2))
    try:
        save_record(result_path, record, root)
    except (Exception, KeyboardInterrupt) as error:
        failure('save_result', error)
        print(f'Unable to save final result: {error}', file=sys.stderr, flush=True)
        # A transient write failure may permit saving terminal failure, never reporting PASS.
        try:
            save_record(result_path, record, root)
        except (Exception, KeyboardInterrupt) as retry_error:
            failure('save_result', retry_error)
            print(f'Terminal result remains unverified: {retry_error}', file=sys.stderr, flush=True)
    if record['status'] == 'pass':
        updated_owner = dict(owner, last_successful_stage=args.stage)
        try:
            write_json(root / OWNER_FILE, updated_owner, root)
        except (Exception, KeyboardInterrupt) as error:
            failure('save_owner', error)
            print(f'Unable to advance ownership marker: {error}', file=sys.stderr, flush=True)
            try:
                save_record(result_path, record, root)
            except (Exception, KeyboardInterrupt) as save_error:
                failure('save_result', save_error)
                print(f'Terminal result remains unverified: {save_error}', file=sys.stderr, flush=True)
    print(json.dumps(record, ensure_ascii=False, indent=2), flush=True)
    return 130 if record['interrupted'] else (0 if record['status'] == 'pass' else 1)


if __name__ == '__main__':
    raise SystemExit(main())
