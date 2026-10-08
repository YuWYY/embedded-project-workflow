#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
"""Small, coordinate-driven planning canvas. SVG uses only the standard library.

Adapted from the original planning examples' text, box, route and arrow
primitives. This is a drawing helper, not a project parser or layout engine.
Pillow and an explicitly supplied existing font are optional PNG dependencies.
"""
from html import escape
import importlib
import math
from pathlib import Path
import re

INK = '#26323D'
MUTED = '#65727E'
BORDER = '#9BA7B0'
DATA = '#2B68A3'
CONTROL = '#2E835C'
CLOCK = '#B77916'
RESET = '#AD4C4C'
WHITE = '#FFFFFF'


def _number(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be a finite number')
    if not math.isfinite(value) or (positive and value <= 0):
        raise ValueError(f'{name} must be finite' + (' and positive' if positive else ''))
    return value


def _label(value):
    value = str(value)
    if any(not (c in '\n\r\t' or 0x20 <= ord(c) <= 0xD7FF or
                0xE000 <= ord(c) <= 0xFFFD or 0x10000 <= ord(c) <= 0x10FFFF)
           for c in value):
        raise ValueError('Label contains a character forbidden by XML 1.0')
    return value


def _color(value):
    if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}|none', value):
        raise ValueError('Colors must be #RRGGBB or none')
    return value


def _fmt(value):
    return f'{value:g}'


