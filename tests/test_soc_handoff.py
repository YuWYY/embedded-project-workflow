# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
"""Original synthetic metadata fixtures: these are not vendor build evidence."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'skills/embedded-project-workflow/scripts/soc_handoff.py'
SPEC = importlib.util.spec_from_file_location('soc_handoff', SCRIPT)
soc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(soc)

PART = 'xczu9eg-ffvb1156-2-e'
PARAMS = {'C_IS_DUAL': 1, 'C_GPIO_WIDTH': 2, 'C_GPIO2_WIDTH': 32,
          'C_ALL_INPUTS': 0, 'C_ALL_OUTPUTS': 1, 'C_ALL_INPUTS_2': 1, 'C_ALL_OUTPUTS_2': 0}


def write_bd(path, base=0xa0000000, width=2):
    params = dict(PARAMS, C_GPIO_WIDTH=width)
    obj = {'design': {'design_info': {'device': PART, 'tool_version': '2025.1'},
                      'components': {'axi_gpio_0': {'vlnv': 'xilinx.com:ip:axi_gpio:2.0',
                                      'parameters': {k: {'value': str(v)} for k, v in params.items()}}},
                      'addressing': {'/zynq_ultra_ps_e_0': {'address_spaces': {'Data': {'segments': {
                          'SEG_axi_gpio_0_Reg': {'address_block': '/axi_gpio_0/S_AXI/Reg',
                                                 'offset': hex(base), 'range': '64K'}}}}}}}}
    path.write_text(json.dumps(obj), encoding='utf-8')


def write_xsa(path, base=0xa0000000, width=2):
    params = dict(PARAMS, C_GPIO_WIDTH=width)
    parameters = ''.join('<PARAMETER NAME="'+k+'" VALUE="'+str(v)+'"/>' for k, v in params.items())
    hwh = ('<EDKSYSTEM VIVADOVERSION="2025.1"><SYSTEMINFO DEVICE="xczu9eg" PACKAGE="ffvb1156" SPEEDGRADE="-2"/>'
           '<MODULES><MODULE INSTANCE="axi_gpio_0" VLNV="xilinx.com:ip:axi_gpio:2.0"><PARAMETERS>'+parameters+
           '</PARAMETERS></MODULE><MODULE INSTANCE="psu_cortexa53_0"><MEMORYMAP><MEMRANGE INSTANCE="axi_gpio_0" '+
           'BASEVALUE="'+hex(base)+'" HIGHVALUE="'+hex(base+65535)+'"/></MEMORYMAP></MODULE></MODULES></EDKSYSTEM>')
    manifest = {'generatedVersion': '2025.1', 'devices': [{'part': {'name': PART}}],
                'board': {'boardPart': 'xilinx.com:zcu102:part0:3.4'}}
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('system.hwh', hwh)
        archive.writestr('xsa.json', json.dumps(manifest))
        archive.writestr('hwdef.xml', '<Project><SYSTEMINFO PART="'+PART+'"/>'
            '<File Type="HW_HANDOFF" Name="system.hwh" BD_TYPE="DEFAULT_BD"/></Project>')


def gpio_dts(base, width=2):
    return '''axi_gpio_0: gpio@%x {
        compatible = "xlnx,xps-gpio-1.00.a";
        reg = <0x0 0x%x 0x0 0x10000>;
        xlnx,is-dual = <1>; xlnx,gpio-width = <%d>; xlnx,gpio2-width = <32>;
        xlnx,all-inputs = <0>; xlnx,all-outputs = <1>;
        xlnx,all-inputs-2 = <1>; xlnx,all-outputs-2 = <0>;
    };''' % (base, base, width)


def write_sdt(directory, base=0xa0000000, width=2):
    directory.mkdir(exist_ok=True)
    (directory/'system-top.dts').write_text('/dts-v1/;\n#include "pl.dtsi"\n/ { device_id = "xczu9eg"; };\n', encoding='utf-8')
    (directory/'pl.dtsi').write_text('/ { #address-cells = <2>; #size-cells = <2>;\n'
                                    'amba_pl: amba_pl@0 { #address-cells = <2>; #size-cells = <2>; ranges;\n'+
                                    gpio_dts(base, width)+'\n}; };', encoding='utf-8')
    return directory/'system-top.dts'


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.inputs = self.root/'inputs'; self.inputs.mkdir()
        self.bd = self.inputs/'system.bd'; self.xsa = self.inputs/'system.xsa'
        write_bd(self.bd); write_xsa(self.xsa)
        self.sdt = write_sdt(self.inputs/'sdt')
        self.run_id = 0

    def tearDown(self):
        self.temp.cleanup()

    def arguments(self, command='inspect', *extra):
        self.run_id += 1
        output = self.root/('report-'+str(self.run_id))
        return [command, '--bd', str(self.bd), '--xsa', str(self.xsa), '--sdt', str(self.sdt),
                '--report-dir', str(output), *extra], output

    def invoke(self, command='inspect', *extra):
        args, output = self.arguments(command, *extra)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            status = soc.main(args)
        record = json.loads((output/'result.json').read_text()) if (output/'result.json').exists() else None
        return status, record, output

    def test_three_layer_semantics_and_identity(self):
        code, record, out = self.invoke('verify', '--expected-base', '0xa0000000', '--expected-range', '0x10000')
        self.assertEqual(code, 0)
        self.assertEqual(record['terminal_state'], 'PASS')
        self.assertEqual(record['artifacts']['sdt']['base'], 0xa0000000)
        self.assertIsNone(record['actual_process_exit_code'])
        self.assertEqual(set(record['sources']['sdt']['dependencies']), {'system-top.dts', 'pl.dtsi'})
        code, again, _ = self.invoke('verify', '--record', str(out/'result.json'))
        self.assertEqual(code, 0)

    def test_stale_bd_xsa(self):
        write_bd(self.bd, 0xa0010000)
        code, record, _ = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(record['failure_type'], 'STALE_BD_XSA')
        self.assertEqual(record['failure_stage'], 'consistency')
        self.assertEqual(record['stages']['source_identity']['state'], 'NOT_RUN')
        self.assertEqual(record['sources']['bd']['sha256'], soc.sha(self.bd))
        self.assertIn('pl.dtsi', record['sources']['sdt']['dependencies'])

    def test_stale_xsa_sdt(self):
        write_bd(self.bd, 0xa0010000); write_xsa(self.xsa, 0xa0010000)
        code, record, _ = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(record['failure_type'], 'STALE_XSA_SDT')

    def test_new_three_layer_consistency(self):
        write_bd(self.bd, 0xa0010000); write_xsa(self.xsa, 0xa0010000)
        write_sdt(self.sdt.parent, 0xa0010000)
        code, record, _ = self.invoke('verify', '--expected-base', '0xa0010000')
        self.assertEqual(code, 0)

    def test_width_mismatch_same_address(self):
        write_sdt(self.sdt.parent, width=4)
        code, record, _ = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(record['failure_type'], 'STALE_XSA_SDT')
        self.assertIn('gpio_width', record['error'])

    def test_record_rejects_new_source_even_same_semantics(self):
        _, _, out = self.invoke()
        self.bd.write_text(self.bd.read_text()+'\n')
        code, record, _ = self.invoke('verify', '--record', str(out/'result.json'))
        self.assertEqual(code, 1)
        self.assertEqual(record['failure_type'], 'STALE_RECORD')

    def test_record_rejects_unconfirmed_state(self):
        old = self.root/'old'; old.mkdir()
        (old/'record.json').write_text('{"terminal_state":"RUNNING"}')
        code, record, _ = self.invoke('verify', '--record', str(old/'record.json'))
        self.assertEqual(code, 1)
        self.assertEqual(record['failure_type'], 'UNCONFIRMED_RECORD')

    def test_missing_product_records_not_started_process(self):
        self.xsa.unlink()
        code, record, _ = self.invoke()
        self.assertEqual(code, 1)
        self.assertIsNone(record['actual_process_exit_code'])
        self.assertEqual(record['terminal_state'], 'FAIL')
        self.assertEqual(record['failure_stage'], 'xsa')
        self.assertEqual(record['stages']['bd']['state'], 'PASS')
        self.assertEqual(record['stages']['xsa']['state'], 'FAIL')

    def test_native_format_version_is_not_guessed(self):
        self.bd.write_text(self.bd.read_text().replace('2025.1', '2024.2'))
        code, record, _ = self.invoke()
        self.assertEqual(code, 1)
        self.assertIn('2025.1', record['error'])

    def test_scoped_smartconnect_handoff_is_not_confused_with_top(self):
        with zipfile.ZipFile(self.xsa) as archive:
            entries = {name: archive.read(name) for name in archive.namelist()}
        entries['hwdef.xml'] = entries['hwdef.xml'].replace(b'</Project>',
            b'<File Type="HW_HANDOFF" Name="scoped.hwh" BD_TYPE="SCOPED_BD"/></Project>')
        entries['scoped.hwh'] = b'<EDKSYSTEM/>'
        with zipfile.ZipFile(self.xsa, 'w') as archive:
            for name, value in entries.items(): archive.writestr(name, value)
        code, record, _ = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(record['artifacts']['xsa']['hwh_member'], 'system.hwh')

    def test_undeclared_handoff_is_rejected(self):
        with zipfile.ZipFile(self.xsa, 'a') as archive:
            archive.writestr('other.hwh', '<EDKSYSTEM/>')
        with self.assertRaisesRegex(soc.HandoffError, 'hwdef.xml disagree'):
            soc.parse_xsa(self.xsa, 'axi_gpio_0')

    def test_known_amendment_changes_effective_node(self):
        with self.sdt.open('a') as stream:
            stream.write('\n&axi_gpio_0 { xlnx,gpio-width = <4>; };')
        values, _ = soc.parse_sdt(self.sdt, 'axi_gpio_0')
        self.assertEqual(values['gpio_width'], 4)

    def test_unknown_amendment_fails(self):
        with self.sdt.open('a') as stream:
            stream.write('\n&missing_gpio { xlnx,gpio-width = <2>; };')
        with self.assertRaisesRegex(soc.HandoffError, 'Unresolved'):
            soc.parse_sdt(self.sdt, 'axi_gpio_0')

    def test_macro_in_address_cannot_pass_via_other_string(self):
        path = self.sdt.parent/'pl.dtsi'
        text = path.read_text().replace('reg = <0x0 0xa0000000', 'reg = <0x0 OLD_ADDRESS')
        path.write_text(text+'\n/* 0xa0000000 is the expected address */')
        with self.assertRaisesRegex(soc.HandoffError, 'integer expression'):
            soc.parse_sdt(self.sdt, 'axi_gpio_0')

    def test_parent_ranges_translate_address(self):
        path = self.sdt.parent/'pl.dtsi'
        text = path.read_text().replace('ranges;', 'ranges = <0x0 0x1000 0x0 0xa0000000 0x0 0x20000>;')
        text = text.replace('reg = <0x0 0xa0000000', 'reg = <0x0 0x1000')
        path.write_text(text)
        values, _ = soc.parse_sdt(self.sdt, 'axi_gpio_0')
        self.assertEqual(values['base'], 0xa0000000)
        self.assertEqual(values['range'], 65536)

    def test_missing_or_partial_parent_mapping_fails(self):
        path = self.sdt.parent/'pl.dtsi'
        original = path.read_text()
        for ranges in ('', 'ranges = <0 0xa0000000 0 0xa0000000 0 0x100>;'):
            with self.subTest(ranges=ranges):
                path.write_text(original.replace('ranges;', ranges))
                with self.assertRaises(soc.HandoffError):
                    soc.parse_sdt(self.sdt, 'axi_gpio_0')

    def test_one_cell_parent_address_and_size(self):
        path = self.sdt.parent/'pl.dtsi'
        text = path.read_text().replace('#address-cells = <2>', '#address-cells = <1>')
        text = text.replace('#size-cells = <2>', '#size-cells = <1>')
        text = text.replace('reg = <0x0 0xa0000000 0x0 0x10000>', 'reg = <0xa0000000 0x10000>')
        path.write_text(text)
        values, _ = soc.parse_sdt(self.sdt, 'axi_gpio_0')
        self.assertEqual(values['base'], 0xa0000000)

    def test_disabled_gpio_is_not_available(self):
        with self.sdt.open('a') as stream:
            stream.write('\n&axi_gpio_0 { status = "disabled"; };')
        with self.assertRaisesRegex(soc.HandoffError, 'disabled'):
            soc.parse_sdt(self.sdt, 'axi_gpio_0')

    def test_deleted_gpio_is_not_present(self):
        with self.sdt.open('a') as stream:
            stream.write('\n&amba_pl { /delete-node/ gpio@a0000000; };')
        with self.assertRaisesRegex(soc.HandoffError, 'effective SDT'):
            soc.parse_sdt(self.sdt, 'axi_gpio_0')

    def test_duplicate_instance_and_property_rejected(self):
        path = self.sdt.parent/'pl.dtsi'
        original = path.read_text()
        path.write_text(original.replace('xlnx,is-dual = <1>;', 'xlnx,is-dual = <1>; xlnx,is-dual = <0>;'))
        with self.assertRaisesRegex(soc.HandoffError, 'Duplicate'):
            soc.parse_sdt(self.sdt, 'axi_gpio_0')

    def test_duplicate_gpio_node_cannot_silently_override(self):
        with self.sdt.open('a') as stream:
            stream.write('\n/ { amba_pl@0 { '+gpio_dts(0xa0000000, 4)+' }; };')
        with self.assertRaisesRegex(soc.HandoffError, 'Duplicate GPIO'):
            soc.parse_sdt(self.sdt, 'axi_gpio_0')

    def test_second_gpio_instance_rejected(self):
        with self.sdt.open('a') as stream:
            stream.write('\n/ { amba_pl@0 { '+gpio_dts(0xa0010000).replace('axi_gpio_0:', 'axi_gpio_1:')+' }; };')
        with self.assertRaisesRegex(soc.HandoffError, 'one AXI GPIO'):
            soc.parse_sdt(self.sdt, 'axi_gpio_0')

    def test_include_edit_invalidates_prior_record(self):
        _, _, output = self.invoke()
        path = self.sdt.parent/'pl.dtsi'
        path.write_text(path.read_text()+'\n/* human edit */\n')
        code, record, _ = self.invoke('verify', '--record', str(output/'result.json'))
        self.assertEqual(code, 1)
        self.assertEqual(record['failure_type'], 'STALE_RECORD')

    def test_bd_hash_changed_during_parse_fails(self):
        real = soc.parse_bd
        def moving_input(path, instance):
            result = real(path, instance)
            path.write_text(path.read_text()+'\n')
            return result
        with mock.patch.object(soc, 'parse_bd', side_effect=moving_input):
            code, record, _ = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(record['failure_type'], 'INPUT_CHANGED')

    def test_include_escape_and_recursive_include_rejected(self):
        self.sdt.write_text('#include "../escape.dtsi"\n')
        with self.assertRaises(soc.HandoffError):
            soc.parse_sdt(self.sdt, 'axi_gpio_0')
        self.sdt.write_text('#include "system-top.dts"\n')
        with self.assertRaisesRegex(soc.HandoffError, 'Recursive'):
            soc.parse_sdt(self.sdt, 'axi_gpio_0')

    def test_report_cannot_overwrite_inputs(self):
        args, _ = self.arguments()
        args[args.index('--report-dir')+1] = str(self.inputs/'reports')
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(soc.main(args), 2)
        self.assertFalse((self.inputs/'reports').exists())

    def test_report_cannot_be_sibling_under_native_project(self):
        nested = self.inputs/'native/project.srcs/sources_1/bd/system/system.bd'
        nested.parent.mkdir(parents=True)
        write_bd(nested)
        args, _ = self.arguments()
        args[args.index('--bd')+1] = str(nested)
        output = self.inputs/'native/reports'
        args[args.index('--report-dir')+1] = str(output)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(soc.main(args), 2)
        self.assertFalse(output.exists())

    def test_invalid_argument_rejected_before_writing(self):
        args, output = self.arguments('verify', '--expected-range', '0')
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            soc.main(args)
        self.assertEqual(caught.exception.code, 2)
        self.assertFalse(output.exists())

    def test_initial_record_failure_does_not_parse_inputs(self):
        with mock.patch.object(soc, 'atomic_json', side_effect=OSError('disk unavailable')), \
             mock.patch.object(soc, 'parse_bd') as parse:
            code, _, _ = self.invoke()
        self.assertEqual(code, 1)
        parse.assert_not_called()

    def test_final_record_failure_cannot_return_success(self):
        real = soc.atomic_json
        def fail_final(path, value):
            if value['terminal_state'] in ('PASS', 'FAIL'):
                raise OSError('persistent final write failure')
            real(path, value)
        with mock.patch.object(soc, 'atomic_json', side_effect=fail_final):
            code, record, _ = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(record['terminal_state'], 'RUNNING')

    def test_recoverable_final_save_failure_names_persist_phase(self):
        real = soc.atomic_json
        def fail_success_save(path, value):
            if value['terminal_state'] == 'PASS':
                raise OSError('final success save failed')
            real(path, value)
        with mock.patch.object(soc, 'atomic_json', side_effect=fail_success_save):
            code, record, _ = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(record['failure_stage'], 'persist_result')
        self.assertEqual(record['terminal_state'], 'FAIL')

    def test_final_source_check_failure_names_identity_stage(self):
        with mock.patch.object(soc, 'require_unchanged', side_effect=soc.HandoffError('INPUT_CHANGED', 'late edit')):
            code, record, _ = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(record['failure_stage'], 'source_identity')
        self.assertEqual(record['stages']['source_identity']['state'], 'FAIL')

    def test_invalid_instance_and_existing_report_are_parameter_errors(self):
        args, output = self.arguments('inspect', '--instance', 'invalid/instance')
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(soc.main(args), 2)
        self.assertFalse(output.exists())
        args, output = self.arguments()
        output.mkdir()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(soc.main(args), 2)

    def test_interruption_has_null_process_exit_and_retained_stages(self):
        with mock.patch.object(soc, 'parse_xsa', side_effect=KeyboardInterrupt):
            code, record, _ = self.invoke()
        self.assertEqual(code, 130)
        self.assertEqual(record['terminal_state'], 'INTERRUPTED')
        self.assertEqual(record['stages']['bd']['state'], 'PASS')
        self.assertEqual(record['stages']['xsa']['state'], 'FAIL')
        self.assertEqual(record['stages']['sdt']['state'], 'NOT_RUN')
        self.assertIsNone(record['actual_process_exit_code'])

    def test_doctor_does_not_claim_directory_means_working_vitis(self):
        tool = self.root/'tools'; (tool/'Vitis').mkdir(parents=True)
        (tool/'Vitis/sourceVersion.txt').write_text('release: 2025.1.0\n')
        result = soc.doctor(tool)
        self.assertEqual(result['execution'], 'NOT_RUN')
        self.assertEqual(result['vitis_platform_bsp_app'], 'NOT_RUN')
        self.assertEqual(result['a53_baremetal_compiler']['state'], 'NOT_FOUND_IN_SEARCH_ROOTS')
        self.assertEqual(result['components']['vitis_launcher']['state'], 'MISSING')


if __name__ == '__main__':
    unittest.main()
