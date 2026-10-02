#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
"""Copy only raw selected regression inputs and a candidate skill snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

CASES = ('18_authorized_adjustment', '21_user_ui_change', '23_partial_generation',
         '24_resume_new_source', '26_local_small_edit')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    out = args.output.resolve()
    if out == repo or repo in out.parents or out in repo.parents:
        parser.error('Use an empty directory outside and not containing the repository')
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        parser.error('Output must be new or empty')
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(repo/'skills/embedded-project-workflow', out/'skill',
                    ignore=shutil.ignore_patterns('__pycache__'))
    for name in CASES:
        target = out/'cases'/name
        shutil.copytree(repo/'evaluations/v02/cases'/name, target)
        if (target/'baseline').is_dir():
            shutil.copytree(target/'baseline', target/'work')
    hashes = {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(out.rglob('*')) if p.is_file()}
    (out/'prepared-inputs.json').write_text(json.dumps(hashes, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'cases': len(CASES), 'files': len(hashes)}, sort_keys=True))


if __name__ == '__main__':
    main()
