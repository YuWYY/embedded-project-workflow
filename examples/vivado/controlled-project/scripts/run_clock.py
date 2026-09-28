"""Run one isolated Clocking Wizard generation, simulation and synthesis stage.

Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import uuid


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


CLOCK_SOURCES = ('clock.xdc', 'clock_top.sv', 'tb_clock.sv')
OWNER_FILE = '.controlled-clock-project.json'
OWNER_FORMAT = 'embedded-project-workflow/controlled-clock'


def inventory(package, source_root=None):
    source_root = source_root or package / 'sources'
    found = {str(p.relative_to(package)).replace('\\', '/'): sha(p)
             for folder in ('config', 'scripts')
             for p in sorted((package / folder).rglob('*'))
             if p.is_file() and '__pycache__' not in p.parts}
    found.update({'sources/' + name: sha(source_root / name) for name in CLOCK_SOURCES})
    return found


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vivado', help='Existing Vivado executable; otherwise resolve Windows vivado.bat/exe from PATH')
    parser.add_argument('--build-root')
    parser.add_argument('--regenerate', action='store_true')
    parser.add_argument('--stage', required=True)
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
    root.mkdir(parents=True, exist_ok=True)
    work.mkdir(exist_ok=True)
    evidence.mkdir(parents=True)
    write_json(root / OWNER_FILE, owner)
    initial = inventory(package, shared_sources)
    for folder in ('scripts', 'config'):
        shutil.copytree(package / folder, root / folder, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__'))
    (root / 'sources').mkdir(exist_ok=True)
    for name in CLOCK_SOURCES:
        shutil.copy2(shared_sources / name, root / 'sources' / name)
    shutil.copy2(package / 'config/clock-config.tcl', evidence / 'clock-config.tcl')
    marker = work / 'completed.txt'
    sim = work / 'p/c.sim/sim_1/behav/xsim/clock_result.txt'
    removed_old_results = []
    for old_result in (marker, sim):
        if old_result.exists():
            old_result.unlink()
            removed_old_results.append(old_result.name)
    command = [str(executable), '-mode', 'batch', '-notrace', '-source',
               str(root / 'scripts/clock.tcl'), '-tclargs', str(root / 'sources')]
    if args.regenerate:
        command.append('regenerate')
    started = time.monotonic()
    record = {'stage': args.stage, 'command': command, 'cwd': str(work),
              'build_root': str(root), 'source_sha256': initial,
              'owner_id': owner['owner_id'], 'requested_output_mhz': requested_mhz,
              'expected_period_ns': 1000.0 / requested_mhz,
              'removed_old_result_files': removed_old_results,
              'status': 'running', 'coverage': 'IP generation, XSim, IP/top synthesis only'}
    write_json(evidence / 'result.json', record)
    print('Build directory:', root, flush=True)
    with (evidence / 'stdout.log').open('w', encoding='utf-8') as output:
        result = subprocess.run(command, cwd=work, stdout=output,
                                stderr=subprocess.STDOUT, check=False,
                                creationflags=subprocess.CREATE_NO_WINDOW)
    record.update(returncode=result.returncode,
                  elapsed_seconds=round(time.monotonic()-started, 2),
                  sources_unchanged=(initial == inventory(package, shared_sources) == inventory(root)))
    record['completion'] = marker.read_text(encoding='utf-8').strip() if marker.exists() else ''
    record['simulation'] = sim.read_text(encoding='utf-8').strip() if sim.exists() else ''
    for p in work.glob('*.rpt'):
        shutil.copy2(p, evidence / p.name)
    for name in ('ip_properties.txt', 'completed.txt', 'tool_version.txt'):
        if (work / name).is_file():
            shutil.copy2(work / name, evidence / name)
    if sim.is_file():
        shutil.copy2(sim, evidence / sim.name)
    simlog = sim.with_name('simulate.log')
    if simlog.is_file():
        shutil.copy2(simlog, evidence / 'simulate.log')
    record['status'] = ('pass' if result.returncode == 0
                        and record['sources_unchanged']
                        and matching_results(record['completion'], record['simulation'], requested_mhz)
                        else 'fail')
    write_json(evidence / 'result.json', record)
    if record['status'] == 'pass':
        owner['last_successful_stage'] = args.stage
        write_json(root / OWNER_FILE, owner)
    print(json.dumps(record, ensure_ascii=False, indent=2), flush=True)
    return 0 if record['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
