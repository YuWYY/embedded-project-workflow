#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
"""Compile real C sources and verify an independent contract and wrong-mean negative."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    repo = source.parents[2]
    out = args.output.resolve()
    if out == repo or repo in out.parents or out in repo.parents:
        parser.error('Use output outside and not containing source repository')
    if out.exists():
        parser.error('Output must not exist')
    cc = args.cc.resolve(strict=True)
    out.mkdir(parents=True)
    record = {'status': 'STARTED', 'evidence': 'HOST_C_ONLY', 'commands': [],
              'inputs': {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in (source/'epw_stats.c', source/'epw_stats.h', Path(__file__).resolve(), source/'tests/stats_contract.c')}}
    result = out/'result.json'
    def save():
        temp = out/'result.tmp'
        temp.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
        temp.replace(result)
    def run(name, cmd, expected=0):
        log = out/(name+'.log')
        item = {'name': name, 'returncode': None, 'expected': expected}
        record['commands'].append(item)
        save()
        with log.open('wb') as stream:
            p = subprocess.run([str(v) for v in cmd], cwd=out, stdout=stream,
                               stderr=subprocess.STDOUT, timeout=60)
        item['returncode'] = p.returncode
        save()
        if p.returncode != expected:
            raise RuntimeError(name+' unexpected exit: '+str(p.returncode))
        return log.read_text(encoding='utf-8', errors='replace')
    save()
    try:
        options = [cc, '-std=c99', '-Wall', '-Wextra', '-Werror', '-I', source]
        run('compile', [*options, source/'epw_stats.c', source/'tests/stats_contract.c', '-o', out/'contract.exe'])
        output = run('positive', [out/'contract.exe'])
        if 'stats contract PASS' not in output: raise RuntimeError('Missing positive completion marker')
        wrapper = out/'wrong_mean.c'
        wrapper.write_text('''#include "epw_stats.h"
bool epw_stats_read_original(const epw_stats *, epw_stats_result *);
bool epw_stats_read(const epw_stats *s, epw_stats_result *r) {
    bool ok = epw_stats_read_original(s,r);
    if(ok) { r->mean ^= 1U; }
    return ok;
}
''', encoding='utf-8')
        run('compile_original', [*options, '-Depw_stats_read=epw_stats_read_original', '-c', source/'epw_stats.c', '-o', out/'original.o'])
        run('compile_negative', [*options, out/'original.o', wrapper, source/'tests/stats_contract.c', '-o', out/'negative.exe'])
        negative = run('wrong_mean_negative', [out/'negative.exe'], expected=1)
        if 'value.mean == mean' not in negative: raise RuntimeError('Negative did not fail on mean contract')
        for name, identity in record['inputs'].items():
            if hashlib.sha256((source/name).read_bytes()).hexdigest() != identity:
                raise RuntimeError('Input changed during verification: '+name)
        record['status'] = 'PASS'
    except BaseException as exc:
        record.update(status='FAIL', error=str(exc))
        raise
    finally:
        save()
    print(json.dumps({'status': record['status'], 'evidence': record['evidence'], 'negative': 'wrong mean rejected'}))


if __name__ == '__main__':
    main()
