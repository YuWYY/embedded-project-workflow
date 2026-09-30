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

    def invoke(self, generated=None, tool_returncode=1):
        def fake_tool(*args, **kwargs):
            self.assertEqual(Path(kwargs['cwd']), self.work)
            self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)
            self.assertEqual(kwargs['creationflags'], 16)
            self.assertEqual(kwargs['startupinfo'].dwFlags, 1)
            self.assertEqual(kwargs['startupinfo'].wShowWindow, 0)
            for relative in runner.EVIDENCE_FILES:
                self.assertFalse((self.work / relative).exists(), relative)
            for relative, text in (generated or {}).items():
                target = self.work / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
            return SimpleNamespace(returncode=tool_returncode)

        argv = ['run_clock.py', '--vivado', str(self.executable), '--build-root',
                str(self.root), '--stage', 'current', '--regenerate']
        with patch.object(runner, '__file__', str(self.package / 'scripts/run_clock.py')), \
                patch.object(runner, 'os', SimpleNamespace(name='nt')), \
                patch.object(subprocess, 'CREATE_NEW_CONSOLE', 16, create=True), \
                patch.object(subprocess, 'STARTF_USESHOWWINDOW', 1, create=True), \
                patch.object(subprocess, 'SW_HIDE', 0, create=True), \
                patch.object(subprocess, 'STARTUPINFO',
                             side_effect=lambda: SimpleNamespace(dwFlags=0, wShowWindow=1), create=True), \
                patch.object(runner.subprocess, 'run', side_effect=fake_tool) as tool, \
                patch.object(sys, 'argv', argv), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
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
        self.assertEqual(json.loads((self.root / runner.OWNER_FILE).read_text())['last_successful_stage'], 'current')
        self.assertEqual(bytes_in(self.previous), self.prior_snapshot)

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
