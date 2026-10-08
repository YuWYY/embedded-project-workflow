#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
"""Drawing/export regression checks, not hardware or scheduling validation."""
import importlib.util
import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / 'embedded-project-workflow'
ASSETS = SKILL / 'assets' / 'planning-diagrams'
SCRIPT = SKILL / 'scripts' / 'planning_canvas.py'
spec = importlib.util.spec_from_file_location('planning_canvas', SCRIPT)
canvas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(canvas)
generator_spec = importlib.util.spec_from_file_location('generate_templates', ASSETS / 'generate_templates.py')
generator = importlib.util.module_from_spec(generator_spec)
generator_spec.loader.exec_module(generator)
NS = {'svg': 'http://www.w3.org/2000/svg'}


class CanvasChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='planning_canvas_')
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)

    def test_literal_unicode_long_labels_and_attributes_are_xml_escaped(self):
        drawing = canvas.Canvas(width=900, height=300, font_family='A "quoted" & B')
        label = '中文 <配置> & 状态 "引用" / ' + 'long_label_' * 8
        drawing.text(20, 20, label+'\n第二行', size=12)
        drawing.scope(20, 80, 700, 120, '域 <A> & "B"')
        root = ET.fromstring(drawing.to_svg())
        texts = root.findall('svg:text', NS)
        self.assertEqual(texts[0].text, label)
        self.assertEqual(texts[1].text, '第二行')
        self.assertEqual(texts[0].get('font-family'), 'A "quoted" & B')
        self.assertIn('&lt;配置&gt;', drawing.to_svg())
        with self.assertRaisesRegex(ValueError, 'XML'):
            drawing.text(20, 20, 'bad\x00label')

    def test_geometry_and_solid_orthogonal_reset_route(self):
        drawing = canvas.Canvas(400, 300)
        drawing.wire([(20, 30), (100, 30), (100, 150)], color=canvas.RESET)
        root = ET.fromstring(drawing.to_svg())
        route = root.find('svg:polyline', NS)
        self.assertEqual(route.get('points'), '20,30 100,30 100,150')
        self.assertIsNone(route.get('stroke-dasharray'))
        self.assertEqual(root.find('svg:polygon', NS).get('points').split()[0], '100,150')
        for points in ([(0, 0), (4, 7)], [(2, 2), (2, 2)], [(0, 0), (401, 0)], [(1, 1)]):
            with self.subTest(points=points), self.assertRaises(ValueError):
                drawing.wire(points)
        for size in (0, -1, float('nan'), float('inf')):
            with self.subTest(size=size), self.assertRaises(ValueError):
                canvas.Canvas(width=size)
        with self.assertRaises(ValueError):
            drawing.rect(390, 20, 30, 50)

    def test_one_dashed_contour_per_named_scope(self):
        drawing = canvas.Canvas(400, 300)
        drawing.scope(30, 30, 330, 220, 'clk_a')
        root = ET.fromstring(drawing.to_svg())
        dashed = [e for e in root.iter() if e.get('stroke-dasharray')]
        self.assertEqual(len(dashed), 1)
        self.assertEqual(dashed[0].tag, '{'+NS['svg']+'}rect')
        self.assertEqual(dashed[0].get('data-scope'), 'clk_a')
        self.assertEqual(len(root.findall('svg:polyline', NS)), 0)
        with self.assertRaisesRegex(ValueError, 'name'):
            drawing.scope(40, 50, 100, 100, ' ')

    def test_border_is_not_a_signal_endpoint_in_either_creation_order(self):
        for scope_first in (True, False):
            drawing = canvas.Canvas(400, 300)
            actions = [lambda: drawing.scope(50, 50, 250, 200, 'domain'),
                       lambda: drawing.wire([(20, 160), (50, 160)])]
            for action in actions if scope_first else reversed(actions):
                action()
            with self.subTest(scope_first=scope_first), self.assertRaisesRegex(ValueError, 'scope border'):
                drawing.save(self.output / 'not-created', 'bad-endpoint')
            self.assertFalse((self.output / 'not-created').exists())
        crossing = canvas.Canvas(400, 300)
        crossing.scope(50, 50, 250, 200, 'domain')
        crossing.wire([(20, 160), (100, 160)])
        ET.fromstring(crossing.to_svg())

    def test_dot_requires_real_branch_and_crossings_have_no_implicit_dot(self):
        drawing = canvas.Canvas(300, 300)
        drawing.wire([(20, 150), (280, 150)], arrow=False)
        drawing.wire([(150, 20), (150, 280)])
        self.assertEqual(len(ET.fromstring(drawing.to_svg()).findall('svg:circle', NS)), 0)
        drawing.dot(150, 150)
        self.assertEqual(len(ET.fromstring(drawing.to_svg()).findall('svg:circle', NS)), 1)
        drawing.dot(40, 150)
        with self.assertRaisesRegex(ValueError, 'three incident'):
            drawing.to_svg()

    def test_output_stem_cannot_escape_the_selected_directory(self):
        drawing = canvas.Canvas()
        for stem in ('../escape', '..\\escape', '/absolute', 'C:' + chr(92) + 'escape', 'x.svg', 'a/b', '', '..'):
            with self.subTest(stem=stem), self.assertRaisesRegex(ValueError, 'stem'):
                drawing.save(self.output, stem)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_windows_reserved_stems_are_rejected_before_directory_creation_on_every_platform(self):
        drawing = canvas.Canvas()
        for stem in ('NUL', 'con', 'Aux', 'PRN', 'COM1', 'com9', 'LPT1', 'lpt9'):
            output = self.output / ('case-' + stem) / 'new'
            with self.subTest(stem=stem), self.assertRaisesRegex(ValueError, 'reserved'):
                drawing.save(output, stem)
            self.assertFalse(output.parent.exists())
        for stem in ('console', 'COM0', 'COM10', 'NUL-data', 'normal_01'):
            self.assertTrue(drawing.save(self.output, stem)['svg'].is_file())

    def test_text_region_is_optional_no_auto_wrap_and_line_height_is_in_pixels(self):
        drawing = canvas.Canvas(600, 200)
        drawing.text(100, 20, 'first\nsecond', size=10, anchor='center', max_width=40, line_height=31)
        root = ET.fromstring(drawing.to_svg())
        lines = root.findall('svg:text', NS)
        self.assertEqual([node.get('y') for node in lines], ['20', '51'])
        self.assertEqual([node.text for node in lines], ['first', 'second'])
        for kwargs in ({'max_width': 0}, {'max_width': float('inf')}, {'line_height': -1}, {'line_height': True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                drawing.text(10, 10, 'text', **kwargs)
        with self.assertRaisesRegex(ValueError, 'below'):
            drawing.text(20, 180, 'a\nb', size=10, line_height=20)

    def test_block_draws_background_first_with_explicit_multiline_title_and_padding(self):
        drawing = canvas.Canvas(600, 400)
        drawing.block(20, 30, 400, 300, '标题\n第二行', 'Detail\nBody',
                      title_size=20, body_size=14, padding=12, gap=8, line_height=30)
        self.assertEqual([i['kind'] for i in drawing.items], ['rect', 'text', 'text'])
        self.assertEqual(drawing.items[1]['y'], 42)
        self.assertEqual(drawing.items[2]['y'], 100)
        self.assertEqual(drawing.items[2]['max_width'], 376)
        before = copy.deepcopy(drawing.items)
        with self.assertRaises(ValueError):
            drawing.block(20, 30, 400, 300, 'bad', padding=200)
        self.assertEqual(drawing.items, before)
        with self.assertRaises(ValueError):
            drawing.block(20, 320, 400, 70, 'a\nb\nc\nd')
        self.assertEqual(drawing.items, before)

    def test_diagnostics_find_t_touch_without_mutating_or_changing_export_acceptance(self):
        drawing = canvas.Canvas(400, 300)
        drawing.wire([(20, 150), (380, 150)], arrow=False)
        drawing.wire([(180, 20), (180, 150)])
        original = copy.deepcopy(drawing.items)
        reports = drawing.diagnose()
        self.assertEqual([x['code'] for x in reports], ['AMBIGUOUS_T_JUNCTION'])
        self.assertEqual(set(reports[0]['item_indices']), {0, 1})
        self.assertEqual(drawing.items, original)
        ET.fromstring(drawing.to_svg())  # advisory, not a new export gate
        drawing.dot(180, 150)
        self.assertEqual(drawing.diagnose(), [])

    def test_legitimate_x_crossings_elbows_and_scope_crossings_do_not_warn(self):
        drawing = canvas.Canvas(500, 400)
        drawing.wire([(10, 150), (400, 150)], arrow=False)
        drawing.wire([(150, 10), (150, 300)], arrow=False)
        drawing.wire([(400, 150), (400, 350), (450, 350)])
        drawing.scope(60, 70, 180, 180, 'domain')
        self.assertEqual([r['code'] for r in drawing.diagnose()], ['TEXT_METRICS_UNAVAILABLE'])
        ET.fromstring(drawing.to_svg())

    def test_route_crosses_unrelated_module_but_not_its_own_endpoint_modules(self):
        drawing = canvas.Canvas(600, 300)
        drawing.rect(10, 100, 90, 100)
        drawing.rect(200, 100, 100, 100)
        drawing.rect(400, 100, 90, 100)
        drawing.wire([(100, 150), (400, 150)])
        reports = drawing.diagnose()
        self.assertEqual([r['code'] for r in reports], ['WIRE_THROUGH_MODULE'])
        self.assertEqual(reports[0]['item_indices'], [3, 1])
        # A path along a border is not a path through the module interior.
        along = canvas.Canvas(600, 300)
        along.rect(200, 100, 100, 100)
        along.wire([(100, 100), (400, 100)])
        self.assertEqual(along.diagnose(), [])

    def test_missing_measurement_conditions_are_reported_not_estimated(self):
        drawing = canvas.Canvas()
        drawing.text(20, 20, 'Long text ' * 10, max_width=5)
        with patch.object(canvas.importlib, 'import_module', side_effect=AssertionError('no font supplied')):
            reports = drawing.diagnose()
        self.assertEqual([r['code'] for r in reports], ['TEXT_METRICS_UNAVAILABLE'])
        self.assertEqual(reports[0]['item_indices'], [0])
        fake = self.output / 'font.ttf'
        fake.write_bytes(b'not a font')
        with patch.object(canvas.importlib, 'import_module', side_effect=ImportError('Pillow missing')):
            reports = drawing.diagnose(fake)
        self.assertEqual([r['code'] for r in reports], ['TEXT_METRICS_UNAVAILABLE'])

    def real_font(self):
        """Optional actual rendering checks, no dependency or font installation."""
        try:
            from PIL import Image, ImageChops
        except ImportError:
            self.skipTest('Optional Pillow unavailable; real PNG checks not executed')
        supplied = os.environ.get('EPW_TEST_FONT')
        candidates = ([Path(supplied)] if supplied else [])
        if os.name == 'nt' and os.environ.get('WINDIR'):
            candidates.append(Path(os.environ['WINDIR']) / 'Fonts' / 'msyh.ttc')
        for font in candidates:
            if font.is_file():
                return font, Image, ImageChops
        self.skipTest('No existing test font selected; set EPW_TEST_FONT to run actual PNG/metrics checks')

    def test_none_is_invisible_for_every_png_primitive_but_scope_title_remains_visible(self):
        font, Image, ImageChops = self.real_font()
        base = canvas.Canvas(500, 340)
        base.rect(20, 20, 430, 280, fill='#F2D8D8', stroke='none')
        base.text(36, 162, 'Scope title', size=20, color=canvas.MUTED)
        drawing = canvas.Canvas(500, 340)
        drawing.rect(20, 20, 430, 280, fill='#F2D8D8', stroke='none')
        drawing.text(30, 30, 'HIDDEN', color='none')
        drawing.wire([(30, 100), (180, 100)], color='none')
        drawing.wire([(100, 70), (100, 130)], color='none')
        drawing.dot(100, 100, color='none')
        drawing.rect(200, 30, 120, 100, fill='none', stroke='none')
        drawing.scope(20, 150, 400, 140, 'Scope title', color='none', size=20)
        expected = base.save(self.output, 'reference', format='both', font=font)
        result = drawing.save(self.output, 'none-primitives', format='both', font=font)
        self.assertIsNone(result['png_gap'])
        ET.parse(result['svg'])
        with Image.open(expected['png']) as a, Image.open(result['png']) as b:
            self.assertIsNone(ImageChops.difference(a, b).getbbox())
            self.assertNotEqual(b.getpixel((50, 250)), (255, 255, 255))

    def test_actual_font_detects_overflow_and_later_occlusion_without_scope_false_positive(self):
        font, _, _ = self.real_font()
        drawing = canvas.Canvas(600, 350)
        drawing.text(50, 50, 'A long function name', max_width=20, size=24)
        drawing.rect(40, 40, 300, 60)
        drawing.text(50, 180, 'uncovered', size=24, max_width=400)
        drawing.scope(20, 150, 500, 130, 'transparent scope')
        reports = drawing.diagnose(font)
        self.assertEqual([r['code'] for r in reports], ['LABEL_OVERFLOW', 'TEXT_COVERED_BY_LATER_RECT'])
        self.assertEqual(reports[1]['item_indices'], [0, 1])

    def test_actual_text_bounds_respect_center_right_anchors_and_block_bottom(self):
        font, _, _ = self.real_font()
        drawing = canvas.Canvas(700, 400)
        drawing.text(400, 40, 'fit', size=20, anchor='right', max_width=100)
        drawing.text(400, 90, 'fit', size=20, anchor='center', max_width=100)
        drawing.block(20, 150, 500, 100, 'title', 'line1\nline2\nline3', body_size=20)
        reports = drawing.diagnose(font)
        self.assertEqual([r['code'] for r in reports], ['LABEL_OVERFLOW'])
        self.assertEqual(reports[0]['item_indices'], [4])

    def test_optional_font_gap_preserves_svg_and_does_not_claim_stale_png(self):
        drawing = canvas.Canvas()
        drawing.text(20, 20, '中文 SVG')
        stale = self.output / 'drawing.png'
        stale.write_bytes(b'old PNG')
        with patch.object(canvas.importlib, 'import_module', side_effect=AssertionError('must not import Pillow')):
            result = drawing.save(self.output, 'drawing', format='both')
        ET.parse(result['svg'])
        self.assertIsNone(result['png'])
        self.assertIn('PNG_GAP', result['png_gap'])
        self.assertIn('not refreshed', result['png_gap'])
        self.assertEqual(stale.read_bytes(), b'old PNG')

    def test_missing_pillow_and_unloadable_font_preserve_svg(self):
        drawing = canvas.Canvas()
        drawing.text(10, 10, 'Text')
        font = self.output / 'placeholder.ttf'
        font.write_bytes(b'not a font')
        with patch.object(canvas.importlib, 'import_module', side_effect=ImportError('Pillow absent')):
            missing = drawing.save(self.output, 'missing-pillow', format='both', font=font)
        self.assertIn('Pillow', missing['png_gap'])
        self.assertTrue(missing['svg'].exists())
        def bad_font(*args, **kwargs):
            raise OSError('invalid font')
        with patch.object(canvas.importlib, 'import_module', return_value=SimpleNamespace(truetype=bad_font)):
            bad = drawing.save(self.output, 'bad-font', format='both', font=font)
        self.assertIn('cannot be loaded', bad['png_gap'])
        self.assertTrue(bad['svg'].exists())
        self.assertIsNone(bad['png'])

    def test_write_failures_remain_failures_with_no_false_success(self):
        drawing = canvas.Canvas()
        with patch.object(Path, 'write_text', side_effect=PermissionError('read only')):
            with self.assertRaises(PermissionError):
                drawing.save(self.output, 'blocked')
        with patch.object(drawing, '_png', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                drawing.save(self.output, 'png-write-failed', format='both')
        ET.parse(self.output / 'png-write-failed.svg')

    def test_templates_regenerate_as_public_text_and_render_with_standard_library(self):
        result = subprocess.run([sys.executable, '-S', str(ASSETS / 'generate_templates.py'),
                                 '--output', str(self.output), '--format', 'svg'],
                                cwd=self.output, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(list(self.output.glob('*.svg'))), 5)
        self.assertEqual(list(self.output.glob('*.png')), [])
        for stem, factory in generator.TEMPLATES:
            actual = self.output / (stem+'.svg')
            self.assertEqual(actual.read_text(encoding='utf-8'), (ASSETS / actual.name).read_text(encoding='utf-8'))
            root = ET.parse(actual).getroot()
            self.assertIn('示例', ''.join(root.itertext()))
            self.assertNotIn('image', {e.tag.split('}')[-1] for e in root.iter()})
            for node in root.iter():
                if node.get('stroke-dasharray'):
                    self.assertTrue(node.get('data-scope'))
            self.assertEqual(factory().to_svg(), actual.read_text(encoding='utf-8'))

    def test_both_cli_reports_png_gap_in_stdlib_only_mode(self):
        font = self.output / 'placeholder.ttf'
        font.write_bytes(b'font need not load because Pillow is absent under -S')
        result = subprocess.run([sys.executable, '-S', str(ASSETS / 'generate_templates.py'),
                                 '--output', str(self.output / 'exports'), '--format', 'both', '--font', str(font)],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr.count('PNG_GAP'), 5)
        self.assertEqual(len(list((self.output / 'exports').glob('*.svg'))), 5)
        self.assertEqual(list((self.output / 'exports').glob('*.png')), [])


if __name__ == '__main__':
    unittest.main()
