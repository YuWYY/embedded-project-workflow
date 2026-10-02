"""Runner file/state tests. The vendor subprocess is mocked; no Vivado coverage.

Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT
"""

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/run_clock.py'
SPEC = importlib.util.spec_from_file_location('controlled_clock_runner', SCRIPT)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def bytes_in(directory):
    return {p.relative_to(directory).as_posix(): p.read_bytes()
            for p in directory.rglob('*') if p.is_file()}


class RunnerEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='controlled-clock-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.package = self.base / 'example/controlled-project'
        (self.package / 'scripts').mkdir(parents=True)
        (self.package / 'config').mkdir()
        shutil.copy2(SCRIPT, self.package / 'scripts/run_clock.py')
        (self.package / 'scripts/clock.tcl').write_text('# Vendor call is mocked.\n')
        (self.package / 'config/clock-config.tcl').write_text('set output_mhz 125\n')
        shared = self.package.parent / 'sources'
        shared.mkdir()
        for name in runner.CLOCK_SOURCES:
            (shared / name).write_text('// Synthetic runner fixture, not HDL validation.\n')
        self.executable = self.base / 'vivado.bat'
        self.executable.write_text('Never executed.\n')
        self.root = self.base / 'build'
        self.work = self.root / 'clock'
        (self.work / 'p').mkdir(parents=True)
        (self.work / 'p/c.xpr').write_text('Synthetic ownership fixture.\n')
        self.previous = self.root / 'stage-results/previous'
        self.previous.mkdir(parents=True)
        shutil.copy2(self.package / 'config/clock-config.tcl', self.previous / 'clock-config.tcl')
        self.owner = {'format': runner.OWNER_FORMAT, 'version': 1,
                      'owner_id': 'a' * 32, 'last_successful_stage': 'previous'}
        runner.write_json(self.root / runner.OWNER_FILE, self.owner)
        runner.write_json(self.previous / 'result.json', {
            'stage': 'previous', 'owner_id': self.owner['owner_id'],
            'status': 'pass', 'returncode': 0, 'build_root': str(self.root),
            'source_sha256': {'config/clock-config.tcl': runner.sha(self.previous / 'clock-config.tcl')},
            'completion': 'CLOCK_COMPLETE mhz=125 synth_status=synth_design Complete!',
            'simulation': 'PASS samples=400 resets=2 expected_ns=8.000',
        })
        self.old = {}
        for relative in runner.EVIDENCE_FILES:
            path = self.work / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            data = ('previous stage: ' + relative + '\n').encode()
            path.write_bytes(data)
            (self.previous / path.name).write_bytes(data)
            self.old[relative] = data
        # Unrelated user report and source are deliberately outside the evidence list.
        (self.work / 'user-notes.rpt').write_text('Keep user notes.\n')
        (self.work / 'user.sv').write_text('// Keep user source.\n')
        self.prior_snapshot = bytes_in(self.previous)

    def invoke(self, generated=None, tool_returncode=1, launch_error=None,
               wait_error=None, cleanup_returncode=0, cleanup_timeout=False,
               remains_live=False, extra_args=None):
        self.wait_timeouts = []
        self.cleanup_commands = []
        self.helper_wait_timeouts = []
        self.helper_killed = False
        process = SimpleNamespace(pid=43210, returncode=None)

        def wait(timeout):
            self.wait_timeouts.append(timeout)
            if len(self.wait_timeouts) == 1 and wait_error is not None:
                raise wait_error
            if remains_live:
                raise subprocess.TimeoutExpired('owned fake', timeout)
            if process.returncode is None:
                process.returncode = tool_returncode
            return process.returncode

        process.wait = wait
        process.poll = lambda: process.returncode
        self.vendor = process

        def fake_tool(command, **kwargs):
            if '/PID' in command:
                self.cleanup_commands.append(command)
                self.assertEqual(command[1:], ['/PID', '43210', '/T', '/F'])
                self.assertTrue(Path(command[0]).is_absolute())
                self.assertEqual(Path(command[0]).name, 'taskkill.exe')
                self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)
                self.assertEqual(kwargs['creationflags'], 16)
                helper = SimpleNamespace(returncode=None)

                def helper_wait(timeout):
                    self.helper_wait_timeouts.append(timeout)
                    if cleanup_timeout and timeout == 10:
                        raise subprocess.TimeoutExpired(command, timeout)
                    helper.returncode = cleanup_returncode
                    if cleanup_returncode == 0 and not remains_live:
                        process.returncode = -9
                    return helper.returncode

                def kill_helper():
                    self.helper_killed = True

                helper.wait = helper_wait
                helper.kill = kill_helper
                helper.poll = lambda: helper.returncode
                return helper
            self.assertEqual(Path(kwargs['cwd']), self.work)
            self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)
            self.assertEqual(kwargs['creationflags'], 16)
            self.assertEqual(kwargs['startupinfo'].dwFlags, 1)
            self.assertEqual(kwargs['startupinfo'].wShowWindow, 0)
            for relative in runner.EVIDENCE_FILES:
                self.assertFalse((self.work / relative).exists(), relative)
            self.assertEqual(self.record()['phase'], 'launch')
            self.assertEqual(self.record()['status'], 'running')
            self.assertIsNone(self.record()['returncode'])
            if launch_error is not None:
                raise launch_error
            kwargs['stdout'].write('Vendor output before exit.\n')
            kwargs['stdout'].flush()
            for relative, text in (generated or {}).items():
                target = self.work / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
            return process

        argv = ['run_clock.py', '--vivado', str(self.executable), '--build-root',
                str(self.root), '--stage', 'current', '--regenerate', *(extra_args or [])]
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()
        with patch.object(runner, '__file__', str(self.package / 'scripts/run_clock.py')), \
                patch.object(runner, 'os', SimpleNamespace(name='nt', environ=os.environ)), \
                patch.object(subprocess, 'CREATE_NEW_CONSOLE', 16, create=True), \
                patch.object(subprocess, 'STARTF_USESHOWWINDOW', 1, create=True), \
                patch.object(subprocess, 'SW_HIDE', 0, create=True), \
                patch.object(subprocess, 'STARTUPINFO',
                             side_effect=lambda: SimpleNamespace(dwFlags=0, wShowWindow=1), create=True), \
                patch.object(runner.subprocess, 'Popen', side_effect=fake_tool) as tool, \
                patch.object(sys, 'argv', argv), \
                redirect_stdout(self.stdout), redirect_stderr(self.stderr):
            self.last_tool = tool
            code = runner.main()
        return code, tool.call_count

    def record(self):
        return json.loads((self.root / 'stage-results/current/result.json').read_text())

    def remove_fixture_link(self, link):
        # Remove only this test's link, never recurse into its target.
        self.assertTrue(link.parent.resolve().is_relative_to(self.base))
        if link.is_symlink():
            link.unlink()
        elif getattr(link, 'is_junction', lambda: False)():
            os.rmdir(link)

    def directory_link(self, link, target):
        self.assertTrue(link.parent.resolve().is_relative_to(self.base))
        self.assertTrue(target.resolve().is_relative_to(self.base))
        if os.name == 'nt':
            import _winapi
            _winapi.CreateJunction(str(target), str(link))
        else:
            link.symlink_to(target, target_is_directory=True)
        self.addCleanup(self.remove_fixture_link, link)

    def file_link(self, link, target):
        self.assertTrue(link.parent.resolve().is_relative_to(self.base))
        self.assertTrue(target.resolve().is_relative_to(self.base))
        try:
            link.symlink_to(target)
        except OSError as error:
            if os.name == 'nt' and getattr(error, 'winerror', None) == 1314:
                self.skipTest('Windows file-symlink privilege unavailable; directory junction cases still run')
            raise
        self.addCleanup(self.remove_fixture_link, link)

    def assert_main_rejects_external_link(self, external):
        before = bytes_in(self.root)
        outside_before = bytes_in(external)
        with self.assertRaises(SystemExit) as stopped:
            self.invoke()
        self.assertEqual(stopped.exception.code, 2)
        self.last_tool.assert_not_called()
        self.assertEqual(bytes_in(self.root), before)
        self.assertEqual(bytes_in(external), outside_before)
        self.assertFalse((self.root / 'stage-results/current').exists())

    def test_failed_stage_archives_old_artifacts_without_collecting_them(self):
        code, calls = self.invoke()
        self.assertEqual((code, calls), (1, 1))
        stage = self.root / 'stage-results/current'
        self.assertEqual(self.record()['status'], 'fail')
        self.assertEqual(self.record()['failure_type'], 'nonzero_exit')
        self.assertEqual(self.record()['collected_current_artifacts'], [])
        self.assertEqual(set(self.record()['archived_preexisting_artifacts']), set(self.old))
        for relative, data in self.old.items():
            self.assertEqual((stage / 'preexisting-artifacts' / relative).read_bytes(), data)
            self.assertFalse((stage / Path(relative).name).exists(), relative)
        self.assertEqual(bytes_in(self.previous), self.prior_snapshot)
        self.assertEqual(json.loads((self.root / runner.OWNER_FILE).read_text()), self.owner)
        self.assertEqual((self.work / 'user-notes.rpt').read_text(), 'Keep user notes.\n')
        self.assertEqual((self.work / 'user.sv').read_text(), '// Keep user source.\n')
        self.assertFalse((stage / 'user-notes.rpt').exists())

    def test_current_reports_are_collected_even_when_tool_fails(self):
        new = {'clocks.rpt': 'Current partial clock report.\n',
               'ip_properties.txt': 'Current IP parameters.\n',
               'p/c.sim/sim_1/behav/xsim/simulate.log': 'Current simulation failed.\n'}
        self.assertEqual(self.invoke(new), (1, 1))
        stage = self.root / 'stage-results/current'
        self.assertEqual(set(self.record()['collected_current_artifacts']), set(new))
        for relative, data in new.items():
            self.assertEqual((stage / Path(relative).name).read_text(), data)
            self.assertEqual((stage / 'preexisting-artifacts' / relative).read_bytes(), self.old[relative])
        self.assertEqual(bytes_in(self.previous), self.prior_snapshot)

    def test_old_frequency_results_are_rejected_after_zero_tool_exit(self):
        generated = {'completed.txt': 'CLOCK_COMPLETE mhz=100 synth_status=synth_design Complete!\n',
                     'p/c.sim/sim_1/behav/xsim/clock_result.txt': 'PASS samples=400 resets=2 expected_ns=10.000\n'}
        self.assertEqual(self.invoke(generated, 0), (1, 1))
        self.assertEqual(self.record()['status'], 'fail')
        self.assertEqual(self.record()['failure_type'], 'evidence_mismatch')
        self.assertEqual(json.loads((self.root / runner.OWNER_FILE).read_text()), self.owner)

    def test_missing_completion_is_rejected_after_zero_tool_exit(self):
        generated = {'p/c.sim/sim_1/behav/xsim/clock_result.txt': 'PASS samples=400 resets=2 expected_ns=8.000\n'}
        self.assertEqual(self.invoke(generated, 0), (1, 1))
        self.assertEqual(self.record()['completion'], '')
        self.assertEqual(self.record()['status'], 'fail')

    def test_current_matching_results_can_complete_stage(self):
        generated = {'completed.txt': 'CLOCK_COMPLETE mhz=125 synth_status=synth_design Complete!\n',
                     'p/c.sim/sim_1/behav/xsim/clock_result.txt': 'PASS samples=400 resets=2 expected_ns=8.000\n'}
        self.assertEqual(self.invoke(generated, 0), (0, 1))
        self.assertEqual(self.record()['status'], 'pass')
        self.assertIsNone(self.record()['failure_type'])
        self.assertEqual(json.loads((self.root / runner.OWNER_FILE).read_text())['last_successful_stage'], 'current')
        self.assertEqual(bytes_in(self.previous), self.prior_snapshot)

    def good_results(self):
        return {'completed.txt': 'CLOCK_COMPLETE mhz=125 synth_status=synth_design Complete!\n',
                'p/c.sim/sim_1/behav/xsim/clock_result.txt':
                    'PASS samples=400 resets=2 expected_ns=8.000\n'}

    def assert_owner_unchanged(self):
        self.assertEqual(json.loads((self.root / runner.OWNER_FILE).read_text()), self.owner)
        self.assertEqual(bytes_in(self.previous), self.prior_snapshot)

    def test_launch_error_has_null_actual_returncode(self):
        self.assertEqual(self.invoke(launch_error=OSError('cannot start')), (1, 1))
        result = self.record()
        self.assertEqual(result['failure_phase'], 'launch')
        self.assertEqual(result['failure_type'], 'launch_error')
        self.assertIsNone(result['returncode'])
        self.assertIsNone(result['pid'])
        self.assertEqual(result['collected_current_artifacts'], [])
        self.assertIn('cannot start', '\n'.join(result['diagnostics']))
        self.assert_owner_unchanged()

    def test_timeout_kills_only_owned_live_pid_and_collects_partial_artifacts(self):
        generated = {'clocks.rpt': 'Current report before timeout.\n'}
        self.assertEqual(self.invoke(generated, wait_error=subprocess.TimeoutExpired('Vivado', 0.5),
                                     extra_args=['--timeout', '0.5']), (1, 2))
        result = self.record()
        self.assertTrue(result['timed_out'])
        self.assertEqual(result['failure_type'], 'timeout')
        self.assertEqual(result['returncode'], -9)
        self.assertTrue(result['cleanup']['complete'])
        self.assertEqual(self.wait_timeouts, [0.5, 5])
        self.assertEqual(self.helper_wait_timeouts, [10])
        self.assertEqual(result['collected_current_artifacts'], ['clocks.rpt'])
        self.assertEqual((self.root / 'stage-results/current/stdout.log').read_text(),
                         'Vendor output before exit.\n')
        self.assert_owner_unchanged()

    def test_interrupt_returns_130_and_saves_terminal_failure(self):
        self.assertEqual(self.invoke(self.good_results(), 0, wait_error=KeyboardInterrupt()), (130, 2))
        result = self.record()
        self.assertEqual(result['status'], 'fail')
        self.assertTrue(result['interrupted'])
        self.assertEqual(result['failure_type'], 'interrupted')
        self.assertEqual(result['failure_phase'], 'running')
        self.assertTrue(result['cleanup']['complete'])
        self.assertEqual(self.wait_timeouts, [900.0, 5])
        self.assert_owner_unchanged()

    def test_cleanup_failure_does_not_invent_process_exit(self):
        self.assertEqual(self.invoke(wait_error=subprocess.TimeoutExpired('Vivado', 900),
                                     cleanup_returncode=1, remains_live=True), (1, 2))
        result = self.record()
        self.assertIsNone(result['returncode'])
        self.assertFalse(result['cleanup']['complete'])
        self.assertEqual(result['cleanup']['taskkill_returncode'], 1)
        self.assertTrue(result['cleanup']['diagnostics'])
        self.assert_owner_unchanged()

    def test_cleanup_helper_timeout_is_bounded_and_reported(self):
        self.assertEqual(self.invoke(wait_error=KeyboardInterrupt(), cleanup_timeout=True,
                                     remains_live=True), (130, 2))
        self.assertTrue(self.helper_killed)
        self.assertEqual(self.helper_wait_timeouts, [10, 0])
        self.assertEqual(self.wait_timeouts, [900.0, 5])
        self.assertFalse(self.record()['cleanup']['complete'])

    def test_exited_launcher_is_never_taskkilled(self):
        process = SimpleNamespace(pid=43210, returncode=7, poll=lambda: 7)
        with patch.object(runner.subprocess, 'Popen') as launch:
            result = runner.cleanup_owned_process(process)
        launch.assert_not_called()
        self.assertFalse(result['attempted'])
        self.assertFalse(result['complete'])
        self.assertIn('unknown', result['diagnostics'][0])

    def test_missing_systemroot_reports_incomplete_cleanup_without_path_search(self):
        process = SimpleNamespace(pid=43210, returncode=None, poll=lambda: None,
                                  wait=lambda timeout: None)
        with patch.object(runner, 'os', SimpleNamespace(name='nt', environ={})), \
                patch.object(runner.subprocess, 'Popen') as launch:
            result = runner.cleanup_owned_process(process)
        launch.assert_not_called()
        self.assertFalse(result['attempted'])
        self.assertFalse(result['complete'])
        self.assertIn('SystemRoot', result['diagnostics'][0])

    def test_source_copy_error_has_record_before_archive_or_launch(self):
        real_copy = shutil.copy2

        def fail_one(source, destination, *args, **kwargs):
            if Path(destination) == self.root / 'sources/clock_top.sv':
                self.assertEqual(self.record()['phase'], 'copy_sources')
                raise OSError('copy denied')
            return real_copy(source, destination, *args, **kwargs)

        with patch.object(runner.shutil, 'copy2', side_effect=fail_one):
            self.assertEqual(self.invoke(), (1, 0))
        result = self.record()
        self.assertEqual(result['failure_phase'], 'copy_sources')
        self.assertEqual(result['failure_type'], 'io_error')
        self.assertIsNone(result['returncode'])
        self.assertEqual(result['collected_current_artifacts'], [])
        for relative, data in self.old.items():
            self.assertEqual((self.work / relative).read_bytes(), data)
        self.assert_owner_unchanged()

    def test_partial_archive_error_records_moves_without_relabeling_old_evidence(self):
        real_replace = Path.replace

        def fail_archive(source, destination):
            if 'preexisting-artifacts' in Path(destination).parts and Path(destination).name == 'clocks.rpt':
                raise OSError('archive denied')
            return real_replace(source, destination)

        with patch.object(Path, 'replace', fail_archive):
            self.assertEqual(self.invoke(), (1, 0))
        result = self.record()
        self.assertEqual(result['failure_phase'], 'archive_preexisting_artifacts')
        self.assertEqual(result['archived_preexisting_artifacts'], ['utilization.rpt'])
        self.assertEqual(result['collected_current_artifacts'], [])
        self.assertEqual((self.work / 'clocks.rpt').read_bytes(), self.old['clocks.rpt'])
        self.assert_owner_unchanged()

    def test_collection_failure_still_collects_other_available_artifacts(self):
        real_copy = shutil.copy2

        def fail_report(source, destination, *args, **kwargs):
            if Path(destination) == self.root / 'stage-results/current/clocks.rpt':
                raise OSError('report copy denied')
            return real_copy(source, destination, *args, **kwargs)

        generated = dict(self.good_results(), **{'utilization.rpt': 'Current utilization.\n',
                                                 'clocks.rpt': 'Current clocks.\n',
                                                 'timing_synth.rpt': 'Current timing.\n'})
        with patch.object(runner.shutil, 'copy2', side_effect=fail_report):
            self.assertEqual(self.invoke(generated, 0), (1, 1))
        result = self.record()
        self.assertEqual(result['returncode'], 0)
        self.assertEqual(result['failure_phase'], 'collect_current_artifacts')
        self.assertEqual(set(result['collected_current_artifacts']), set(generated) - {'clocks.rpt'})
        self.assert_owner_unchanged()

    def test_first_checkpoint_failure_prevents_all_copy_archive_and_launch(self):
        real_write = runner.write_json

        def fail_initial(path, record, root=None):
            if record.get('phase') == 'initialize':
                raise OSError('first checkpoint denied')
            return real_write(path, record, root)

        with patch.object(runner, 'write_json', side_effect=fail_initial):
            self.assertEqual(self.invoke(), (1, 0))
        self.assertEqual(self.record()['failure_phase'], 'initialize')
        self.assertFalse((self.root / 'sources').exists())
        for relative, data in self.old.items():
            self.assertEqual((self.work / relative).read_bytes(), data)
        self.assert_owner_unchanged()

    def test_final_write_failure_never_reports_pass_or_advances_owner(self):
        real_write = runner.write_json

        def fail_final(path, record, root=None):
            if record.get('phase') == 'complete':
                raise OSError('final checkpoint denied')
            return real_write(path, record, root)

        with patch.object(runner, 'write_json', side_effect=fail_final):
            self.assertEqual(self.invoke(self.good_results(), 0), (1, 1))
        self.assertEqual(self.record()['status'], 'running')
        self.assertIn('Unable to save final result', self.stderr.getvalue())
        self.assertNotIn('"status": "pass"', self.stdout.getvalue())
        self.assert_owner_unchanged()

    def test_saved_result_readback_failure_prevents_owner_advance(self):
        real_save = runner.save_record

        def fail_verification(path, record, root):
            real_save(path, record, root)
            if record.get('status') == 'pass':
                raise OSError('saved result readback failed')

        with patch.object(runner, 'save_record', side_effect=fail_verification):
            self.assertEqual(self.invoke(self.good_results(), 0), (1, 1))
        self.assertEqual(self.record()['status'], 'fail')
        self.assertEqual(self.record()['failure_phase'], 'save_result')
        self.assert_owner_unchanged()

    def test_owner_replace_failure_preserves_previous_marker(self):
        real_replace = Path.replace

        def fail_owner(source, destination):
            if Path(destination) == self.root / runner.OWNER_FILE:
                self.assertEqual(self.record()['status'], 'pass')
                raise OSError('owner replace denied')
            return real_replace(source, destination)

        with patch.object(Path, 'replace', fail_owner):
            self.assertEqual(self.invoke(self.good_results(), 0), (1, 1))
        self.assertEqual(self.record()['status'], 'fail')
        self.assertEqual(self.record()['failure_phase'], 'save_owner')
        self.assertIn('Unable to advance ownership marker', self.stderr.getvalue())
        self.assert_owner_unchanged()

    def test_atomic_replace_failure_preserves_complete_previous_json(self):
        target = self.root / 'atomic.json'
        runner.write_json(target, {'old': 'retained'}, self.root)
        with patch.object(Path, 'replace', side_effect=OSError('replace denied')):
            with self.assertRaisesRegex(OSError, 'replace denied'):
                runner.write_json(target, {'new': 'not committed'}, self.root)
        self.assertEqual(json.loads(target.read_text()), {'old': 'retained'})
        self.assertEqual(list(self.root.glob('.atomic.json.*.tmp')), [])

    def test_atomic_json_rejects_target_outside_root(self):
        target = self.base / 'outside.json'
        with self.assertRaisesRegex(ValueError, 'escapes'):
            runner.write_json(target, {'bad': True}, self.root)
        self.assertFalse(target.exists())

    def test_invalid_timeout_is_rejected_before_writes_or_launch(self):
        before = bytes_in(self.root)
        for value in ('0', '-1', 'nan', 'inf', '-inf', 'nope'):
            with self.subTest(timeout=value):
                with self.assertRaises(SystemExit) as stopped:
                    self.invoke(extra_args=['--timeout=' + value])
                self.assertEqual(stopped.exception.code, 2)
                self.last_tool.assert_not_called()
                self.assertEqual(bytes_in(self.root), before)

    def test_unowned_project_is_rejected_before_tool_or_archive(self):
        (self.root / runner.OWNER_FILE).write_text('{"format": "other-project"}\n')
        before = bytes_in(self.root)
        with self.assertRaises(SystemExit) as stopped:
            self.invoke()
        self.assertEqual(stopped.exception.code, 2)
        self.last_tool.assert_not_called()
        self.assertEqual(bytes_in(self.root), before)

    def test_artifact_destination_outside_root_is_rejected_before_move(self):
        outside = self.base / 'outside-evidence'
        before = bytes_in(self.root)
        with self.assertRaisesRegex(ValueError, 'escapes'):
            runner.archive_preexisting_artifacts(self.root, self.work, outside)
        self.assertEqual(bytes_in(self.root), before)
        self.assertFalse(outside.exists())

    def test_copy_directory_junctions_are_rejected_before_any_write(self):
        for folder in ('scripts', 'config', 'sources'):
            with self.subTest(folder=folder):
                outside = self.base / ('external-' + folder)
                outside.mkdir()
                (outside / 'sentinel.txt').write_text('External original.\n')
                link = self.root / folder
                self.directory_link(link, outside)
                try:
                    self.assert_main_rejects_external_link(outside)
                finally:
                    self.remove_fixture_link(link)

    def test_native_output_junction_is_rejected_before_any_write(self):
        outside = self.base / 'external-native-output'
        outside.mkdir()
        (outside / 'sentinel.txt').write_text('External native output original.\n')
        self.directory_link(self.work / 'p/c.runs', outside)
        self.assert_main_rejects_external_link(outside)

    def test_copied_single_file_links_are_rejected_before_any_write(self):
        for relative in ('scripts/run_clock.py', 'config/clock-config.tcl', 'sources/clock_top.sv'):
            with self.subTest(relative=relative):
                outside = self.base / ('external-file-' + Path(relative).name)
                outside.mkdir()
                target = outside / 'original.txt'
                target.write_text('External file original.\n')
                link = self.root / relative
                link.parent.mkdir(parents=True, exist_ok=True)
                self.file_link(link, target)
                try:
                    self.assert_main_rejects_external_link(outside)
                finally:
                    self.remove_fixture_link(link)

    def test_owner_marker_file_link_is_rejected_before_any_write(self):
        outside = self.base / 'external-owner'
        outside.mkdir()
        target = outside / 'original-owner.json'
        marker = self.root / runner.OWNER_FILE
        target.write_bytes(marker.read_bytes())
        marker.unlink()
        self.file_link(marker, target)
        self.assert_main_rejects_external_link(outside)


if __name__ == '__main__':
    unittest.main(verbosity=2)
