"""Physical terminal geometry, independent of Film's footer and post effects."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from music import MusicState
from player import Canvas
from scenes import (B, N, R, W, draw_scene, legacy_mesh,
                    heart_contains,
                    lyric_circle_circumference,
                    lyric_daynight_clock, lyric_erase_fragments,
                    lyric_happy_execution, lyric_heart, lyric_only_execution,
                    point)


SIZES = ((64, 24), (80, 30), (120, 30), (128, 44), (180, 55))


class GeometryCanvas(Canvas):
    """Keep draw requests as well as the real raster, so clipping cannot hide bugs."""
    def __init__(self, w, h):
        super().__init__(w, h)
        self.requests = []
        self.lines = []

    def put(self, x, y, text, style=N):
        self.requests.append((x, y, str(text), style))
        super().put(x, y, text, style)

    def line(self, x0, y0, x1, y1, ch='.', style=0):
        self.lines.append((x0, y0, x1, y1, ch, style))
        super().line(x0, y0, x1, y1, ch, style)


def bounds(points):
    return (min(x for x, y in points), min(y for x, y in points),
            max(x for x, y in points), max(y for x, y in points))


class PhysicalGeometryTests(unittest.TestCase):
    def canvas(self, size, inset=0):
        w, h = size
        area = (2, 1 + inset, w - 3, h - 4 - inset)
        c = GeometryCanvas(w, h)
        c.clip = (area[1], area[3])
        return c, area

    def test_heart_profile_handles_a_float_next_to_the_bottom_tip(self):
        self.assertTrue(heart_contains(0,-.9999999999999999))
        self.assertFalse(heart_contains(0,-1.0000000000000002))

    def test_fractional_heartbeat_does_not_overflow_the_heart_profile(self):
        c,area=self.canvas((180,55))
        lyric_happy_execution(c,67.3,area,MusicState(time=67.3,low=1,beat=.4830917874396188))
        self.assertTrue(self.heart_points(c,area,'happy'))

    def assert_round(self, points):
        x0, y0, x1, y1 = bounds(points)
        physical_width = (x1 - x0 + 1) * .5
        physical_height = y1 - y0 + 1
        self.assertLessEqual(abs(physical_width - physical_height),
                             max(physical_width, physical_height) * .10 + 1)

    def assert_heart_aspect(self, points):
        x0, y0, x1, y1 = bounds(points)
        physical_width = (x1 - x0 + 1) * .5
        physical_height = y1 - y0 + 1
        self.assertLessEqual(abs(physical_width - physical_height * 1.22),
                             max(physical_width, physical_height) * .10 + .5)

    def assert_inside(self, points, area):
        l, top, r, bottom = area
        self.assertTrue(points)
        for x, y in points:
            self.assertGreaterEqual(int(x), l)
            self.assertLessEqual(int(x), r)
            self.assertGreaterEqual(int(y), top)
            self.assertLessEqual(int(y), bottom)

    def test_projection_uses_one_physical_scale_at_every_size_and_depth(self):
        for size in SIZES:
            c, area = self.canvas(size)
            for depth in (-.7, 0, .7):
                with self.subTest(size=size, depth=depth):
                    center = point(0, 0, depth, area, rotate=False)
                    horizontal = point(1, 0, depth, area, rotate=False)
                    vertical = point(0, 1, depth, area, rotate=False)
                    self.assertAlmostEqual((horizontal[0] - center[0]) * .5,
                                           vertical[1] - center[1])
                    self.assert_inside([(horizontal[0], horizontal[1]),
                                        (vertical[0], vertical[1])], area)

    def test_projection_keeps_perspective_and_rotation(self):
        for size in SIZES:
            c, area = self.canvas(size)
            l, top, r, bottom = area
            cx, cy = (l + r) / 2, (top + bottom) / 2
            near = point(.5, .5, -.7, area, rotate=False)
            far = point(.5, .5, .7, area, rotate=False)
            self.assertGreater(near[0] - cx, far[0] - cx)
            self.assertGreater(near[1] - cy, far[1] - cy)
            rotated = point(.5, .5, 0, area, t=2)
            self.assertNotEqual(rotated, point(.5, .5, 0, area, t=0))

    def test_clock_face_is_round_and_large_without_borrowing_status_rows(self):
        for size in SIZES:
            for at in (92.015, 93.2, 94.55, 95.45):
                with self.subTest(size=size, time=at):
                    c, area = self.canvas(size)
                    l, top, r, bottom = area
                    lyric_daynight_clock(c, at, area)
                    face = [(int(x), int(y)) for x, y, text, ink in c.requests
                            if text == '.' and ink == N and x < (l + r) / 2]
                    self.assert_round(face)
                    x0, y0, x1, y1 = bounds(face)
                    height = bottom - top + 1
                    attainable = min(height * .70, ((l + r) / 2 - l - 2) * .5)
                    self.assertGreaterEqual(y1 - y0 + 1, attainable - 1)
                    self.assertLessEqual(y1 - y0 + 1, height * .85 + 1)
                    self.assertGreater(y0, top)
                    self.assertLess(y1, bottom)
                    self.assert_inside(face, area)
                    headers = [text for x, y, text, ink in c.requests
                               if int(y) <= top + 1 and len(text.strip()) > 10]
                    footers = [text for x, y, text, ink in c.requests
                               if int(y) >= bottom - 1 and len(text.strip()) > 10]
                    self.assertEqual(len(headers), 1)
                    self.assertEqual(len(footers), 1)

    def test_clock_has_twelve_centered_roman_numerals_in_clockwise_order(self):
        roman=('XII','I','II','III','IV','V','VI','VII','VIII','IX','X','XI')
        for size in SIZES:
            with self.subTest(size=size):
                c,area=self.canvas(size)
                lyric_daynight_clock(c,93.2,area)
                labels=[(int(x),int(y),text) for x,y,text,ink in c.requests if text in roman]
                self.assertEqual([text for x,y,text in labels],list(roman))
                cx,cy=next((x,y) for x,y,text,ink in c.requests if text=='@')
                top,right,bottom,left=(labels[i] for i in (0,3,6,9))
                self.assertLess(top[1],cy)
                self.assertGreater(right[0],cx)
                self.assertGreater(bottom[1],cy)
                self.assertLess(left[0],cx)
                self.assertLessEqual(abs(top[0]+1-cx),.5)
                for x,y,text in labels:
                    self.assert_inside([(x,y),(x+len(text)-1,y)],area)

    def test_roman_numerals_survive_hands_and_composed_role_overlays(self):
        from player import Film
        film=Film();roman={'XII','I','II','III','IV','V','VI','VII','VIII','IX','X','XI'}
        for size in SIZES:
            for t in (92.1,92.5,93.2,93.8,94.55,95.2,95.45):
                with self.subTest(size=size,time=t):
                    c,area=self.canvas(size)
                    lyric_daynight_clock(c,t,area)
                    final=film.render(t,*size,hud_visible=False)
                    for x,y,text,ink in c.requests:
                        if text in roman:
                            shown=''.join(ch for ch,_ in final.cells[int(y)][int(x):int(x)+len(text)])
                            self.assertEqual(shown,text)

    def test_clock_bitmap_preserves_font_with_one_integer_scale_and_retains_am_pm(self):
        for size in SIZES:
            for at, leading_pixel in ((93.2, False), (95.2, True)):
                with self.subTest(size=size, time=at):
                    c, area = self.canvas(size)
                    lyric_daynight_clock(c, at, area)
                    mid = (area[0] + area[2]) / 2
                    pixels = {(int(x), int(y)) for x, y, text, ink in c.requests
                              if text == '#' and ink == W and x > mid}
                    x0, y0, x1, y1 = bounds(pixels)
                    self.assertEqual((x1 - x0 + 1) % 11, 0)
                    self.assertEqual((y1 - y0 + 1) % 5, 0)
                    k = (y1 - y0 + 1) // 5
                    self.assertEqual(x1 - x0 + 1, 11 * k)
                    self.assertEqual((x0, y0) in pixels, leading_pixel)
                    self.assert_inside(list(pixels), area)

    def test_clock_bitmap_and_digital_time_are_visible_with_clearance_at_all_sizes(self):
        cases = (((64, 24), 2), ((80, 30), 3), ((120, 30), 3),
                 ((128, 44), 4), ((180, 55), 4))
        for size, scale in cases:
            for at in (93.2, 95.2):
                with self.subTest(size=size, time=at):
                    c, area = self.canvas(size)
                    lyric_daynight_clock(c, at, area)
                    mid = (area[0] + area[2]) // 2
                    pixels = {(int(x), int(y)) for x, y, text, ink in c.requests
                              if text == '#' and ink == W and x > mid}
                    x0, y0, x1, y1 = bounds(pixels)
                    self.assertEqual((x1-x0+1, y1-y0+1), (11*scale, 5*scale))
                    self.assertGreater(x0, mid + 1)
                    self.assertLess(x1, area[2])
                    self.assertGreater(y0, area[1] + 1)
                    for x, y in pixels:
                        self.assertEqual(c.cells[y][x], ('#', W))
                    tx, ty, text, ink = next(request for request in c.requests
                                            if len(request[2]) == 5 and request[2][2] == ':'
                                            and request[2][:2].isdigit())
                    self.assertGreaterEqual(ty, y1 + 2)
                    self.assertLessEqual(ty, area[3] - 2)
                    self.assertGreater(tx, mid + 1)
                    self.assertLess(tx + len(text) - 1, area[2])
                    self.assertEqual(''.join(ch for ch, ink in
                                             c.cells[int(ty)][int(tx):int(tx)+5]), text)

    def test_clock_marks_and_hands_share_the_face_scale(self):
        for size in SIZES:
            for at in (92.015, 93.2, 94.55, 95.45):
                with self.subTest(size=size, time=at):
                    c, area = self.canvas(size)
                    lyric_daynight_clock(c, at, area)
                    cx, cy = next((x, y) for x, y, text, ink in c.requests if text == '@')
                    rim = [(x, y) for x, y, text, ink in c.requests
                           if text == '.' and ink == N and x < (area[0] + area[2]) / 2]
                    radius = (max(x for x, y in rim) - min(x for x, y in rim)) * .25
                    marks = [line for line in c.lines if line[4:] == ('#', B)]
                    self.assertEqual(len(marks), 13)
                    for x0, y0, x1, y1, ch, ink in marks[:12]:
                        self.assertAlmostEqual(((x1-cx)**2 * .25 + (y1-cy)**2)**.5,
                                               radius, places=6)
                    for fraction, ch, ink in ((.52, '#', B), (.83, '*', W)):
                        x0, y0, x1, y1, _, _ = next(line for line in reversed(c.lines)
                                                   if line[4:] == (ch, ink))
                        self.assertAlmostEqual(((x1-x0)**2 * .25 + (y1-y0)**2)**.5,
                                               radius * fraction, places=6)

    def heart_points(self, c, area, kind):
        l, top, r, bottom = area
        if kind == 'happy':
            rail = max(9, min(22, (c.w - 8) // 6))
            l, r = l + rail + 2, r - rail - 3
            inks = (N, B, W)
        elif kind == 'only':
            rail = max(10, min(20, c.w // 7))
            l, r = l + rail + 1, r - rail - 1
            inks = (R, 7)
        else:
            inks = (N, B, W)
        return {(int(x), int(y)) for x, y, text, ink in c.requests
                if text in ('#', '*', '.', '0', '1') and ink in inks
                and l <= x <= r}

    def render_heart(self, size, kind, peak=False, inset=0, at=None):
        c, area = self.canvas(size, inset)
        if kind == 'happy':
            at = 67.3 if at is None else at
            lyric_happy_execution(c, at, area, MusicState(time=at, low=1, beat=int(peak)))
        elif kind == 'repair':
            at = 123.24 if at is None else at
            lyric_erase_fragments(c, at, area, at - 118.333)
        elif kind == 'only':
            at = 167.0 if at is None else at
            lyric_only_execution(c, at, area, MusicState(time=at, low=1, beat=int(peak)))
        else:
            at = 190.0 if at is None else at
            lyric_heart(c, at, area, 2, int(peak))
        return c, area, self.heart_points(c, area, kind)

    def test_all_four_hearts_have_recognizable_physical_aspect_and_scale(self):
        for size in SIZES:
            for kind in ('happy', 'repair', 'only', 'trapped'):
                with self.subTest(size=size, heart=kind):
                    c, area, pixels = self.render_heart(size, kind)
                    self.assert_heart_aspect(pixels)
                    x0, y0, x1, y1 = bounds(pixels)
                    height = area[3] - area[1] + 1
                    # The side registers constrain the two execution hearts on small windows.
                    available_width = area[2] - area[0] + 1
                    if kind == 'happy':
                        available_width -= 2 * max(9, min(22, (c.w - 8) // 6)) + 5
                    elif kind == 'only':
                        available_width -= 2 * max(10, min(20, c.w // 7)) + 2
                    attainable = min(height * .70, available_width * .5 / 1.22)
                    self.assertGreaterEqual(y1 - y0 + 1, attainable - 1)
                    self.assertLessEqual(y1 - y0 + 1, height * .85 + 1)
                    # Two lobes, a central notch, and a tapering lower point.
                    upper = y0 + max(1, (y1 - y0) // 9)
                    middle = (x0 + x1) / 2
                    self.assertTrue(any(x < middle - 1 and y <= upper for x, y in pixels))
                    self.assertTrue(any(x > middle + 1 and y <= upper for x, y in pixels))
                    self.assertNotIn((int(middle), y0), pixels)
                    tip_width = sum(y == y1 for x, y in pixels)
                    self.assertLess(tip_width, (x1 - x0 + 1) * .5)
                    self.assert_inside(list(pixels), area)

    def test_heart_has_a_deep_cleft_between_two_full_lobes(self):
        for size in SIZES:
            for kind in ('happy', 'repair', 'only', 'trapped'):
                with self.subTest(size=size, heart=kind):
                    c, area, pixels = self.render_heart(size, kind)
                    x0, y0, x1, y1 = bounds(pixels)
                    height=y1-y0+1
                    middle=(x0+x1)/2
                    center_top=min(y for x,y in pixels if abs(x-middle)<=.51)
                    self.assertGreaterEqual(center_top-y0, height*.18-.5)
                    self.assertLessEqual(center_top-y0, height*.32+1)
                    shoulder=y0+int(height*.30)
                    span=[x for x,y in pixels if y==shoulder]
                    self.assertGreaterEqual(max(span)-min(span), (x1-x0)*.80)

    def test_happiness_heart_has_a_continuous_bright_edge_and_quieter_fill(self):
        for size in SIZES:
            with self.subTest(size=size):
                c,area,pixels=self.render_heart(size,'happy')
                edge={p for p in pixels if any((p[0]+dx,p[1]+dy) not in pixels
                                              for dx,dy in ((-1,0),(1,0),(0,-1),(0,1)))}
                bright=sum(c.cells[y][x][1]==W for x,y in edge)
                self.assertGreaterEqual(bright,len(edge)*.85)
                interior=pixels-edge
                quiet=sum(c.cells[y][x][1] in (N,5,6) for x,y in interior)
                self.assertGreater(quiet,len(interior)*.5)

    def test_trapped_label_leaves_the_bottom_point_visible(self):
        for size in SIZES:
            with self.subTest(size=size):
                c,area=self.canvas(size)
                draw_scene(c,190.,area[1],area[3],MusicState(time=190.,low=1,beat=1),None)
                pixels=self.heart_points(c,area,'trapped')
                tip=max(y for x,y in pixels)
                self.assertTrue(any(c.cells[y][x][0]=='#' for x,y in pixels if y==tip))
                labels=[y for x,y,text,ink in c.requests if text=='TRAPPED']
                self.assertTrue(labels)
                self.assertGreater(min(labels),tip)

    def test_peak_hearts_fit_before_canvas_clipping_and_have_closed_silhouettes(self):
        for size in SIZES:
            for kind in ('happy', 'repair', 'only', 'trapped'):
                with self.subTest(size=size, heart=kind):
                    c, area, pixels = self.render_heart(size, kind, peak=True)
                    x0, y0, x1, y1 = bounds(pixels)
                    self.assertGreater(y0, area[1] + 1)
                    self.assertLess(y1, area[3] - 1)
                    self.assert_inside(list(pixels), area)
                    # A clipped heart has a broad, flat bottom or side.
                    self.assertLess(sum(y == y1 for x, y in pixels), (x1 - x0 + 1) * .5)
                    for xedge in (x0, x1):
                        self.assertLess(sum(x == xedge for x, y in pixels),
                                        (y1 - y0 + 1) * .6 + 1)

    def test_heart_size_grows_with_window_and_pulse(self):
        for kind in ('happy', 'repair', 'only', 'trapped'):
            extents = []
            for size in ((64, 24), (120, 30), (180, 55)):
                c, area, pixels = self.render_heart(size, kind)
                x0, y0, x1, y1 = bounds(pixels)
                extents.append(y1 - y0 + 1)
            self.assertGreater(extents[1], extents[0], kind)
            self.assertGreater(extents[2], extents[1], kind)
            if kind != 'repair':
                c, area, resting = self.render_heart((180, 55), kind)
                c, area, peak = self.render_heart((180, 55), kind, peak=True)
                self.assertGreater(len(peak), len(resting), kind)

    def test_broken_fragments_fit_without_flattening_at_lower_bound(self):
        for size in SIZES:
            for at in (123.8, 124.89, 125.69):
                with self.subTest(size=size, time=at):
                    c, area = self.canvas(size)
                    lyric_erase_fragments(c, at, area, at - 118.333)
                    points = [(x, y) for x, y, text, ink in c.requests
                              if len(text) == 1 and text in '#x01.' and ink in (N, B, W, R, 7)]
                    self.assert_inside(points, (area[0], area[1] + 2,
                                                area[2], area[3] - 2))

    def test_geometry_obeys_supplied_shorter_scene_bounds(self):
        for size in SIZES:
            c, area = self.canvas(size, inset=3)
            lyric_daynight_clock(c, 93.2, area)
            self.assert_inside([(x, y) for x, y, text, ink in c.requests
                                if text.strip()], area)
            for kind in ('happy', 'repair', 'only', 'trapped'):
                c, area, pixels = self.render_heart(size, kind, peak=True, inset=3)
                self.assert_inside(list(pixels), area)
                self.assert_heart_aspect(pixels)

    def test_projected_sphere_is_round_and_organic_models_keep_their_forms(self):
        for size in SIZES:
            for form in ('sphere', 'eggplant', 'tomato'):
                with self.subTest(size=size, form=form):
                    c, area = self.canvas(size)
                    legacy_mesh(c, 0, area, form)
                    pixels = [(x, y) for y, row in enumerate(c.cells)
                              for x, (ch, ink) in enumerate(row) if ch.strip()]
                    self.assert_inside(pixels, area)
                    x0, y0, x1, y1 = bounds(pixels)
                    ratio = (x1 - x0 + 1) * .5 / (y1 - y0 + 1)
                    if form == 'sphere':
                        self.assert_round(pixels)
                    elif form == 'eggplant':
                        self.assertLess(ratio, .65)
                    else:
                        self.assertGreater(ratio, 1.25)
                        self.assertLess(ratio, 1.7)

    def test_active_circle_stays_round_at_peak_audio(self):
        for size in SIZES:
            with self.subTest(size=size):
                c, area = self.canvas(size)
                lyric_circle_circumference(c, 35.2, area, 35.2 - 33.412,
                                          MusicState(time=35.2, low=1, beat=1))
                rim = [(int(x), int(y)) for x, y, text, ink in c.requests
                       if text in ('o', '\u25c9')]
                self.assert_round(rim)
                self.assert_inside(rim, area)

    def test_active_heart_routing_leaves_visible_silhouettes_under_overlays(self):
        for size in SIZES:
            for kind, at in (('happy', 67.3), ('repair', 123.24),
                             ('only', 167.0), ('trapped', 190.0)):
                with self.subTest(size=size, heart=kind):
                    c, area = self.canvas(size)
                    draw_scene(c, at, area[1], area[3], MusicState(time=at, low=1, beat=1), None)
                    pixels = self.heart_points(c, area, kind)
                    self.assert_heart_aspect(pixels)
                    visible = {(x, y) for x, y in pixels
                               if c.cells[y][x][0] in ('#', '0', '1', '*', '.')}
                    self.assertGreater(len(visible), len(pixels) * .3)
                    self.assert_heart_aspect(visible)

    def test_active_eggplant_tomato_and_cat_stay_in_supplied_bounds(self):
        for size in SIZES:
            for at in (74.1, 76.9, 77.6, 80.9, 81.4, 84.9):
                with self.subTest(size=size, time=at):
                    c, area = self.canvas(size)
                    draw_scene(c, at, area[1], area[3], MusicState(time=at), None)
                    self.assert_inside([(x + offset, y)
                                        for x, y, text, ink in c.requests
                                        for offset, ch in enumerate(text) if ch.strip()], area)


if __name__ == '__main__':
    unittest.main(verbosity=2)
