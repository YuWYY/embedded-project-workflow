#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
"""Real Windows parent/child/grandchild cleanup, without vendor executables.

RUNNER_UNDER_TEST may select another independently distributed rebuild.py.
The interruption test injects KeyboardInterrupt into the owned parent's wait;
all processes, descendant handles, taskkill and cleanup waits are real.
"""
import ctypes
from ctypes import wintypes
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

SCRIPT = Path(os.environ.get('RUNNER_UNDER_TEST', str(Path(__file__).resolve().parents[1]/'rebuild.py')))
spec = importlib.util.spec_from_file_location('rebuild_under_test', SCRIPT)
rebuild = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rebuild)

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


@unittest.skipUnless(os.name == 'nt', 'Real taskkill process-tree validation needs Windows')
class RealProcessTreeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.child_script=self.root/'tree.py'
        self.child_script.write_text(TREE_SCRIPT, encoding='utf-8')
        self.handles=[]
        self.kernel=ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.OpenProcess.argtypes=(wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        self.kernel.OpenProcess.restype=wintypes.HANDLE
        self.kernel.WaitForSingleObject.argtypes=(wintypes.HANDLE,wintypes.DWORD)
        self.kernel.WaitForSingleObject.restype=wintypes.DWORD
        self.kernel.TerminateProcess.argtypes=(wintypes.HANDLE,wintypes.UINT)
        self.kernel.CloseHandle.argtypes=(wintypes.HANDLE,)
        self.independent=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],
                                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL, **rebuild.hidden_process_options())

    def tearDown(self):
        # Handles were opened while each known test child was alive. Never kill a stale PID.
        for handle in self.handles:
            if self.kernel.WaitForSingleObject(handle,0)==258:
                self.kernel.TerminateProcess(handle,1)
                self.kernel.WaitForSingleObject(handle,5000)
            self.kernel.CloseHandle(handle)
        if self.independent.poll() is None:
            self.independent.kill()
        self.independent.wait(timeout=5)
        self.temp.cleanup()

    def hold_tree_handles(self):
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if all((self.root/(str(level)+'.pid')).is_file() for level in range(3)):
                break
            time.sleep(0.02)
        for level in range(3):
            pid=int((self.root/(str(level)+'.pid')).read_text())
            handle=self.kernel.OpenProcess(0x00100000|0x0001,False,pid)
            self.assertTrue(handle, 'Could not hold test descendant process handle')
            self.handles.append(handle)

    def exercise(self, interrupted):
        trial=rebuild.Trial(self.root/'results.json', ('tree', 'later'), 0.2, os.environ.copy())
        original_wait=subprocess.Popen.wait
        armed=[True]

        def wait_owned(proc, timeout=None):
            if armed[0]:
                armed[0]=False
                self.hold_tree_handles()
                if interrupted:
                    raise KeyboardInterrupt()
            return original_wait(proc, timeout=timeout)

        expected=KeyboardInterrupt if interrupted else subprocess.TimeoutExpired
        with mock.patch.object(subprocess.Popen, 'wait', wait_owned):
            with self.assertRaises(expected):
                with trial.stage('tree'):
                    trial.run([sys.executable, str(self.child_script), '0', str(self.root)],
                              self.root, self.root/'tree.log')
        trial.checkpoint()
        result=json.loads((self.root/'results.json').read_text(encoding='utf-8'))
        stage=result['stages'][0]
        self.assertEqual(result['status'],'FAIL')
        self.assertEqual(stage['status'],'INTERRUPTED' if interrupted else 'TIMEOUT')
        self.assertEqual(stage['failure']['stage'],'tree')
        self.assertEqual(stage['failure']['phase'],'wait')
        self.assertEqual(stage['cleanup']['status'],'COMPLETE')
        self.assertEqual(stage['cleanup']['tree_kill_returncode'],0)
        self.assertEqual(result['stages'][1]['status'],'NOT_RUN')
        field='exit_code' if 'exit_code' in stage else 'returncode'
        self.assertIsNotNone(stage[field])
        self.assertIn('tree level 2 ready',(self.root/'tree.log').read_text())
        for handle in self.handles:
            self.assertEqual(self.kernel.WaitForSingleObject(handle,1000),0,
                             'A held test descendant survived cleanup')
        self.assertIsNone(self.independent.poll(),
                          'An independent process using the same executable was affected')

    def test_timeout_reaps_owned_tree_and_leaves_same_executable_alive(self):
        self.exercise(interrupted=False)

    def test_controlled_interrupt_reaps_owned_tree_and_leaves_same_executable_alive(self):
        self.exercise(interrupted=True)


if __name__ == '__main__':
    unittest.main()
