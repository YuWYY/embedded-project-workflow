#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
"""Host-only failure tests: no CubeMX, Keil or hardware is invoked."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1]/'rebuild.py'
spec = importlib.util.spec_from_file_location('cubemx_rebuild', SCRIPT)
rebuild = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rebuild)


class FailureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.trial = rebuild.Trial(self.root/'results.json', ('completed', 'current', 'later'), 5, os.environ.copy())
        with self.trial.stage('completed'):
            pass

    def run_failure(self, command, exception=RuntimeError):
        with self.assertRaises(exception):
            with self.trial.stage('current'):
                self.trial.run(command, self.root, self.root/'child.log', expected=0)
        self.trial.checkpoint()
        result = json.loads((self.root/'results.json').read_text(encoding='utf-8'))
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['stages'][0]['status'], 'PASS')
        self.assertEqual(result['stages'][2]['status'], 'NOT_RUN')
        return result['stages'][1]

    def test_launch_failure_keeps_null_code_and_log(self):
        stage = self.run_failure([str(self.root/'nonexistent.exe')], OSError)
        self.assertIsNone(stage['exit_code'])
        self.assertEqual(stage['failure']['kind'], 'launch')
        self.assertTrue((self.root/'child.log').exists())

    def test_native_nonzero_is_preserved_with_streamed_output(self):
        stage = self.run_failure([sys.executable, '-c', 'print("native diagnostic", flush=True); raise SystemExit(7)'])
        self.assertEqual(stage['exit_code'], 7)
        self.assertIn('native diagnostic', (self.root/'child.log').read_text())

    def test_timeout_kills_only_the_owned_live_process(self):
        self.trial.timeout = 0.15
        stage = self.run_failure([sys.executable, '-c', 'import time; print("started", flush=True); time.sleep(30)'], subprocess.TimeoutExpired)
        self.assertEqual(stage['status'], 'TIMEOUT')
        self.assertEqual(stage['failure']['kind'], 'timeout')
        self.assertIsNotNone(stage['exit_code'])
        self.assertEqual(stage['cleanup']['pid'], stage['pid'])
        self.assertIn('started', (self.root/'child.log').read_text())

    def test_interrupt_records_cleanup_and_terminal_state(self):
        proc = mock.Mock(pid=1234)
        proc.wait.side_effect = KeyboardInterrupt
        proc.poll.return_value = -9
        with mock.patch.object(rebuild.subprocess, 'Popen', return_value=proc), \
             mock.patch.object(rebuild, 'stop_owned_process', return_value={'pid': 1234, 'status': 'INCOMPLETE'}) as cleanup:
            stage = self.run_failure(['owned-child'], KeyboardInterrupt)
        cleanup.assert_called_once_with(proc)
        self.assertEqual(stage['status'], 'INTERRUPTED')
        self.assertEqual(stage['exit_code'], -9)

    def test_exited_process_is_never_killed(self):
        proc = mock.Mock(pid=1234)
        proc.poll.return_value = 0
        with mock.patch.object(rebuild.subprocess, 'run') as run:
            self.assertEqual(rebuild.stop_owned_process(proc)['status'], 'NOT_NEEDED')
        run.assert_not_called()
        proc.kill.assert_not_called()

    def test_wait_io_failure_still_cleans_owned_process(self):
        proc = mock.Mock(pid=1234)
        proc.wait.side_effect = OSError('wait handle failure')
        proc.poll.return_value = -9
        with mock.patch.object(rebuild.subprocess, 'Popen', return_value=proc), \
             mock.patch.object(rebuild, 'stop_owned_process', return_value={'pid': 1234, 'status': 'COMPLETE'}) as cleanup:
            stage = self.run_failure(['owned-child'], OSError)
        cleanup.assert_called_once_with(proc)
        self.assertEqual(stage['failure']['kind'], 'io')
        self.assertEqual(stage['failure']['phase'], 'wait')
        self.assertEqual(stage['exit_code'], -9)
        self.assertEqual(stage['cleanup']['status'], 'COMPLETE')

    @unittest.skipUnless(os.name == 'nt', 'Windows taskkill contract')
    def test_taskkill_is_absolute_pid_scoped_bounded_and_hidden(self):
        proc = mock.Mock(pid=3456)
        proc.poll.return_value = None
        proc.wait.return_value = 1
        with mock.patch.object(rebuild.subprocess, 'run', return_value=mock.Mock(returncode=0)) as run:
            cleanup = rebuild.stop_owned_process(proc)
        command = run.call_args.args[0]
        self.assertEqual(Path(command[0]), Path(os.environ['SystemRoot'])/'System32/taskkill.exe')
        self.assertEqual(command[1:], ['/PID', '3456', '/T', '/F'])
        self.assertEqual(run.call_args.kwargs['timeout'], 10)
        self.assertIn('startupinfo', run.call_args.kwargs)
        self.assertLessEqual(proc.wait.call_args.kwargs['timeout'], 5)
        self.assertEqual(cleanup['status'], 'COMPLETE')

    def test_failed_tree_cleanup_is_marked_incomplete_after_direct_kill(self):
        proc = mock.Mock(pid=3456)
        proc.poll.return_value = None
        proc.wait.return_value = 1
        with mock.patch.object(rebuild.subprocess, 'run', side_effect=OSError('taskkill unavailable')):
            cleanup = rebuild.stop_owned_process(proc)
        proc.kill.assert_called_once()
        self.assertEqual(cleanup['status'], 'INCOMPLETE')

    def fake_install(self):
        install = self.root/'install'
        install.mkdir()
        cubemx, uv4 = install/'cubemx.exe', install/'uv4.exe'
        cubemx.touch()
        uv4.touch()
        firmware=install/'firmware'
        firmware.mkdir()
        return ['--cubemx', str(cubemx), '--uv4', str(uv4), '--firmware', str(firmware),
                '--build-root', str(self.root/'build')]

    def test_zero_exit_without_created_products_fails_production_postcheck(self):
        def native(trial, command, cwd, log, expected=None):
            trial.current['exit_code'] = 0
            trial.phase = 'postcheck'
            log.write_text('generation returned without output', encoding='utf-8')
            return trial.current
        with mock.patch.object(rebuild.Trial, 'run', native), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(rebuild.main(self.fake_install()), 1)
        result = json.loads((self.root/'build/reports/result.json').read_text())
        stage = next(s for s in result['stages'] if s['name'] == 'generate_initial')
        self.assertEqual(stage['status'], 'FAIL')
        self.assertEqual(stage['exit_code'], 0)
        self.assertEqual(result['stages'][2]['status'], 'NOT_RUN')

    def test_initial_checkpoint_failure_launches_nothing(self):
        stderr, stdout = io.StringIO(), io.StringIO()
        with mock.patch.object(rebuild, 'write_json', side_effect=OSError('checkpoint denied')), \
             mock.patch.object(rebuild.subprocess, 'Popen') as popen, \
             contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(stdout):
            self.assertEqual(rebuild.main(self.fake_install()), 1)
        popen.assert_not_called()
        self.assertNotIn('PASS:', stdout.getvalue())
        self.assertIn('checkpoint denied', stderr.getvalue())

    def test_atomic_replace_failure_keeps_previous_valid_json(self):
        path = self.root/'results.json'
        before = path.read_bytes()
        with mock.patch.object(rebuild.os, 'replace', side_effect=OSError('replace denied')):
            with self.assertRaises(OSError):
                rebuild.write_json(path, {'status': 'PASS'})
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_final_checkpoint_failure_cannot_report_pass(self):
        for name in ('current', 'later'):
            with self.trial.stage(name):
                pass
        with mock.patch.object(rebuild, 'write_json', side_effect=OSError('final checkpoint denied')):
            with self.assertRaises(OSError) as raised:
                self.trial.finish()
            self.assertEqual(self.trial.fail(raised.exception), 1)
        self.assertEqual(self.trial.results['status'], 'FAIL')
        self.assertEqual(self.trial.results['failure']['phase'], 'checkpoint')

    def test_validation_survives_optimized_python(self):
        code = ('import runpy; m=runpy.run_path(' + repr(str(SCRIPT)) + '); '
                'm["require"](False, "optimized evidence check")')
        proc = subprocess.run([sys.executable, '-B', '-O', '-c', code], capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('optimized evidence check', proc.stderr)

    def test_invalid_timeout_cli_returns_two(self):
        for value in ('0', '-1', 'nan', 'inf'):
            with self.subTest(value=value):
                proc = subprocess.run([sys.executable, '-B', str(SCRIPT), '--cubemx', str(self.root),
                                       '--uv4', str(self.root), '--firmware', str(self.root),
                                       '--build-root', str(self.root/'never-created'), '--timeout', value],
                                      capture_output=True, text=True)
                self.assertEqual(proc.returncode, 2)
        self.assertFalse((self.root/'never-created').exists())

    def keil_fixture(self):
        work=self.root/'keil-work'
        (work/'MDK-ARM').mkdir(parents=True)
        (work/'Core/Src').mkdir(parents=True)
        (work/'MDK-ARM'/('rtos_ownership.uvprojx')).write_text('<Project/>', encoding='utf-8')
        (work/'Core/Src/app_freertos.c').write_text(
            'uint32_t ProducerStack[256];\nuint32_t ConsumerStack[256];\nuint8_t SamplesStorage[8 * 4];\n', encoding='utf-8')
        (work/'MDK-ARM/rtos_ownership.map').write_text(
            'Producer_Entry 0x08000000 Thumb Code 16 rtos_app.o\n'
            'Consumer_Entry 0x08000010 Thumb Code 16 rtos_app.o\n'
            'RtosApp_CheckCreated 0x08000020 Thumb Code 16 rtos_app.o\n'
            'ProducerStack 0x20000000 Data 1024 app_freertos.o\n'
            'ConsumerStack 0x20000400 Data 1024 app_freertos.o\n'
            'SamplesStorage 0x20000800 Data 32 app_freertos.o\n', encoding='utf-8')
        (work/'MDK-ARM/rtos_ownership.axf').write_bytes(b'synthetic map and image fixture')
        args=type('Args', (), {'reports': self.root/'reports', 'uv4': self.root/'uv4.exe', 'trial': self.trial})()
        args.reports.mkdir()
        return work, args

    def fake_keil(self, code, body):
        def native(trial, command, cwd, log, expected=None):
            trial.current['exit_code']=code
            trial.phase='postcheck'
            Path(command[-1]).write_text(body, encoding='utf-8')
            log.write_text('synthetic process log', encoding='utf-8')
            return trial.current
        return native

    def test_keil_exit_one_with_zero_errors_keeps_success_semantics(self):
        work,args=self.keil_fixture()
        with mock.patch.object(rebuild.Trial, 'run', self.fake_keil(1, '0 Error(s), 3 Warning(s)')), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.trial.stage('current'):
                result=rebuild.build(work, 'build', args, {}, negative=False)
        self.assertEqual(result['exit_code'], 1)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['errors'], 0)
        self.assertTrue(result['application_symbols_resolve_to_user_object'])
        self.assertEqual(result['map_static_storage_bytes']['ProducerStack'], 1024)

    def test_keil_exit_zero_without_map_is_not_success(self):
        work,args=self.keil_fixture()
        (work/'MDK-ARM/rtos_ownership.map').unlink()
        with mock.patch.object(rebuild.Trial, 'run', self.fake_keil(0, '0 Error(s), 0 Warning(s)')):
            with self.assertRaises(RuntimeError):
                with self.trial.stage('current'):
                    rebuild.build(work, 'build', args, {}, negative=False)
        self.assertEqual(self.trial.current['exit_code'], 0)
        self.assertEqual(self.trial.current['status'], 'FAIL')

    def test_negative_requires_specific_link_error_and_no_compile_error(self):
        work,args=self.keil_fixture()
        bodies=('1 Error(s), 0 Warning(s)\nError: #20: parser failure',
                '1 Error(s), 0 Warning(s)\nL6218E: Undefined symbol Other_Entry',
                '2 Error(s), 0 Warning(s)\nL6218E: Undefined symbol Consumer_Entry\nerror: unrelated')
        for number,body in enumerate(bodies):
            with self.subTest(body=body), mock.patch.object(rebuild.Trial, 'run', self.fake_keil(2, body)):
                with self.assertRaises(RuntimeError):
                    with self.trial.stage('current'):
                        rebuild.build(work, 'negative-'+str(number), args, {}, negative=True)
        with mock.patch.object(rebuild.Trial, 'run', self.fake_keil(2, '1 Error(s), 0 Warning(s)\nL6218E: Undefined symbol Consumer_Entry')), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.trial.stage('current'):
                result=rebuild.build(work, 'intended-negative', args, {}, negative=True)
        self.assertTrue(result['expected_missing_external_symbol_detected'])

    def test_negative_requires_actual_link_error_exit(self):
        work,args=self.keil_fixture()
        body='1 Error(s), 0 Warning(s)\nL6218E: Undefined symbol Consumer_Entry'
        for number in (0, 1, 3, 255):
            with self.subTest(code=number), mock.patch.object(rebuild.Trial, 'run', self.fake_keil(number, body)):
                with self.assertRaisesRegex(RuntimeError, 'exit code 2'):
                    with self.trial.stage('current'):
                        rebuild.build(work, 'wrong-exit-'+str(number), args, {}, negative=True)

    def test_map_cross_reference_cannot_mask_generated_weak_entry(self):
        work,args=self.keil_fixture()
        path=work/'MDK-ARM/rtos_ownership.map'
        text=path.read_text().replace('Producer_Entry 0x08000000 Thumb Code 16 rtos_app.o',
                                    'Producer_Entry 0x08000000 Thumb Code 16 app_freertos.o')
        path.write_text(text+'Referenced symbol Producer_Entry from rtos_app.o\n', encoding='utf-8')
        with mock.patch.object(rebuild.Trial, 'run', self.fake_keil(0, '0 Error(s), 0 Warning(s)')):
            with self.assertRaisesRegex(RuntimeError, 'MAP definition'):
                with self.trial.stage('current'):
                    rebuild.build(work, 'wrong-owner', args, {}, negative=False)



if __name__ == '__main__':
    unittest.main()
