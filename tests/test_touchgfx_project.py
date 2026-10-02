#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
"""Fault and source-boundary tests; run unchanged with python -O as well."""
import argparse
from contextlib import redirect_stdout, redirect_stderr
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'skills/embedded-project-workflow/scripts/touchgfx_project.py'
spec = importlib.util.spec_from_file_location('touchgfx_project',SCRIPT)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tgfx_test_')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project,self.install = self.root/'Project',self.root/'Install'
        self.project.mkdir()
        self.install.mkdir()
        example = ROOT/'examples/feature-handoff/touchgfx'
        for src,dest in [('CounterHandoff.touchgfx','Project.touchgfx'),('application.config','application.config'),('texts.xml','assets/texts/texts.xml')]:
            self.put(dest,(example/src).read_bytes())
        for name in ('designer/tgfx.exe','env/MinGW/bin/g++.exe'):
            path=self.install/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(b'fake-tool')
        self.put('gui/user.cpp',b'original source\n')

    def put(self,name,value):
        path=self.project/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(value)
        return path

    def edit(self,fn):
        path=self.project/'Project.touchgfx'
        config=json.loads(path.read_text())
        fn(config['Application'])
        path.write_text(json.dumps(config))

    def journal(self,timeout=3):
        reports=self.root/'journal'
        reports.mkdir()
        return runner.Journal(reports,['command'],timeout,os.environ.copy())

    def test_inspect_is_read_only_without_child_process(self):
        before=runner.hashes(self.project)
        with patch.object(runner.subprocess,'Popen',side_effect=AssertionError('inspect launched tool')):
            info=runner.inspect_project(self.project,self.install)
        self.assertEqual(info['screens'],['Dashboard','Controls'])
        self.assertEqual(before,runner.hashes(self.project))

    def test_arbitrary_commands_and_external_paths_rejected_before_launch(self):
        for field,value in [('GenerateAssetsCommand','echo injected'),('PostGenerateCommand','cmd /c whoami'),
                            ('CompileSimulatorCommand','make & echo injected'),('UIPath','../escape'),
                            ('TouchGfxPath',str(self.root/'external'))]:
            with self.subTest(field=field):
                old=(self.project/'Project.touchgfx').read_bytes()
                self.edit(lambda app:app.update({field:value}))
                with self.assertRaises(runner.ProjectError):
                    runner.inspect_project(self.project,self.install)
                (self.project/'Project.touchgfx').write_bytes(old)

    def test_json_duplicate_key_rejected(self):
        self.put('Project.touchgfx',b'{"Version":"4.26.1","Version":"4.25.0"}')
        with self.assertRaisesRegex(runner.ProjectError,'Duplicate'):
            runner.inspect_project(self.project,self.install)

    def test_native_makefile_injection_rejected(self):
        self.put('simulator/gcc/Makefile',b'all:\n\techo injected\n')
        with self.assertRaisesRegex(runner.ProjectError,'Makefile'):
            runner.inspect_project(self.project,self.install)

    def test_gcc_configuration_injection_rejected(self):
        self.put('config/gcc/app.mk',b'touchgfx_path := touchgfx\nuser_cflags := $(shell echo injected)\n')
        with self.assertRaises(runner.ProjectError):
            runner.inspect_project(self.project,self.install)

    def test_xml_external_entity_and_font_path_rejected(self):
        for value in (b'<!DOCTYPE a [<!ENTITY x SYSTEM "file:///outside-secret">]><TextDatabase/>',
                      b'<TextDatabase><Typography Font="../escape.ttf"/></TextDatabase>'):
            self.put('assets/texts/texts.xml',value)
            with self.assertRaises(runner.ProjectError):
                runner.inspect_project(self.project,self.install)

    def test_hardlink_external_write_boundary_rejected(self):
        outside=self.root/'external.cpp'
        outside.write_bytes(b'unchanged')
        os.link(outside,self.project/'linked.cpp')
        with self.assertRaisesRegex(runner.ProjectError,'Hard-linked'):
            runner.inspect_project(self.project,self.install)
        self.assertEqual(outside.read_bytes(),b'unchanged')

    def test_user_edit_is_reported_and_never_reverted(self):
        info=runner.inspect_project(self.project,self.install)
        self.put('gui/user.cpp',b'human change')
        self.assertIn('gui/user.cpp',runner.protected_changes(self.project,info['source_hashes']))
        self.assertEqual((self.project/'gui/user.cpp').read_bytes(),b'human change')

    def test_timeout_values_remain_enforced_under_optimization(self):
        for value in ('nan','inf','-1','0','bogus'):
            with self.subTest(value=value),self.assertRaises(argparse.ArgumentTypeError):
                runner.positive_timeout(value)

    def test_real_nonzero_exit_has_streamed_log_and_actual_code(self):
        journal=self.journal()
        with self.assertRaises(runner.ProjectError):
            with journal.stage('command'):
                journal.run([sys.executable,'-c','import sys; print("diagnostic",flush=True); sys.exit(7)'],self.root)
        journal.checkpoint()
        data=json.loads((journal.reports/'results.json').read_text())
        self.assertEqual(data['status'],'FAIL')
        self.assertEqual(data['stages'][0]['returncode'],7)
        self.assertIn('diagnostic',(journal.reports/'command.log').read_text())

    def test_real_large_output_does_not_fill_pipe(self):
        journal=self.journal()
        with journal.stage('command'):
            journal.run([sys.executable,'-c','print("x"*1000000)'],self.root)
        self.assertGreater((journal.reports/'command.log').stat().st_size,1000000)

    def test_launch_failure_journal(self):
        journal=self.journal()
        with self.assertRaises(OSError):
            with journal.stage('command'):
                journal.run([str(self.root/'missing.exe')],self.root)
        journal.checkpoint()
        self.assertEqual(journal.result['failure']['kind'],'launch')
        self.assertIsNone(journal.result['stages'][0]['returncode'])

    def test_real_timeout_cleans_only_owned_live_process(self):
        journal=self.journal(.15)
        with self.assertRaises(subprocess.TimeoutExpired):
            with journal.stage('command'):
                journal.run([sys.executable,'-c','import time; print("started",flush=True); time.sleep(30)'],self.root)
        journal.checkpoint()
        stage=journal.result['stages'][0]
        self.assertEqual(stage['status'],'TIMEOUT')
        self.assertEqual(stage['cleanup']['status'],'COMPLETE')
        self.assertIsNotNone(stage['returncode'])

    def test_already_exited_process_is_not_killed_by_reused_pid(self):
        process=MagicMock(pid=12345)
        process.poll.return_value=0
        with patch.object(runner.subprocess,'run') as killer:
            self.assertEqual(runner.stop_owned_process(process)['status'],'NOT_NEEDED')
        killer.assert_not_called()
        process.kill.assert_not_called()

    def test_atomic_journal_preserves_previous_file_on_replace_failure(self):
        path=self.root/'state.json'
        runner.write_json(path,{'status':'before'})
        with patch.object(runner.os,'replace',side_effect=OSError('injected replace failure')):
            with self.assertRaises(OSError):runner.write_json(path,{'status':'after'})
        self.assertEqual(json.loads(path.read_text())['status'],'before')
        self.assertEqual(list(self.root.glob('state.json.*.tmp')),[])

    def test_unsafe_reports_refused_before_writing(self):
        args=argparse.Namespace(command='generate',project=self.project,touchgfx_root=self.install,
                                reports=self.project/'reports',timeout=1)
        with patch.object(runner.os,'name','nt'),self.assertRaises(runner.ProjectError):
            runner.execute(args)
        self.assertFalse(args.reports.exists())

    def test_environment_drops_make_and_ruby_injection(self):
        with patch.dict(os.environ,{'MAKEFLAGS':'-f evil.mk','RUBYOPT':'-revil','PYTHONPATH':'evil'}):
            env=runner.environment(self.install,self.root)
        for key in ('MAKEFLAGS','RUBYOPT','PYTHONPATH'):
            self.assertNotIn(key,env)

    def test_cross_volume_reports_refused_before_writes_or_tools(self):
        args=argparse.Namespace(command='generate',project=self.project,touchgfx_root=self.install,
                                reports=self.root/'other-volume',timeout=1)
        before=runner.hashes(self.project)
        with patch.object(runner, 'volume_id', side_effect=[1,2]), \
             patch.object(runner.subprocess, 'Popen') as process:
            with self.assertRaisesRegex(runner.ProjectError, 'same volume'):
                runner.execute(args)
        process.assert_not_called()
        self.assertFalse(args.reports.exists())
        self.assertEqual(before,runner.hashes(self.project))

    def test_fake_success_without_fresh_products_cannot_pass(self):
        self.put('build/bin/simulator.exe',b'stale')
        args=argparse.Namespace(command='build',project=self.project,touchgfx_root=self.install,
                                reports=self.root/'reports',timeout=1)
        def fake_run(journal,command,cwd):
            journal.current['returncode']=0
            return '4.26.1' if command[1]=='version' else 'Generation & Update complete\nCompilation Succeded'
        with patch.object(runner.Journal,'run',fake_run),redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            self.assertEqual(runner.execute(args),1)
        report=json.loads((args.reports/'results.json').read_text())
        self.assertEqual(report['status'],'FAIL')
        self.assertEqual(report['stages'][3]['status'],'NOT_RUN')
        self.assertEqual((args.reports/'previous-build/bin/simulator.exe').read_bytes(),b'stale')
        self.assertFalse((self.project/'build/bin/simulator.exe').exists())


if __name__=='__main__':
    unittest.main()
