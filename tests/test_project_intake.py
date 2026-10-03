"""Read-only intake contracts; synthetic snippets are not vendor-tool evidence.

Original IOC and TouchGFX inputs are read directly from the public examples.
XPR/BD fixtures below reproduce native field shapes without vendor products.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO/'skills/embedded-project-workflow/scripts/project_intake.py'
SPEC = importlib.util.spec_from_file_location('project_intake', SCRIPT)
intake = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(intake)
IOC = REPO/'examples/feature-handoff/cubemx/sample_statistics.ioc'
IOC_B = REPO/'examples/cubemx-rtos/adapter-fixture-b/telemetry_fixture.ioc'
TOUCHGFX = REPO/'examples/feature-handoff/touchgfx/human-continuation/StatisticsHandoff.touchgfx'


def tree_hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and not p.is_symlink()}


def codes(report):
    return {d['code'] for d in report.get('diagnostics', [])} | {
        d['code'] for s in report.get('sources', []) for d in s['diagnostics']}


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='epw-intake-')
        self.root = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, text):
        path = self.root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def json_file(self, name, data):
        return self.write(name, json.dumps(data, ensure_ascii=False))

    def touch_data(self):
        return json.loads(TOUCHGFX.read_text(encoding='utf-8-sig'))

    def bd_data(self, name='system'):
        return {'design': {'design_info': {'name': name, 'tool_version': '2025.1', 'device': 'xczu9eg-ffvb1156-2-e'},
            'components': {'axi_gpio_0': {'vlnv': 'xilinx.com:ip:axi_gpio:2.0', 'ip_revision': '37'},
                           'counter32_0': {'vlnv': 'xilinx.com:module_ref:counter32:1.0',
                                           'reference_info': {'ref_type': 'hdl', 'ref_name': 'counter32'}}},
            'nets': {'control': {'ports': ['axi_gpio_0/gpio_io_o', 'counter32_0/control']}},
            'interface_nets': {'axi': {'interface_ports': ['smartconnect_0/M00_AXI', 'axi_gpio_0/S_AXI']}},
            'addressing': {'/ps': {'address_spaces': {'Data': {'segments': {'SEG_gpio': {
                'address_block': '/axi_gpio_0/S_AXI/Reg', 'offset': '0xA0010000', 'range': '64K'}}}}}}}}

    def xpr(self, resources=None):
        if resources is None:
            resources = ['$PPRDIR/rtl/counter32.v', '$PSRCDIR/sources_1/bd/system/system.bd',
                         '$PGENDIR/sources_1/bd/system/hdl/system_wrapper.v',
                         '$PSRCDIR/sources_1/bd/design_1/design_1.bd']
        self.write('rtl/counter32.v', 'module counter32; endmodule\n')
        self.json_file('demo.srcs/sources_1/bd/system/system.bd', self.bd_data())
        self.json_file('demo.srcs/sources_1/bd/design_1/design_1.bd', {'design': {
            'design_info': {'name': 'design_1', 'tool_version': '2025.1'}, 'components': {}}})
        self.write('demo.gen/sources_1/bd/system/hdl/system_wrapper.v', 'module system_wrapper; endmodule\n')
        return self.write('demo.xpr', '<Project Product="Vivado" Version="7" Minor="70" Path="old-location/moved.xpr">'
            '<Configuration><Option Name="Part" Val="xczu9eg-ffvb1156-2-e"/>'
            '<Option Name="BoardPart" Val="xilinx.com:zcu102:part0:3.4"/></Configuration>'
            '<FileSets><FileSet Name="sources_1" Type="DesignSrcs">' + ''.join(
                '<File Path="'+r+'"><FileInfo><Attr Name="UsedIn" Val="synthesis"/></FileInfo></File>' for r in resources) +
            '<Config><Option Name="TopModule" Val="system_wrapper"/><Option Name="DesignMode" Val="RTL"/></Config>'
            '</FileSet></FileSets></Project>')

    def source(self, report, kind):
        return next(s for s in report['sources'] if s['kind'] == kind)

    def test_original_ioc_without_vendor_environment(self):
        result = intake.inspect_project(IOC)
        self.assertEqual(result['status'], 'READ_ONLY')
        source = self.source(result, 'cubemx')
        self.assertEqual(source['facts']['device'], 'STM32G474RET6')
        self.assertEqual([(t['name'], t['stack_words'], t['allocation']) for t in source['facts']['rtos']['tasks']],
                         [('SampleFeed', 256, 'Static'), ('StatsWorker', 384, 'Dynamic')])
        self.assertEqual(source['facts']['rtos']['queues'][0]['capacity_elements'], 12)
        self.assertNotIn('stack_bytes', source['facts']['rtos']['tasks'][0])
        self.assertEqual(source['execution_profile']['execution_eligibility'], 'NOT_CHECKED')
        self.assertTrue(source['execution_profile']['declared_metadata_match'])
        self.assertTrue(all(v == 'NOT_RUN' for v in result['verification'].values()))

    def test_original_b_names_order_and_allocation_remain_distinct(self):
        source = self.source(intake.inspect_project(IOC_B), 'cubemx')
        self.assertEqual([x['name'] for x in source['facts']['rtos']['tasks']], ['Logger', 'Sampler'])
        self.assertEqual(source['facts']['rtos']['tasks'][0]['stack_words'], 320)
        self.assertEqual(source['facts']['rtos']['queues'][0]['name'], 'Frames')

    def test_text_device_uses_declared_user_name_when_cpn_absent(self):
        path = self.write('minimal.ioc', 'MxCube.Version=6.18.1\nMcu.UserName=STM32G474RETx\n')
        report = intake.inspect_project(path)
        self.assertIn('device STM32G474RETx', intake.format_text(report))
        self.assertIsNone(report['sources'][0]['facts']['device'])

    def test_first_use_original_fragments_can_be_inventoried(self):
        result = intake.inspect_project(REPO/'examples/first-use')
        self.assertEqual(len(result['sources']), 4)
        self.assertNotEqual(result['status'], 'ERROR')
        self.assertEqual(len([r for r in result['relationships'] if r['kind'] == 'xpr_references_bd']), 1)
        self.assertTrue(all(v == 'NOT_RUN' for v in result['verification'].values()))

    def test_unknown_ioc_version_keeps_stable_metadata(self):
        p = self.write('unknown.ioc', IOC.read_text().replace('MxCube.Version=6.18.1', 'MxCube.Version=99.1'))
        result = intake.inspect_project(p)
        self.assertEqual(result['status'], 'PARTIAL')
        self.assertIn('VERSION_UNVERIFIED', codes(result))
        self.assertEqual(result['sources'][0]['facts']['device'], 'STM32G474RET6')
        self.assertFalse(result['sources'][0]['execution_profile']['declared_metadata_match'])

    def test_unknown_rtos_shape_is_not_guessed(self):
        content = IOC.read_text().replace('SampleFeed,24,256,SampleFeed_Entry,As external,NULL,Static,SampleFeedStack,SampleFeedTCB',
                                          'SampleFeed,alternate-format')
        p = self.write('unknown.ioc', content+'\nFREERTOS.Tasks02=custom\n')
        result = intake.inspect_project(p)
        self.assertEqual(result['status'], 'PARTIAL')
        self.assertIn('RTOS_ROW_UNSUPPORTED', codes(result))
        self.assertIn('RTOS_TABLE_UNSUPPORTED', codes(result))
        self.assertEqual([x['name'] for x in result['sources'][0]['facts']['rtos']['tasks']], ['StatsWorker'])

    def test_duplicate_ioc_key_is_error(self):
        p = self.write('bad.ioc', IOC.read_text()+'\nMxCube.Version=6.18.1\n')
        result = intake.inspect_project(p)
        self.assertEqual(result['status'], 'ERROR')
        self.assertIn('DUPLICATE_KEY', codes(result))

    def test_duplicate_rtos_name_is_error(self):
        p = self.write('bad.ioc', IOC.read_text().replace(';StatsWorker,', ';SampleFeed,'))
        self.assertIn('DUPLICATE_OBJECT', codes(intake.inspect_project(p)))

    def test_actual_touchgfx_reset_callback_and_navigation(self):
        result = intake.inspect_project(TOUCHGFX)
        self.assertEqual(result['status'], 'READ_ONLY')
        facts = result['sources'][0]['facts']
        self.assertEqual(facts['StartupScreenName'], 'Dashboard')
        statistics = next(s for s in facts['screens'] if s['name'] == 'Statistics')
        interaction = next(x for x in statistics['interactions'] if x['trigger_component'] == 'resetButton')
        self.assertEqual((interaction['name'], interaction['function']), ('Interaction1', 'function1'))
        self.assertIn('CompileSimulatorCommand', facts['declared_commands'])

    def test_unknown_touchgfx_version_and_action_are_partial(self):
        data = self.touch_data()
        data['Version'] = '99.0'
        data['Application']['Screens'][0]['Interactions'][0]['Action']['Type'] = 'NewNativeAction'
        result = intake.inspect_project(self.json_file('new.touchgfx', data))
        self.assertEqual(result['status'], 'PARTIAL')
        self.assertEqual(len(result['sources'][0]['facts']['screens']), 3)
        self.assertIn('INTERACTION_UNEXPANDED', codes(result))

    def test_duplicate_json_key_and_malformed_json_fail(self):
        for text in ('{"Version":"4.26.1","Version":"4.26.1"}', '{'):
            with self.subTest(text=text):
                result = intake.inspect_project(self.write('bad.touchgfx', text))
                self.assertEqual(result['status'], 'ERROR')

    def test_duplicate_component_is_not_silently_selected(self):
        data = self.touch_data()
        components = data['Application']['Screens'][0]['Components']
        components.append(components[0])
        result = intake.inspect_project(self.json_file('bad.touchgfx', data))
        self.assertIn('DUPLICATE_OBJECT', codes(result))

    def test_coexisting_ioc_and_touchgfx_not_conflict(self):
        self.write('controller.ioc', IOC.read_text())
        self.json_file('ui.touchgfx', self.touch_data())
        result = intake.inspect_project(self.root)
        self.assertEqual(result['status'], 'READ_ONLY')
        self.assertEqual(len(result['sources']), 2)
        self.assertIsNone(result['primary_source'])
        self.assertEqual(result['relationships'][0]['kind'], 'co_located_sources')
        self.assertEqual(result['diagnostics'], [])

    def test_multiple_projects_listed_without_guess_and_entry_narrows(self):
        self.write('b/second.ioc', IOC_B.read_text())
        self.write('a/first.ioc', IOC.read_text())
        all_sources = intake.inspect_project(self.root)
        self.assertEqual([s['path'] for s in all_sources['sources']], ['a/first.ioc', 'b/second.ioc'])
        self.assertIsNone(all_sources['primary_source'])
        selected = intake.inspect_project(self.root, 'b/second.ioc')
        self.assertEqual([s['path'] for s in selected['sources']], ['b/second.ioc'])

    def test_entry_outside_and_file_entry_are_rejected(self):
        p = self.write('a.ioc', IOC.read_text())
        for root, entry in ((self.root, '../a.ioc'), (self.root, str(p)), (p, 'a.ioc')):
            with self.subTest(entry=entry):
                with self.assertRaises(intake.IntakeError):
                    intake.inspect_project(root, entry)

    def test_xpr_internal_macros_two_bds_and_historical_path(self):
        result = intake.inspect_project(self.xpr())
        self.assertEqual(result['status'], 'READ_ONLY')
        source = self.source(result, 'vivado_project')
        self.assertEqual(source['facts']['historical_project_path'], 'old-location/moved.xpr')
        self.assertIsNone(source['facts']['tool_version'])
        self.assertEqual(source['facts']['bd_tool_versions'], ['2025.1'])
        self.assertEqual(source['facts']['format_version'], '7')
        self.assertEqual(source['facts']['filesets'][0]['top_module'], 'system_wrapper')
        self.assertEqual(len([r for r in result['relationships'] if r['kind'] == 'xpr_references_bd']), 2)
        self.assertEqual(len([s for s in result['sources'] if s['kind'] == 'vivado_bd']), 2)
        self.assertIsNone(result['primary_source'])
        self.assertTrue(all(r['state'] == 'INTERNAL' for r in source['facts']['filesets'][0]['resources']))

    def test_bd_user_rtl_ip_connections_and_declared_address(self):
        result = intake.inspect_project(self.json_file('system.bd', self.bd_data()))
        facts = result['sources'][0]['facts']
        self.assertEqual([x['implementation'] for x in facts['instances']], ['declared_ip', 'user_module_reference'])
        self.assertEqual(facts['instances'][1]['reference_name'], 'counter32')
        self.assertEqual(facts['address_segments'][0]['offset_declared'], '0xA0010000')
        self.assertEqual(facts['address_segments'][0]['range_declared'], '64K')
        self.assertEqual(len(facts['connections']), 2)

    def test_xpr_missing_bd_is_partial_not_generated_success(self):
        result = intake.inspect_project(self.xpr(['$PSRCDIR/missing.bd']))
        self.assertEqual(result['status'], 'PARTIAL')
        self.assertIn('MISSING_REFERENCE', codes(result))
        self.assertEqual(result['verification']['generation'], 'NOT_RUN')

    def test_xpr_unknown_macro_and_external_reference_not_followed(self):
        with tempfile.TemporaryDirectory(prefix='epw-intake-external-') as temp:
            external = Path(temp)/'external.bd'
            external.write_text('{broken JSON must not be parsed}', encoding='utf-8')
            result = intake.inspect_project(self.xpr([external.as_posix(), '$OTHER_ROOT/design.bd']))
            self.assertIn('EXTERNAL_REFERENCE_NOT_READ', codes(result))
            self.assertIn('UNRESOLVED_PATH_MACRO', codes(result))
            self.assertNotIn('PARSE_ERROR', codes(result))
            self.assertEqual(len(result['sources']), 1)

    def test_xpr_broken_referenced_bd_retains_project_facts(self):
        p = self.xpr()
        self.write('demo.srcs/sources_1/bd/system/system.bd', '{')
        result = intake.inspect_project(p)
        self.assertEqual(result['status'], 'ERROR')
        self.assertIn('RELATED_SOURCE_ERROR', codes(result))
        self.assertEqual(self.source(result, 'vivado_project')['facts']['device'], 'xczu9eg-ffvb1156-2-e')

    def test_malformed_xml_dtd_and_duplicate_option_are_rejected(self):
        texts = ['<Project>', '<!DOCTYPE Project [<!ENTITY x "value">]><Project/>',
                 '<Project Version="7"><Configuration><Option Name="Part" Val="a"/>'
                 '<Option Name="Part" Val="b"/></Configuration></Project>']
        for text in texts:
            with self.subTest(text=text):
                self.assertEqual(intake.inspect_project(self.write('bad.xpr', text))['status'], 'ERROR')

    def test_native_repeated_list_options_are_not_scalar_conflicts(self):
        path = self.xpr()
        content = path.read_text().replace('</Configuration>',
            '<Option Name="SimTypes" Val="rtl"/><Option Name="SimTypes" Val="gate"/></Configuration>')
        path.write_text(content, encoding='utf-8')
        self.assertEqual(intake.inspect_project(path)['status'], 'READ_ONLY')

    def test_unknown_xpr_and_bd_versions_retain_known_facts(self):
        p = self.xpr()
        p.write_text(p.read_text().replace('Version="7"', 'Version="99"'), encoding='utf-8')
        result = intake.inspect_project(p)
        self.assertIn('FORMAT_UNVERIFIED', codes(result))
        self.assertEqual(self.source(result, 'vivado_project')['facts']['board_part'], 'xilinx.com:zcu102:part0:3.4')
        data = self.bd_data()
        data['design']['design_info']['tool_version'] = '2099.1'
        result = intake.inspect_project(self.json_file('future.bd', data))
        self.assertIn('VERSION_UNVERIFIED', codes(result))
        self.assertEqual(len(result['sources'][0]['facts']['instances']), 2)

    def test_unicode_spaces_and_bom_are_readable(self):
        path = self.write('中文 工程/采样 配置.ioc', '\ufeff'+IOC.read_text())
        result = intake.inspect_project(self.root, path.relative_to(self.root).as_posix())
        self.assertEqual(result['status'], 'READ_ONLY')
        self.assertEqual(result['sources'][0]['path'], '中文 工程/采样 配置.ioc')

    def test_invalid_encoding_is_not_mislabeled_valid(self):
        path = self.write('bad.ioc', '')
        path.write_bytes(b'\xff\x00\x80')
        self.assertEqual(intake.inspect_project(path)['status'], 'ERROR')

    def test_discovery_skips_derived_output_but_keeps_srcs(self):
        self.xpr()
        self.write('build/bad.ioc', 'not a native config')
        self.write('.git/bad.ioc', 'not a native config')
        result = intake.inspect_project(self.root)
        self.assertEqual(len(result['sources']), 3)
        self.assertEqual(result['status'], 'READ_ONLY')

    def test_discovery_bound_is_visible(self):
        self.write('one.ioc', IOC.read_text())
        self.write('two.ioc', IOC.read_text())
        with patch.object(intake, 'MAX_DISCOVERY_ITEMS', 1):
            result = intake.inspect_project(self.root)
        self.assertEqual(result['status'], 'PARTIAL')
        self.assertIn('DISCOVERY_ITEM_LIMIT', codes(result))

    def test_linked_entry_refused_and_directory_link_not_followed(self):
        target = self.write('target.ioc', IOC.read_text())
        link = self.root/'linked.ioc'
        try:
            link.symlink_to(target)
        except OSError:
            # Windows hosts may not grant symlink creation. Exercise the same
            # rejection branch without claiming an OS-created link was tested.
            real_linked = intake.linked
            with patch.object(intake, 'linked', side_effect=lambda p: p == target or real_linked(p)):
                with self.assertRaisesRegex(intake.IntakeError, 'Linked path'):
                    intake.inspect_project(target)
            return
        with self.assertRaisesRegex(intake.IntakeError, 'Linked path'):
            intake.inspect_project(link)
        result = intake.inspect_project(self.root)
        self.assertIn('LINK_NOT_READ', codes(result))
        self.assertEqual(len(result['sources']), 1)

    def test_linked_xpr_reference_not_read(self):
        p = self.xpr()
        real_linked = intake.linked
        bd = self.root/'demo.srcs/sources_1/bd/system/system.bd'
        with patch.object(intake, 'linked', side_effect=lambda path: path == bd or real_linked(path)):
            result = intake.inspect_project(p)
        self.assertIn('LINK_NOT_READ', codes(result))
        self.assertFalse(any(s['path'].endswith('/system/system.bd') for s in result['sources']))

    def test_input_mutation_during_read_invalidates_identity(self):
        path = self.write('one.ioc', IOC.read_text())
        inventory = intake.Inventory(self.root)
        inventory.read(path)
        path.write_text(path.read_text()+'\n# newer source\n', encoding='utf-8')
        inventory.check_sources_unchanged()
        self.assertEqual(inventory.records['one.ioc']['status'], 'ERROR')
        self.assertEqual(inventory.records['one.ioc']['diagnostics'][-1]['code'], 'SOURCE_CHANGED_DURING_READ')

    def test_readonly_no_process_no_writes_and_identity_refresh(self):
        path = self.write('one.ioc', IOC.read_text())
        before = tree_hashes(self.root)
        with (patch('subprocess.Popen', side_effect=AssertionError('No child process allowed')),
              patch.object(Path, 'write_text', side_effect=AssertionError('No write allowed')),
              patch.object(Path, 'write_bytes', side_effect=AssertionError('No write allowed')),
              patch.object(Path, 'mkdir', side_effect=AssertionError('No mkdir allowed'))):
            result = intake.inspect_project(self.root)
        self.assertEqual(before, tree_hashes(self.root))
        identity = result['sources'][0]['sha256']
        path.write_text(path.read_text().replace('SampleQueue,12,', 'SampleQueue,16,'), encoding='utf-8')
        current = intake.inspect_project(path)
        self.assertNotEqual(identity, current['sources'][0]['sha256'])
        self.assertEqual(current['sources'][0]['facts']['rtos']['queues'][0]['capacity_elements'], 16)

    def test_cli_json_and_text_have_same_identity_and_no_install_arguments(self):
        path = self.write('one.ioc', IOC.read_text())
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = intake.main(['inspect', '--project', str(path), '--format', 'json'])
        self.assertEqual(code, 0)
        report = json.loads(output.getvalue())
        self.assertIn(report['sources'][0]['sha256'], intake.format_text(report))
        self.assertIn('NOT_RUN', intake.format_text(report))

    def test_cli_actual_process_utf8_and_argument_error(self):
        path = self.write('中文/工程.ioc', IOC.read_text())
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'ascii'
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), 'inspect', '--project', str(path),
                                 '--format', 'json'], env=env, capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['sources'][0]['path'], '工程.ioc')
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), 'inspect'], capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 2)

    def test_cli_errors_and_empty_directory_are_not_success(self):
        for path in (self.root/'absent.ioc', self.root):
            with self.subTest(path=path), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(intake.main(['inspect', '--project', str(path), '--format', 'json']), 1)

    def legacy_bd(self, version='2020.2', vlnv='xilinx.com:ip:processing_system7:5.5'):
        blocks = ','.join('"address_block":' + json.dumps({'name': name, 'base_address': address,
                             'range': '64K', 'width': '32'})
                          for name, address in [('one', '0x00000000'), ('two', '0x00010000')])
        data = {'design': {'design_info': {'name': 'old', 'tool_version': version, 'device': 'xc7z010clg400-1'},
                'components': {'processing_system7_0': {'vlnv': vlnv,
                    'addressing': {'address_spaces': {'Data': {'local_memory_map': {
                        'address_blocks': '__BLOCKS__'}}}}},
                    'AXIWS2812Strip_0': {'vlnv': 'xilinx.com:user:AXIWS2812Strip:1.0'}},
                'nets': {}, 'interface_nets': {}, 'addressing': {}}}
        return json.dumps(data).replace('"__BLOCKS__"', '{'+blocks+'}')

    def test_legacy_ps7_duplicate_blocks_preserve_every_value_and_order(self):
        path = self.write('old.bd', self.legacy_bd())
        result = intake.inspect_project(path)
        self.assertEqual(result['status'], 'PARTIAL')
        facts = result['sources'][0]['facts']
        section = facts['unexpanded_sections'][0]
        self.assertEqual(section['count'], 2)
        self.assertEqual([b['name'] for b in section['entries']], ['one', 'two'])
        self.assertEqual([b['base_address'] for b in section['entries']], ['0x00000000', '0x00010000'])
        self.assertEqual(facts['instances'][1]['vlnv_library'], 'user')
        self.assertEqual(facts['instances'][1]['implementation'], 'declared_ip')
        self.assertIn('LEGACY_PS7_ADDRESS_BLOCKS_RETAINED', codes(result))
        self.assertIn('2 entries', intake.format_text(result))
        self.assertEqual(result['verification']['tools'], 'NOT_RUN')
        self.assertEqual(result['sources'][0]['execution_profile']['execution_eligibility'], 'NOT_CHECKED')

    def test_legacy_exception_does_not_apply_to_another_version_ip_or_path(self):
        examples = [self.legacy_bd(version='2025.1'), self.legacy_bd(version='2020.1'),
                    self.legacy_bd(vlnv='xilinx.com:ip:processing_system7:5.4'),
                    self.legacy_bd().replace('"local_memory_map"', '"other_map"'),
                    self.legacy_bd().replace('"address_blocks"', '"segments"')]
        for text in examples:
            with self.subTest(text=text):
                report = intake.inspect_project(self.write('old.bd', text))
                self.assertEqual(report['status'], 'ERROR')
                self.assertIn('DUPLICATE_KEY', codes(report))
                self.assertNotIn('LEGACY_PS7_ADDRESS_BLOCKS_RETAINED', codes(report))

    def test_legacy_block_conflicts_and_invalid_structure_still_rejected(self):
        examples = [self.legacy_bd().replace('"name": "two"', '"name": "one"'),
                    self.legacy_bd().replace('"name": "one"', '"name": "one", "name": "other"'),
                    self.legacy_bd().replace('"width": "32"', '"width": []'),
                    self.legacy_bd().replace('"tool_version": "2020.2"', '"tool_version":"2020.2","tool_version":"2020.2"'),
                    self.legacy_bd().replace('"vlnv": "xilinx.com:ip:processing_system7:5.5"',
                                            '"vlnv":"xilinx.com:ip:processing_system7:5.5","vlnv":"other"')]
        for text in examples:
            with self.subTest(text=text):
                self.assertEqual(intake.inspect_project(self.write('old.bd', text))['status'], 'ERROR')

    def test_legacy_does_not_accept_mixed_address_block_keys(self):
        text = self.legacy_bd().replace('"address_block":', '"unexpected":{},"address_block":', 1)
        self.assertIn('DUPLICATE_KEY', codes(intake.inspect_project(self.write('old.bd', text))))

    def test_bd_metadata_survives_unrelated_duplicate_but_status_stays_error(self):
        text = self.legacy_bd().replace('"nets": {}', '"nets": {}, "nets": {}')
        result = intake.inspect_project(self.write('old.bd', text))
        self.assertEqual(result['status'], 'ERROR')
        self.assertEqual(result['sources'][0]['facts']['device'], 'xc7z010clg400-1')

    def test_bd_wrong_metadata_type_is_reported_without_decoder_crash(self):
        for value in (17, None, [], 'version'):
            with self.subTest(value=value):
                report = intake.inspect_project(self.json_file('bad.bd', {'design': {'design_info': value}}))
                self.assertEqual(report['status'], 'ERROR')
                self.assertIn('INVALID_STRUCTURE', codes(report))

    def test_late_structure_failure_retains_completed_sections(self):
        data = self.bd_data()
        data['design']['nets']['bad'] = {'ports': 'not-an-array'}
        result = intake.inspect_project(self.json_file('invalid.bd', data))
        self.assertEqual(result['status'], 'ERROR')
        self.assertEqual(len(result['sources'][0]['facts']['instances']), 2)
        data = self.touch_data()
        data['Application']['Screens'][-1]['Interactions'] = 'not-an-array'
        result = intake.inspect_project(self.json_file('invalid.touchgfx', data))
        self.assertEqual(result['status'], 'ERROR')
        self.assertEqual(len(result['sources'][0]['facts']['screens']), 3)
        self.assertTrue(result['sources'][0]['facts']['screens'][0]['components'])
        result = intake.inspect_project(self.write('invalid.ioc', IOC.read_text().replace(';StatsWorker,', ';SampleFeed,')))
        self.assertEqual(result['status'], 'ERROR')
        self.assertEqual(result['sources'][0]['facts']['device'], 'STM32G474RET6')

    def test_xpr_preserves_first_fileset_on_later_duplicate(self):
        path = self.xpr()
        path.write_text(path.read_text().replace('</FileSets>', '<FileSet Name="sources_1"/></FileSets>'), encoding='utf-8')
        result = intake.inspect_project(path)
        self.assertEqual(result['status'], 'ERROR')
        self.assertEqual(len(self.source(result, 'vivado_project')['facts']['filesets']), 1)

    def test_xpr_repositories_and_reference_categories_are_declarations(self):
        path = self.xpr()
        self.write('ip repo/never-read.py', 'raise RuntimeError("must not run")')
        path.write_text(path.read_text().replace('</Configuration>',
            '<Option Name="IPRepoPath" Val="$PPRDIR/ip repo"/>'
            '<Option Name="IPRepoPath" Val="$PPRDIR/absent"/></Configuration>'), encoding='utf-8')
        result = intake.inspect_project(path)
        facts = self.source(result, 'vivado_project')['facts']
        self.assertEqual([x['state'] for x in facts['ip_repositories']], ['INTERNAL', 'MISSING_REFERENCE'])
        self.assertEqual([x['category'] for x in facts['filesets'][0]['resources']],
                         ['hdl_source', 'block_design_source', 'generated_product_reference', 'block_design_source'])
        self.assertEqual(intake.reference_category('$PSRCDIR/board.xdc'), 'constraint_source')
        self.assertIn('contents NOT_READ', intake.format_text(result))
        self.assertFalse(any(s['path'].endswith('.py') for s in result['sources']))

    def test_ip_repositories_external_unknown_and_link_not_followed(self):
        path = self.xpr()
        self.write('repo/file', 'unread')
        text = path.read_text().replace('</Configuration>',
            '<Option Name="IPRepoPath" Val="$PPRDIR/../outside"/>'
            '<Option Name="IPRepoPath" Val="$OTHER/repo"/>'
            '<Option Name="IPRepoPath" Val="$PPRDIR/repo"/></Configuration>')
        path.write_text(text, encoding='utf-8')
        original = intake.linked
        with patch.object(intake, 'linked', side_effect=lambda p: p == self.root/'repo' or original(p)):
            result = intake.inspect_project(path)
        self.assertTrue({'EXTERNAL_REFERENCE_NOT_READ', 'UNRESOLVED_PATH_MACRO', 'LINK_NOT_READ'} <= codes(result))

    def cmake_fixture(self):
        self.write('CMakeLists.txt', '# project(fake)\ncmake_minimum_required(VERSION 3.22)\n'
                   'set(CMAKE_PROJECT_NAME Trial)\nproject(${CMAKE_PROJECT_NAME})\n'
                   'enable_language(C ASM)\nadd_subdirectory(cmake/stm32cubemx)\n'
                   'include(unknown.cmake)\nexecute_process(COMMAND never-launch)\n'
                   'file(WRITE forbidden.txt "no")\n')
        self.write('cmake/gcc.cmake', 'set(TOOLCHAIN_PREFIX arm-none-eabi-)\nset(CMAKE_C_COMPILER ${TOOLCHAIN_PREFIX}gcc)\n')
        return self.json_file('CMakePresets.json', {'version': 3, 'configurePresets': [
            {'name': 'default', 'hidden': True, 'generator': 'Ninja',
             'toolchainFile': '${sourceDir}/cmake/gcc.cmake'},
            {'name': 'Debug', 'inherits': 'default', 'cacheVariables': {'CMAKE_BUILD_TYPE': 'Debug'}}],
            'buildPresets': [{'name': 'Debug', 'configurePreset': 'Debug'}]})

    def test_cmake_declarations_presets_and_toolchain_without_evaluation(self):
        self.cmake_fixture()
        report = intake.inspect_project(self.root)
        self.assertEqual(report['status'], 'PARTIAL')
        self.assertEqual(len(report['sources']), 3)
        cmake = next(s for s in report['sources'] if s['path'] == 'CMakeLists.txt')
        clues = cmake['facts']['declaration_clues']
        self.assertEqual([x['command_clue'] for x in clues], ['cmake_minimum_required', 'set', 'project',
                                                            'enable_language', 'add_subdirectory', 'include'])
        self.assertIn('${CMAKE_PROJECT_NAME}', clues[2]['line_text'])
        presets = self.source(report, 'cmake_presets')['facts']['configure_presets']
        self.assertEqual(presets[0]['toolchain_reference']['state'], 'INTERNAL')
        self.assertNotIn('toolchain_reference', presets[1])
        self.assertFalse((self.root/'forbidden.txt').exists())
        self.assertIn('inheritance NOT_EVALUATED', intake.format_text(report))

    def test_ioc_cmake_nearby_files_are_candidates_not_authority(self):
        self.cmake_fixture()
        path = self.write('example.ioc', 'MxCube.Version=6.15.0\nMcu.CPN=STM32F103C8T6\nProjectManager.TargetToolchain=CMake\n')
        result = intake.inspect_project(path)
        self.assertEqual(len(result['sources']), 4)
        self.assertIsNone(result['primary_source'])
        self.assertFalse(self.source(result, 'cubemx')['execution_profile']['declared_metadata_match'])
        self.assertTrue(any(r['kind'] == 'co_located_cmake_candidate' for r in result['relationships']))

    def test_cmake_bracket_comments_and_strings_not_listed_as_declarations(self):
        path = self.write('CMakeLists.txt', '#[[\nproject(pretend)\n]]\nset(OTHER [=[\nproject(fake)\n]=])\nproject(real)\n')
        clues = intake.inspect_project(path)['sources'][0]['facts']['declaration_clues']
        self.assertEqual([c['line_text'] for c in clues], ['project(real)'])

    def test_preset_duplicate_and_late_failure_do_not_discard_confirmed_entries(self):
        path = self.json_file('CMakePresets.json', {'version': 3, 'configurePresets': [
            {'name': 'a', 'generator': 'Ninja'}, {'name': 'a', 'generator': 'other'}]})
        report = intake.inspect_project(path)
        self.assertEqual(report['status'], 'ERROR')
        self.assertEqual(report['sources'][0]['facts']['configure_presets'][0]['generator'], 'Ninja')
        self.assertIn('DUPLICATE_KEY', codes(intake.inspect_project(self.write('CMakePresets.json', '{"version":3,"version":3}'))))

    def test_preset_includes_inheritance_relative_and_environment_paths_unexpanded(self):
        path = self.json_file('CMakePresets.json', {'version': 99, 'include': ['../not-read.json'], 'configurePresets': [
            {'name': 'relative', 'toolchainFile': 'tool.cmake'},
            {'name': 'env', 'toolchainFile': '$env{SDK}/tool.cmake'},
            {'name': 'missing', 'toolchainFile': '${sourceDir}/missing.cmake'},
            {'name': 'escape', 'toolchainFile': '${sourceDir}/../outside.cmake'}]})
        report = intake.inspect_project(path)
        self.assertEqual(report['status'], 'PARTIAL')
        presets = report['sources'][0]['facts']['configure_presets']
        self.assertEqual([p['toolchain_reference']['state'] for p in presets],
                         ['UNRESOLVED_RELATIVE_TOOLCHAIN', 'UNRESOLVED_PATH_MACRO', 'MISSING_REFERENCE', 'EXTERNAL_REFERENCE_NOT_READ'])
        self.assertEqual(len(report['sources']), 1)

    def test_toolchain_cache_declaration_and_linked_target(self):
        toolchain = self.write('tool.cmake', 'set(CMAKE_SYSTEM_PROCESSOR arm)\n')
        path = self.json_file('CMakeUserPresets.json', {'version': 3, 'configurePresets': [{
            'name': 'local', 'cacheVariables': {'CMAKE_TOOLCHAIN_FILE': {'type': 'FILEPATH', 'value': '${sourceDir}/tool.cmake'}}}]})
        self.assertEqual(len(intake.inspect_project(path)['sources']), 2)
        original = intake.linked
        with patch.object(intake, 'linked', side_effect=lambda p: p == toolchain or original(p)):
            self.assertIn('LINK_NOT_READ', codes(intake.inspect_project(path)))

    def test_new_inputs_no_process_no_write_and_exact_hashes(self):
        self.cmake_fixture()
        self.write('legacy.bd', self.legacy_bd())
        self.xpr()
        before = tree_hashes(self.root)
        with (patch('subprocess.Popen', side_effect=AssertionError('No child process allowed')),
              patch('os.system', side_effect=AssertionError('No shell allowed')),
              patch.object(Path, 'write_text', side_effect=AssertionError('No write allowed')),
              patch.object(Path, 'write_bytes', side_effect=AssertionError('No write allowed')),
              patch.object(Path, 'mkdir', side_effect=AssertionError('No mkdir allowed'))):
            result = intake.inspect_project(self.root)
        self.assertNotEqual(result['status'], 'ERROR')
        self.assertEqual(before, tree_hashes(self.root))
        for source in result['sources']:
            self.assertEqual(source['sha256'], before[source['path']])


if __name__ == '__main__':
    unittest.main()
