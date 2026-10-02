#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
"""Create this original two-screen fixture in a NEW destination; never take over an existing project.
The existing-project runner remains the only generate/build entry point.
Requires the already installed TouchGFX 4.26.1 BlankUI/Simulator 2.0.0 packages.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--touchgfx-root',type=Path,required=True)
    parser.add_argument('--destination',type=Path,required=True)
    parser.add_argument('--reports',type=Path,required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    script = source.parents[2]/'skills/embedded-project-workflow/scripts/touchgfx_project.py'
    spec = importlib.util.spec_from_file_location('touchgfx_project',script)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    install,destination,reports = args.touchgfx_root.resolve(),args.destination.resolve(),args.reports.resolve()
    for path in (args.destination,args.reports):
        runner.no_links(path)
        runner.require(not path.exists(),'Destination and reports must be new')
    for left,right in ((destination,source),(destination,install),(reports,destination),(reports,install)):
        runner.require(not left.is_relative_to(right) and not right.is_relative_to(left),'Roots must be disjoint')
    reports.mkdir(parents=True)
    (reports/'tmp').mkdir()
    trial = runner.Journal(reports,['tool-version','create-native','install-original-source'],300,runner.environment(install,reports))
    try:
        with trial.stage('tool-version'):
            runner.require(trial.run([install/'designer/tgfx.exe','version'],reports).strip()=='4.26.1','Unsupported version')
        with trial.stage('create-native'):
            trial.run([install/'designer/tgfx.exe','new','--ui='+str(install/'app/packages/BlankUI-2.0.0.tpa'),
                       '--at='+str(install/'app/packages/Simulator-2.0.0.tpa'),'--out='+str(destination.parent),
                       '--prj='+destination.name],reports)
            runner.require((destination/(destination.name+'.touchgfx')).is_file(),'Native creation produced no project')
        with trial.stage('install-original-source'):
            config = json.loads((source/'CounterHandoff.touchgfx').read_text(encoding='utf8'))
            config['Application']['Name'] = destination.name
            (destination/(destination.name+'.touchgfx')).write_text(json.dumps(config,indent=2)+'\n',encoding='utf8')
            shutil.copyfile(source/'application.config',destination/'application.config')
            shutil.copyfile(source/'texts.xml',destination/'assets/texts/texts.xml')
            for path in (source/'user').rglob('*'):
                if path.is_file():
                    target = destination/path.relative_to(source/'user')
                    target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(path,target)
            trial.result['source_package_hashes'] = runner.hashes(source,('__pycache__',))
        trial.result.update(status='PASS',project=str(destination),generation='NOT_RUN',build='NOT_RUN')
        trial.checkpoint()
        print('Prepared original fixture: '+str(destination))
        return 0
    except (Exception,KeyboardInterrupt) as error:
        code = trial.fail(error)
        trial.checkpoint()
        print('FAIL: '+str(error),file=sys.stderr)
        return code


if __name__ == '__main__':
    sys.exit(main())
