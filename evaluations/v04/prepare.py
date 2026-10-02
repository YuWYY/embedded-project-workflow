#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
"""Prepare raw v04 requests and an explicit skill snapshot, never reviewer answers."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

OLD_CASES = ('17_prescribed_structure', '18_authorized_adjustment', '19_explicit_conflict',
             '21_user_ui_change', '23_partial_generation', '24_resume_new_source',
             '26_local_small_edit')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    out = args.output.resolve()
    if out == repo or repo in out.parents or out in repo.parents:
        parser.error('Output must be outside and not contain the repository')
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        parser.error('Use a new or empty output directory')
    if any(p.is_symlink() for p in [args.output.absolute(), *args.output.absolute().parents]):
        parser.error('Linked output paths are not supported')
    common = repo/'examples/common/rolling-stats'
    if not all((common/name).is_file() for name in ('epw_stats.c', 'epw_stats.h')):
        parser.error('Shared original component sources must exist before preparing cases')
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(repo/'skills/embedded-project-workflow', out/'skill',
                    ignore=shutil.ignore_patterns('__pycache__'))
    cases = [repo/'evaluations/v02/cases'/name for name in OLD_CASES]
    cases += sorted(p for p in (repo/'evaluations/v04/cases').iterdir() if p.is_dir())
    for case in cases:
        target = out/'cases'/case.name
        shutil.copytree(case, target)
        if (target/'baseline').is_dir():
            shutil.copytree(target/'baseline', target/'work')
        if case.name == 'esp-config':
            app = target/'work/examples/esp-idf'
            shutil.copytree(repo/'examples/esp-idf', app,
                            ignore=shutil.ignore_patterns('build', '__pycache__'))
            module = target/'work/examples/common/rolling-stats'
            module.mkdir(parents=True)
            for name in ('epw_stats.c', 'epw_stats.h'):
                shutil.copy2(common/name, module/name)
            for name in ('main/app_main.c', 'sdkconfig', 'sdkconfig.defaults'):
                shutil.copy2(target/'input'/name, app/name)
    hashes = {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(out.rglob('*')) if p.is_file()}
    (out/'prepared-inputs.json').write_text(json.dumps(hashes, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'cases': len(cases), 'files': len(hashes)}))


if __name__ == '__main__':
    main()
