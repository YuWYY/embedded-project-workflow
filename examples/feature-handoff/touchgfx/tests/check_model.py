#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
"""Run the actual original Model/core on the host; never a GUI or board test."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location('touchgfx_project', REPO/'skills/embedded-project-workflow/scripts/touchgfx_project.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def host_environment(cxx, out):
    """Use an explicitly selected host compiler without requiring a GUI SDK."""
    env = os.environ.copy()
    for key in ('CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'LIBRARY_PATH',
                'GCC_EXEC_PREFIX', 'COMPILER_PATH', 'LD_PRELOAD', 'DYLD_INSERT_LIBRARIES',
                'PYTHONPATH', 'PYTHONHOME'):
        env.pop(key, None)
    env.update(TEMP=str(out/'tmp'), TMP=str(out/'tmp'), TMPDIR=str(out/'tmp'), PYTHONUTF8='1')
    env['PATH'] = str(cxx.parent) + os.pathsep + env.get('PATH', '')
    return env


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    compiler = parser.add_mutually_exclusive_group(required=True)
    compiler.add_argument('--touchgfx-root', type=Path, help='Use the existing TouchGFX bundled MinGW compiler')
    compiler.add_argument('--cxx', type=Path, help='Explicit existing g++/clang++ executable; no TouchGFX SDK required')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--with-reset', action='store_true')
    args = parser.parse_args(argv)
    for p in (args.project, args.output): runner.no_links(p)
    project, out = args.project.resolve(), args.output.resolve()
    inputs_roots = [project, REPO]
    if args.touchgfx_root is not None:
        runner.no_links(args.touchgfx_root)
        install = args.touchgfx_root.resolve()
        inputs_roots.append(install)
        cxx = install/'env/MinGW/bin/g++.exe'
        env = runner.environment(install, out)
        compiler_source = 'TOUCHGFX_BUNDLED_COMPILER'
    else:
        # Distribution compiler names commonly point to a versioned executable.
        # Resolving that explicit executable does not redirect project writes.
        cxx = args.cxx.resolve(strict=True)
        env = host_environment(cxx, out)
        compiler_source = 'EXPLICIT_HOST_COMPILER'
    for p in inputs_roots:
        runner.require(not out.is_relative_to(p) and not p.is_relative_to(out), 'Output must be separate from inputs')
    runner.require(not out.exists(), 'Use a new output directory')
    runner.require(cxx.is_file(), 'Existing C++ compiler executable is required')
    source = project/'gui/src/model/Model.cpp'
    core = project/'gui/src/core/epw_stats.c'
    test = Path(__file__).with_name('model_contract.cpp')
    inputs = [source, core, test, Path(__file__).resolve(),
              project/'gui/include/gui/model/Model.hpp',
              project/'gui/include/gui/model/ModelListener.hpp', project/'gui/include/epw_stats.h']
    identity = {str(p):runner.sha(p) for p in inputs}
    out.mkdir(parents=True)
    stages = ['compile','positive'] + (['compile-mutated-model','compile-negative','noop-reset-negative'] if args.with_reset else [])
    journal = runner.Journal(out, stages, 60, env)
    journal.result.update(scope='HOST_MODEL_ONLY', with_reset=args.with_reset, inputs=identity,
                          compiler={'source':compiler_source,'path':str(cxx),'sha256':runner.sha(cxx)},
                          simulator='NOT_RUN', gui_interaction='NOT_RUN', board='NOT_RUN')
    journal.checkpoint()
    try:
        (out/'tmp').mkdir()
        opts = [str(cxx),'-std=c++11','-Wall','-Wextra','-Werror',
                '-DEPW_WITH_RESET='+str(int(args.with_reset)),'-I',str(project/'gui/include')]
        with journal.stage('compile'):
            journal.run(opts+[str(source),str(core),str(test),'-o',str(out/'contract.exe')],out)
        with journal.stage('positive'):
            text = journal.run([str(out/'contract.exe')],out)
            runner.require('model contract PASS' in text,'Missing Model contract completion')
        if args.with_reset:
            noop = out/'noop.cpp'
            noop.write_text('#include <epw_stats.h>\nextern "C" void epw_stats_reset_noop(epw_stats *s) { (void)s; }\n',encoding='utf-8')
            with journal.stage('compile-mutated-model'):
                journal.run(opts+['-Depw_stats_reset=epw_stats_reset_noop','-c',str(source),'-o',str(out/'model-noop.o')],out)
            with journal.stage('compile-negative'):
                journal.run(opts+[str(out/'model-noop.o'),str(core),str(noop),str(test),'-o',str(out/'negative.exe')],out)
            with journal.stage('noop-reset-negative'):
                # This program is supposed to compile and fail its business contract.
                journal.current['expected_returncode'] = 1
                try:
                    journal.run([str(out/'negative.exe')],out)
                except runner.ProjectError:
                    runner.require(journal.current['returncode']==1 and journal.phase=='postcheck',
                                   'Negative failed for a different process reason')
                else:
                    raise runner.ProjectError('No-op Reset unexpectedly passed')
                text = (out/'noop-reset-negative.log').read_text(encoding='utf-8',errors='replace')
                runner.require('s.count==0' in text,'Negative did not reject the non-cleared window')
        runner.require(all(runner.sha(Path(p))==v for p,v in identity.items()),'Model inputs changed during test')
        journal.result['status']='PASS'
        journal.checkpoint()
    except BaseException:
        journal.result['status']='FAIL'
        journal.checkpoint()
        raise
    print(json.dumps({'status':'PASS','scope':'HOST_MODEL_ONLY','reset_negative':args.with_reset}))


if __name__=='__main__':
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as error:
        print(str(error),file=sys.stderr)
        raise SystemExit(1)
