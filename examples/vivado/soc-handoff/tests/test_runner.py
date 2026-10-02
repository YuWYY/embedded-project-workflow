#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
"""Host fault checks with mocked vendor processes; not AMD execution evidence."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
import zipfile
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1]/'scripts/run.py'
spec = importlib.util.spec_from_file_location('soc_case_runner', SCRIPT)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RunnerFaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='epw-soc-runner-')
        self.root = Path(self.temp.name)
        self.fake_executable = self.root/'vendor-install/Vivado/bin/vivado.bat'
        self.fake_executable.parent.mkdir(parents=True)
        self.fake_executable.write_text('REM mocked only\n')

    def tearDown(self):
        self.temp.cleanup()

    def arguments(self, command='prepare'):
        return argparse.Namespace(command=command, output=self.root/'out',
            vivado=self.fake_executable, project=None, timeout=1.0)

    def fake_process(self, error=None, exitcode=0):
        process = SimpleNamespace(pid=123456, returncode=None)
        def wait(timeout):
            if error is not None:
                raise error
            process.returncode = exitcode
            return exitcode
        process.wait = wait
        process.poll = lambda: process.returncode
        def launch(*args, **kwargs):
            kwargs['stdout'].write(b'partial real-file output\n')
            return process
        return process, launch

    def invoke_native(self, launch, cleanup=None):
        with patch.object(runner.subprocess, 'Popen', side_effect=launch), \
             patch.object(runner.helpers, 'hidden_startup', return_value=None), \
             patch.object(runner.subprocess, 'CREATE_NEW_CONSOLE', 16, create=True), \
             patch.object(runner.helpers, 'cleanup_owned_process', side_effect=cleanup) as clean:
            result = runner.native(self.fake_executable, [], self.root/'work',
                                   self.root/'report', 1.0)
        return result, clean

    def test_launch_failure_has_null_tool_exit_and_log(self):
        def launch(*args, **kwargs):
            raise FileNotFoundError('controlled launch failure')
        result, cleanup = self.invoke_native(launch)
        self.assertEqual(result['status'], 'fail')
        self.assertIsNone(result['returncode'])
        self.assertEqual(result['failure_phase'], 'launch')
        self.assertTrue((self.root/'report/stdout.log').exists())
        cleanup.assert_not_called()

    def test_timeout_keeps_output_and_only_cleans_owned_process(self):
        process, launch = self.fake_process(subprocess.TimeoutExpired('vendor', 1))
        def cleanup(owned):
            self.assertIs(owned, process)
            process.returncode = -9
            return {'complete':True, 'pid':process.pid}
        result, clean = self.invoke_native(launch, cleanup)
        self.assertTrue(result['timed_out'])
        self.assertEqual(result['returncode'], -9)
        clean.assert_called_once_with(process)
        self.assertIn(b'partial real-file output', (self.root/'report/stdout.log').read_bytes())

    def test_cleanup_failure_is_not_claimed_complete(self):
        process, launch = self.fake_process(subprocess.TimeoutExpired('vendor', 1))
        result, _ = self.invoke_native(launch, lambda owned: {'complete':False})
        self.assertFalse(result['process_cleanup_complete'])
        self.assertIsNone(result['returncode'])

    def test_timeout_after_launcher_exit_keeps_descendants_unknown(self):
        process, launch = self.fake_process(subprocess.TimeoutExpired('vendor', 1))
        process.poll = lambda: 0
        result, clean = self.invoke_native(launch, lambda owned: {'complete':False})
        clean.assert_called_once_with(process)
        self.assertFalse(result['process_cleanup_complete'])

    def test_interrupt_has_its_own_failure_type(self):
        process, launch = self.fake_process(KeyboardInterrupt())
        def cleanup(owned):
            process.returncode = -9
            return {'complete':True}
        result, _ = self.invoke_native(launch, cleanup)
        self.assertTrue(result['interrupted'])
        self.assertEqual(result['failure_type'], 'KeyboardInterrupt')

    def test_initial_record_failure_never_launches(self):
        with patch.object(runner.helpers, 'write_json', side_effect=OSError('disk full')), \
             patch.object(runner.subprocess, 'Popen') as launch:
            with self.assertRaises(OSError):
                runner.native(self.fake_executable, [], self.root/'work', self.root/'report', 1)
        launch.assert_not_called()

    def test_final_record_failure_is_not_success(self):
        real = runner.helpers.write_json
        process, launch = self.fake_process()
        def save(path, record):
            if record.get('phase') == 'finished':
                raise OSError('controlled final save failure')
            return real(path, record)
        with patch.object(runner.helpers, 'write_json', side_effect=save):
            with self.assertRaises(OSError):
                self.invoke_native(launch)
        previous = json.loads((self.root/'report/result.json').read_text())
        self.assertNotEqual(previous['status'], 'pass')

    @unittest.skipUnless(sys.platform == 'win32', 'Windows case runner')
    def test_copy_failure_preserves_ledger_and_unstarted_stages(self):
        with patch.object(runner.shutil, 'copytree', side_effect=OSError('copy stopped')), \
             patch.object(runner, 'native') as native:
            with self.assertRaises(OSError):
                runner.run(self.arguments())
        record = json.loads((self.root/'out/result.json').read_text())
        self.assertEqual(record['status'], 'fail')
        self.assertEqual(record['failure_phase'], 'copy_inputs')
        self.assertTrue(all(x['status']=='NOT_RUN' and x['returncode'] is None for x in record['stages']))
        native.assert_not_called()

    @unittest.skipUnless(sys.platform == 'win32', 'Windows case runner')
    def test_zero_exit_without_xsa_is_rejected(self):
        result = {'status':'pass','interrupted':False,'returncode':0,'process_cleanup_complete':True}
        with patch.object(runner, 'native', return_value=result):
            with self.assertRaisesRegex(RuntimeError, 'Invalid current XSA product.*Errno 2'):
                runner.run(self.arguments())
        record = json.loads((self.root/'out/result.json').read_text())
        self.assertEqual(record['status'], 'fail')
        self.assertEqual(record['stages'][-1]['status'], 'NOT_RUN')

    @unittest.skipUnless(sys.platform == 'win32', 'Windows case runner')
    def test_zero_exit_with_empty_xsa_fails_before_sdt(self):
        def native(executable, arguments, directory, report, timeout, expected_success):
            if report.name == 'export':
                (directory/'hardware.xsa').write_bytes(b'')
            return {'status':'pass','interrupted':False,'returncode':0,'process_cleanup_complete':True}
        with patch.object(runner, 'native', side_effect=native):
            with self.assertRaisesRegex(RuntimeError, 'Invalid current XSA'):
                runner.run(self.arguments())
        record = json.loads((self.root/'out/result.json').read_text())
        self.assertEqual(record['status'], 'fail')
        self.assertEqual(record['failure_phase'], 'export_products')
        self.assertEqual(record['stages'][-1]['status'], 'NOT_RUN')

    def synthetic_xsa(self, include_top=True):
        path = self.root/'synthetic.xsa'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('xsa.json', '{}')
            archive.writestr('hwdef.xml', '<HW><File Type="HW_HANDOFF" BD_TYPE="DEFAULT_BD" Name="system.hwh"/></HW>')
            if include_top:
                archive.writestr('system.hwh', '<SYSTEM><MODULES><MODULE INSTANCE="sample_gpio"/></MODULES></SYSTEM>')
        return path

    def test_product_integrity_accepts_synthetic_container_not_hardware_semantics(self):
        result = runner.check_xsa(self.synthetic_xsa())
        self.assertEqual(result['declared_top_hwh'], 'system.hwh')

    def test_corrupt_xsa_container_is_rejected(self):
        path = self.root/'bad.xsa'
        path.write_bytes(b'not a ZIP')
        with self.assertRaisesRegex(RuntimeError, 'Invalid current XSA'):
            runner.check_xsa(path)

    def test_xsa_declared_missing_top_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'DEFAULT_BD'):
            runner.check_xsa(self.synthetic_xsa(include_top=False))

    def synthetic_sdt(self, include_content):
        folder = self.root/'sdt'
        folder.mkdir()
        top = folder/'system-top.dts'
        top.write_text('/dts-v1/;\n#include "pl.dtsi"\n/ {};\n')
        (folder/'pl.dtsi').write_text(include_content)
        return top

    def test_sdt_integrity_reads_actual_include_closure(self):
        hashes = runner.check_sdt(self.synthetic_sdt('/ { sample {}; };\n'))
        self.assertEqual(set(hashes), {'system-top.dts', 'pl.dtsi'})

    def test_sdt_empty_output_is_rejected(self):
        top = self.synthetic_sdt('/ {};\n')
        top.write_text('')
        with self.assertRaisesRegex(RuntimeError, 'Invalid current SDT'):
            runner.check_sdt(top)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows case runner')
    def test_zero_exit_with_empty_sdt_keeps_prior_stage_evidence(self):
        archive_bytes = self.synthetic_xsa().read_bytes()
        def native(executable, arguments, directory, report, timeout, expected_success):
            if report.name == 'export':
                (directory/'hardware.xsa').write_bytes(archive_bytes)
            if report.name == 'sdt':
                (directory/'sdt').mkdir()
                (directory/'sdt/system-top.dts').write_text('')
            return {'status':'pass','interrupted':False,'returncode':0,'process_cleanup_complete':True}
        with patch.object(runner, 'native', side_effect=native):
            with self.assertRaisesRegex(RuntimeError, 'Invalid current SDT'):
                runner.run(self.arguments())
        record = json.loads((self.root/'out/result.json').read_text())
        self.assertEqual(record['status'], 'fail')
        self.assertEqual(record['failure_phase'], 'sdt_products')
        self.assertTrue(all(stage['returncode']==0 for stage in record['stages']))
        self.assertNotEqual(record['artifact_generation'], 'pass')

    def test_sdt_empty_or_escaping_include_is_rejected(self):
        top = self.synthetic_sdt('')
        with self.assertRaisesRegex(RuntimeError, 'Empty SDT product'):
            runner.check_sdt(top)
        (top.parent/'pl.dtsi').write_text('#include "../external.dtsi"\n')
        (self.root/'external.dtsi').write_text('/ {};\n')
        with self.assertRaisesRegex(RuntimeError, 'escapes'):
            runner.check_sdt(top)

    def test_overlap_missing_project_is_parameter_error(self):
        args = self.arguments('address-overlap')
        args.project = self.root/'missing/project/soc_handoff.xpr'
        with self.assertRaises(runner.ParameterError):
            runner.run(args)
        self.assertFalse(args.output.exists())

    @unittest.skipUnless(sys.platform == 'win32', 'Windows case runner')
    def test_controlled_interrupt_cli_status_130(self):
        args = ['run.py','prepare','--vivado',str(self.fake_executable),'--output',str(self.root/'out')]
        result = {'status':'fail','interrupted':True,'returncode':-9,'process_cleanup_complete':True}
        with patch.object(sys, 'argv', args), patch.object(runner, 'native', return_value=result):
            self.assertEqual(runner.main(), 130)
        self.assertTrue(json.loads((self.root/'out/result.json').read_text())['interrupted'])

    def test_invalid_timeouts_exit_2_without_output(self):
        for value in ('0','-1','nan','inf'):
            with self.subTest(value=value):
                args = ['run.py','prepare','--vivado',str(self.fake_executable),
                        '--output',str(self.root/'out'),'--timeout',value]
                with patch.object(sys, 'argv', args), patch.object(runner, 'run') as run:
                    with self.assertRaises(SystemExit) as error:
                        runner.main()
                self.assertEqual(error.exception.code, 2)
                run.assert_not_called()
                self.assertFalse((self.root/'out').exists())

    def test_missing_tool_is_parameter_error_without_output(self):
        args = self.arguments()
        args.vivado = self.root/'absent.bat'
        with self.assertRaises(runner.ParameterError):
            runner.run(args)
        self.assertFalse(args.output.exists())

    def test_export_refuses_unowned_project(self):
        project = self.root/'project/soc_handoff.xpr'
        project.parent.mkdir()
        project.write_text('<Project/>')
        with self.assertRaisesRegex(runner.ParameterError, 'ownership marker'):
            runner.project_inputs(project)

    def mock_owned_project(self, extra):
        owned = self.root/'owned'
        project = owned/'project/soc_handoff.xpr'
        project.parent.mkdir(parents=True)
        (owned/'sources').mkdir()
        (owned/'sources/counter32.v').write_text('// original mock input\n')
        (owned/runner.OWNER).write_text(json.dumps({'format':'epw-soc-handoff/1'}))
        project.write_text('<Project><File Path="$PPRDIR/../sources/counter32.v"/>'+extra+'</Project>')
        return project

    def test_external_run_directory_is_refused_before_native(self):
        external = (self.root/'outside-owned/synth_1').as_posix()
        project = self.mock_owned_project('<Run Dir="'+external+'"/>')
        with self.assertRaises(runner.ParameterError):
            runner.project_inputs(project)
        self.assertFalse((self.root/'outside-owned').exists())

    def test_external_cache_option_is_refused_before_native(self):
        external = (self.root/'outside-owned/ip').as_posix()
        project = self.mock_owned_project('<Option Name="IPOutputRepo" Val="'+external+'"/>')
        with self.assertRaises(runner.ParameterError):
            runner.project_inputs(project)

    def test_internal_native_cache_option_is_accepted(self):
        project = self.mock_owned_project('<Option Name="IPOutputRepo" Val="$PCACHEDIR/ip"/>')
        inputs = runner.project_inputs(project)
        self.assertTrue(inputs)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows case runner')
    def test_output_under_install_is_refused_without_writing(self):
        args = self.arguments()
        args.output = self.root/'vendor-install/outputs'
        with self.assertRaises(runner.ParameterError):
            runner.run(args)
        self.assertFalse(args.output.exists())

    @unittest.skipUnless(sys.platform == 'win32', 'Windows case runner')
    def test_native_final_save_error_does_not_mark_process_unstarted(self):
        def failed_native(executable, arguments, directory, report, timeout, expected_success):
            report.mkdir(parents=True)
            (report/'result.json').write_text(json.dumps({'status':'running','returncode':0,'pid':9876}))
            raise OSError('controlled native final record failure')
        with patch.object(runner, 'native', side_effect=failed_native):
            with self.assertRaises(OSError):
                runner.run(self.arguments())
        record = json.loads((self.root/'out/result.json').read_text())
        stage = record['stages'][0]
        self.assertEqual(stage['status'], 'UNCONFIRMED')
        self.assertEqual(stage['returncode'], 0)
        self.assertEqual(stage['pid'], 9876)
        self.assertEqual(record['stages'][1]['status'], 'NOT_RUN')

    def test_negative_mutation_must_match_exactly_once(self):
        source = self.root/'original.v'
        source.write_text('line\nline\n')
        with self.assertRaises(ValueError):
            runner.mutate_once(source, 'line', 'replacement')
        self.assertEqual(source.read_text(), 'line\nline\n')

    def test_regenerated_known_wrapper_is_recorded_separately(self):
        project = self.mock_owned_project('')
        user = self.root/'owned/sources/counter32.v'
        wrapper = project.parent/'soc_handoff.gen/sources_1/bd/system/hdl/system_wrapper.v'
        wrapper.parent.mkdir(parents=True)
        wrapper.write_text('// Date: before\nmodule system_wrapper; endmodule\n')
        before = {str(user.resolve()):runner.helpers.sha(user), str(wrapper.resolve()):runner.helpers.sha(wrapper)}
        wrapper.write_text('// Date: after\nmodule system_wrapper; endmodule\n')
        after = {str(user.resolve()):runner.helpers.sha(user), str(wrapper.resolve()):runner.helpers.sha(wrapper)}
        result = runner.check_source_retention(project,before,after)
        self.assertEqual(len(result['user_sources']), 1)
        self.assertEqual(len(result['generated_wrapper_changes']), 1)

    def test_changed_user_rtl_is_rejected(self):
        project = self.mock_owned_project('')
        user = self.root/'owned/sources/counter32.v'
        before = {str(user.resolve()):runner.helpers.sha(user)}
        user.write_text('// unexpected user source edit\n')
        after = {str(user.resolve()):runner.helpers.sha(user)}
        with self.assertRaisesRegex(RuntimeError, 'Current user source changed'):
            runner.check_source_retention(project,before,after)

    def test_user_named_wrapper_outside_generated_location_is_still_protected(self):
        project = self.mock_owned_project('')
        user = self.root/'owned/sources/system_wrapper.v'
        user.write_text('// user wrapper before\n')
        before = {str(user.resolve()):runner.helpers.sha(user)}
        user.write_text('// user wrapper after\n')
        after = {str(user.resolve()):runner.helpers.sha(user)}
        with self.assertRaisesRegex(RuntimeError, 'Current user source changed'):
            runner.check_source_retention(project,before,after)

    def test_unchanged_user_rtl_losing_reference_is_rejected(self):
        project = self.mock_owned_project('')
        user = self.root/'owned/sources/counter32.v'
        before = {str(user.resolve()):runner.helpers.sha(user)}
        with self.assertRaisesRegex(RuntimeError, 'lost its project reference'):
            runner.check_source_retention(project,before,{})

    def test_generated_wrapper_cannot_disappear_from_project(self):
        project = self.mock_owned_project('')
        wrapper = project.parent/'soc_handoff.gen/sources_1/bd/system/hdl/system_wrapper.v'
        before = {str(wrapper.resolve()):'previous-generated-digest'}
        with self.assertRaisesRegex(RuntimeError, 'Tool-managed wrapper lost'):
            runner.check_source_retention(project,before,{})


if __name__ == '__main__':
    unittest.main()