class Canvas:
    """Explicit coordinates; text coordinates denote the top of each line.

    Dashed contours are exclusively named scopes. Wires are solid, orthogonal
    and may cross a scope, but cannot end on its border. A dot explicitly joins
    at least three incident route directions; crossings without dots do not join.
    Geometry checks are drawing checks, not electrical or timing validation.
    """

    def __init__(self, width=1600, height=1000, font_family='sans-serif'):
        self.width = _number(width, 'width', True)
        self.height = _number(height, 'height', True)
        self.font_family = _label(font_family)
        self.items = []

    def _point(self, x, y):
        _number(x, 'x')
        _number(y, 'y')
        if not 0 <= x <= self.width or not 0 <= y <= self.height:
            raise ValueError(f'Point ({x}, {y}) is outside the canvas')

    def text(self, x, y, value, size=24, color=INK, bold=False, anchor='left',
             max_width=None, line_height=None):
        """Literal text; max_width declares a diagnostic region, not auto-wrap.

        line_height is the baseline spacing in canvas pixels (default 1.35*size).
        Width extends right/around/left of x according to the text anchor.
        """
        self._point(x, y)
        _number(size, 'font size', True)
        if anchor not in ('left', 'center', 'right'):
            raise ValueError('Text anchor must be left, center or right')
        if max_width is not None:
            _number(max_width, 'label width', True)
        if line_height is not None:
            _number(line_height, 'line height', True)
        value = _label(value)
        lines = value.split('\n')
        step = size * 1.35 if line_height is None else line_height
        if y + size + step * (len(lines) - 1) > self.height:
            raise ValueError('Text extends below the canvas')
        self.items.append(dict(kind='text', x=x, y=y, value=value, size=size,
                               color=_color(color), bold=bool(bold), anchor=anchor,
                               max_width=max_width, line_height=line_height))

    def block(self, x, y, width, height, title, detail='', title_size=25,
              body_size=20, padding=15, gap=13, line_height=None,
              fill=WHITE, stroke=BORDER):
        """Module background followed by title/body; explicit newlines only.

        Text uses a centered label region with the given padding. diagnose()
        checks its width and bottom when font metrics are available. Coordinates
        and labels remain caller-owned; this helper does not fit or move them.
        """
        _number(padding, 'padding')
        _number(gap, 'gap')
        _number(title_size, 'title size', True)
        _number(body_size, 'body size', True)
        if padding < 0 or gap < 0 or 2 * padding >= min(width, height):
            raise ValueError('Block padding/gap is outside its bounds')
        if line_height is not None:
            _number(line_height, 'line height', True)
        start = len(self.items)
        try:
            self.rect(x, y, width, height, fill=fill, stroke=stroke)
            self.text(x + width / 2, y + padding, title, size=title_size,
                      bold=True, anchor='center', max_width=width - 2 * padding,
                      line_height=line_height)
            self.items[-1]['label_bottom'] = y + height - padding
            step = title_size * 1.35 if line_height is None else line_height
            body_y = y + padding + title_size + (len(str(title).split('\n')) - 1) * step + gap
            if detail:
                self.text(x + width / 2, body_y, detail, size=body_size,
                          color=MUTED, anchor='center', max_width=width - 2 * padding,
                          line_height=line_height)
                self.items[-1]['label_bottom'] = y + height - padding
        except (ValueError, TypeError):
            del self.items[start:]
            raise

    def rect(self, x, y, width, height, fill=WHITE, stroke=BORDER, radius=4,
             line_width=2):
        self._point(x, y)
        _number(width, 'rectangle width', True)
        _number(height, 'rectangle height', True)
        self._point(x + width, y + height)
        _number(radius, 'radius')
        if radius < 0 or radius > min(width, height) / 2:
            raise ValueError('Rectangle radius is outside its bounds')
        _number(line_width, 'line width', True)
        self.items.append(dict(kind='rect', x=x, y=y, width=width, height=height,
                               fill=_color(fill), stroke=_color(stroke),
                               radius=radius, line_width=line_width))

    def scope(self, x, y, width, height, name, color=BORDER, size=22):
        """One dashed outline with a required name, never a signal endpoint."""
        if not _label(name).strip():
            raise ValueError('A grouping or domain scope must have a name')
        self.rect(x, y, width, height, fill='none', stroke=color, radius=0)
        self.items[-1]['kind'] = 'scope'
        self.items[-1]['name'] = str(name)
        self.text(x + 16, y + 12, name, size=size, color=MUTED)

    def wire(self, points, color=DATA, arrow=True, width=3):
        """Draw one solid route. Adjacent points must differ in one axis."""
        points = tuple(tuple(p) for p in points)
        if len(points) < 2 or any(len(p) != 2 for p in points):
            raise ValueError('A route needs at least two coordinate pairs')
        for point in points:
            self._point(*point)
        for a, b in zip(points, points[1:]):
            if a == b or (a[0] != b[0] and a[1] != b[1]):
                raise ValueError('Routes must be orthogonal and nonzero')
        _number(width, 'wire width', True)
        self.items.append(dict(kind='wire', points=points, color=_color(color),
                               arrow=bool(arrow), width=width))

    def dot(self, x, y, color=DATA, radius=5):
        """Declare a real junction; connectivity is checked when exporting."""
        _number(radius, 'dot radius', True)
        self._point(x - radius, y - radius)
        self._point(x + radius, y + radius)
        self.items.append(dict(kind='dot', x=x, y=y, color=_color(color), radius=radius))

    def _validate_connections(self):
        scopes = [item for item in self.items if item['kind'] == 'scope']
        wires = [item for item in self.items if item['kind'] == 'wire']
        for route in wires:
            for x, y in (route['points'][0], route['points'][-1]):
                for scope in scopes:
                    sx, sy = scope['x'], scope['y']
                    ex, ey = sx + scope['width'], sy + scope['height']
                    vertical = (x == sx or x == ex) and sy <= y <= ey
                    horizontal = (y == sy or y == ey) and sx <= x <= ex
                    if vertical or horizontal:
                        raise ValueError('Signal endpoint lies on scope border: ' + scope['name'])
        for dot in (item for item in self.items if item['kind'] == 'dot'):
            x, y = dot['x'], dot['y']
            directions = set()
            for route in wires:
                for a, b in zip(route['points'], route['points'][1:]):
                    if a[0] == b[0] == x and min(a[1], b[1]) <= y <= max(a[1], b[1]):
                        directions.update((0, 1 if p[1] > y else -1) for p in (a, b) if p[1] != y)
                    if a[1] == b[1] == y and min(a[0], b[0]) <= x <= max(a[0], b[0]):
                        directions.update((1 if p[0] > x else -1, 0) for p in (a, b) if p[0] != x)
            if len(directions) < 3:
                raise ValueError(f'Junction ({x}, {y}) needs at least three incident directions')

    def diagnose(self, font=None):
        """Return advisory {code, item_indices, message} records (zero-based).

        Does not mutate or export the drawing, nor change save() acceptance.
        A supplied existing font and optional Pillow enable text measurements;
        otherwise TEXT_METRICS_UNAVAILABLE explicitly leaves those checks open.
        Crossings, electrical direction, arrow/text collisions, arbitrary shapes
        and complete scope/clock/reset semantics are outside these diagnostics.
        """
        findings = []

        def report(code, indices, message):
            findings.append(dict(code=code, item_indices=list(indices), message=message))

        def on_segment(p, a, b):
            return ((a[0] == b[0] == p[0] and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])) or
                    (a[1] == b[1] == p[1] and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])))

        def directions(points, p):
            result = set()
            for a, b in zip(points, points[1:]):
                if on_segment(p, a, b):
                    for q in (a, b):
                        if q != p:
                            result.add((0 if q[0] == p[0] else (1 if q[0] > p[0] else -1),
                                        0 if q[1] == p[1] else (1 if q[1] > p[1] else -1)))
            return result

        def inside_or_border(p, rect):
            return (rect['x'] <= p[0] <= rect['x'] + rect['width'] and
                    rect['y'] <= p[1] <= rect['y'] + rect['height'])

        wires = [(i, item) for i, item in enumerate(self.items)
                 if item['kind'] == 'wire' and item['color'] != 'none']
        dots = {(item['x'], item['y']) for item in self.items
                if item['kind'] == 'dot' and item['color'] != 'none'}
        seen = set()
        for i, route in wires:
            for point in (route['points'][0], route['points'][-1]):
                if point in dots:
                    continue
                for j, other in wires:
                    if i == j or point in (other['points'][0], other['points'][-1]):
                        continue
                    incident = directions(route['points'], point) | directions(other['points'], point)
                    if len(incident) >= 3 and directions(other['points'], point):
                        identity = (min(i, j), max(i, j), point)
                        if identity not in seen:
                            seen.add(identity)
                            report('AMBIGUOUS_T_JUNCTION', [i, j],
                                   f'Route endpoint at {point} touches another route without a visible junction dot.')
            for j, rect in enumerate(self.items):
                if rect['kind'] != 'rect' or (rect['fill'] == rect['stroke'] == 'none'):
                    continue
                if any(inside_or_border(p, rect) for p in (route['points'][0], route['points'][-1])):
                    continue
                left, top = rect['x'], rect['y']
                right, bottom = left + rect['width'], top + rect['height']
                for a, b in zip(route['points'], route['points'][1:]):
                    cross = ((a[0] == b[0] and left < a[0] < right and
                              max(min(a[1], b[1]), top) < min(max(a[1], b[1]), bottom)) or
                             (a[1] == b[1] and top < a[1] < bottom and
                              max(min(a[0], b[0]), left) < min(max(a[0], b[0]), right)))
                    if cross:
                        report('WIRE_THROUGH_MODULE', [i, j],
                               'Route crosses a module interior that contains neither route endpoint.')
                        break

        texts = [(i, item) for i, item in enumerate(self.items)
                 if item['kind'] == 'text' and item['color'] != 'none']
        if not texts:
            return findings
        if font is None or not Path(font).is_file():
            report('TEXT_METRICS_UNAVAILABLE', [i for i, _ in texts],
                   'Text width/occlusion checks were not run: supply an existing suitable font file.')
            return findings
        try:
            ImageFont = importlib.import_module('PIL.ImageFont')
            # Measure at a larger resolution to preserve fractional font sizes.
            measured = {item['size']: ImageFont.truetype(str(font), max(1, round(item['size'] * 4)))
                        for _, item in texts}
        except (ImportError, OSError) as error:
            report('TEXT_METRICS_UNAVAILABLE', [i for i, _ in texts],
                   'Text width/occlusion checks were not run: font metrics unavailable (' + type(error).__name__ + ').')
            return findings
        for i, item in texts:
            bounds = []
            overflow = False
            step = item['size'] * 1.35 if item['line_height'] is None else item['line_height']
            for line_number, line in enumerate(item['value'].split('\n')):
                if not line:
                    continue
                anchor = {'left': 'lt', 'center': 'mt', 'right': 'rt'}[item['anchor']]
                raw = measured[item['size']].getbbox(line, anchor=anchor)
                box = (item['x'] + raw[0] / 4, item['y'] + line_number * step + raw[1] / 4,
                       item['x'] + raw[2] / 4, item['y'] + line_number * step + raw[3] / 4)
                bounds.append(box)
                if item['max_width'] is not None:
                    region_left = item['x'] - item['max_width'] * {'left': 0, 'center': .5, 'right': 1}[item['anchor']]
                    overflow |= box[0] < region_left or box[2] > region_left + item['max_width']
                    overflow |= 'label_bottom' in item and box[3] > item['label_bottom']
            if overflow:
                report('LABEL_OVERFLOW', [i], 'Measured text exceeds its declared label region; wrap or resize explicitly.')
            for j in range(i + 1, len(self.items)):
                rect = self.items[j]
                if rect['kind'] != 'rect' or rect['fill'] == 'none':
                    continue
                left, top = rect['x'], rect['y']
                right, bottom = left + rect['width'], top + rect['height']
                # Exclude rounded corners: only report definite overlap with
                # one of the rectangle's two fully filled central strips.
                radius = rect['radius']
                strips = [(left + radius, top, right - radius, bottom),
                          (left, top + radius, right, bottom - radius)]
                if any(max(b[0], r[0]) < min(b[2], r[2]) and max(b[1], r[1]) < min(b[3], r[3])
                       for b in bounds for r in strips):
                    report('TEXT_COVERED_BY_LATER_RECT', [i, j],
                           'A later filled rectangle overlaps measured text; draw backgrounds before labels.')
        return findings

    @staticmethod
    def _arrow(points):
        tx, ty = points[-1]
        px, py = points[-2]
        length = math.hypot(tx - px, ty - py)
        ux, uy = (tx - px) / length, (ty - py) / length
        head = min(12, length * .65)
        half = head * .45
        return [(tx, ty), (tx - head * ux + half * uy, ty - head * uy - half * ux),
                (tx - head * ux - half * uy, ty - head * uy + half * ux)]

    def to_svg(self):
        self._validate_connections()
        svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{_fmt(self.width)}" '
               f'height="{_fmt(self.height)}" viewBox="0 0 {_fmt(self.width)} {_fmt(self.height)}">',
               '<rect width="100%" height="100%" fill="#FFFFFF"/>']
        for item in self.items:
            kind = item['kind']
            if kind == 'text':
                anchor = {'left': 'start', 'center': 'middle', 'right': 'end'}[item['anchor']]
                for index, line in enumerate(item['value'].split('\n')):
                    y = item['y'] + index * (item['size'] * 1.35 if item['line_height'] is None else item['line_height'])
                    svg.append(f'<text x="{_fmt(item["x"])}" y="{_fmt(y)}" '
                               f'font-size="{_fmt(item["size"])}" fill="{item["color"]}" '
                               f'font-family="{escape(self.font_family, quote=True)}" '
                               f'font-weight="{700 if item["bold"] else 400}" text-anchor="{anchor}" '
                               f'dominant-baseline="text-before-edge">{escape(line)}</text>')
            elif kind in ('rect', 'scope'):
                dash = ' stroke-dasharray="9 7" data-scope="' + escape(item['name'], quote=True) + '"' if kind == 'scope' else ''
                svg.append(f'<rect x="{_fmt(item["x"])}" y="{_fmt(item["y"])}" '
                           f'width="{_fmt(item["width"])}" height="{_fmt(item["height"])}" '
                           f'rx="{_fmt(item["radius"])}" fill="{item["fill"]}" stroke="{item["stroke"]}" '
                           f'stroke-width="{_fmt(item["line_width"])}"{dash}/>')
            elif kind == 'wire':
                points = ' '.join(f'{_fmt(x)},{_fmt(y)}' for x, y in item['points'])
                svg.append(f'<polyline points="{points}" fill="none" stroke="{item["color"]}" '
                           f'stroke-width="{_fmt(item["width"])}" stroke-linejoin="round"/>')
                if item['arrow']:
                    triangle = ' '.join(f'{_fmt(x)},{_fmt(y)}' for x, y in self._arrow(item['points']))
                    svg.append(f'<polygon points="{triangle}" fill="{item["color"]}"/>')
            elif kind == 'dot':
                svg.append(f'<circle cx="{_fmt(item["x"])}" cy="{_fmt(item["y"])}" '
                           f'r="{_fmt(item["radius"])}" fill="{item["color"]}"/>')
        return '\n'.join(svg + ['</svg>', ''])

    def _png(self, path, font, scale):
        if font is None:
            return 'PNG_GAP: supply --font (or font=) with an existing suitable font file; SVG is available.'
        font = Path(font)
        if not font.is_file():
            return 'PNG_GAP: supplied font file is unavailable; SVG is available.'
        try:
            Image = importlib.import_module('PIL.Image')
            ImageDraw = importlib.import_module('PIL.ImageDraw')
            ImageFont = importlib.import_module('PIL.ImageFont')
        except ImportError:
            return 'PNG_GAP: optional Pillow is unavailable; SVG is available. No dependency was installed.'
        try:
            fonts = {item['size']: ImageFont.truetype(str(font), round(item['size'] * scale))
                     for item in self.items if item['kind'] == 'text' and item['color'] != 'none'}
        except OSError:
            return 'PNG_GAP: supplied font cannot be loaded; SVG is available.'
        image = Image.new('RGB', (round(self.width * scale), round(self.height * scale)), WHITE)
        draw = ImageDraw.Draw(image)
        def coords(points):
            return [(round(x * scale), round(y * scale)) for x, y in points]
        for item in self.items:
            kind = item['kind']
            if kind == 'text':
                if item['color'] == 'none':
                    continue
                for index, line in enumerate(item['value'].split('\n')):
                    y = item['y'] + index * (item['size'] * 1.35 if item['line_height'] is None else item['line_height'])
                    draw.text((round(item['x'] * scale), round(y * scale)), line,
                              font=fonts[item['size']], fill=item['color'],
                              anchor={'left': 'lt', 'center': 'mt', 'right': 'rt'}[item['anchor']],
                              # Outlining dense CJK glyphs closes their counters at native scale.
                              # PNG uses the supplied font's own weight; size retains hierarchy.
                              # SVG keeps its font-weight for the viewer's font selection.
                              stroke_width=0)
            elif kind in ('rect', 'scope'):
                x, y, w, h = item['x'], item['y'], item['width'], item['height']
                line_width = max(1, round(item['line_width'] * scale))
                if kind == 'scope':
                    if item['stroke'] == 'none':
                        continue
                    # No solid outline or second SVG contour underneath these dashes.
                    for a, b in [((x, y), (x + w, y)), ((x + w, y), (x + w, y + h)),
                                 ((x + w, y + h), (x, y + h)), ((x, y + h), (x, y))]:
                        length = math.hypot(b[0] - a[0], b[1] - a[1])
                        for start in range(0, math.ceil(length), 16):
                            end = min(start + 9, length)
                            segment = [(a[0] + (b[0] - a[0]) * t / length,
                                        a[1] + (b[1] - a[1]) * t / length) for t in (start, end)]
                            draw.line(coords(segment), fill=item['stroke'], width=line_width)
                else:
                    if item['fill'] == item['stroke'] == 'none':
                        continue
                    draw.rounded_rectangle(coords([(x, y), (x + w, y + h)]),
                                           radius=round(item['radius'] * scale),
                                           fill=None if item['fill'] == 'none' else item['fill'],
                                           outline=None if item['stroke'] == 'none' else item['stroke'], width=line_width)
            elif kind == 'wire':
                if item['color'] == 'none':
                    continue
                draw.line(coords(item['points']), fill=item['color'], width=max(1, round(item['width'] * scale)), joint='curve')
                if item['arrow']:
                    draw.polygon(coords(self._arrow(item['points'])), fill=item['color'])
            elif kind == 'dot':
                if item['color'] == 'none':
                    continue
                x, y, r = item['x'], item['y'], item['radius']
                draw.ellipse(coords([(x-r, y-r), (x+r, y+r)]), fill=item['color'])
        image.resize((round(self.width), round(self.height)), Image.Resampling.LANCZOS).save(path)
        return None

    def save(self, output_dir, stem, format='svg', font=None, scale=2):
        """Write SVG first. Optional PNG failure is explicit and preserves SVG.

        ``output_dir`` is the caller-selected directory. ``stem`` must be a
        simple filename, preventing accidental traversal out of that directory.
        Missing PNG dependencies are reported through ``png_gap``; other I/O
        failures raise normally. An old PNG, if any, is not a new export.
        """
        if not isinstance(stem, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', stem):
            raise ValueError('stem must be a simple ASCII filename without an extension or path')
        if re.fullmatch(r'CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]', stem, re.IGNORECASE):
            raise ValueError('stem is a Windows reserved device name')
        if format not in ('svg', 'both'):
            raise ValueError('format must be svg or both')
        _number(scale, 'PNG scale', True)
        source = self.to_svg()
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        svg_path = output_dir / (stem + '.svg')
        svg_path.write_text(source, encoding='utf-8')
        result = {'svg': svg_path, 'png': None, 'png_gap': None}
        if format == 'both':
            png_path = output_dir / (stem + '.png')
            result['png_gap'] = self._png(png_path, font, scale)
            if result['png_gap'] is None:
                result['png'] = png_path
            elif png_path.exists():
                result['png_gap'] += ' A pre-existing PNG was not refreshed.'
        return result
