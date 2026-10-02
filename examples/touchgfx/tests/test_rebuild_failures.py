#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
"""Host-only failure tests: no TouchGFX installation or GUI is invoked."""
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
spec = importlib.util.spec_from_file_location('touchgfx_rebuild', SCRIPT)
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
                self.trial.run(command, self.root, self.root/'child.log')
        self.trial.checkpoint()
        result = json.loads((self.root/'results.json').read_text(encoding='utf-8'))
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['stages'][0]['status'], 'PASS')
        self.assertEqual(result['stages'][2]['status'], 'NOT_RUN')
        return result['stages'][1]

    def test_launch_failure_keeps_null_code_and_log(self):
        stage = self.run_failure([str(self.root/'nonexistent.exe')], OSError)
        self.assertIsNone(stage['returncode'])
        self.assertEqual(stage['failure']['kind'], 'launch')
        self.assertTrue((self.root/'child.log').exists())

    def test_native_nonzero_is_preserved_with_streamed_output(self):
        stage = self.run_failure([sys.executable, '-c', 'print("native diagnostic", flush=True); raise SystemExit(7)'])
        self.assertEqual(stage['returncode'], 7)
        self.assertIn('native diagnostic', (self.root/'child.log').read_text())

    def test_timeout_kills_only_the_owned_live_process(self):
        self.trial.timeout = 0.15
        stage = self.run_failure([sys.executable, '-c', 'import time; print("started", flush=True); time.sleep(30)'], subprocess.TimeoutExpired)
        self.assertEqual(stage['status'], 'TIMEOUT')
        self.assertEqual(stage['failure']['kind'], 'timeout')
        self.assertIsNotNone(stage['returncode'])
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
        self.assertEqual(stage['returncode'], -9)

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
        self.assertEqual(stage['returncode'], -9)
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
        for name in ('designer/tgfx.exe', 'env/MinGW/bin/g++.exe',
                     'app/packages/BlankUI-2.0.0.tpa', 'app/packages/Simulator-2.0.0.tpa'):
            path = install/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        return ['--touchgfx-root', str(install), '--build-root', str(self.root/'build')]

    @unittest.skipUnless(os.name == 'nt', 'Windows production entry point')
    def test_zero_exit_without_created_products_fails_production_postcheck(self):
        def native(trial, command, cwd, log, expected=0):
            trial.current['returncode'] = 0
            trial.phase = 'postcheck'
            return '4.26.1' if command[1] == 'version' else ''
        with mock.patch.object(rebuild.Trial, 'run', native), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(rebuild.main(self.fake_install()), 1)
        result = json.loads((self.root/'build/results.json').read_text())
        stage = next(s for s in result['stages'] if s['name'] == 'create-local')
        self.assertEqual(stage['status'], 'FAIL')
        self.assertEqual(stage['returncode'], 0)
        self.assertEqual(result['stages'][3]['status'], 'NOT_RUN')

    @unittest.skipUnless(os.name == 'nt', 'Windows production entry point')
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

    def test_expected_negative_requires_startup_diagnostic(self):
        rebuild.validate_model_negative('FAIL: startup\n')
        for output in ('FAIL: partial period\n', 'unexpected exception\n', 'prefix FAIL: startup suffix\n'):
            with self.subTest(output=output), self.assertRaises(RuntimeError):
                rebuild.validate_model_negative(output)

    def test_validation_survives_optimized_python(self):
        code = ('import runpy; m=runpy.run_path(' + repr(str(SCRIPT)) + '); '
                'm["validate_model_negative"]("FAIL: partial period")')
        proc = subprocess.run([sys.executable, '-B', '-O', '-c', code], capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('Expected model startup', proc.stderr)

    def test_invalid_timeout_cli_returns_two(self):
        for value in ('0', '-1', 'nan', 'inf'):
            with self.subTest(value=value):
                proc = subprocess.run([sys.executable, '-B', str(SCRIPT), '--touchgfx-root', str(self.root),
                                       '--build-root', str(self.root/'never-created'), '--timeout', value],
                                      capture_output=True, text=True)
                self.assertEqual(proc.returncode, 2)
        self.assertFalse((self.root/'never-created').exists())


if __name__ == '__main__':
    unittest.main()
