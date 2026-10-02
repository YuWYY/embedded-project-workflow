# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
"""Independent reconstruction checks with original synthetic XPR/BD inputs.

Vendor processes are mocked. These tests are not Vivado build evidence.
"""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

SCRIPT = Path(__file__).resolve().parents[1]/'scripts/rebuild_current.py'
SPEC = importlib.util.spec_from_file_location('reviewed_reconstruction', SCRIPT)
rebuild = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rebuild)


class ReconstructionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='epw-rebuild-host-')
        self.root = Path(self.temp.name)
        self.owned = self.root/'owned'
        self.project = self.owned/'project/soc_handoff.xpr'
        self.project.parent.mkdir(parents=True)
        self.counter = self.owned/'sources/counter32.v'
        self.counter.parent.mkdir()
        self.counter.write_text('module counter32; endmodule\n')
        self.bd = self.project.parent/'soc_handoff.srcs/sources_1/bd/system/system.bd'
        self.bd.parent.mkdir(parents=True)
        self.bd.write_text(json.dumps({'design': {'design_info': {'name': 'system'}, 'design_tree': {}}}))
        (self.owned/rebuild.runner.OWNER).write_text('{"format":"epw-soc-handoff/1"}')
        self.project.write_text('''<Project><Configuration>
          <Option Name="Part" Val="xczu9eg-ffvb1156-2-e"/>
          <Option Name="BoardPart" Val="xilinx.com:zcu102:part0:3.4"/>
          <Option Name="DefaultLib" Val="xil_defaultlib"/>
        </Configuration><FileSets><FileSet Name="sources_1">
          <File Path="$PPRDIR/../sources/counter32.v"><FileInfo>
            <Attr Name="UsedIn" Val="synthesis"/><Attr Name="UsedIn" Val="implementation"/>
            <Attr Name="UsedIn" Val="simulation"/>
          </FileInfo></File>
          <File Path="$PSRCDIR/sources_1/bd/system/system.bd"><FileInfo>
            <Attr Name="UsedIn" Val="synthesis"/><Attr Name="UsedIn" Val="implementation"/>
            <Attr Name="UsedIn" Val="simulation"/>
          </FileInfo></File>
          <Config><Option Name="DesignMode" Val="RTL"/>
            <Option Name="TopModule" Val="system_wrapper"/></Config>
        </FileSet></FileSets></Project>''')
        self.executable = self.root/'vendor/Vivado/bin/vivado.bat'
        self.executable.parent.mkdir(parents=True)
        self.executable.write_text('REM never executed\n')

    def tearDown(self):
        self.temp.cleanup()

    def args(self):
        return argparse.Namespace(project=self.project, output=self.root/'out', vivado=self.executable, timeout=1)

    def edit_xml(self, operation):
        tree = ET.parse(self.project)
        operation(tree.getroot())
        tree.write(self.project, encoding='unicode')

    def add_file(self, path):
        def add(root):
            file = ET.SubElement(root.find('./FileSets/FileSet'), 'File', {'Path': str(path)})
            info = ET.SubElement(file, 'FileInfo')
            for usage in ('synthesis', 'implementation', 'simulation'):
                ET.SubElement(info, 'Attr', {'Name': 'UsedIn', 'Val': usage})
        self.edit_xml(add)

    def test_minimal_current_case_keeps_config_and_references(self):
        refs, config, options, bds = rebuild.read_case(self.project)
        self.assertIn(str(self.counter), refs)
        self.assertEqual(config['Part'], 'xczu9eg-ffvb1156-2-e')
        self.assertEqual(options['TopModule'], 'system_wrapper')
        self.assertEqual(bds, [self.bd])

    def test_nonempty_verilog_define_is_not_silently_lost(self):
        self.edit_xml(lambda root: ET.SubElement(root.find('./FileSets/FileSet/Config'), 'Option',
            {'Name': 'VerilogDefines', 'Val': 'SLOW_COUNTER=1'}))
        with self.assertRaises(rebuild.runner.ParameterError):
            rebuild.read_case(self.project)

    def test_nonempty_generic_is_not_silently_lost(self):
        self.edit_xml(lambda root: ET.SubElement(root.find('./FileSets/FileSet/Config'), 'Option',
            {'Name': 'Generic', 'Val': 'WIDTH=8'}))
        with self.assertRaises(rebuild.runner.ParameterError):
            rebuild.read_case(self.project)

    def test_synthesis_disabled_source_is_not_silently_enabled(self):
        def change(root):
            info = root.find('./FileSets/FileSet/File/FileInfo')
            for node in list(info):
                if node.get('Name') == 'UsedIn' and node.get('Val') == 'synthesis':
                    info.remove(node)
        self.edit_xml(change)
        with self.assertRaises(rebuild.runner.ParameterError):
            rebuild.read_case(self.project)

    def test_custom_file_library_is_not_silently_reset(self):
        self.edit_xml(lambda root: ET.SubElement(root.find('./FileSets/FileSet/File/FileInfo'), 'Attr',
            {'Name': 'Library', 'Val': 'userlib'}))
        with self.assertRaises(rebuild.runner.ParameterError):
            rebuild.read_case(self.project)

    def test_native_import_provenance_is_allowed_without_following_it(self):
        provenance = self.root/'unread-import-origin/system.bd'
        def add(root):
            info = root.findall('./FileSets/FileSet/File/FileInfo')[1]
            ET.SubElement(info, 'Attr', {'Name': 'ImportPath', 'Val': str(provenance)})
            ET.SubElement(info, 'Attr', {'Name': 'ImportTime', 'Val': '1790953215'})
        self.edit_xml(add)
        refs, _, _, bds = rebuild.read_case(self.project)
        self.assertIn(self.bd, bds)
        self.assertNotIn(str(provenance), refs)
        self.assertFalse(provenance.parent.exists())

    def test_unknown_effective_compile_attribute_remains_rejected(self):
        self.edit_xml(lambda root: ET.SubElement(root.find('./FileSets/FileSet/File/FileInfo'), 'Attr',
            {'Name': 'IsGlobalInclude', 'Val': '1'}))
        with self.assertRaises(rebuild.runner.ParameterError):
            rebuild.read_case(self.project)

    def test_precisely_managed_wrapper_is_allowed(self):
        wrapper = self.project.parent/'soc_handoff.gen/sources_1/bd/system/hdl/system_wrapper.v'
        wrapper.parent.mkdir(parents=True)
        wrapper.write_text('module system_wrapper; endmodule\n')
        self.add_file(wrapper)
        rebuild.read_case(self.project)

    def test_user_named_wrapper_is_not_discarded_as_generated(self):
        wrapper = self.owned/'sources/system_wrapper.v'
        wrapper.write_text('// user-owned wrapper\n')
        self.add_file(wrapper)
        with self.assertRaises(rebuild.runner.ParameterError):
            rebuild.read_case(self.project)

    def test_empty_secondary_bd_is_retained_but_nonempty_is_rejected(self):
        second = self.project.parent/'soc_handoff.srcs/sources_1/bd/spare/spare.bd'
        second.parent.mkdir(parents=True)
        data = {'design': {'design_info': {'name': 'spare'}, 'design_tree': {}}}
        second.write_text(json.dumps(data))
        self.add_file(second)
        self.assertIn(second, rebuild.read_case(self.project)[3])
        data['design']['design_tree']['extra'] = ''
        second.write_text(json.dumps(data))
        with self.assertRaises(rebuild.runner.ParameterError):
            rebuild.read_case(self.project)

    @unittest.skipUnless(os.name == 'nt', 'Windows native entry boundary')
    def test_copy_failure_records_phase_and_no_vendor_start(self):
        args = self.args()
        with patch.object(rebuild.shutil, 'copy2', side_effect=OSError('controlled copy failure')), \
             patch.object(rebuild.runner, 'native') as native:
            with self.assertRaises(OSError): rebuild.run(args)
        record = json.loads((args.output/'result.json').read_text())
        self.assertEqual(record['failure_phase'], 'copy_current_inputs')
        self.assertTrue(all(s['status'] == 'NOT_RUN' for s in record['stages']))
        native.assert_not_called()

    @unittest.skipUnless(os.name == 'nt', 'Windows native entry boundary')
    def test_initial_record_failure_never_launches_native(self):
        with patch.object(rebuild.runner.helpers, 'write_json', side_effect=OSError('storage unavailable')), \
             patch.object(rebuild.runner, 'native') as native:
            with self.assertRaises(OSError): rebuild.run(self.args())
        native.assert_not_called()

    @unittest.skipUnless(os.name == 'nt', 'Windows native entry boundary')
    def test_controlled_native_interrupt_returns_130_and_retains_phase(self):
        args = self.args()
        returned = {'status': 'fail', 'returncode': -9, 'interrupted': True, 'process_cleanup_complete': True}
        argv = ['rebuild_current.py', '--project', str(args.project), '--output', str(args.output),
                '--vivado', str(args.vivado)]
        with patch.object(sys, 'argv', argv), patch.object(rebuild.runner, 'native', return_value=returned):
            self.assertEqual(rebuild.main(), 130)
        record = json.loads((args.output/'result.json').read_text())
        self.assertEqual(record['status'], 'fail')
        self.assertEqual(record['failure_phase'], 'import_current')
        self.assertEqual(record['stages'][0]['returncode'], -9)
        self.assertEqual(record['stages'][1]['status'], 'NOT_RUN')

    @unittest.skipUnless(os.name == 'nt', 'Windows native entry boundary')
    def test_native_record_failure_is_unconfirmed_not_unstarted(self):
        args = self.args()
        def failed(executable, argv, directory, report, timeout):
            report.mkdir(parents=True)
            (report/'result.json').write_text('{"status":"running","pid":12345,"returncode":0}')
            raise OSError('native result persistence failed')
        with patch.object(rebuild.runner, 'native', side_effect=failed):
            with self.assertRaises(OSError): rebuild.run(args)
        record = json.loads((args.output/'result.json').read_text())
        self.assertEqual(record['stages'][0]['status'], 'UNCONFIRMED')
        self.assertEqual(record['stages'][0]['pid'], 12345)
        self.assertFalse(record['process_cleanup_complete'])

    @unittest.skipUnless(os.name == 'nt', 'Windows native entry boundary')
    def test_tool_install_output_is_rejected_before_write(self):
        args = self.args(); args.output = self.root/'vendor/new-output'
        with patch.object(rebuild.runner, 'native') as native:
            with self.assertRaises(rebuild.runner.ParameterError): rebuild.run(args)
        self.assertFalse(args.output.exists())
        native.assert_not_called()

    @unittest.skipUnless(os.name == 'nt', 'Windows native entry boundary')
    def test_missing_project_is_parameter_error(self):
        args = self.args(); args.project = self.root/'missing/project.xpr'
        with self.assertRaises(rebuild.runner.ParameterError): rebuild.run(args)
        self.assertFalse(args.output.exists())

    def post_fixture(self):
        """Synthetic recorded stages only, never represented as native evidence."""
        data = json.loads(self.bd.read_text())
        data['design']['addressing'] = {'/zynq_ultra_ps_e_0': {'address_spaces': {'Data': {'segments': {
            'SEG_axi_gpio_0_Reg': {'address_block': '/axi_gpio_0/S_AXI/Reg',
                                 'offset': '0xA0010000', 'range': '64K'}}}}}}
        self.bd.write_text(json.dumps(data))
        actual = self.root/'rebuilt'
        reference = self.root/'reference'
        original_refs, config, options, _ = rebuild.read_case(self.project)
        cases = {str(self.project): (original_refs, config, options, [self.bd])}
        for owned in (actual, reference):
            project = owned/'project/soc_handoff.xpr'
            project.parent.mkdir(parents=True)
            project.write_text(self.project.read_text())
            counter = owned/'sources/counter32.v'
            counter.parent.mkdir(); counter.write_bytes(self.counter.read_bytes())
            bd = project.parent/'soc_handoff.srcs/sources_1/bd/system/system.bd'
            bd.parent.mkdir(parents=True); bd.write_bytes(self.bd.read_bytes())
            refs = {str(path): rebuild.runner.helpers.sha(path) for path in (project, counter, bd)}
            cases[str(project)] = (refs, config, options, [bd])
        def archive(path):
            with zipfile.ZipFile(path, 'w') as output:
                output.writestr('xsa.json', '{}')
                output.writestr('hwdef.xml', '<Project><File Type="HW_HANDOFF" Name="system.hwh" BD_TYPE="DEFAULT_BD"/></Project>')
                output.writestr('system.hwh', '''<EDKSYSTEM><MODULES><MODULE INSTANCE="zynq_ultra_ps_e_0">
                    <MEMORYMAP><MEMRANGE INSTANCE="axi_gpio_0" SLAVEBUSINTERFACE="S_AXI"
                    ADDRESSBLOCK="Reg" MASTERBUSINTERFACE="M_AXI_HPM0_FPD"
                    BASEVALUE="0xA0010000" HIGHVALUE="0xA001FFFF"/></MEMORYMAP>
                    </MODULE></MODULES></EDKSYSTEM>''')
        archive(actual/'hardware.xsa')
        reference_export = self.root/'reference-export'; reference_export.mkdir()
        archive(reference_export/'hardware.xsa')
        sdt = actual/'sdt'; sdt.mkdir()
        (sdt/'system-top.dts').write_text('/dts-v1/;\n#include "pl.dtsi"\n/ {};\n')
        (sdt/'pl.dtsi').write_text('/ {};\n')
        for name in ('rebuild_current.py', 'rebuild_current.tcl', 'export.tcl', 'sdt.tcl'):
            script = actual/'scripts'/name; script.parent.mkdir(exist_ok=True)
            script.write_text('# synthetic non-executed script\n')
        fixed_bd = actual/'input_bd/system/system.bd'; fixed_bd.parent.mkdir(parents=True)
        fixed_bd.write_bytes(self.bd.read_bytes())
        native = {'status': 'fail', 'error': 'synthetic previous validation failure',
            'source_project': str(self.project), 'input_sha256': original_refs,
            'copied_input_sha256': {p.relative_to(actual).as_posix(): rebuild.runner.helpers.sha(p)
                for folder in ('scripts', 'sources', 'input_bd') for p in (actual/folder).rglob('*') if p.is_file()},
            'stages': [{'name': name, 'status': 'pass', 'returncode': 0}
                       for name in ('import_current', 'export', 'sdt')],
            'xsa_integrity': rebuild.runner.check_xsa(actual/'hardware.xsa'),
            'sdt_product_sha256': rebuild.runner.check_sdt(sdt/'system-top.dts')}
        ref_project = reference/'project/soc_handoff.xpr'
        ref_record = {'project': str(ref_project),
            'stages': [{'name': name, 'status': 'pass', 'returncode': 0} for name in ('export', 'sdt')],
            'current_input_sha256': cases[str(ref_project)][0],
            'xsa_integrity': rebuild.runner.check_xsa(reference_export/'hardware.xsa')}
        (actual/'result.json').write_text(json.dumps(native))
        (reference_export/'result.json').write_text(json.dumps(ref_record))
        args = argparse.Namespace(output=actual, project=self.project,
            reference_project=ref_project, reference_xsa=reference_export/'hardware.xsa')
        return args, cases, native, ref_record

    def run_post(self, args, cases):
        with patch.object(rebuild, 'read_case', side_effect=lambda p: cases[str(p)]):
            return rebuild.post_validate(args)

    def test_post_fixture_preserves_original_failure_record(self):
        args, cases, _, _ = self.post_fixture()
        before = (args.output/'result.json').read_bytes()
        result = self.run_post(args, cases)
        self.assertEqual(json.loads(result.read_text())['status'], 'pass')
        self.assertEqual((args.output/'result.json').read_bytes(), before)

    def test_numbered_post_report_preserves_both_prior_records(self):
        args, cases, _, _ = self.post_fixture()
        old = args.output/'post-validation.json'
        old.write_text('{"status":"fail","error":"prior review"}')
        original = old.read_bytes()
        args.post_report_name = 'post-validation-v2.json'
        result = self.run_post(args, cases)
        self.assertEqual(result.name, args.post_report_name)
        self.assertEqual(old.read_bytes(), original)
        with self.assertRaisesRegex(rebuild.runner.ParameterError, 'already exists'):
            self.run_post(args, cases)

    def test_post_report_name_cannot_escape_or_replace_native_record(self):
        args, cases, _, _ = self.post_fixture()
        original = (args.output/'result.json').read_bytes()
        for name in ('result.json', '../post-validation-v2.json', 'sub/post-validation.json',
                     'post-validation-测试.json', 'post-validation.json.tmp'):
            args.post_report_name = name
            with self.subTest(name=name), self.assertRaises(rebuild.runner.ParameterError):
                self.run_post(args, cases)
        self.assertEqual((args.output/'result.json').read_bytes(), original)

    def test_post_report_name_in_native_mode_is_parameter_error(self):
        args = self.args()
        argv = ['rebuild_current.py', '--project', str(args.project), '--output', str(args.output),
                '--vivado', str(args.vivado), '--post-report-name', 'post-validation-v2.json']
        with patch.object(sys, 'argv', argv), patch.object(rebuild, 'run') as native:
            self.assertEqual(rebuild.main(), 2)
        native.assert_not_called()
        self.assertFalse(args.output.exists())

    def test_post_missing_native_stage_cannot_pass(self):
        args, cases, native, _ = self.post_fixture()
        native['stages'].pop()
        (args.output/'result.json').write_text(json.dumps(native))
        with self.assertRaisesRegex(RuntimeError, 'All three original native stages'): self.run_post(args, cases)
        self.assertEqual(json.loads((args.output/'post-validation.json').read_text())['status'], 'fail')

    def test_post_missing_reference_stage_cannot_pass(self):
        args, cases, _, reference = self.post_fixture()
        reference['stages'] = []
        (args.reference_xsa.parent/'result.json').write_text(json.dumps(reference))
        with self.assertRaisesRegex(RuntimeError, 'Reference native stages'): self.run_post(args, cases)

    def test_post_changed_original_source_cannot_pass(self):
        args, cases, _, _ = self.post_fixture()
        self.counter.write_text('// changed after native run\n')
        with self.assertRaisesRegex(RuntimeError, 'Original native input changed'): self.run_post(args, cases)

    def test_post_missing_source_hash_cannot_pass(self):
        args, cases, native, _ = self.post_fixture()
        native['input_sha256'] = {}
        (args.output/'result.json').write_text(json.dumps(native))
        with self.assertRaisesRegex(RuntimeError, 'Native input identity map'): self.run_post(args, cases)

    def test_post_missing_copied_input_hash_cannot_pass(self):
        args, cases, native, _ = self.post_fixture()
        native['copied_input_sha256'].pop('scripts/sdt.tcl')
        (args.output/'result.json').write_text(json.dumps(native))
        with self.assertRaisesRegex(RuntimeError, 'Native copied-input identity map'): self.run_post(args, cases)

    def test_post_missing_reference_input_hash_cannot_pass(self):
        args, cases, _, reference = self.post_fixture()
        reference['current_input_sha256'] = {}
        (args.reference_xsa.parent/'result.json').write_text(json.dumps(reference))
        with self.assertRaisesRegex(RuntimeError, 'Reference current-input identity map'): self.run_post(args, cases)

    def test_post_changed_reference_xsa_identity_cannot_pass(self):
        args, cases, _, _ = self.post_fixture()
        with args.reference_xsa.open('ab') as stream: stream.write(b'changed-container-identity')
        with self.assertRaisesRegex(RuntimeError, 'Reference XSA identity'): self.run_post(args, cases)

    def test_post_changed_current_xsa_identity_cannot_pass(self):
        args, cases, _, _ = self.post_fixture()
        with (args.output/'hardware.xsa').open('ab') as stream: stream.write(b'changed-container-identity')
        with self.assertRaisesRegex(RuntimeError, 'Current XSA is not the recorded'): self.run_post(args, cases)

    def test_post_changed_sdt_dependency_cannot_pass(self):
        args, cases, _, _ = self.post_fixture()
        with (args.output/'sdt/pl.dtsi').open('a') as stream: stream.write('\n/* changed after native */\n')
        with self.assertRaisesRegex(RuntimeError, 'Current SDT is not the recorded'): self.run_post(args, cases)

    def test_gpio_old_address_fails_even_if_archive_identity_is_valid(self):
        args, _, _, _ = self.post_fixture()
        hardware, _ = rebuild.effective_hwh(args.reference_xsa)
        rebuild.verify_gpio_address(self.bd, hardware)
        mapping = hardware['zynq_ultra_ps_e_0']['memory_ranges'][0]
        mapping.update(BASEVALUE='0xA0000000', HIGHVALUE='0xA000FFFF')
        with self.assertRaisesRegex(RuntimeError, 'BD and XSA GPIO handoff disagree'):
            rebuild.verify_gpio_address(self.bd, hardware)

    def test_gpio_wrong_master_or_duplicate_mapping_fails(self):
        args, _, _, _ = self.post_fixture()
        hardware, _ = rebuild.effective_hwh(args.reference_xsa)
        wrong = copy.deepcopy(hardware)
        wrong['zynq_ultra_ps_e_0']['memory_ranges'][0]['MASTERBUSINTERFACE'] = 'M_AXI_HPM1_FPD'
        duplicate = copy.deepcopy(hardware)
        duplicate['zynq_ultra_ps_e_0']['memory_ranges'].append(
            copy.deepcopy(duplicate['zynq_ultra_ps_e_0']['memory_ranges'][0]))
        for modified in (wrong, duplicate):
            with self.subTest(modified=modified), self.assertRaisesRegex(RuntimeError, 'BD and XSA GPIO handoff disagree'):
                rebuild.verify_gpio_address(self.bd, modified)

    def expansion_fixture(self):
        path = '/components/zynq_ultra_ps_e_0/parameters/PSU_MIO_22_INPUT_TYPE'
        raw = [{'path': path, 'before': None, 'after': {'value': 'cmos'}}]
        xci = {'zynq_ultra_ps_e_0': {'parameters': {'component_parameters': {'PSU_MIO_22_INPUT_TYPE': ['cmos']},
                                                   'model_parameters': {'unrelated_value': ['42']}}}}
        hwh = {'zynq_ultra_ps_e_0': {'parameters': {'PSU_MIO_22_INPUT_TYPE': 'cmos'}}}
        return raw, xci, hwh

    def xci_fixture(self, reference):
        data = json.loads(self.bd.read_text())
        data['design']['components'] = {'counter32_0': {'xci_name': 'test_counter'}}
        self.bd.write_text(json.dumps(data))
        path = self.bd.parent/'ip/test_counter/test_counter.xci'
        path.parent.mkdir(parents=True)
        instance = {'component_reference': reference, 'ip_revision': '1',
                    'parameters': {'component_parameters': {'WIDTH': [{'value': '32'}]}}}
        path.write_text(json.dumps({'ip_inst': instance}))
        return path, instance

    def test_module_reference_without_model_parameters_is_an_empty_model(self):
        path, _ = self.xci_fixture('xilinx.com:module_ref:counter32:1.0')
        values, hashes = rebuild.effective_xci(self.bd)
        self.assertEqual(values['counter32_0']['parameters']['model_parameters'], {})
        self.assertEqual(values['counter32_0']['parameters']['component_parameters']['WIDTH'], ['32'])
        self.assertEqual(hashes[str(path)], rebuild.runner.helpers.sha(path))

    def test_vendor_ip_missing_model_parameters_cannot_be_assumed_empty(self):
        self.xci_fixture('xilinx.com:ip:axi_gpio:2.0')
        with self.assertRaises(RuntimeError):
            rebuild.effective_xci(self.bd)

    def test_module_reference_nonempty_model_parameters_are_not_discarded(self):
        path, instance = self.xci_fixture('xilinx.com:module_ref:counter32:1.0')
        before, _ = rebuild.effective_xci(self.bd)
        instance['parameters']['model_parameters'] = {'WIDTH': [{'value': '16'}]}
        path.write_text(json.dumps({'ip_inst': instance}))
        after, _ = rebuild.effective_xci(self.bd)
        with self.assertRaisesRegex(RuntimeError, 'effective configuration differs'):
            rebuild.resolve_native_expansions([], before, after, {}, {})

    def test_reviewed_expansion_requires_matching_effective_values(self):
        raw, xci, hwh = self.expansion_fixture()
        result = rebuild.resolve_native_expansions(raw, xci, copy.deepcopy(xci), hwh, copy.deepcopy(hwh))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['effective_value'], 'cmos')

    def test_changed_effective_mio_value_cannot_be_explained_away(self):
        raw, xci, hwh = self.expansion_fixture()
        changed = copy.deepcopy(xci)
        changed['zynq_ultra_ps_e_0']['parameters']['component_parameters']['PSU_MIO_22_INPUT_TYPE'] = ['lvttl']
        with self.assertRaises(RuntimeError): rebuild.resolve_native_expansions(raw, xci, changed, hwh, hwh)

    def test_unrelated_effective_parameter_change_also_fails(self):
        raw, xci, hwh = self.expansion_fixture()
        changed = copy.deepcopy(xci)
        changed['zynq_ultra_ps_e_0']['parameters']['model_parameters']['unrelated_value'] = ['43']
        with self.assertRaises(RuntimeError): rebuild.resolve_native_expansions(raw, xci, changed, hwh, hwh)

    def test_other_raw_difference_or_missing_evidence_is_not_ignored(self):
        raw, xci, hwh = self.expansion_fixture()
        for change in ({'path': raw[0]['path'], 'before': {'value': 'NA'}, 'after': {'value': 'cmos'}},
                       {'path': '/components/zynq_ultra_ps_e_0/parameters/PSU_MIO_23_INPUT_TYPE',
                        'before': None, 'after': {'value': 'cmos'}}):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                rebuild.resolve_native_expansions([change], xci, xci, hwh, hwh)
        with self.assertRaises(RuntimeError): rebuild.resolve_native_expansions(raw, {}, {}, {}, {})


if __name__ == '__main__':
    unittest.main()
