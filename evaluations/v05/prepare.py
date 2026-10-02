#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
"""Prepare original raw requests plus a Skill snapshot, without reviewer answers."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    out = args.output.absolute()
    for path in (out, *out.parents):
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            parser.error('Linked output is not supported')
    out = out.resolve()
    if out == repo or repo in out.parents or out in repo.parents:
        parser.error('Use an output outside the repository')
    if out.exists():
        parser.error('Use a new output directory')
    cases = json.loads((Path(__file__).with_name('cases.json')).read_text(encoding='utf-8'))
    out.mkdir(parents=True)
    shutil.copytree(repo/'skills/embedded-project-workflow', out/'skill',
                    ignore=shutil.ignore_patterns('__pycache__'))
    for case in cases:
        target = out/'cases'/case['id']
        target.mkdir(parents=True)
        (target/'REQUEST.md').write_text(case['request']+'\n', encoding='utf-8')
        work = target/'work'
        work.mkdir()
        for name, content in case['files'].items():
            path = work/name
            if path.parent != work:
                raise ValueError('Only flat original inputs are supported')
            path.write_text(content, encoding='utf-8')
    manifest = {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(out.rglob('*')) if p.is_file()}
    (out/'prepared-inputs.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'cases':len(cases), 'files':len(manifest)}))


if __name__ == '__main__':
    main()
