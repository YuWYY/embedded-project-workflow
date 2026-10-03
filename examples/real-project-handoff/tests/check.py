#!/usr/bin/env python3
"""Host contracts for the original status module; no vendor SDK or board claim.
Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc', required=True, type=Path)
    parser.add_argument('--source-dir', type=Path, default=Path(__file__).resolve().parents[1]/'status')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists(): parser.error('output must be new')
    args.output.mkdir(parents=True)
    env = os.environ.copy(); env['PATH'] = str(args.cc.resolve().parent) + os.pathsep + env.get('PATH', '')
    source = args.source_dir.resolve()
    tests = Path(__file__).with_name('status_contract.c').resolve()
    record = {'status': 'RUNNING', 'source_sha256': None, 'inputs': {}, 'cases': []}
    def save():
        temp = args.output/'result.tmp'; temp.write_text(json.dumps(record,indent=2),encoding='utf-8'); temp.replace(args.output/'result.json')
    save()
    try:
        inputs = {'epw_status.c': source/'epw_status.c', 'epw_status.h': source/'epw_status.h',
                  'status_contract.c': tests}
        record['inputs'] = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name,path in inputs.items()}
        record['source_sha256'] = record['inputs']['epw_status.c']
        record['compiler_sha256'] = hashlib.sha256(args.cc.read_bytes()).hexdigest()
        save()
        mutations = [('positive', None, None), ('fixed-time', '(uint32_t)(state->elapsed_ms / 1000u)', '0u'),
                     ('refresh-count', '(uint32_t)(state->elapsed_ms / 1000u)', 'state->visible.seconds + 1u'),
                     ('fixed-period', '< state->period_ms', '< 100u'),
                     ('truncated-uptime', 'state->elapsed_ms += (uint32_t)(now_ms - state->last_tick);',
                      'state->elapsed_ms = (uint32_t)(state->elapsed_ms + (uint32_t)(now_ms - state->last_tick));')]
        reasons = {'fixed-time': 'real elapsed time, not refresh count', 'refresh-count': 'real elapsed time, not refresh count', 'fixed-period': '250 config honored',
                   'truncated-uptime': 'elapsed survives full tick period'}
        for name, old, new in mutations:
            work=args.output/name; work.mkdir(); shutil.copy2(source/'epw_status.h',work/'epw_status.h')
            body=(source/'epw_status.c').read_text(encoding='utf-8')
            if old is not None:
                if body.count(old)!=1: raise RuntimeError('Mutation target is no longer unique: '+name)
                body=body.replace(old,new)
            (work/'epw_status.c').write_text(body,encoding='utf-8')
            binary=work/('contract.exe' if os.name=='nt' else 'contract')
            case={'name':name,'status':'RUNNING','compile_exit':None,'run_exit':None}; record['cases'].append(case);save()
            with (work/'compile.log').open('wb') as log:
                result=subprocess.run([str(args.cc.resolve()),'-std=c11','-Wall','-Wextra','-Werror','-I',str(work.resolve()),str(work/'epw_status.c'),str(tests),'-o',str(binary)],stdout=log,stderr=subprocess.STDOUT,env=env,timeout=60)
            case['compile_exit']=result.returncode
            if result.returncode: raise RuntimeError('Host compilation failed: '+name)
            with (work/'run.log').open('wb') as log:
                result=subprocess.run([str(binary.resolve())],stdout=log,stderr=subprocess.STDOUT,env=env,timeout=10)
            case['run_exit']=result.returncode
            text=(work/'run.log').read_text(encoding='utf-8',errors='replace')
            expected=(result.returncode==0 and 'PASS status' in text) if name=='positive' else (result.returncode==1 and reasons[name] in text)
            if not expected: raise RuntimeError('Unexpected contract result: '+name+' '+text)
            case['status']='PASS' if name=='positive' else 'EXPECTED_FAILURE';save()
        if any(hashlib.sha256(path.read_bytes()).hexdigest()!=record['inputs'][name] for name,path in inputs.items()):
            raise RuntimeError('Inputs changed while running host contracts')
        record['status']='PASS';save();print('PASS host status and four discriminating negatives');return 0
    except (Exception,KeyboardInterrupt) as error:
        record['status']='FAIL';record['error']=str(error)
        if record['cases'] and record['cases'][-1]['status']=='RUNNING':
            record['cases'][-1]['status']='FAIL'
        save();print(str(error),file=sys.stderr);return 130 if isinstance(error,KeyboardInterrupt) else 1
if __name__=='__main__':raise SystemExit(main())
