#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
"""Rebuild the two-screen ownership trial using a local TouchGFX installation.

No downloads, installer actions, target build, flash, or simulator GUI launch.
All generated/vendor material stays in the explicitly supplied empty build root.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hashes(root):
    return {p.relative_to(root).as_posix(): digest(p)
            for p in sorted(root.rglob('*')) if p.is_file()}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--touchgfx-root', type=Path, required=True)
    parser.add_argument('--build-root', type=Path, required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    install = args.touchgfx_root.resolve()
    build = args.build_root.resolve()
    require(os.name == 'nt', 'This verified entry point uses the Windows TouchGFX package.')
    require(source != build and source not in build.parents,
            'Choose an empty build directory outside this source package.')
    require(not build.exists() or not any(build.iterdir()), 'Build root must be empty.')
    tgfx = install / 'designer/tgfx.exe'
    cxx = install / 'env/MinGW/bin/g++.exe'
    for p in (tgfx, cxx, install/'app/packages/BlankUI-2.0.0.tpa',
              install/'app/packages/Simulator-2.0.0.tpa'):
        require(p.is_file(), 'Missing local dependency: ' + str(p))
    before = tree_hashes(source)
    (build/'tmp').mkdir(parents=True, exist_ok=True)
    logs = build/'logs'
    logs.mkdir()
    env = os.environ.copy()
    env.update(TEMP=str(build/'tmp'), TMP=str(build/'tmp'), PYTHONUTF8='1')
    env['PATH'] = os.pathsep.join(str(install/p) for p in
        ('env/MinGW/bin', 'env/MinGW/msys/1.0/bin', 'touchgfx/framework/tools')) + os.pathsep + env.get('PATH', '')
    stages = []

    def run(name, cmd, cwd, expected=0):
        start = time.monotonic()
        result = subprocess.run([str(x) for x in cmd], cwd=cwd, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=300)
        output = result.stdout.decode('utf-8', errors='replace')
        (logs/(name+'.log')).write_bytes(result.stdout)
        stages.append(dict(name=name, returncode=result.returncode,
                           seconds=round(time.monotonic()-start, 3)))
        require(result.returncode == expected,
                name + ': unexpected exit code; inspect ' + str(logs/(name+'.log')))
        print(name + ': exit ' + str(result.returncode), flush=True)
        return output

    version = run('tool-version', [tgfx, 'version'], build).strip()
    require(version == '4.26.1', 'This fixture is validated with TouchGFX 4.26.1.')
    run('create-local', [tgfx, 'new', '--ui='+str(install/'app/packages/BlankUI-2.0.0.tpa'),
        '--at='+str(install/'app/packages/Simulator-2.0.0.tpa'), '--out='+str(build/'work'),
        '--prj=HumanControl'], build)
    project = build/'work/HumanControl'
    project_file = project/'HumanControl.touchgfx'
    config = json.loads(project_file.read_text(encoding='utf-8-sig'))
    app = config['Application']
    app['SelectedColorDepth'] = 16
    app['StartupScreenName'] = 'Dashboard'
    app['Screens'] = json.loads((source/'ui-before.json').read_text(encoding='utf-8'))
    project_file.write_text(json.dumps(config, indent=2)+'\n', encoding='utf-8')
    resource_config = project/'application.config'
    resources = json.loads(resource_config.read_text(encoding='utf-8-sig'))
    resources['text_configuration']['framebuffer_bpp'] = '16'
    resources['image_configuration']['opaque_image_format'] = 'RGB565'
    resource_config.write_text(json.dumps(resources, indent=2)+'\n', encoding='utf-8')
    shutil.copyfile(source/'texts.xml', project/'assets/texts/texts.xml')

    def generate(label):
        output = run(label, [tgfx, 'generate', '-p', project_file, '-v'], project)
        require('Generation & Update complete' in output, label + ': completion not reported')
        require((project/'generated/gui_generated/include/gui_generated/dashboard_screen/DashboardViewBase.hpp').is_file(),
                'Missing generated Dashboard base class')

    def compile_simulator(label, expected=0):
        output = run(label, [tgfx, 'compile', '-p', project_file, '-s', '-v'], project, expected)
        if expected == 0:
            require('Compilation Succeded' in output and (project/'build/bin/simulator.exe').is_file(),
                    label + ': simulator build not demonstrated')
        return output

    generate('generate-before-user-code')
    for p in (source/'user').rglob('*'):
        if not p.is_file():
            continue
        dest = project/p.relative_to(source/'user')
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = p.read_text(encoding='utf-8')
        if p.name == 'DashboardView.cpp':
            text = text.replace('sampleValue', 'counterValue').replace('SAMPLEVALUE_SIZE', 'COUNTERVALUE_SIZE')
        dest.write_text(text, encoding='utf-8')
    compile_simulator('compile-original-user-design')
    original_gui = tree_hashes(project/'gui')

    app['Screens'] = json.loads((source/'ui-after.json').read_text(encoding='utf-8'))
    project_file.write_text(json.dumps(config, indent=2)+'\n', encoding='utf-8')
    expected_user_source = digest(project_file)
    generate('generate-user-rename-and-move')
    require(tree_hashes(project/'gui') == original_gui, 'Regeneration changed existing user code')
    generated = (project/'generated/gui_generated/src/dashboard_screen/DashboardViewBase.cpp').read_text()
    require('sampleValue.setPosition(40, 80, 300, 36)' in generated,
            'Generated layout does not implement the user source change')
    failed = compile_simulator('compile-stale-reference-expected-failure', expected=2)
    require('counterValueBuffer' in failed and 'not declared' in failed,
            'Expected stale-reference failure was not observed')
    target = project/'gui/src/dashboard_screen/DashboardView.cpp'
    target.write_bytes((source/'user/gui/src/dashboard_screen/DashboardView.cpp').read_bytes())
    require(digest(project_file) == expected_user_source, 'User design source was altered by adaptation')
    compile_simulator('compile-adapted-user-code')

    final_gui = tree_hashes(project/'gui')
    generate('generate-retention')
    require(tree_hashes(project/'gui') == final_gui, 'Second regeneration changed user implementation')
    require(digest(project_file) == expected_user_source, 'Retention generation changed the user source')
    compile_simulator('compile-retention')

    test_exe = build/'model_test.exe'
    run('compile-production-model-test', [cxx, '-std=c++11', '-O2', '-Wall', '-Wextra', '-Werror',
        '-I'+str(project/'gui/include'), project/'gui/src/model/Model.cpp',
        source/'tests/model_test.cpp', '-static', '-o', test_exe], build)
    run('production-model-pass', [test_exe], build)
    run('production-model-negative-control', [test_exe, '--inject-extra-period'], build, expected=1)
    require(tree_hashes(source) == before, 'Source package changed during rebuild')
    results = dict(tool_version=version, stages=stages, user_source_preserved=True,
        user_code_preserved_by_regeneration=True, model_test='PASS', negative_control='EXPECTED_FAILURE',
        simulator_build='PASS', gui_launch='NOT_RUN', gui_interaction='NOT_RUN',
        target_build='NOT_RUN', hardware='NOT_RUN', source_unchanged=True,
        simulator_sha256=digest(project/'build/bin/simulator.exe'))
    (build/'results.json').write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8')
    print('PASS: source configuration, generated interface, user adaptation, model tests, simulator build')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print('FAIL: ' + str(error), file=sys.stderr)
        sys.exit(1)
