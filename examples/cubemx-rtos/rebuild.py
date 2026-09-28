#!/usr/bin/env python3
"""Original CubeMX/Keil source-ownership trial; never flashes or starts a debugger.

Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT
Vendor tools, packs and generated sources remain external dependencies.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET

SOURCE = Path(__file__).resolve().parent
NAME = 'rtos_ownership'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def run(command, cwd, log, env, timeout=360):
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    start = time.monotonic()
    with log.open('w', encoding='utf-8') as stream:
        proc = subprocess.run(command, cwd=cwd, env=env, stdout=stream,
                              stderr=subprocess.STDOUT, startupinfo=startup, timeout=timeout)
    result = {'command': [str(x) for x in command], 'exit_code': proc.returncode,
              'seconds': round(time.monotonic() - start, 2)}
    write_json(log.with_suffix('.json'), result)
    return result

def generate(work, stage, args, env):
    out = args.reports / stage
    out.mkdir(parents=True, exist_ok=False)
    ioc = work / (NAME + '.ioc')
    shutil.copy2(ioc, out / 'source-before.ioc')
    script = out / 'generate.mxscript'
    script.write_text('\n'.join([
        f'config load "{ioc.as_posix()}"', 'project toolchain "MDK-ARM V5.27"',
        f'project setCustomFWPath "{args.firmware.as_posix()}"',
        'project generate', 'exit', '']), encoding='utf-8')
    java = args.cubemx.parent / 'jre/bin/java.exe'
    result = run([str(java), '--add-opens', 'java.desktop/java.awt=ALL-UNNAMED',
        '--add-exports', 'java.desktop/sun.awt=ALL-UNNAMED', '-Dfile.encoding=UTF-8',
        '-jar', str(args.cubemx), '-q', str(script)], work, out / 'cubemx.log', env)
    body = (out / 'cubemx.log').read_text(encoding='utf-8', errors='replace')
    expected = [work/'Core/Src/app_freertos.c', work/'Core/Src/main.c',
                work/'MDK-ARM'/f'{NAME}.uvprojx']
    assert result['exit_code'] == 0 and all(p.is_file() for p in expected), 'Generation incomplete'
    assert not re.search(r'Exception|Code generation failed|FileNotFound', body), 'Native generation error'
    result['expected_products_present'] = True
    result['ioc_sha256'] = digest(ioc)
    write_json(out / 'result.json', result)
    print(json.dumps({'stage': stage, **result}, ensure_ascii=False), flush=True)
    return result

def integrate(work):
    shutil.copytree(SOURCE/'APP', work/'APP')
    path = work/'Core/Src/app_freertos.c'
    body = path.read_text(encoding='utf-8')
    body = body.replace('/* USER CODE BEGIN Includes */',
                        '/* USER CODE BEGIN Includes */\n#include "rtos_app.h"')
    body = body.replace('/* USER CODE BEGIN RTOS_THREADS */',
                        '/* USER CODE BEGIN RTOS_THREADS */\n  RtosApp_CheckCreated();')
    path.write_text(body, encoding='utf-8')
    project = work/'MDK-ARM'/f'{NAME}.uvprojx'
    tree = ET.parse(project)
    root = tree.getroot()
    for parent, key, value in [
        (root.find('.//Target'), 'pCCUsed', r'5060960::V5.06 update 7 (build 960)::.\ARMCC'),
        (root.find('.//Target'), 'uAC6', '0'),
        (root.find('.//TargetCommonOption'), 'PackID', 'Keil.STM32G4xx_DFP.2.0.0')]:
        node=parent.find(key)
        if node is None:
            node=ET.SubElement(parent,key)
        node.text=value
    for node in root.findall('.//RunUserProg1') + root.findall('.//RunUserProg2'):
        node.text = '0'
    inc = root.find('.//Cads/VariousControls/IncludePath')
    inc.text = (inc.text or '') + r';..\APP'
    group = ET.SubElement(root.find('.//Groups'), 'Group')
    ET.SubElement(group, 'GroupName').text = 'User Application'
    files = ET.SubElement(group, 'Files')
    file = ET.SubElement(files, 'File')
    for key, value in [('FileName','rtos_app.c'), ('FileType','1'), ('FilePath',r'..\APP\rtos_app.c')]:
        ET.SubElement(file, key).text = value
    tree.write(project, encoding='utf-8', xml_declaration=True)
    # A newly generated companion file is required by subsequent native regeneration.
    opt = project.with_suffix('.uvoptx')
    if opt.exists():
        data = opt.read_text(encoding='utf-8-sig')
        data = re.sub(r'<UpdateFlashBeforeDebugging>\d+</UpdateFlashBeforeDebugging>',
                      '<UpdateFlashBeforeDebugging>0</UpdateFlashBeforeDebugging>', data)
        opt.write_text(data, encoding='utf-8')

def inspect(work, words, depth, dynamic):
    body = (work/'Core/Src/app_freertos.c').read_text(encoding='utf-8')
    checks = {
        'two_unique_task_creations': len(re.findall(r'=\s*osThreadNew\(', body)) == 2,
        'one_queue_creation': len(re.findall(r'=\s*osMessageQueueNew\s*\(', body)) == 1,
        'external_producer': 'extern void Producer_Entry(void *argument);' in body,
        'external_consumer': 'extern void Consumer_Entry(void *argument);' in body,
        'consumer_has_no_generated_body': not re.search(r'void\s+Consumer_Entry\([^)]*\)\s*\{', body),
        'first_task_weak_fallback_is_known': bool(re.search(r'__weak void Producer_Entry\(', body)),
        'queue_capacity': bool(re.search(r'osMessageQueueNew\s*\(\s*'+str(depth)+r'\s*,\s*sizeof\(uint32_t\)', body)),
        'queue_static_storage': bool(re.search(r'uint8_t SamplesStorage\[\s*'+str(depth)+r'\s*\*', body)),
        'consumer_words': bool(re.search(r'uint32_t ConsumerStack\[\s*256\s*\]', body)),
        'creation_check_hook': 'RtosApp_CheckCreated();' in body,
    }
    if dynamic:
        checks['producer_dynamic_no_static_buffer'] = 'uint32_t ProducerStack' not in body
        checks['producer_bytes_from_words'] = bool(re.search(r'\.stack_size\s*=\s*'+str(words)+r'\s*\*\s*4', body))
    else:
        checks['producer_static_buffer_words'] = bool(re.search(r'uint32_t ProducerStack\[\s*'+str(words)+r'\s*\]', body))
        checks['producer_bytes_from_sizeof'] = '.stack_size = sizeof(ProducerStack)' in body
    project = ET.parse(work/'MDK-ARM'/f'{NAME}.uvprojx').getroot()
    checks['compiler_version_retained'] = project.find('.//pCCUsed').text.startswith('5060960::')
    checks['armcc5_selected'] = project.find('.//uAC6').text == '0'
    checks['device_pack_retained'] = project.find('.//PackID').text == 'Keil.STM32G4xx_DFP.2.0.0'
    paths = [n.text for n in project.findall('.//FilePath')]
    checks['app_compiled_once'] = sum(p.replace('\\','/').endswith('/APP/rtos_app.c') for p in paths) == 1
    for p in paths:
        resolved = (work/'MDK-ARM'/p.replace('\\','/')).resolve()
        assert resolved.is_relative_to(work.resolve()) and resolved.is_file(), f'Escaping or missing input: {p}'
    assert all(checks.values()), checks
    return {'checks': checks, 'producer_stack_words': words, 'producer_stack_bytes': words*4,
            'queue_elements': depth, 'queue_data_bytes': depth*4,
            'producer_allocation': 'Dynamic' if dynamic else 'Static'}

def build(work, stage, args, env, negative=False):
    out = args.reports/stage
    out.mkdir(parents=True, exist_ok=False)
    project = work/'MDK-ARM'/f'{NAME}.uvprojx'
    # CubeMX can restore a checked, empty AfterMake action on regeneration.
    # This trial permits only generation and rebuild: disable project hooks each time.
    tree=ET.parse(project)
    disabled=[]
    for node in tree.getroot().findall('.//RunUserProg1') + tree.getroot().findall('.//RunUserProg2'):
        if node.text != '0':
            disabled.append(node.tag)
        node.text='0'
    tree.write(project,encoding='utf-8',xml_declaration=True)
    opt=project.with_suffix('.uvoptx')
    if opt.exists():
        body=opt.read_text(encoding='utf-8-sig')
        body=re.sub(r'<UpdateFlashBeforeDebugging>\d+</UpdateFlashBeforeDebugging>',
                    '<UpdateFlashBeforeDebugging>0</UpdateFlashBeforeDebugging>',body)
        opt.write_text(body,encoding='utf-8')
    log = out/'keil.log'
    result = run([str(args.uv4), '-r', str(project), '-o', str(log)],
                 project.parent, out/'process.log', env)
    body = log.read_text(encoding='utf-8', errors='replace') if log.exists() else ''
    match = re.search(r'(\d+) Error\(s\), (\d+) Warning\(s\)', body)
    errors, warnings = (int(match[1]), int(match[2])) if match else (-1,-1)
    result.update(errors=errors, warnings=warnings, expected_failure=negative,
                  generated_hook_flags_disabled=disabled)
    if negative:
        assert errors > 0 and 'L6218E: Undefined symbol Consumer_Entry' in body, body[-3000:]
        assert not re.search(r'error:|Error: #', body), 'Failure must be link-only'
        result['expected_missing_external_symbol_detected'] = True
    else:
        assert errors == 0 and result['exit_code'] in (0,1), body[-3500:]
        maps = list((work/'MDK-ARM').rglob(NAME+'.map'))
        assert len(maps) == 1, maps
        text = maps[0].read_text(encoding='utf-8', errors='replace')
        for symbol in ('Producer_Entry','Consumer_Entry','RtosApp_CheckCreated'):
            assert re.search(r'\b'+symbol+r'\b[^\r\n]*rtos_app\.o', text), symbol
        result['application_symbols_resolve_to_user_object'] = True
        sizes={}
        for symbol in ('ProducerStack','ConsumerStack','SamplesStorage'):
            found=re.search(r'^\s*'+symbol+r'\s+0x[0-9a-fA-F]+\s+Data\s+(\d+)\s',text,re.M)
            if found:
                sizes[symbol]=int(found[1])
        generated=(work/'Core/Src/app_freertos.c').read_text(encoding='utf-8')
        for symbol in ('ProducerStack','ConsumerStack'):
            found=re.search(r'uint32_t '+symbol+r'\[\s*(\d+)\s*\]',generated)
            if found:
                assert sizes.get(symbol)==int(found[1])*4, 'MAP stack size differs from configuration'
        found=re.search(r'uint8_t SamplesStorage\[\s*(\d+)\s*\*',generated)
        assert found and sizes.get('SamplesStorage')==int(found[1])*4, 'MAP queue storage mismatch'
        result['map_static_storage_bytes']=sizes
        result['map_sha256'] = digest(maps[0])
        shutil.copy2(maps[0], out/'firmware.map')
        images = list((work/'MDK-ARM').rglob(NAME+'.axf'))
        assert len(images) == 1
        result['axf_sha256'] = digest(images[0])
    write_json(out/'result.json', result)
    print(json.dumps({'stage':stage, **result}, ensure_ascii=False), flush=True)
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cubemx', type=Path, required=True)
    ap.add_argument('--firmware', type=Path, required=True)
    ap.add_argument('--uv4', type=Path, required=True)
    ap.add_argument('--build-root', type=Path, required=True)
    ap.add_argument('--reports', type=Path)
    args=ap.parse_args()
    for key in ('cubemx','firmware','uv4','build_root'):
        setattr(args,key,getattr(args,key).resolve())
    assert args.cubemx.is_file() and args.uv4.is_file() and args.firmware.is_dir()
    args.reports=(args.reports or args.build_root/'reports').resolve()
    for label, path in (('build root',args.build_root), ('report directory',args.reports)):
        if path.is_relative_to(SOURCE):
            ap.error(f'The {label} must be outside the original source tree')
        if path.exists() and (not path.is_dir() or any(path.iterdir())):
            ap.error(f'Use a new or empty {label}')
    args.build_root.mkdir(parents=True,exist_ok=True)
    args.reports.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    temp=args.build_root/'tmp'; temp.mkdir()
    env.update(TEMP=str(temp),TMP=str(temp),PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
    for key in ('PROTOCOL_TEST_EXE','GIT_DIR','GIT_WORK_TREE','GIT_INDEX_FILE','PYTHONPATH'):
        env.pop(key,None)
    results={}
    work=args.build_root/'static'; work.mkdir()
    shutil.copy2(SOURCE/(NAME+'.ioc'),work/(NAME+'.ioc'))
    results['generate_initial']=generate(work,'01-generate',args,env)
    integrate(work)
    results['initial_configuration']=inspect(work,256,8,False)
    original_app={p.name:digest(p) for p in (work/'APP').iterdir()}
    results['build_initial']=build(work,'02-build',args,env)
    ioc=work/(NAME+'.ioc')
    text=ioc.read_text(encoding='utf-8').replace('Producer,24,256,','Producer,24,384,')
    text=text.replace('Samples,8,uint32_t','Samples,16,uint32_t')
    ioc.write_text(text,encoding='utf-8')
    results['generate_edited']=generate(work,'03-regenerate',args,env)
    results['edited_configuration']=inspect(work,384,16,False)
    assert original_app=={p.name:digest(p) for p in (work/'APP').iterdir()}, 'Application overwritten'
    results['application_preserved_after_regeneration']=True
    results['build_edited']=build(work,'04-rebuild',args,env)
    dynamic=args.build_root/'dynamic'; dynamic.mkdir()
    text=(SOURCE/(NAME+'.ioc')).read_text(encoding='utf-8')
    text=text.replace('Producer,24,256,Producer_Entry,As external,NULL,Static,ProducerStack,ProducerTCB',
                      'Producer,24,256,Producer_Entry,As external,NULL,Dynamic,NULL,NULL')
    (dynamic/(NAME+'.ioc')).write_text(text,encoding='utf-8')
    results['generate_dynamic']=generate(dynamic,'05-generate-dynamic',args,env)
    integrate(dynamic)
    results['dynamic_configuration']=inspect(dynamic,256,8,True)
    results['build_dynamic']=build(dynamic,'06-build-dynamic',args,env)
    negative=args.build_root/'missing-entry'
    shutil.copytree(work,negative,ignore=shutil.ignore_patterns('*.o','*.d','*.axf','*.hex','*.map','*.htm','*.lst'))
    app=negative/'APP/rtos_app.c'
    app.write_text('#define RTOS_TEST_OMIT_CONSUMER 1\n'+app.read_text(encoding='utf-8'),encoding='utf-8')
    results['missing_external_negative']=build(negative,'07-negative',args,env,negative=True)
    results['status']='PASS'
    results['coverage']={'native_generation':True,'target_build':True,'linkage':True,
                         'runtime_scheduling':False,'board_test':False,'download':False}
    results['original_source_sha256']={p.relative_to(SOURCE).as_posix():digest(p)
                                      for p in SOURCE.rglob('*') if p.is_file()}
    write_json(args.reports/'result.json',results)
    print('PASS: generated, built, regenerated, allocation variant, missing-entry negative. No hardware run.',flush=True)

if __name__=='__main__':
    main()
