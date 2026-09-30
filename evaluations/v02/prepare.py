#!/usr/bin/env python3
"""Prepare original cases and a skill snapshot in a new external directory."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    repo = source.parents[1]
    out = args.output.resolve()
    if out == repo or repo in out.parents:
        parser.error('Output must be outside the repository')
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        parser.error('Output must be a new or empty directory')
    inventory = json.loads((source / 'inventory.json').read_text(encoding='utf-8'))
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(repo / 'skills/embedded-project-workflow', out / 'skill')
    for item in inventory:
        case = item['case']
        shutil.copytree(source / 'cases' / case, out / 'cases' / case)
        baseline = out / 'cases' / case / 'baseline'
        if baseline.is_dir():
            shutil.copytree(baseline, out / 'cases' / case / 'work')
    hashes = {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in out.rglob('*') if p.is_file()}
    (out / 'prepared-inputs.json').write_text(json.dumps(hashes, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'cases': len(inventory), 'files': len(hashes), 'output': str(out)}))


if __name__ == '__main__':
    main()
