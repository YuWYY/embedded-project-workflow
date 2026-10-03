"""Create a single blind case workspace; never copies the reviewer rubric."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil


def prepare(case_id, output, skill=None):
    cases = json.loads(Path(__file__).with_name('cases.json').read_text(encoding='utf-8'))
    case = next(c for c in cases if c['id'] == case_id)
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Output must be a new directory')
    output.mkdir(parents=True)
    for name, content in case['files'].items():
        target = output / name
        if not target.resolve().is_relative_to(output):
            raise ValueError('Case path escapes workspace')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
    prompt = case['request']
    if skill:
        shutil.copytree(skill, output / 'candidate-skill', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        prompt = '本次请显式读取 candidate-skill/SKILL.md，并按需读取其引用。\n' + prompt
    (output / 'REQUEST.md').write_text(prompt, encoding='utf-8')
    return {name: hashlib.sha256((output/name).read_bytes()).hexdigest() for name in case['files']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--skill', type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.case, args.output, args.skill), indent=2))
