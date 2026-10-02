#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
"""Real Windows process-tree checks; no AMD executables or hardware.

Interruption is injected only into the real owned Python launcher's wait.
Children, held handles, taskkill and cleanup waits are real. Optional
EPW_PROCESS_TREE_EVIDENCE names a new directory for retained local evidence.
"""
import ctypes
from ctypes import wintypes
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1]/'scripts/run.py'
SPEC = importlib.util.spec_from_file_location('soc_process_tree_runner', SCRIPT)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)

TREE_SCRIPT = '''import os, pathlib, subprocess, sys, time
level=int(sys.argv[1])
root=pathlib.Path(sys.argv[2])
(root/(str(level)+'.pid')).write_text(str(os.getpid()))
if level < 2:
    subprocess.Popen([sys.executable, __file__, str(level+1), str(root)],
                     stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
print('tree level '+str(level)+' ready', flush=True)
time.sleep(60)
'''


@unittest.skipUnless(os.name == 'nt', 'Real taskkill process-tree checks require Windows')
class RealProcessTreeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='epw-soc-tree-')
        self.root = Path(self.temp.name)
        self.child_script = self.root/'tree.py'
        self.child_script.write_text(TREE_SCRIPT, encoding='utf-8')
        self.handles = []
        self.pids = []
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
        self.kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        self.independent = subprocess.Popen(
            [sys.executable, '-c', 'import time; time.sleep(60)'],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            startupinfo=runner.helpers.hidden_startup(), creationflags=subprocess.CREATE_NEW_CONSOLE)

    def tearDown(self):
        # Open handles identify these exact test processes even if PIDs get reused.
        for handle in self.handles:
            if self.kernel.WaitForSingleObject(handle, 0) == 258:
                self.kernel.TerminateProcess(handle, 1)
                self.kernel.WaitForSingleObject(handle, 5000)
            self.kernel.CloseHandle(handle)
        if self.independent.poll() is None:
            self.independent.kill()
        self.independent.wait(timeout=5)
        self.temp.cleanup()

    def hold_tree_handles(self, parent):
        deadline = time.monotonic()+8
        for level in range(3):
            path = self.root/(str(level)+'.pid')
            while time.monotonic() < deadline:
                if path.is_file() and path.read_text().strip():
                    break
                time.sleep(0.02)
            self.assertTrue(path.is_file(), 'Test descendant did not report its identity')
            pid = int(path.read_text())
            if level == 0:
                self.assertEqual(pid, parent.pid)
            handle = self.kernel.OpenProcess(0x00100000 | 0x0001, False, pid)
            self.assertTrue(handle, 'Could not hold the known test descendant handle')
            self.handles.append(handle)
            self.pids.append(pid)

    def exercise(self, scenario, interrupted=False, fail_final_save=False):
        report = self.root/'report'
        original_wait = subprocess.Popen.wait
        original_save = runner.helpers.write_json
        armed = [True]

        def wait_owned(process, timeout=None):
            if armed[0]:
                armed[0] = False
                self.hold_tree_handles(process)
                if interrupted:
                    raise KeyboardInterrupt('Controlled interruption of real test tree')
            return original_wait(process, timeout=timeout)

        def save(path, record, *args, **kwargs):
            if fail_final_save and record.get('phase') == 'finished':
                raise OSError('Controlled final record write failure')
            return original_save(path, record, *args, **kwargs)

        with mock.patch.object(subprocess.Popen, 'wait', wait_owned), \
             mock.patch.object(runner.helpers, 'write_json', save):
            if fail_final_save:
                with self.assertRaisesRegex(OSError, 'final record write failure'):
                    runner.native(sys.executable, [self.child_script, '0', self.root],
                                  self.root, report, 0.2)
            else:
                returned = runner.native(sys.executable, [self.child_script, '0', self.root],
                                         self.root, report, 0.2)

        record = json.loads((report/'result.json').read_text())
        if fail_final_save:
            self.assertEqual(record['status'], 'running', 'Unconfirmed saved state must not claim success')
            self.assertEqual(record['phase'], 'wait')
        else:
            self.assertEqual(record, returned)
            self.assertEqual(record['status'], 'fail')
            self.assertEqual(record['failure_phase'], 'wait')
            self.assertEqual(record['failure_type'], 'KeyboardInterrupt' if interrupted else 'TimeoutExpired')
            self.assertEqual(record['interrupted'], interrupted)
            self.assertEqual(record['timed_out'], not interrupted)
            self.assertEqual(record['cleanup']['pid'], self.pids[0])
            self.assertTrue(record['cleanup']['complete'])
            self.assertEqual(record['cleanup']['taskkill_returncode'], 0)
            self.assertTrue(record['process_cleanup_complete'])
            self.assertIsNotNone(record['returncode'])
        self.assertEqual(record['pid'], self.pids[0])
        self.assertIn('tree level 2 ready', (report/'stdout.log').read_text())
        for handle in self.handles:
            self.assertEqual(self.kernel.WaitForSingleObject(handle, 1000), 0,
                             'A held owned descendant survived cleanup')
        self.assertIsNone(self.independent.poll(), 'Independent same-executable process was affected')

        evidence = os.environ.get('EPW_PROCESS_TREE_EVIDENCE')
        if evidence:
            destination = Path(evidence)/scenario
            destination.mkdir(parents=True, exist_ok=False)
            shutil.copy2(report/'stdout.log', destination/'stdout.log')
            shutil.copy2(report/'result.json', destination/'native-result.json')
            (destination/'observation.json').write_text(json.dumps({
                'scenario': scenario, 'result': 'PASS', 'python': sys.version,
                'optimized': bool(sys.flags.optimize), 'runner_sha256': runner.helpers.sha(SCRIPT),
                'shared_helper_sha256': runner.helpers.sha(runner.UTILITY),
                'test_sha256': runner.helpers.sha(Path(__file__)),
                'owned_pids': self.pids, 'owned_handle_exit_checks': 'all signaled',
                'independent_same_executable_alive': True,
                'interruption_injected': interrupted, 'final_save_failure_injected': fail_final_save,
                'vendor_processes': 'NOT_RUN', 'hardware': 'NOT_RUN'
            }, indent=2)+'\n', encoding='utf-8')

    def test_timeout_cleans_real_tree_and_preserves_independent_python(self):
        self.exercise('timeout')

    def test_controlled_interrupt_cleans_real_tree_and_preserves_independent_python(self):
        self.exercise('interrupt', interrupted=True)

    def test_final_save_failure_keeps_unconfirmed_state_after_real_tree_cleanup(self):
        self.exercise('final-save-failure', interrupted=True, fail_final_save=True)


if __name__ == '__main__':
    unittest.main()
