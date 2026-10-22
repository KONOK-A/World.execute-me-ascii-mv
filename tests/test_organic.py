"""Organic silhouettes and causal packets, observed on the real terminal grid."""
import importlib
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from music import MusicState
from player import Canvas
import visuals as v


SIZES = ((64, 24), (80, 30), (120, 30), (128, 44), (180, 55))


class OrganicTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('scenes_organic'),
                             'The independent organic renderer has not been implemented')
        return importlib.import_module('scenes_organic')

    def render(self, t, size=(128, 44), area=None, music=None):
        w, h = size
        c = Canvas(w, h)
        area = area if area is not None else (2, 1, w-3, h-4)
        self.module().draw_organic(c, t, area, music or MusicState(time=t))
        return c

    def subject_cells(self, c, inks):
        # Ignore code, actors and resource buffer; inspect the object, without titles.
        first_row = 5 if c.w < 100 or c.h < 34 else 7
        return {(x, y) for y, row in enumerate(c.cells)
                for x, (ch, ink) in enumerate(row)
                if c.w*.18 <= x <= c.w*.67 and first_row <= y < c.h-5
                and ch.strip() and ink in inks}

    def bounds(self, cells):
        self.assertTrue(cells, 'A visible procedural object is required')
        xs, ys = zip(*cells)
        return min(xs), min(ys), max(xs), max(ys)

    def test_phase_changes_at_the_lyric_boundaries_and_never_early(self):
        renderer = self.module()
        cases = (
            (74.045, 'eggplant', 'cast'), (75.421, 'eggplant', 'cast'),
            (75.422, 'eggplant', 'extract'), (76.958, 'eggplant', 'extract'),
            (76.959, 'eggplant', 'receive'), (77.575, 'eggplant', 'receive'),
            (77.576, 'tomato', 'cast'), (79.225, 'tomato', 'cast'),
            (79.226, 'tomato', 'extract'), (80.619, 'tomato', 'extract'),
            (80.620, 'tomato', 'receive'), (81.350, 'tomato', 'receive'),
            (81.351, 'cat', 'cast'), (82.832, 'cat', 'cast'),
            (82.833, 'cat', 'extract'), (84.267, 'cat', 'extract'),
            (84.268, 'cat', 'receive'), (85.077, 'cat', 'receive'),
        )
        for t, subject, phase in cases:
            with self.subTest(time=t):
                state = renderer.organic_state(t)
                self.assertEqual((state.subject, state.phase), (subject, phase))
                self.assertGreaterEqual(state.progress, 0)
                self.assertLess(state.progress, 1)
        for t in (74.045, 75.422, 76.959, 77.576, 79.226, 80.620,
                  81.351, 82.833, 84.268):
            self.assertEqual(renderer.organic_state(t).progress, 0)

    def test_outside_the_owned_interval_is_a_noop(self):
        for t in (0, 74.044, 85.078, 200):
            self.assertIsNone(self.module().organic_state(t))
            c = self.render(t)
            self.assertFalse(c.plain().strip())
            self.assertFalse(c.protected)

    def test_eggplant_has_a_large_tapered_violet_fruit_and_green_calyx(self):
        for size in SIZES:
            with self.subTest(size=size):
                c = self.render(74.8, size)
                fruit = self.subject_cells(c, {v.VIOLET, v.VIOLET_HIGH})
                l, top, r, bottom = self.bounds(fruit)
                self.assertGreaterEqual(bottom-top+1, (c.h-4)*.43)
                self.assertGreaterEqual(r-l+1, c.w*.14)
                upper = [x for x, y in fruit if y == top+round((bottom-top)*.2)]
                lower = [x for x, y in fruit if y == top+round((bottom-top)*.65)]
                self.assertGreater(len(lower), len(upper)*1.25,
                                   'The fruit must widen below its neck')
                greens = self.subject_cells(c, {v.GREEN, v.GREEN_HIGH})
                self.assertLess(min(y for _, y in greens), top)
                self.assertGreater(max(x for x, _ in greens)-min(x for x, _ in greens),
                                   (r-l)*.35, 'A broad leaf cap must attach to the stem')

    def test_tomato_is_round_in_physical_cells_with_a_leaf_star_and_stem(self):
        for size in SIZES:
            with self.subTest(size=size):
                c = self.render(78.4, size)
                fruit = self.subject_cells(c, {v.TOMATO, v.TOMATO_DIM, v.TOMATO_HIGH})
                l, top, r, bottom = self.bounds(fruit)
                ratio = (r-l+1)*v.CELL_ASPECT/(bottom-top+1)
                self.assertGreater(ratio, .8)
                self.assertLess(ratio, 1.25)
                self.assertGreaterEqual(bottom-top+1, (c.h-4)*.40)
                greens = self.subject_cells(c, {v.GREEN, v.GREEN_HIGH})
                gl, gt, gr, gb = self.bounds(greens)
                self.assertLess(gt, top)
                self.assertGreater(gr-gl, (r-l)*.35)
                self.assertLess(gb, top+(bottom-top)*.4)

    def test_cat_has_two_ears_eyes_whiskers_stripes_and_a_separate_curled_tail(self):
        for size in SIZES:
            with self.subTest(size=size):
                c = self.render(82.0, size)
                fur = self.subject_cells(c, {v.N, v.D, v.G})
                l, top, r, bottom = self.bounds(fur)
                self.assertGreaterEqual(bottom-top+1, (c.h-4)*.5)
                self.assertGreaterEqual(r-l+1, c.w*.28)
                ears = False
                for y in range(top, top+max(2, (bottom-top)//5)):
                    xs = sorted(x for x, yy in fur if yy == y)
                    ears |= any(b-a >= 3 for a, b in zip(xs, xs[1:]))
                self.assertTrue(ears, 'Two pointed ears need a visible gap')
                eyes = self.subject_cells(c, {v.GREEN_HIGH})
                el, et, er, eb = self.bounds(eyes)
                self.assertGreater(er-el, (r-l)*.17)
                self.assertLessEqual(eb-et, 2)
                stripes = {(x, y) for x, y in self.subject_cells(c, {v.G}) if y > eb}
                self.assertGreaterEqual(len(stripes), 6)
                whiskers = {(x, y) for x, y in self.subject_cells(c, {v.W})
                            if eb < y < top+(bottom-top)*.65}
                self.assertTrue(any(x < el for x, _ in whiskers))
                self.assertTrue(any(x > er for x, _ in whiskers))
                self.assertGreater(r-er, (er-el)*.9, 'A curled tail must extend beside the body')

    def test_highlighted_code_resource_and_output_share_one_phase(self):
        cases = ((74.8, 'me.cast(Eggplant)', 'CAST'),
                 (76.0, 'r = me.nutrients()', 'EXTRACT'),
                 (77.2, 'you.receive(r)', 'NUTRIENTS'),
                 (78.0, 'me.cast(Tomato)', 'CAST'),
                 (79.7, 'r = me.antioxidants()', 'EXTRACT'),
                 (80.9, 'you.receive(r)', 'ANTIOXIDANTS'),
                 (82.0, 'me.cast(TabbyCat)', 'CAST'),
                 (83.4, 'r = me.purr()', 'PURR'),
                 (84.6, 'you.receive(r)', 'ENJOYMENT'))
        for size in SIZES:
            for t, clause, status in cases:
                with self.subTest(size=size, time=t):
                    c = self.render(t, size)
                    active = [''.join(ch for ch, ink in row if ink == v.W)
                              for row in c.cells]
                    self.assertTrue(any('> '+clause in line for line in active))
                    self.assertIn(status, c.plain())
                    code_rows = sum(''.join(ch for ch, _ in row).lstrip().startswith(
                        ('> ', 'me.', 'r =', 'you.')) for row in c.cells)
                    self.assertLessEqual(code_rows, 2 if size[0] < 100 or size[1] < 34 else 4)
                    self.assertEqual(self.module().organic_state(t).resource,
                                     'ENJOYMENT' if t > 81.351 else
                                     'ANTIOXIDANTS' if t >= 77.576 else 'NUTRIENTS')

    def test_packets_travel_from_me_to_object_then_from_object_to_you(self):
        for early, late, ink in ((74.25, 75.2, v.ME),
                                 (75.7, 76.7, v.GREEN_HIGH),
                                 (77.0, 77.5, v.GREEN_HIGH),
                                 (79.4, 80.4, v.GREEN_HIGH),
                                 (80.7, 81.2, v.GREEN_HIGH),
                                 (83.0, 84.1, v.ROSE),
                                 (84.3, 84.9, v.ROSE)):
            with self.subTest(times=(early, late)):
                heads = []
                for t in (early, late):
                    c = self.render(t)
                    heads.append([(x, y) for y, row in enumerate(c.cells)
                                  for x, cell in enumerate(row)
                                  if 5 <= y < c.h-5 and cell == ('>', ink)])
                    self.assertEqual(len(heads[-1]), 1, 'Each active route needs one packet head')
                    self.assertIn('ME', c.plain())
                    self.assertIn('YOU', c.plain())
                self.assertLess(heads[0][0][0], heads[1][0][0])
                self.assertLess(heads[1][0][0], 128*.90)
                self.assertEqual(heads[0][0][1], heads[1][0][1])
        self.assertNotIn('RX OK', self.render(77.0).plain())
        self.assertIn('RX OK', self.render(77.55).plain())

    def test_call_arrival_and_extraction_start_touch_the_visible_object(self):
        # A packet ending at an empty layout box would leave the causal path broken.
        cases = ((75.421, v.ME, {v.VIOLET, v.VIOLET_HIGH}),
                 (75.422, v.GREEN_HIGH, {v.VIOLET, v.VIOLET_HIGH}),
                 (79.225, v.ME, {v.TOMATO, v.TOMATO_DIM, v.TOMATO_HIGH}),
                 (79.226, v.GREEN_HIGH, {v.TOMATO, v.TOMATO_DIM, v.TOMATO_HIGH}),
                 (82.832, v.ME, {v.N, v.D, v.G, v.W}),
                 (82.833, v.ROSE, {v.N, v.D, v.G, v.W}))
        for size in SIZES:
            for t, ink, fruit_inks in cases:
                with self.subTest(size=size, time=t):
                    c = self.render(t, size)
                    heads = [(x, y) for y, row in enumerate(c.cells)
                             for x, cell in enumerate(row)
                             if 5 <= y < c.h-5 and cell == ('>', ink)]
                    self.assertEqual(len(heads), 1)
                    x, y = heads[0]
                    distance = min(abs(x-fx)+abs(y-fy)
                                   for fx, fy in self.subject_cells(c, fruit_inks))
                    self.assertLessEqual(distance, 2, 'Packets must touch the object surface')

    def test_fruit_resources_are_visible_payloads_on_multiple_transport_rows(self):
        for size in SIZES:
            for at,token in ((76.1,'[N]'),(79.9,'{A}')):
                with self.subTest(size=size,time=at):
                    c=self.render(at,size)
                    rows=[''.join(ch for ch,_ in row) for row in c.cells]
                    payload_rows=[y for y,row in enumerate(rows) if token in row]
                    self.assertGreaterEqual(len(payload_rows),2,
                                            'Fruit transport must show grouped payloads, not just a pointer')
                    self.assertIn('STORE',c.plain())

    def test_resource_receipt_lights_the_receiver_only_after_packet_arrival(self):
        for size in SIZES:
            for start,end in ((76.959,77.576),(80.620,81.351)):
                with self.subTest(size=size,start=start):
                    early=self.render(start+.001,size)
                    late=self.render(end-.025,size)
                    self.assertIn('RX +00',early.plain())
                    self.assertIn('RX +06',late.plain())
                    self.assertIn('RX OK',late.plain())
                    def charge(c):
                        label_y=next(y for y,row in enumerate(c.cells)
                                     if 'YOU' in ''.join(ch if ink==v.YOU else ' ' for ch,ink in row))
                        return sum(ch=='+' and ink==v.GREEN_HIGH
                                   for y,row in enumerate(c.cells) for x,(ch,ink) in enumerate(row)
                                   if x>=c.w*.86 and abs(y-label_y)<=2)
                    self.assertEqual(charge(early),0)
                    self.assertGreater(charge(late),2)
                    self.assertIn('YOU',late.plain())

    def test_resource_packets_do_not_appear_during_object_creation(self):
        for at,token in ((75.1,'[N]'),(78.8,'{A}')):
            with self.subTest(time=at):
                c=self.render(at)
                self.assertNotIn(token,c.plain())
                self.assertNotIn('RX +',c.plain())

    def test_role_labels_survive_packets_and_use_distinct_core_shapes_and_palette(self):
        for t in (75.3, 76.8, 77.55, 80.5, 81.3, 84.1, 85.0):
            for size in SIZES:
                with self.subTest(time=t, size=size):
                    c = self.render(t, size)
                    for label, ink in (('ME', v.ME), ('YOU', v.YOU)):
                        matches = [(x, y) for y, row in enumerate(c.cells)
                                   for x in range(c.w-len(label)+1)
                                   if ''.join(ch for ch, _ in row[x:x+len(label)]) == label
                                   and all(style == ink for _, style in row[x:x+len(label)])]
                        self.assertEqual(len(matches), 1)
                        x, y = matches[0]
                        for xx in range(x, x+len(label)):
                            self.assertEqual(c.protected[xx, y], c.cells[y][xx])
                    self.assertTrue(any(ch == '#' and ink == v.ME
                                        for row in c.cells for ch, ink in row))
                    self.assertTrue(any(ch == '#' and ink == v.YOU
                                        for row in c.cells for ch, ink in row))
                    self.assertTrue(all(ink in v.STYLES for row in c.cells for _, ink in row))
                    self.assertFalse(any(ch.strip() and ink == v.R
                                         for row in c.cells for ch, ink in row),
                                     'Error red is not organic/resource ink')

    def test_inclusive_translated_areas_preserve_every_cell_outside_and_the_callers_clip(self):
        for w, h in SIZES:
            for area in ((0, 0, w-1, h-1), (7, 3, w-8, h-5)):
                for t in (74.1, 76.959, 78.1, 80.620, 82.0, 84.268, 85.077):
                    with self.subTest(size=(w, h), area=area, time=t):
                        c = Canvas(w, h)
                        c.clip = (0, h-1)
                        for y in range(h):
                            c.put(0, y, '@'*w, v.NEUTRAL)
                        self.module().draw_organic(c, t, area, MusicState(time=t))
                        l, top, r, bottom = area
                        self.assertEqual(c.clip, (0, h-1))
                        self.assertTrue(all(cell == ('@', v.NEUTRAL)
                                            for y, row in enumerate(c.cells)
                                            for x, cell in enumerate(row)
                                            if not (l <= x <= r and top <= y <= bottom)))
                        self.assertTrue(all(l <= x <= r and top <= y <= bottom
                                            for x, y in c.protected))
                        self.assertTrue(any(c.cells[bottom][x] != ('@', v.NEUTRAL)
                                            for x in range(l, r+1)),
                                        'The passed bottom row is usable; no footer is implied')

    def test_ambient_blink_breath_and_purr_follow_audio_time_and_music(self):
        cat_frames = [self.render(81.351+i*.05) for i in range(60)]
        eye_counts = [len(self.subject_cells(c, {v.GREEN_HIGH})) for c in cat_frames]
        self.assertEqual(min(eye_counts), 0, 'The cat must occasionally blink')
        self.assertGreater(max(eye_counts), 1)
        shapes = [self.subject_cells(c, {v.N, v.D, v.G}) for c in cat_frames]
        self.assertGreater(len({frozenset(points) for points in shapes}), 3)
        before = self.render(82.7)
        after = self.render(83.5)
        self.assertFalse(any(ch == '~' and ink == v.ROSE
                             for row in before.cells for ch, ink in row))
        self.assertTrue(any(ch == '~' and ink == v.ROSE
                            for row in after.cells for ch, ink in row))
        quiet = self.render(83.5, music=MusicState(time=83.5, low=0, beat=0, beat_position=0))
        loud = self.render(83.5, music=MusicState(time=83.5, low=1, beat=1, beat_position=3))
        self.assertNotEqual(quiet.cells, loud.cells)

    def test_same_audio_sample_is_independent_of_seek_order_or_frame_rate(self):
        times = (74.045, 75.422, 76.959, 77.576, 79.226, 80.620,
                 81.351, 82.5, 82.833, 84.268, 85.077)
        expected = {t: self.render(t).cells for t in times}
        states = {t: self.module().organic_state(t) for t in times}
        for fps in (15, 30, 60):
            for t in reversed(times):
                self.render(t-1/fps)
                self.assertEqual(self.render(t).cells, expected[t])
                self.assertEqual(self.module().organic_state(t), states[t])

    def test_runtime_module_import_does_not_load_player_or_scenes(self):
        self.module()
        result = subprocess.run(
            [sys.executable, '-B', '-c',
             "import sys; import scenes_organic; "
             "assert 'player' not in sys.modules; assert 'scenes' not in sys.modules"],
            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
