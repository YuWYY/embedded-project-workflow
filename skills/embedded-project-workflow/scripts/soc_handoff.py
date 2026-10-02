#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
"""Read-only Vivado 2025.1 MPSoC / dual AXI GPIO handoff inspection.

This is an intentionally narrow metadata checker, not a DTS compiler, Vivado
executor, platform builder or board test. No vendor process is started. Each
command writes a new report directory, never modifies its input artifacts.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
import zipfile


class HandoffError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def require(condition, message, code='UNSUPPORTED_INPUT'):
    if not condition:
        raise HandoffError(code, message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def no_links(path):
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            require(not part.is_symlink() and not (getattr(part.lstat(), 'st_file_attributes', 0) & 0x400),
                    'Links/reparse points are unsupported: '+str(part), 'UNSAFE_PATH')
    return path


def read_bytes(path):
    path = no_links(path)
    require(path.is_file(), 'Required input file is absent: '+str(path), 'MISSING_PRODUCT')
    return path.read_bytes()


def input_boundary(path):
    """Protect a native project, not just the deeply nested BD directory."""
    if path.is_dir():
        return path
    for parent in path.parents:
        if parent.name.endswith('.srcs'):
            return parent.parent
        if list(parent.glob('*.xpr')):
            return parent
    return path.parent


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key: '+key)
        result[key] = value
    return result


def json_data(data):
    return json.loads(data.decode('utf-8-sig'), object_pairs_hook=unique_object)


def number(value):
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    text = str(value).strip()
    match = re.fullmatch(r'(0[xX][0-9a-fA-F]+|[0-9]+)([KMGTP]?)', text)
    require(match is not None, 'Unsupported integer expression: '+text)
    return int(match[1], 16 if match[1].lower().startswith('0x') else 10) * (1024 ** ('KMGTP'.index(match[2])+1) if match[2] else 1)


def nonnegative_argument(value):
    try:
        result = int(value, 0)
    except ValueError:
        raise argparse.ArgumentTypeError('Expected an integer, optionally prefixed with 0x')
    if result < 0:
        raise argparse.ArgumentTypeError('Expected a non-negative integer')
    return result


def positive_argument(value):
    result = nonnegative_argument(value)
    if result == 0:
        raise argparse.ArgumentTypeError('Expected a positive integer')
    return result


def atomic_json(path, value):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name+'.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


# AXI GPIO 2.0 defaults; Vivado omits unchanged parameters from BD JSON.
# Source: AMD installed data/ip/xilinx/axi_gpio_v2_0/component.xml.
GPIO_DEFAULTS = {'C_IS_DUAL': 0, 'C_GPIO_WIDTH': 32, 'C_GPIO2_WIDTH': 32,
                 'C_ALL_INPUTS': 0, 'C_ALL_OUTPUTS': 0,
                 'C_ALL_INPUTS_2': 0, 'C_ALL_OUTPUTS_2': 0}
PARAM_NAMES = {'C_IS_DUAL': 'is_dual', 'C_GPIO_WIDTH': 'gpio_width',
               'C_GPIO2_WIDTH': 'gpio2_width', 'C_ALL_INPUTS': 'all_inputs',
               'C_ALL_OUTPUTS': 'all_outputs', 'C_ALL_INPUTS_2': 'all_inputs2',
               'C_ALL_OUTPUTS_2': 'all_outputs2'}
GPIO_FIELDS = ('base', 'range', *PARAM_NAMES.values())


def gpio_parameters(parameters, defaults=False):
    values = {}
    used_defaults = []
    for key, output in PARAM_NAMES.items():
        item = parameters.get(key)
        if item is None:
            require(defaults, 'Missing AXI GPIO parameter: '+key)
            item = GPIO_DEFAULTS[key]
            used_defaults.append(key)
        if isinstance(item, dict):
            item = item['value']
        values[output] = number(item)
    require(values['is_dual'] == 1, 'Only dual-channel AXI GPIO is supported')
    for key in ('gpio_width', 'gpio2_width'):
        require(1 <= values[key] <= 32, 'Invalid GPIO width: '+key)
    for key in ('all_inputs', 'all_outputs', 'all_inputs2', 'all_outputs2'):
        require(values[key] in (0, 1), 'Invalid GPIO direction: '+key)
    require(not (values['all_inputs'] and values['all_outputs']) and
            not (values['all_inputs2'] and values['all_outputs2']), 'Contradictory GPIO directions')
    return values, used_defaults


def dictionaries(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from dictionaries(child)
    elif isinstance(value, list):
        for child in value:
            yield from dictionaries(child)


def parse_bd(path, instance):
    root = json_data(read_bytes(path))
    design = root['design']
    info = design['design_info']
    require(info['tool_version'] == '2025.1', 'Only Vivado 2025.1 BD JSON is supported')
    require(str(info['device']).startswith('xczu'), 'Only MPSoC BD input is supported')
    components = design['components']
    require(sum(c.get('vlnv') == 'xilinx.com:ip:axi_gpio:2.0' for c in components.values()) == 1,
            'Only one AXI GPIO instance is supported by this profile')
    require(instance in components, 'GPIO instance absent from top-level BD: '+instance)
    component = components[instance]
    require(component.get('vlnv') == 'xilinx.com:ip:axi_gpio:2.0', 'Expected AXI GPIO 2.0')
    require(not any('components' in c for c in components.values()), 'Hierarchical BD is outside the narrow profile')
    values, defaults = gpio_parameters(component.get('parameters', {}), defaults=True)
    matches = []
    for item in dictionaries(design.get('addressing', {})):
        # Native assigned-address records refer to the slave address segment.
        references = [v for k, v in item.items() if k in ('address_block', 'slave_segment', 'address_segment')]
        if any(isinstance(v, str) and v.strip('/').startswith(instance+'/') for v in references):
            if 'offset' in item and 'range' in item:
                matches.append((number(item['offset']), number(item['range'])))
            elif 'base_address' in item and 'range' in item:
                matches.append((number(item['base_address']), number(item['range'])))
    require(len(matches) == 1, 'Expected one explicit assigned GPIO address in BD; found '+str(len(matches)))
    values.update(instance=instance, part=info['device'], tool_version=info['tool_version'],
                  base=matches[0][0], range=matches[0][1], defaults_used=defaults)
    return values


def parse_xsa(path, instance):
    read_bytes(path)
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), 'Duplicate XSA zip members')
        hwh_names = [n for n in names if n.endswith('.hwh')]
        require(hwh_names and 'xsa.json' in names and 'hwdef.xml' in names, 'Expected HWH, hwdef.xml and xsa.json in XSA')
        for name in (*hwh_names, 'xsa.json', 'hwdef.xml'):
            require(archive.getinfo(name).file_size <= 64*1024*1024, 'Oversized XSA metadata member')
        def xml_member(name):
            data = archive.read(name)
            require(b'<!DOCTYPE' not in data and b'<!ENTITY' not in data, 'XML declarations are unsupported')
            return ET.fromstring(data)
        hwdef = xml_member('hwdef.xml')
        handoffs = [n for n in hwdef.findall('File') if n.get('Type') == 'HW_HANDOFF']
        top_handoffs = [n for n in handoffs if n.get('BD_TYPE') == 'DEFAULT_BD']
        require(len(top_handoffs) == 1, 'Expected one DEFAULT_BD hardware handoff in hwdef.xml')
        declared = [n.get('Name') for n in handoffs]
        require(len(declared) == len(set(declared)) and set(declared) == set(hwh_names), 'HWH members and hwdef.xml disagree')
        hwh_name = top_handoffs[0].get('Name')
        hwh = xml_member(hwh_name)
        manifest = json_data(archive.read('xsa.json'))
    require(hwh.attrib.get('VIVADOVERSION') == '2025.1' and manifest.get('generatedVersion') == '2025.1',
            'Only Vivado 2025.1 XSA metadata is supported')
    devices = manifest.get('devices', [])
    require(len(devices) == 1, 'Expected one XSA device')
    part = devices[0]['part']['name']
    hwdef_info = hwdef.find('SYSTEMINFO')
    require(hwdef_info is not None and hwdef_info.get('PART') == part, 'XSA hwdef and manifest part disagree', 'XSA_INTERNAL_MISMATCH')
    modules = [n for n in hwh.findall('.//MODULE') if n.attrib.get('INSTANCE') == instance]
    require(len(modules) == 1, 'Expected one HWH GPIO instance')
    module = modules[0]
    require(module.attrib.get('VLNV') == 'xilinx.com:ip:axi_gpio:2.0', 'Expected AXI GPIO 2.0 in HWH')
    parameters = {}
    for node in module.findall('./PARAMETERS/PARAMETER'):
        key = node.attrib['NAME']
        require(key not in parameters, 'Duplicate HWH parameter: '+key)
        parameters[key] = node.attrib['VALUE']
    values, _ = gpio_parameters(parameters)
    mappings = set()
    for node in hwh.findall('.//MEMRANGE'):
        if node.attrib.get('INSTANCE', '').strip('/') == instance:
            base, high = number(node.attrib['BASEVALUE']), number(node.attrib['HIGHVALUE'])
            require(high >= base, 'Invalid HWH address range')
            mappings.add((base, high-base+1))
    require(len(mappings) == 1, 'Expected one consistent HWH GPIO address range')
    base, size = next(iter(mappings))
    system = hwh.find('SYSTEMINFO')
    require(system is not None, 'HWH SYSTEMINFO is absent')
    require(part.startswith(system.attrib['DEVICE']+'-'+system.attrib['PACKAGE']+system.attrib['SPEEDGRADE']),
            'XSA manifest and HWH device disagree', 'XSA_INTERNAL_MISMATCH')
    values.update(instance=instance, part=part, base=base, range=size,
                  board=manifest.get('board', {}).get('boardPart'), hwh_member=hwh_name)
    return values


COMMENT = re.compile(r'("(?:\\.|[^"\\])*")|/\*.*?\*/|//[^\n]*', re.S)
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|[A-Za-z0-9_#.,+@/\-]+|[{};=:<>\[\]&()|~*!?%^]')


def strip_comments(text):
    return COMMENT.sub(lambda m: m[1] if m[1] is not None else ' ', text)


class Node:
    def __init__(self, name, parent=None):
        self.name, self.parent = name, parent
        self.properties, self.children, self.labels = {}, {}, set()

    @property
    def path(self):
        return '/' if self.parent is None else self.parent.path.rstrip('/')+'/'+self.name


class DeviceTree:
    """Literal generated DTS subset with local includes and resolved amendments.

    Noncritical property expressions are kept opaque. Numerical fields used by
    this checker must be literal 32-bit cells; unresolved macros never pass.
    Plugin overlays, preprocessor conditions in DTS and unresolved targets fail.
    """
    def __init__(self, top):
        self.top = no_links(top)
        self.root_dir = self.top.parent
        self.dependencies, self.labels = {}, {}
        self.root = Node('/')
        text = self.expand(self.top, [])
        tokens = []
        offset = 0
        for match in TOKEN.finditer(text):
            require(not text[offset:match.start()].strip(), 'Unsupported DTS token: '+text[offset:match.start()])
            tokens.append(match.group())
            offset = match.end()
        require(not text[offset:].strip(), 'Unsupported trailing DTS text')
        self.tokens, self.index = tokens, 0
        while self.index < len(tokens):
            if self.peek() == '/dts-v1/':
                self.take(); self.expect(';')
            elif self.peek() == '/':
                self.take(); self.expect('{'); self.body(self.root); self.expect(';')
            elif self.peek() == '&':
                self.take()
                label = self.take()
                require(label in self.labels, 'Unresolved DTS amendment target: '+label)
                self.expect('{'); self.body(self.labels[label]); self.expect(';')
            else:
                raise HandoffError('UNSUPPORTED_INPUT', 'Unsupported DTS top-level form: '+self.peek())

    def expand(self, path, stack):
        path = no_links(path)
        require(path.is_relative_to(self.root_dir), 'External DTS include is unsupported', 'UNSAFE_PATH')
        require(path not in stack, 'Recursive DTS include')
        data = read_bytes(path)
        self.dependencies[path.relative_to(self.root_dir).as_posix()] = hashlib.sha256(data).hexdigest()
        text = strip_comments(data.decode('utf-8-sig'))
        # Binding headers only define tokens for unrelated properties. We track
        # their identity, but do not claim to evaluate their preprocessor macros.
        if path.suffix == '.h':
            require(all(not line.strip() or line.lstrip().startswith('#') or
                        (i > 0 and lines[i-1].rstrip().endswith('\\'))
                        for lines in [text.splitlines()] for i, line in enumerate(lines)),
                    'Unsupported non-preprocessor text in binding header')
            for match in re.finditer(r'^\s*#include\s+["<]([^">]+)[">]', text, re.M):
                include_path = path.parent/match[1]
                require(include_path.is_relative_to(self.root_dir), 'External binding include', 'UNSAFE_PATH')
                self.expand(include_path, stack+[path])
            return ''
        include = re.compile(r'^\s*#include\s+["<]([^">]+)[">]\s*$|/include/\s*"([^"]+)"\s*;?', re.M)
        def replace(match):
            name = match[1] or match[2]
            require(not Path(name).is_absolute() and '..' not in Path(name).parts and ':' not in name,
                    'External DTS include is unsupported', 'UNSAFE_PATH')
            return '\n'+self.expand(path.parent/name, stack+[path])+'\n'
        text = include.sub(replace, text)
        require(not re.search(r'^\s*#(?:if|else|endif|define|undef|include|error|pragma)\b', text, re.M),
                'DTS preprocessor directives need a real preprocessing step; unsupported here')
        return text

    def peek(self):
        require(self.index < len(self.tokens), 'Truncated DTS')
        return self.tokens[self.index]

    def take(self):
        result = self.peek(); self.index += 1
        return result

    def expect(self, token):
        require(self.take() == token, 'Expected DTS token '+token)

    def body(self, node):
        seen = set()
        while self.peek() != '}':
            name = self.take()
            if name == '/delete-node/':
                child = self.take(); self.expect(';')
                require(child in node.children, 'Delete of absent DTS node: '+child)
                victim = node.children.pop(child)
                for label, target in list(self.labels.items()):
                    if target.path == victim.path or target.path.startswith(victim.path+'/'):
                        del self.labels[label]
                continue
            if name == '/delete-property/':
                key = self.take(); self.expect(';')
                require(key in node.properties, 'Delete of absent DTS property: '+key)
                del node.properties[key]
                continue
            labels = []
            while self.peek() == ':':
                labels.append(name); self.take(); name = self.take()
            if self.peek() == '{':
                require(not name.startswith('/'), 'Unsupported DTS node directive: '+name)
                existing = node.children.get(name)
                require(existing is None or 'xlnx,xps-gpio-1.00.a' not in strings(existing, 'compatible'),
                        'Duplicate GPIO node declaration; use an explicit resolved amendment')
                child = node.children.setdefault(name, Node(name, node))
                for label in labels:
                    require(label not in self.labels or self.labels[label] is child, 'Duplicate DTS label: '+label)
                    self.labels[label] = child; child.labels.add(label)
                self.take(); self.body(child); self.expect(';')
            else:
                require(not labels and name not in seen, 'Duplicate or labelled DTS property: '+name)
                seen.add(name)
                value = []
                if self.peek() == '=':
                    self.take()
                    while self.peek() != ';':
                        value.append(self.take())
                        require(value[-1] not in ('{', '}'), 'Malformed DTS property')
                self.expect(';')
                node.properties[name] = value
        self.take()

    def walk(self, node=None):
        node = self.root if node is None else node
        yield node
        for child in node.children.values():
            yield from self.walk(child)


def strings(node, key):
    raw = node.properties.get(key, [])
    require(all(t.startswith('"') or t == ',' for t in raw), 'Expected DTS string list: '+key)
    return [json.loads(t) for t in raw if t != ',']


def cells(node, key):
    require(key in node.properties, 'Missing DTS property: '+node.path+':'+key)
    raw = node.properties[key]
    require(raw and raw[0] == '<' and raw[-1] == '>', 'Expected literal DTS cell array: '+key)
    result = []
    for token in raw:
        if token in ('<', '>', ','):
            continue
        value = number(token)
        require(0 <= value <= 0xffffffff, 'DTS cell is outside 32-bit range')
        result.append(value)
    return result


def scalar(node, key, default=None):
    if key not in node.properties and default is not None:
        return default
    result = cells(node, key)
    require(len(result) == 1, 'Expected scalar DTS cell: '+key)
    return result[0]


def cell_integer(values):
    result = 0
    for value in values:
        result = (result << 32) | value
    return result


def address_cells(node):
    result = scalar(node, '#address-cells', 2)
    require(result in (1, 2), 'Unsupported #address-cells')
    return result


def size_cells(node):
    result = scalar(node, '#size-cells', 1)
    require(result in (1, 2), 'Unsupported #size-cells')
    return result


def physical_reg(node):
    bus = node.parent
    require(bus is not None, 'GPIO cannot be the DTS root')
    ac, sc = address_cells(bus), size_cells(bus)
    reg = cells(node, 'reg')
    require(len(reg) == ac+sc, 'Expected exactly one GPIO reg tuple')
    base, size = cell_integer(reg[:ac]), cell_integer(reg[ac:])
    require(size > 0, 'Empty GPIO reg range')
    while bus.parent is not None:
        require('ranges' in bus.properties, 'Missing ranges prevents parent address translation: '+bus.path)
        if bus.properties['ranges']:
            child_ac, parent_ac, range_sc = address_cells(bus), address_cells(bus.parent), size_cells(bus)
            values = cells(bus, 'ranges'); stride = child_ac+parent_ac+range_sc
            require(len(values) % stride == 0, 'Invalid DTS ranges tuple')
            matches = []
            for index in range(0, len(values), stride):
                child = cell_integer(values[index:index+child_ac])
                parent = cell_integer(values[index+child_ac:index+child_ac+parent_ac])
                length = cell_integer(values[index+child_ac+parent_ac:index+stride])
                if child <= base and base+size <= child+length:
                    matches.append(parent+base-child)
            require(len(matches) == 1, 'No unique parent ranges mapping covers GPIO')
            base = matches[0]
        bus = bus.parent
    return base, size


def parse_sdt(path, instance):
    tree = DeviceTree(path)
    candidates = [node for node in tree.walk() if 'xlnx,xps-gpio-1.00.a' in strings(node, 'compatible')]
    matching = [node for node in candidates if instance in node.labels or strings(node, 'xlnx,name') == [instance]]
    require(len(matching) == 1, 'Expected one effective SDT GPIO instance: '+instance)
    node = matching[0]
    require(len(candidates) == 1, 'Only one AXI GPIO instance is supported by this profile')
    cursor = node
    while cursor is not None:
        require(strings(cursor, 'status') in ([], ['okay'], ['ok']), 'GPIO or ancestor is disabled: '+cursor.path)
        cursor = cursor.parent
    base, size = physical_reg(node)
    values = {'instance': instance, 'base': base, 'range': size, 'node': node.path,
              'compatible': strings(node, 'compatible'), 'device_id': strings(tree.root, 'device_id')}
    for name, output in PARAM_NAMES.items():
        values[output] = scalar(node, 'xlnx,'+name[2:].lower().replace('_', '-'))
    require(values['is_dual'] == 1, 'Only dual-channel AXI GPIO SDT is supported')
    return values, tree.dependencies


def check_handoff(data, expected_base=None, expected_range=None):
    bd, xsa, sdt = (data[key] for key in ('bd', 'xsa', 'sdt'))
    require(bd['part'] == xsa['part'], 'BD -> XSA part mismatch', 'STALE_BD_XSA')
    if sdt['device_id']:
        require(len(sdt['device_id']) == 1 and xsa['part'].startswith(sdt['device_id'][0]+'-'),
                'XSA -> SDT device mismatch', 'STALE_XSA_SDT')
    for key in GPIO_FIELDS:
        require(bd[key] == xsa[key], 'BD -> XSA '+key+' mismatch: '+str(bd[key])+' != '+str(xsa[key]), 'STALE_BD_XSA')
        require(xsa[key] == sdt[key], 'XSA -> SDT '+key+' mismatch: '+str(xsa[key])+' != '+str(sdt[key]), 'STALE_XSA_SDT')
    if expected_base is not None:
        require(bd['base'] == expected_base, 'Current base differs from expected change', 'EXPECTED_CHANGE_MISMATCH')
    if expected_range is not None:
        require(bd['range'] == expected_range, 'Current range differs from design contract', 'EXPECTED_CHANGE_MISMATCH')


def require_unchanged(sources):
    for key in ('bd', 'xsa'):
        require(sha(sources[key]['path']) == sources[key]['sha256'], 'Input changed during inspection: '+key,
                'INPUT_CHANGED')
    root = Path(sources['sdt']['path']).parent
    for relative, expected in sources['sdt']['dependencies'].items():
        require(sha(root/relative) == expected, 'SDT input changed during inspection: '+relative, 'INPUT_CHANGED')
    require(sha(Path(__file__)) == sources['checker_sha256'], 'Checker changed during inspection', 'INPUT_CHANGED')


def check_record(record, sources):
    previous = json_data(read_bytes(record))
    require(previous.get('terminal_state') == 'PASS' and previous.get('command') in ('inspect', 'verify'),
            'Previous record is incomplete or failed', 'UNCONFIRMED_RECORD')
    require(previous.get('sources') == sources, 'Current inputs/checker differ from previous record', 'STALE_RECORD')


def doctor(root):
    require(root.is_dir(), 'Tool root is absent', 'ENVIRONMENT_MISSING')
    paths = {'vivado_launcher': 'Vivado/bin/vivado.bat', 'sdtgen_launcher': 'Vivado/bin/sdtgen.bat',
             'sdtgen_executable': 'Vivado/bin/unwrapped/win64.o/sdtgen.exe',
             'hsi_board_library': 'Vivado/lib/win64.o/xv_boardhsitasks.dll',
             'vitis_launcher': 'Vitis/bin/vitis.bat', 'vitis_version': 'Vitis/sourceVersion.txt',
             'vitis_hls_marker': 'Vitis/.vitis_for_hls', 'vitis_python_api': 'Vitis/cli',
             'sdtgen_repository': 'data/system-device-tree-xlnx',
             'embeddedsw': 'data/embeddedsw',
             'mpsoc_device_resources': 'data/parts/xilinx/zynquplus',
             'zcu102_board_file': 'data/xhub/boards/XilinxBoardStore/boards/Xilinx/zcu102/3.4/board.xml',
             'axi_gpio_ip': 'data/ip/xilinx/axi_gpio_v2_0/component.xml',
             'mpsoc_ip': 'data/ip/xilinx/zynq_ultra_ps_e_v3_5/component.xml'}
    result = {'execution': 'NOT_RUN', 'meaning': 'On-disk evidence only; no executable, license, platform, BSP or application validation',
              'components': {}}
    for name, relative in paths.items():
        path = root/relative
        entry = {'path': str(path), 'state': 'FOUND_ON_DISK' if path.exists() else 'MISSING'}
        if path.is_file():
            no_links(path); entry['sha256'] = sha(path)
        result['components'][name] = entry
    version = root/paths['vitis_version']
    result['version_evidence'] = version.read_text(encoding='utf-8') if version.is_file() else None
    board_path = root/paths['zcu102_board_file']
    if board_path.is_file():
        board = ET.fromstring(read_bytes(board_path))
        result['board_file_metadata'] = {'vendor': board.attrib.get('vendor'), 'name': board.attrib.get('name'),
            'file_version': board.findtext('file_version'),
            'compatible_hardware_revisions': [r.text for r in board.findall('./compatible_board_revisions/revision')],
            'meaning': 'Compatible revisions declared by the installed board file, not measured board identity'}
    search_roots = [root/'gnu', root/'Vitis/gnu', root/'Vitis/tools']
    compilers = [str(path) for search in search_roots if search.is_dir()
                 for path in search.rglob('aarch64-none-elf-gcc.exe') if path.is_file()]
    result['a53_baremetal_compiler'] = {'state': 'FOUND_ON_DISK' if compilers else 'NOT_FOUND_IN_SEARCH_ROOTS',
                                       'paths': compilers, 'search_roots': [str(p) for p in search_roots]}
    result['vitis_platform_bsp_app'] = 'NOT_RUN'
    return result


def cli_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest='command', required=True)
    for command in ('doctor', 'inspect', 'verify'):
        sub = subcommands.add_parser(command)
        sub.add_argument('--report-dir', type=Path, required=True, help='New independent report directory')
        if command == 'doctor':
            sub.add_argument('--tool-root', type=Path, required=True, help='AMD 2025.1 root containing Vivado and Vitis')
        else:
            sub.add_argument('--bd', type=Path, required=True)
            sub.add_argument('--xsa', type=Path, required=True)
            sub.add_argument('--sdt', type=Path, required=True, help='system-top.dts, with local includes')
            sub.add_argument('--instance', default='axi_gpio_0')
            if command == 'verify':
                sub.add_argument('--record', type=Path)
                sub.add_argument('--expected-base', type=nonnegative_argument)
                sub.add_argument('--expected-range', type=positive_argument)
    return parser


def main(argv=None):
    args = cli_parser().parse_args(argv)
    record = None
    report = None
    current_phase = 'parameters'
    try:
        output = no_links(args.report_dir)
        require(not output.exists(), 'Report directory must not already exist', 'UNSAFE_PATH')
        inputs = [no_links(getattr(args, key)) for key in ('bd', 'xsa', 'sdt', 'record', 'tool_root')
                  if getattr(args, key, None) is not None]
        for path in inputs:
            require(not output.is_relative_to(input_boundary(path)) and not path.is_relative_to(output),
                    'Report directory must be outside input and tool directories', 'UNSAFE_PATH')
        if args.command != 'doctor':
            require(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', args.instance) is not None, 'Invalid instance name')
        if args.command == 'verify':
            require(args.expected_base is None or args.expected_base >= 0, 'Expected base must be non-negative')
            require(args.expected_range is None or args.expected_range > 0, 'Expected range must be positive')
        output.mkdir(parents=True)
        report = output/'result.json'
        stages = ['doctor'] if args.command == 'doctor' else ['bd', 'xsa', 'sdt', 'consistency', 'source_identity']
        record = {'schema': 1, 'command': args.command, 'started_at': time.time(), 'terminal_state': 'RUNNING',
                  'phase': 'initialize',
                  'failure_type': None, 'failure_stage': None, 'actual_process_exit_code': None,
                  'timeout_seconds': None, 'cleanup': {'state': 'NOT_NEEDED', 'reason': 'No processes are started'},
                  'stages': {stage: {'state': 'NOT_RUN'} for stage in stages},
                  'scope': 'Metadata consistency only; no native generation/build, PS bus access or board validation'}
        current_phase = 'initialize'
        checker_hash = sha(Path(__file__))
        atomic_json(report, record)

        def stage(name, operation):
            nonlocal current_phase
            current_phase = name
            record['phase'] = name
            record['stages'][name] = {'state': 'RUNNING', 'started_at': time.time()}
            atomic_json(report, record)
            result = operation()
            record['stages'][name].update(state='PASS', finished_at=time.time())
            atomic_json(report, record)
            return result

        if args.command == 'doctor':
            record['doctor'] = stage('doctor', lambda: doctor(no_links(args.tool_root)))
        else:
            bd, xsa, sdt = (no_links(getattr(args, key)) for key in ('bd', 'xsa', 'sdt'))
            before_hashes = {}
            record['artifacts'] = {}
            def parse_with_identity(name, path, parse):
                before_hashes[name] = hashlib.sha256(read_bytes(path)).hexdigest()
                result = parse(path, args.instance)
                require(sha(path) == before_hashes[name], 'Input changed while parsing: '+name, 'INPUT_CHANGED')
                return result
            for name, path, parse in (('bd', bd, parse_bd), ('xsa', xsa, parse_xsa)):
                record['artifacts'][name] = stage(name, lambda n=name, p=path, f=parse: parse_with_identity(n, p, f))
            def sdt_with_identity():
                info, dependencies = parse_sdt(sdt, args.instance)
                record['sources'] = {'bd': {'path': str(bd), 'sha256': before_hashes['bd']},
                                     'xsa': {'path': str(xsa), 'sha256': before_hashes['xsa']},
                                     'sdt': {'path': str(sdt), 'dependencies': dependencies},
                                     'checker_sha256': checker_hash}
                return info
            sdt_info = stage('sdt', sdt_with_identity)
            record['artifacts']['sdt'] = sdt_info
            stage('consistency', lambda: check_handoff(record['artifacts'], getattr(args, 'expected_base', None),
                                                       getattr(args, 'expected_range', None)))
            def identity():
                if getattr(args, 'record', None):
                    check_record(args.record, record['sources'])
                require_unchanged(record['sources'])
            stage('source_identity', identity)
        current_phase = 'persist_result'
        record.update(terminal_state='PASS', phase='complete', finished_at=time.time())
        atomic_json(report, record)
        print(str(report))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        code = (130 if isinstance(error, KeyboardInterrupt) else
                2 if record is None and isinstance(error, HandoffError) else 1)
        if record is not None:
            active = next((key for key, value in record['stages'].items() if value['state'] == 'RUNNING'), None)
            if active:
                record['stages'][active].update(state='FAIL', finished_at=time.time())
            record.update(terminal_state='INTERRUPTED' if code == 130 else 'FAIL', failure_stage=active or current_phase,
                          failure_type=getattr(error, 'code', type(error).__name__), error=str(error), finished_at=time.time())
            try:
                atomic_json(report, record)
            except Exception as save_error:
                print('Result persistence failed: '+str(save_error), file=sys.stderr)
        print(type(error).__name__+': '+str(error), file=sys.stderr)
        return code


if __name__ == '__main__':
    sys.exit(main())
