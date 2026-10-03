#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
"""Read native project sources without an SDK, generation, execution or writes.

This inventory is not an execution preflight or a hardware correctness check.
Unknown formats retain readable facts and diagnostics; they never widen the
supported profiles of the separate native executors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import sys
import xml.etree.ElementTree as ET


KINDS = {'.ioc': 'cubemx', '.touchgfx': 'touchgfx', '.xpr': 'vivado_project', '.bd': 'vivado_bd'}
CMAKE_NAMES = {'cmakelists.txt': 'cmake_declarations', 'cmakepresets.json': 'cmake_presets',
               'cmakeuserpresets.json': 'cmake_presets'}
SKIP_NAMES = {'.git', '.cache', '__pycache__', 'dist', 'build', 'generated', '.xil'}
SKIP_SUFFIXES = ('.runs', '.cache', '.gen', '.sim')
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_DISCOVERY_ITEMS = 50000
MAX_DISCOVERY_DEPTH = 24
KNOWN_VERSIONS = {'cubemx': '6.18.1', 'touchgfx': '4.26.1', 'vivado_bd': '2025.1'}


class IntakeError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def source_kind(path):
    return CMAKE_NAMES.get(path.name.lower(), KINDS.get(path.suffix.lower(),
                           'cmake_declarations' if path.suffix.lower() == '.cmake' else None))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def linked(path):
    return path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction())


def no_link_components(path):
    for component in (path, *path.parents):
        if linked(component):
            raise IntakeError('LINK_NOT_READ', 'Linked path is not read: ' + str(component))


def unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise IntakeError('DUPLICATE_KEY', 'Duplicate JSON key: ' + key)
        obj[key] = value
    return obj


class JsonPairs(list):
    """Distinguish JSON objects from arrays, retaining duplicate keys and order."""


def pair_field(value, key, default=None):
    if not isinstance(value, JsonPairs):
        raise IntakeError('INVALID_STRUCTURE', 'Expected a JSON object while reading ' + key)
    matches = [item for name, item in value if name == key]
    if len(matches) > 1:
        raise IntakeError('DUPLICATE_KEY', 'Duplicate JSON key: ' + key)
    return matches[0] if matches else default


def decode_bd(text, record):
    """One historical PS7 encoding is retained as data, never dict-last-wins."""
    raw = json.loads(text, object_pairs_hook=JsonPairs)
    design = pair_field(raw, 'design')
    info_pairs = pair_field(design, 'design_info', JsonPairs())
    if not isinstance(info_pairs, JsonPairs):
        raise IntakeError('INVALID_STRUCTURE', 'design_info must be an object')
    info = unique_pairs(info_pairs)
    record['facts'] = {key: info.get(key) for key in ('name', 'tool_version', 'device')}
    components = pair_field(design, 'components', JsonPairs())
    retained = []

    def convert(value, path=()):
        if isinstance(value, JsonPairs):
            names = [name for name, _ in value]
            duplicate = len(names) != len(set(names))
            allowed = (duplicate and info.get('tool_version') == '2020.2' and len(path) == 8
                       and path[:2] == ('design', 'components')
                       and path[3:5] == ('addressing', 'address_spaces')
                       and path[6:] == ('local_memory_map', 'address_blocks')
                       and set(names) == {'address_block'})
            if allowed:
                component = pair_field(components, path[2])
                allowed = pair_field(component, 'vlnv') == 'xilinx.com:ip:processing_system7:5.5'
            if duplicate and not allowed:
                raise IntakeError('DUPLICATE_KEY', 'Duplicate JSON key at /' + '/'.join(path))
            if allowed:
                blocks = []
                seen = set()
                for index, (_, item) in enumerate(value):
                    block = object_value(convert(item, path + ('address_block', str(index))), 'PS7 address_block')
                    name = block.get('name')
                    if not isinstance(name, str) or not name or name in seen:
                        raise IntakeError('DUPLICATE_OBJECT', 'PS7 address_block name is absent or duplicated')
                    if any(not isinstance(block.get(key), str) or not block[key]
                           for key in ('base_address', 'range', 'width')):
                        raise IntakeError('INVALID_STRUCTURE', 'PS7 address_block lacks declared address/size fields')
                    seen.add(name)
                    blocks.append(block)
                retained.append({'path': '/' + '/'.join(path), 'count': len(blocks),
                                 'encoding': 'ordered repeated address_block', 'entries': blocks,
                                 'interpretation': 'NOT_RUN: local PS7 map retained, not an effective address map'})
                # This subtree is not consumed by parse_bd. Preserve a list
                # internally as well, rather than discarding all but one entry.
                return {'address_block': blocks}
            return {key: convert(item, path + (key,)) for key, item in value}
        if isinstance(value, list):
            return [convert(item, path + (str(index),)) for index, item in enumerate(value)]
        return value

    result = convert(raw)
    if retained:
        record['facts']['unexpanded_sections'] = retained
        issue(record, 'LEGACY_PS7_ADDRESS_BLOCKS_RETAINED',
              'Vivado 2020.2 PS7 5.5 repeated local address blocks retained in order; address semantics are unverified')
    return object_value(result, 'BD root')


def object_value(value, description):
    if not isinstance(value, dict):
        raise IntakeError('INVALID_STRUCTURE', description + ' must be an object')
    return value


def list_value(value, description):
    if not isinstance(value, list):
        raise IntakeError('INVALID_STRUCTURE', description + ' must be an array')
    return value


def natural(value):
    if not isinstance(value, str) or not value.isdecimal():
        raise ValueError('expected a nonnegative decimal integer')
    return int(value, 10)


def issue(record, code, message, severity='warning'):
    record['diagnostics'].append({'code': code, 'severity': severity, 'message': message})


def version_note(record, version):
    expected = KNOWN_VERSIONS.get(record['kind'])
    if version != expected:
        issue(record, 'VERSION_UNVERIFIED',
              'Declared version is missing or outside the inventory examples; stable fields only. '
              + 'Observed: ' + str(version))


def profile_hint(executor, matches):
    return {'candidate_executor': executor, 'declared_metadata_match': matches,
            'execution_eligibility': 'NOT_CHECKED',
            'note': 'Only source declarations were compared. Tool availability, full profile, build and runtime are not checked.'}


def parse_ioc(text, record):
    values = {}
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if '=' not in line:
            raise IntakeError('INVALID_IOC', 'IOC line has no equals sign: ' + str(line_no))
        key, value = line.split('=', 1)
        if not key or key != key.strip():
            raise IntakeError('INVALID_IOC', 'IOC key is empty or padded: ' + str(line_no))
        if key in values:
            raise IntakeError('DUPLICATE_KEY', 'Duplicate IOC key: ' + key)
        values[key] = value
    fields = {'name': 'ProjectManager.ProjectName', 'device': 'Mcu.CPN',
              'device_name': 'Mcu.UserName', 'family': 'Mcu.Family', 'package': 'Mcu.Package',
              'tool_version': 'MxCube.Version', 'database_version': 'MxDb.Version',
              'firmware': 'ProjectManager.FirmwarePackage', 'toolchain': 'ProjectManager.TargetToolchain',
              'main_location': 'ProjectManager.MainLocation', 'keep_user_code': 'ProjectManager.KeepUserCode'}
    facts = {label: values.get(key) for label, key in fields.items()}
    record['facts'] = facts
    version_note(record, facts['tool_version'])
    facts['peripherals'] = [values[k] for k in sorted(values, key=lambda k: (len(k), k))
                            if re.fullmatch(r'Mcu\.IP\d+', k)]
    facts['rtos'] = {'tasks': [], 'queues': [], 'unparsed_fields': []}
    for key, value in values.items():
        if not re.fullmatch(r'FREERTOS\.(Tasks|Queues)\d+', key):
            continue
        is_task = key.startswith('FREERTOS.Tasks')
        if key not in ('FREERTOS.Tasks01', 'FREERTOS.Queues01'):
            facts['rtos']['unparsed_fields'].append(key)
            issue(record, 'RTOS_TABLE_UNSUPPORTED', 'Table shape not verified: ' + key)
            continue
        seen = set()
        for index, row in enumerate(value.split(';')):
            if not row:
                continue
            parts = row.split(',')
            expected = 9 if is_task else 7
            if len(parts) != expected:
                issue(record, 'RTOS_ROW_UNSUPPORTED', f'{key} row {index + 1}: expected {expected} fields')
                facts['rtos']['unparsed_fields'].append(f'{key}[{index}]')
                continue
            name = parts[0]
            if not name or name in seen:
                raise IntakeError('DUPLICATE_OBJECT', 'Empty or duplicate RTOS object in ' + key + ': ' + name)
            seen.add(name)
            try:
                if is_task:
                    item = {'name': name, 'priority_value': natural(parts[1]), 'stack_words': natural(parts[2]),
                            'entry': parts[3], 'entry_placement': parts[4], 'argument': parts[5],
                            'allocation': parts[6], 'stack_symbol': parts[7], 'control_block_symbol': parts[8]}
                else:
                    item = {'name': name, 'capacity_elements': natural(parts[1]), 'element_type': parts[2],
                            'native_field_3': parts[3], 'allocation': parts[4],
                            'storage_symbol': parts[5], 'control_block_symbol': parts[6]}
            except ValueError:
                issue(record, 'RTOS_VALUE_UNSUPPORTED', f'{key} row {index + 1}: unrecognized size or priority encoding')
                facts['rtos']['unparsed_fields'].append(f'{key}[{index}]')
                continue
            if item['allocation'] not in ('Static', 'Dynamic'):
                issue(record, 'RTOS_ALLOCATION_UNVERIFIED', 'Unrecognized allocation declaration: ' + item['allocation'])
            facts['rtos']['tasks' if is_task else 'queues'].append(item)
    facts['declared_hooks'] = {key: values[key] for key in ('ProjectManager.UAScriptBeforePath',
                                                         'ProjectManager.UAScriptAfterPath') if values.get(key)}
    record['facts'] = facts
    record['execution_profile'] = profile_hint('cubemx_rtos.py',
        facts['tool_version'] == '6.18.1' and facts['firmware'] == 'STM32Cube FW_G4 V1.6.3'
        and facts['device_name'] == 'STM32G474RETx' and facts['toolchain'] == 'MDK-ARM V5.27')


def parse_touchgfx(data, record):
    app = object_value(data.get('Application'), 'Application')
    facts = {key: app.get(key) for key in ('Name', 'Resolution', 'SelectedColorDepth', 'StartupScreenName',
                                         'ApplicationTemplateName', 'ApplicationTemplateVersion', 'UIPath', 'TouchGfxPath')}
    record['facts'] = facts
    facts['tool_version'] = data.get('Version')
    version_note(record, facts['tool_version'])
    facts['screens'] = []
    seen = set()
    for screen in list_value(app.get('Screens', []), 'Application.Screens'):
        screen = object_value(screen, 'Screen')
        name = screen.get('Name')
        if not isinstance(name, str) or not name or name in seen:
            raise IntakeError('DUPLICATE_OBJECT', 'Screen name is absent or duplicated')
        seen.add(name)
        entry = {'name': name, 'components': [], 'interactions': []}
        facts['screens'].append(entry)
        component_names = set()
        for component in list_value(screen.get('Components', []), 'Components'):
            component = object_value(component, 'Component')
            component_name = component.get('Name')
            if not isinstance(component_name, str) or not component_name or component_name in component_names:
                raise IntakeError('DUPLICATE_OBJECT', 'Component name is absent or duplicated in ' + name)
            component_names.add(component_name)
            item = {'name': component_name, 'type': component.get('Type')}
            for key in ('X', 'Y', 'Width', 'Height'):
                if key in component:
                    item[key.lower()] = component[key]
            entry['components'].append(item)
        for interaction in list_value(screen.get('Interactions', []), 'Interactions'):
            interaction = object_value(interaction, 'Interaction')
            trigger = object_value(interaction.get('Trigger', {}), 'Trigger')
            action = object_value(interaction.get('Action', {}), 'Action')
            item = {'name': interaction.get('InteractionName'), 'trigger_type': trigger.get('Type'),
                    'trigger_component': trigger.get('TriggerComponent'), 'action_type': action.get('Type'),
                    'function': action.get('FunctionName'), 'target': action.get('ActionComponent')}
            entry['interactions'].append(item)
            if action.get('Type') not in ('ActionCustom', 'ActionGotoScreen'):
                issue(record, 'INTERACTION_UNEXPANDED', 'Action is listed but its behavior is not interpreted: ' + str(action.get('Type')))
    if facts['StartupScreenName'] not in seen:
        issue(record, 'STARTUP_SCREEN_UNRESOLVED', 'Startup screen is absent from the listed screens')
    for screen in facts['screens']:
        for interaction in screen['interactions']:
            if interaction['action_type'] == 'ActionGotoScreen' and interaction['target'] not in seen:
                issue(record, 'NAVIGATION_UNRESOLVED', 'Declared target screen was not found: ' + str(interaction['target']))
    facts['declared_commands'] = {k: v for k, v in app.items() if 'command' in k.lower()}
    record['facts'] = facts
    record['execution_profile'] = profile_hint('touchgfx_project.py',
        data.get('Version') == '4.26.1' and app.get('ApplicationTemplateName') == 'Simulator'
        and app.get('ApplicationTemplateVersion') == '2.0.0' and app.get('SelectedColorDepth') == 16)


def xml_options(parent, selected):
    values = {}
    if parent is None:
        return values
    for option in parent.findall('Option'):
        name = option.get('Name')
        # Native XPR has repeated list-valued options such as SimTypes. Only
        # fields actually interpreted as scalars participate in uniqueness.
        if name not in selected:
            continue
        if name in values:
            raise IntakeError('DUPLICATE_KEY', 'Empty or duplicate XML Option name: ' + str(name))
        values[name] = option.get('Val')
    return values


def parse_bd(data, record):
    design = object_value(data.get('design'), 'design')
    info = object_value(design.get('design_info', {}), 'design_info')
    facts = {'name': info.get('name'), 'tool_version': info.get('tool_version'), 'device': info.get('device'),
             'instances': [], 'connections': [], 'address_segments': []}
    if 'unexpanded_sections' in record['facts']:
        facts['unexpanded_sections'] = record['facts']['unexpanded_sections']
    record['facts'] = facts
    version_note(record, facts['tool_version'])
    for name, component in object_value(design.get('components', {}), 'components').items():
        component = object_value(component, 'Component ' + name)
        vlnv = component.get('vlnv')
        reference = component.get('reference_info', {})
        reference = object_value(reference, 'reference_info')
        facts['instances'].append({'name': name, 'vlnv': vlnv, 'ip_revision': component.get('ip_revision'),
            'implementation': 'user_module_reference' if isinstance(vlnv, str) and ':module_ref:' in vlnv else
                              'declared_ip' if vlnv else 'unresolved',
            'reference_name': reference.get('ref_name'),
            'vlnv_library': vlnv.split(':')[1] if isinstance(vlnv, str) and len(vlnv.split(':')) == 4 else None})
        if component.get('components'):
            issue(record, 'BD_HIERARCHY_UNEXPANDED', 'Nested components are not expanded: ' + name)
    for group, endpoint_key in (('nets', 'ports'), ('interface_nets', 'interface_ports')):
        for name, net in object_value(design.get(group, {}), group).items():
            net = object_value(net, 'Net ' + name)
            endpoints = list_value(net.get(endpoint_key, []), 'Net endpoints')
            if not all(isinstance(endpoint, str) for endpoint in endpoints):
                raise IntakeError('INVALID_STRUCTURE', 'Net endpoints must be strings')
            facts['connections'].append({'name': name, 'kind': group, 'endpoints': endpoints})
    for master, node in object_value(design.get('addressing', {}), 'addressing').items():
        node = object_value(node, 'Address master')
        for space, item in object_value(node.get('address_spaces', {}), 'address_spaces').items():
            item = object_value(item, 'Address space')
            for name, segment in object_value(item.get('segments', {}), 'segments').items():
                segment = object_value(segment, 'Address segment')
                facts['address_segments'].append({'master': master, 'space': space, 'name': name,
                    'address_block': segment.get('address_block'), 'offset_declared': segment.get('offset'),
                    'range_declared': segment.get('range')})
    facts['address_check'] = 'NOT_RUN: declarations only; no reachability, translation or overlap validation'
    record['facts'] = facts
    record['execution_profile'] = profile_hint('soc_handoff.py', None)


def parse_cmake(text, record):
    """Text clues only: no CMake evaluation, variable expansion or source graph."""
    facts = {'declaration_clues': [], 'interpretation':
             'Textual declarations only; conditionals, functions, variables, includes and targets are not evaluated'}
    record['facts'] = facts
    bracket_end = None
    for line_no, line in enumerate(text.splitlines(), 1):
        if bracket_end:
            if bracket_end in line:
                bracket_end = None
            continue
        bracket = re.search(r'\[(=*)\[', line)
        if bracket:
            end = ']' + bracket.group(1) + ']'
            if end not in line[bracket.end():]:
                bracket_end = end
        match = re.match(r'^\s*(cmake_minimum_required|project|enable_language|include|add_subdirectory|set)\s*\(', line, re.I)
        if not match:
            continue
        command = match.group(1).lower()
        if command == 'set' and not re.match(
                r'\s*(CMAKE_[A-Za-z0-9_]+|TOOLCHAIN_PREFIX|TARGET_FLAGS)\b', line[match.end():]):
            continue
        facts['declaration_clues'].append({'line': line_no, 'command_clue': command, 'line_text': line.strip()})
    issue(record, 'CMAKE_DECLARATIONS_ONLY', 'CMake text was not executed; clues do not establish effective values or build inputs')


def reference_category(declared):
    if not isinstance(declared, str):
        return 'unknown'
    value = declared.replace('\\', '/')
    if value.startswith('$PGENDIR/'):
        return 'generated_product_reference'
    suffix = Path(value).suffix.lower()
    return {'.bd': 'block_design_source', '.xdc': 'constraint_source', '.xci': 'ip_configuration',
            '.v': 'hdl_source', '.sv': 'hdl_source', '.vhd': 'hdl_source',
            '.vhdl': 'hdl_source'}.get(suffix, 'other_declared_reference')


class Inventory:
    def __init__(self, root):
        self.root = root
        self.records = {}
        self.paths = {}
        self.relationships = []
        self.diagnostics = []

    def label(self, path):
        return path.relative_to(self.root).as_posix()

    def location(self, path, directory=False):
        try:
            no_link_components(path)
            resolved = path.resolve()
        except (IntakeError, OSError) as error:
            return None, 'LINK_NOT_READ' if isinstance(error, IntakeError) else 'PATH_UNREADABLE'
        if not resolved.is_relative_to(self.root):
            return None, 'EXTERNAL_REFERENCE_NOT_READ'
        if not (resolved.is_dir() if directory else resolved.is_file()):
            return None, 'MISSING_REFERENCE'
        return resolved, 'INTERNAL'

    def read(self, path):
        key = self.label(path)
        if key in self.records:
            return self.records[key]
        record = {'path': key, 'kind': source_kind(path), 'status': 'READ_ONLY', 'sha256': None,
                  'facts': {}, 'diagnostics': [], 'execution_profile': None}
        self.records[key] = record
        self.paths[key] = path
        try:
            actual, state = self.location(path)
            if state != 'INTERNAL':
                raise IntakeError(state, 'Source is not a readable internal regular file')
            if actual.stat().st_size > MAX_SOURCE_BYTES:
                raise IntakeError('SOURCE_TOO_LARGE', 'Native source exceeds the bounded inventory read limit')
            raw = actual.read_bytes()
            record['sha256'] = digest(raw)
            text = raw.decode('utf-8-sig')
            if '\x00' in text:
                raise IntakeError('INVALID_ENCODING', 'NUL bytes are not supported in native sources')
            if record['kind'] == 'cubemx':
                parse_ioc(text, record)
                if record['facts'].get('toolchain') == 'CMake':
                    self.cmake_companions(actual, record)
            elif record['kind'] == 'vivado_project':
                self.parse_xpr(text, actual, record)
            elif record['kind'] == 'vivado_bd':
                parse_bd(decode_bd(text, record), record)
            elif record['kind'] == 'cmake_declarations':
                parse_cmake(text, record)
                if actual.name.lower() == 'cmakelists.txt':
                    self.cmake_companions(actual, record)
            else:
                data = object_value(json.loads(text, object_pairs_hook=unique_pairs), 'JSON root')
                if record['kind'] == 'cmake_presets':
                    self.parse_presets(data, actual, record)
                else:
                    parse_touchgfx(data, record)
        except (IntakeError, OSError, UnicodeError, ValueError, RecursionError, ET.ParseError) as error:
            issue(record, error.code if isinstance(error, IntakeError) else 'PARSE_ERROR', str(error), 'error')
        self.refresh_status(record)
        return record

    def cmake_companions(self, source, record):
        candidates = []
        for name in ('CMakeLists.txt', 'CMakePresets.json', 'CMakeUserPresets.json'):
            path = source.parent/name
            if path == source:
                continue
            actual, state = self.location(path)
            candidates.append({'declared_path': name, 'state': state})
            if state == 'INTERNAL':
                child = self.read(actual)
                relation = {'kind': 'co_located_cmake_candidate', 'from': record['path'], 'to': child['path'],
                            'meaning': 'Nearby declaration only; effective configuration not established'}
                if relation not in self.relationships:
                    self.relationships.append(relation)
            elif state != 'MISSING_REFERENCE':
                issue(record, state, 'CMake companion not read: ' + name)
        record['facts']['nearby_cmake_candidates'] = candidates

    def parse_presets(self, data, project, record):
        facts = {'format_version': data.get('version'), 'configure_presets': [], 'build_presets': [],
                 'include_declared': data.get('include', []),
                 'interpretation': 'Declarations only; inheritance, conditions, environment and macros are not evaluated'}
        record['facts'] = facts
        issue(record, 'CMAKE_PRESETS_NOT_EVALUATED', 'Preset declarations are not effective configuration; include and inheritance are not resolved')
        if data.get('version') != 3:
            issue(record, 'FORMAT_UNVERIFIED', 'Preset schema version is outside the version-3 example')
        for group, output in (('configurePresets', 'configure_presets'), ('buildPresets', 'build_presets')):
            seen = set()
            for preset in list_value(data.get(group, []), group):
                preset = object_value(preset, group + ' entry')
                name = preset.get('name')
                if not isinstance(name, str) or not name or name in seen:
                    raise IntakeError('DUPLICATE_OBJECT', 'Preset name is absent or duplicated in ' + group)
                seen.add(name)
                item = {key: preset.get(key) for key in ('name', 'hidden', 'inherits', 'generator', 'binaryDir',
                                                        'toolchainFile', 'configurePreset', 'condition') if key in preset}
                facts[output].append(item)
                cache = object_value(preset.get('cacheVariables', {}), 'cacheVariables')
                item['cache_variables_declared'] = {key: cache[key] for key in ('CMAKE_TOOLCHAIN_FILE', 'CMAKE_BUILD_TYPE') if key in cache}
                value = preset.get('toolchainFile')
                if value is None and 'CMAKE_TOOLCHAIN_FILE' in cache:
                    value = cache['CMAKE_TOOLCHAIN_FILE']
                    value = value.get('value') if isinstance(value, dict) else value
                if value is None:
                    continue
                state = 'UNRESOLVED_RELATIVE_TOOLCHAIN'
                actual = None
                # sourceDir is lexical only here because these files reside at
                # the supplied source root. Relative toolchainFile has a native
                # binaryDir-first search order, so do not guess its target.
                if isinstance(value, str) and value.startswith('${sourceDir}/') and '$' not in value[len('${sourceDir}/'):]:
                    actual, state = self.location(project.parent/value[len('${sourceDir}/'):])
                elif not isinstance(value, str) or '$' in value:
                    state = 'UNRESOLVED_PATH_MACRO'
                elif Path(value).is_absolute() or PureWindowsPath(value).drive:
                    state = 'EXTERNAL_REFERENCE_NOT_READ'
                item['toolchain_reference'] = {'declared_path': value, 'state': state,
                                               'path': self.label(actual) if actual else None}
                if state == 'INTERNAL' and actual.suffix.lower() == '.cmake':
                    child = self.read(actual)
                    self.relationships.append({'kind': 'preset_declares_toolchain', 'from': record['path'],
                                               'to': child['path'], 'preset': name})
                elif state != 'INTERNAL':
                    issue(record, state, 'Toolchain declaration not read: ' + str(value))

    @staticmethod
    def refresh_status(record):
        record['status'] = 'ERROR' if any(d['severity'] == 'error' for d in record['diagnostics']) else (
            'PARTIAL' if record['diagnostics'] else 'READ_ONLY')

    def resolve_xpr_reference(self, value, project, directory=False):
        if not isinstance(value, str) or not value:
            return None, 'INVALID_REFERENCE'
        value = value.replace('\\', '/')
        macros = {'$PPRDIR': project.parent, '$PSRCDIR': project.parent/(project.stem+'.srcs'),
                  '$PGENDIR': project.parent/(project.stem+'.gen')}
        for macro, path in macros.items():
            if value == macro or value.startswith(macro + '/'):
                value = str(path) + value[len(macro):]
                break
        if '$' in value:
            return None, 'UNRESOLVED_PATH_MACRO'
        windows = PureWindowsPath(value)
        if os.name != 'nt' and (windows.drive or value.startswith('//')):
            return None, 'EXTERNAL_REFERENCE_NOT_READ'
        path = Path(value)
        if not path.is_absolute():
            if windows.drive:
                return None, 'UNRESOLVED_DRIVE_RELATIVE_PATH'
            path = project.parent/path
        return self.location(path, directory=directory)

    def parse_xpr(self, text, project, record):
        if re.search(r'<!\s*(DOCTYPE|ENTITY)\b', text, re.I):
            raise IntakeError('XML_DECLARATION_UNSUPPORTED', 'DTD/entity declarations are not read')
        tree = ET.fromstring(text)
        if tree.tag != 'Project':
            raise IntakeError('INVALID_XPR', 'Expected Project XML root')
        config = xml_options(tree.find('Configuration'), {'Part', 'BoardPart'})
        facts = {'product': tree.get('Product'), 'format_version': tree.get('Version'),
                 'format_minor': tree.get('Minor'), 'historical_project_path': tree.get('Path'),
                 'device': config.get('Part'), 'board_part': config.get('BoardPart'),
                 'tool_version': None, 'filesets': [],
                 'top_selection': 'Declared TopModule only; active design and elaboration are not verified'}
        record['facts'] = facts
        facts['ip_repositories'] = []
        for option in tree.findall('./Configuration/Option'):
            if option.get('Name') != 'IPRepoPath':
                continue
            declared = option.get('Val')
            resolved, state = self.resolve_xpr_reference(declared, project, directory=True)
            facts['ip_repositories'].append({'declared_path': declared, 'state': state,
                                            'path': self.label(resolved) if resolved else None,
                                            'contents': 'NOT_READ: repository contents and IP resolution unverified'})
            if state != 'INTERNAL':
                issue(record, state, 'Declared IP repository unavailable in supplied input: ' + str(declared))
        if tree.get('Version') != '7':
            issue(record, 'FORMAT_UNVERIFIED', 'XPR format is outside the inventory examples; stable XML fields only')
        seen = set()
        versions = set()
        for fileset in tree.findall('./FileSets/FileSet'):
            name = fileset.get('Name')
            if not name or name in seen:
                raise IntakeError('DUPLICATE_OBJECT', 'Missing or duplicate XPR fileset name')
            seen.add(name)
            options = xml_options(fileset.find('Config'), {'TopModule', 'DesignMode'})
            item = {'name': name, 'type': fileset.get('Type'), 'top_module': options.get('TopModule'),
                    'design_mode': options.get('DesignMode'), 'resources': []}
            facts['filesets'].append(item)
            for resource in fileset.findall('File'):
                declared = resource.get('Path')
                resolved, state = self.resolve_xpr_reference(declared, project)
                reference = {'declared_path': declared, 'state': state,
                             'path': self.label(resolved) if resolved is not None else None,
                             'category': reference_category(declared),
                             'used_in': [a.get('Val') for a in resource.findall('./FileInfo/Attr') if a.get('Name') == 'UsedIn']}
                item['resources'].append(reference)
                if state != 'INTERNAL':
                    issue(record, state, 'Reference unavailable in supplied input (not a claim about a complete upstream project): ' + str(declared))
                    continue
                if resolved.suffix.lower() == '.bd':
                    bd = self.read(resolved)
                    self.relationships.append({'kind': 'xpr_references_bd', 'from': record['path'],
                                               'to': bd['path'], 'fileset': name})
                    reference['source_status'] = bd['status']
                    version = bd['facts'].get('tool_version')
                    if isinstance(version, str):
                        versions.add(version)
                    if bd['status'] == 'ERROR':
                        issue(record, 'RELATED_SOURCE_ERROR', 'Referenced BD could not be parsed: ' + bd['path'])
        facts['bd_tool_versions'] = sorted(versions)
        record['facts'] = facts
        record['execution_profile'] = profile_hint('soc_handoff.py', None)

    def discover(self):
        found = []
        pending = [(self.root, 0)]
        count = 0
        while pending:
            directory, depth = pending.pop()
            if depth > MAX_DISCOVERY_DEPTH:
                self.diagnostics.append({'code': 'DISCOVERY_DEPTH_LIMIT', 'severity': 'warning',
                                         'message': self.label(directory)})
                continue
            try:
                entries = sorted(directory.iterdir(), key=lambda p: (p.name.casefold(), p.name))
            except OSError as error:
                self.diagnostics.append({'code': 'DIRECTORY_UNREADABLE', 'severity': 'warning', 'message': str(error)})
                continue
            for path in entries:
                count += 1
                if count > MAX_DISCOVERY_ITEMS:
                    self.diagnostics.append({'code': 'DISCOVERY_ITEM_LIMIT', 'severity': 'warning',
                                             'message': 'Discovery is incomplete; narrow --project or choose --entry'})
                    return sorted(found, key=self.label)
                if linked(path):
                    self.diagnostics.append({'code': 'LINK_NOT_READ', 'severity': 'warning', 'message': self.label(path)})
                    continue
                if path.is_dir():
                    lower = path.name.lower()
                    if lower not in SKIP_NAMES and not lower.endswith(SKIP_SUFFIXES):
                        pending.append((path, depth + 1))
                elif path.is_file() and (path.suffix.lower() in KINDS or path.name.lower() in CMAKE_NAMES):
                    found.append(path)
        return sorted(found, key=self.label)

    def check_sources_unchanged(self):
        for key, record in self.records.items():
            if record['sha256'] is None:
                continue
            actual, state = self.location(self.paths[key])
            try:
                unchanged = state == 'INTERNAL' and digest(actual.read_bytes()) == record['sha256']
            except OSError:
                unchanged = False
            if not unchanged:
                issue(record, 'SOURCE_CHANGED_DURING_READ', 'Input changed or became unreadable during inventory', 'error')
                self.refresh_status(record)


def inspect_project(project, entry=None):
    project = Path(os.path.abspath(project))
    no_link_components(project)
    if not project.exists():
        raise IntakeError('INPUT_MISSING', 'Project input does not exist')
    if not project.is_dir() and not project.is_file():
        raise IntakeError('INVALID_INPUT', 'Input must be a file or directory')
    project = project.resolve()
    root = project if project.is_dir() else project.parent
    inventory = Inventory(root)
    if entry is not None:
        if not project.is_dir():
            raise IntakeError('INVALID_ENTRY', '--entry requires a directory --project')
        normalized = str(entry).replace('\\', '/')
        if Path(normalized).is_absolute() or PureWindowsPath(normalized).drive or '..' in Path(normalized).parts:
            raise IntakeError('INVALID_ENTRY', '--entry must be a contained relative native file')
        target = root/normalized
        actual, state = inventory.location(target)
        if state != 'INTERNAL':
            raise IntakeError(state, 'Selected entry is not a readable internal file')
        targets = [actual]
    elif project.is_file():
        targets = [project]
    else:
        targets = inventory.discover()
    if any(source_kind(p) is None for p in targets):
        raise IntakeError('UNSUPPORTED_ENTRY', 'Select an IOC, TouchGFX, XPR, BD, CMakeLists.txt, preset JSON or .cmake declaration file')
    for target in targets:
        inventory.read(target)
    inventory.check_sources_unchanged()
    # Co-location is a location fact, not proof that two native files belong to
    # one effective build. Mixed CubeMX/TouchGFX sources are not a conflict.
    by_parent = {}
    for record in inventory.records.values():
        if record['kind'] in ('cubemx', 'touchgfx', 'vivado_project'):
            by_parent.setdefault(str(Path(record['path']).parent).replace('\\', '/'), []).append(record['path'])
    for directory, sources in sorted(by_parent.items()):
        if len(sources) > 1:
            inventory.relationships.append({'kind': 'co_located_sources', 'directory': directory,
                'sources': sorted(sources), 'meaning': 'Shared directory only; no common build or primary source inferred'})
    sources = sorted(inventory.records.values(), key=lambda r: r['path'])
    errors = any(record['status'] == 'ERROR' for record in sources)
    status = 'ERROR' if errors else 'PARTIAL' if inventory.diagnostics or any(r['status'] == 'PARTIAL' for r in sources) else 'READ_ONLY'
    if not sources:
        status = 'NO_NATIVE_SOURCES'
    return {'schema_version': 1, 'operation': 'inspect', 'status': status,
            'scope_root': str(root), 'selection': 'explicit_entry' if entry else 'explicit_file' if project.is_file() else 'directory_inventory',
            'primary_source': None, 'sources': sources, 'relationships': inventory.relationships,
            'diagnostics': inventory.diagnostics,
            'verification': {'tools': 'NOT_RUN', 'generation': 'NOT_RUN', 'build': 'NOT_RUN', 'runtime': 'NOT_RUN'},
            'limits': ['Configuration facts only; declared commands are data and are never executed.',
                       'No SDK, executable profile or hardware correctness has been validated.',
                       'External and linked references are not followed; multiple sources are not resolved into a primary project.',
                       'Inventory parses selected native structures; user code linkage and complete vendor schemas are not verified.']}


def format_text(report):
    lines = ['Project intake: ' + report['status'], 'Read-only; tools, generation, build and runtime: NOT_RUN',
             'Root: ' + report.get('scope_root', '(unresolved)')]
    for source in report.get('sources', []):
        lines.extend(['', source['path'] + ' [' + source['kind'] + ', ' + source['status'] + ']',
                      '  SHA256: ' + str(source['sha256'])])
        facts = source['facts']
        if source['kind'] == 'cubemx':
            device = facts.get('device') or facts.get('device_name') or '(not declared in the recognized fields)'
            lines.append(f"  CubeMX {facts.get('tool_version')} | device {device} | toolchain {facts.get('toolchain')}")
            for task in facts.get('rtos', {}).get('tasks', []):
                lines.append(f"  Task {task['name']}: {task['stack_words']} words, {task['allocation']}, entry={task['entry']}")
            for queue in facts.get('rtos', {}).get('queues', []):
                lines.append(f"  Queue {queue['name']}: {queue['capacity_elements']} elements of {queue['element_type']}, {queue['allocation']}")
        elif source['kind'] == 'touchgfx':
            lines.append(f"  TouchGFX {facts.get('tool_version')} | startup={facts.get('StartupScreenName')} | resolution={facts.get('Resolution')}")
            for screen in facts.get('screens', []):
                lines.append('  Screen '+screen['name']+': '+', '.join(c['name'] for c in screen['components']))
                for action in screen['interactions']:
                    lines.append(f"    {action['name']}: {action['trigger_component']} -> {action['action_type']} -> {action['function'] or action['target']}")
        elif source['kind'] == 'vivado_project':
            lines.append(f"  device={facts.get('device')} | board={facts.get('board_part')} | BD tool versions={facts.get('bd_tool_versions')}")
            for repo in facts.get('ip_repositories', []):
                lines.append(f"  IP repository declaration: {repo['declared_path']} -> {repo['state']} (contents NOT_READ)")
            for fileset in facts.get('filesets', []):
                lines.append(f"  Fileset {fileset['name']}: declared top={fileset['top_module']}")
                for resource in fileset['resources']:
                    lines.append(f"    {resource['declared_path']} -> {resource['state']} [{resource['category']}]")
        elif source['kind'] == 'vivado_bd':
            lines.append(f"  BD {facts.get('name')} | Vivado {facts.get('tool_version')} | device={facts.get('device')}")
            for component in facts.get('instances', []):
                lines.append(f"  {component['name']}: {component['vlnv']} ({component['implementation']})")
            lines.append(f"  Declared connections: {len(facts.get('connections', []))}")
            for address in facts.get('address_segments', []):
                lines.append(f"  Address declaration {address['master']}/{address['space']}: {address['name']} = {address['offset_declared']} + {address['range_declared']}")
            for section in facts.get('unexpanded_sections', []):
                lines.append(f"  Preserved unexpanded section {section['path']}: {section['count']} entries")
        elif source['kind'] == 'cmake_declarations':
            for clue in facts.get('declaration_clues', []):
                lines.append(f"  L{clue['line']} declaration clue: {clue['line_text']}")
        elif source['kind'] == 'cmake_presets':
            lines.append(f"  CMake preset format={facts.get('format_version')}; inheritance NOT_EVALUATED")
            for preset in facts.get('configure_presets', []) + facts.get('build_presets', []):
                lines.append('  Preset declaration: ' + json.dumps(preset, ensure_ascii=False))
        profile = source['execution_profile']
        if profile:
            lines.append(f"  Executor hint: {profile['candidate_executor']}; declared metadata match={profile['declared_metadata_match']}; execution eligibility=NOT_CHECKED")
        for diagnostic in source['diagnostics']:
            lines.append('  ' + diagnostic['code'] + ': ' + diagnostic['message'])
    for relationship in report.get('relationships', []):
        lines.append('Relation: ' + json.dumps(relationship, ensure_ascii=False))
    for diagnostic in report.get('diagnostics', []):
        lines.append(diagnostic['code'] + ': ' + diagnostic['message'])
    if len(report.get('sources', [])) > 1:
        lines.append('Multiple native sources listed; use --entry <relative native file> to narrow the next inspection. No primary source was guessed.')
    lines.extend(report.get('limits', []))
    return '\n'.join(lines)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    inspect = sub.add_parser('inspect', help='Read native sources without vendor tools or writes')
    inspect.add_argument('--project', type=Path, required=True, help='Native source file or directory boundary')
    inspect.add_argument('--entry', help='Contained relative native file; directory input only')
    inspect.add_argument('--format', choices=('text', 'json'), default='text')
    args = parser.parse_args(argv)
    try:
        report = inspect_project(args.project, args.entry)
    except (IntakeError, OSError) as error:
        report = {'schema_version': 1, 'operation': 'inspect', 'status': 'ERROR', 'sources': [],
                  'diagnostics': [{'code': error.code if isinstance(error, IntakeError) else 'INPUT_UNREADABLE',
                                   'severity': 'error', 'message': str(error)}]}
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.format == 'json' else format_text(report))
    return 1 if report['status'] in ('ERROR', 'NO_NATIVE_SOURCES') else 0


if __name__ == '__main__':
    raise SystemExit(main())
