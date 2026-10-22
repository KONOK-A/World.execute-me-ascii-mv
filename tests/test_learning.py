"""Learning's numbers, vocal timing and real Canvas requests share one state."""
from dataclasses import FrozenInstanceError, fields, is_dataclass
import ast
import importlib
import math
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from music import MusicState
from player import Canvas
import visuals as v

try:
    learning = importlib.import_module('scenes_learning')
except ModuleNotFoundError as error:
    if error.name != 'scenes_learning':
        raise
    learning = None


SIZES = ((64, 24), (80, 30), (120, 30), (128, 44), (180, 55))
VOCALS = ((179.929, 180.857), (183.646, 184.540), (187.665, 188.483))
PHASES = (
    (177.4, 'input', ('YOU', 'tokens'), 'ids ='),
    (178.0, 'attention', ('tokens', 'attention'), 'A ='),
    (178.8, 'forward', ('attention', 'W1', 'W2', 'logits'), 'z ='),
    (179.4, 'sample', ('logits', 'sample'), 'tok ='),
    (180.0, 'output', ('sample', 'output'), 'emit('),
    (181.0, 'feedback', ('output', 'feedback', 'W2'), 'W2 -='),
    (181.5, 'input', ('YOU', 'tokens'), 'ids ='),
    (182.1, 'attention', ('tokens', 'attention'), 'A ='),
    (182.8, 'forward', ('attention', 'W1', 'W2', 'logits'), 'z ='),
    (183.2, 'sample', ('logits', 'sample'), 'tok ='),
    (184.7, 'feedback', ('output', 'feedback', 'W2'), 'W2 -='),
    (185.4, 'input', ('YOU', 'tokens'), 'ids ='),
    (186.0, 'attention', ('tokens', 'attention'), 'A ='),
    (186.7, 'forward', ('attention', 'W1', 'W2', 'logits'), 'z ='),
    (187.2, 'sample', ('logits', 'sample'), 'tok ='),
    (188.0, 'output', ('sample', 'output'), 'emit('),
)


class AuditCanvas(Canvas):
    """Real rasterization, recording requests before Canvas can conceal overflow."""
    def __init__(self, w, h):
        super().__init__(w, h)
        self.requests = []
        self.lines = []
        self.rectangles = []

    def put(self, x, y, text, style=1):
        self.requests.append((x, y, str(text), style))
        super().put(x, y, text, style)

    def line(self, x0, y0, x1, y1, ch='.', style=0):
        self.lines.append((x0, y0, x1, y1, ch, style))
        super().line(x0, y0, x1, y1, ch, style)

    def box(self, x, y, w, h, style=0):
        self.rectangles.append((x, y, w, h))
        super().box(x, y, w, h, style)

    def protect(self, x, y, w, h):
        self.rectangles.append((x, y, w, h))
        super().protect(x, y, w, h)


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(learning, 'missing scenes_learning implementation')

    def draw(self, size, at, inset=0, music=None):
        w, h = size
        area = (2 + inset, 1 + inset, w - 3 - inset, h - 4 - inset)
        canvas = AuditCanvas(w, h)
        canvas.clip = (area[1], area[3])
        # The caller's frame and three subtitle rows must survive untouched.
        for y in range(h):
            for x in range(w):
                if not (area[0] <= x <= area[2] and area[1] <= y <= area[3]):
                    canvas.cells[y][x] = ('~', v.NEUTRAL)
        learning.draw_learning(canvas, at, area, music or MusicState(time=at))
        return canvas, area

    def assert_requests_in_area(self, canvas, area):
        l, top, r, bottom = area
        for x, y, text, _ in canvas.requests:
            self.assertGreaterEqual(x, l, (x, y, text))
            self.assertLessEqual(x + len(text) - 1, r, (x, y, text))
            self.assertGreaterEqual(y, top, (x, y, text))
            self.assertLessEqual(y, bottom, (x, y, text))
        for x0, y0, x1, y1, _, _ in canvas.lines:
            for x, y in ((x0, y0), (x1, y1)):
                self.assertTrue(l <= x <= r and top <= y <= bottom)
        for x, y, w, h in canvas.rectangles:
            self.assertTrue(l <= x <= x + w - 1 <= r, (x, y, w, h))
            self.assertTrue(top <= y <= y + h - 1 <= bottom, (x, y, w, h))
        for y, row in enumerate(canvas.cells):
            for x, cell in enumerate(row):
                if not (l <= x <= r and top <= y <= bottom):
                    self.assertEqual(cell, ('~', v.NEUTRAL))

    def test_state_is_recursively_immutable_and_seek_independent(self):
        def immutable(value):
            if is_dataclass(value):
                for field in fields(value):
                    immutable(getattr(value, field.name))
            elif isinstance(value, tuple):
                for part in value:
                    immutable(part)
            else:
                self.assertIsInstance(value, (str, int, float, bool, type(None)))

        original = learning.learning_state(183.646)
        immutable(original)
        hash(original)
        with self.assertRaises((FrozenInstanceError, AttributeError, TypeError)):
            original.output = 'EOS'
        for at in (188.45, 177.246, 180.0, 184.9, 178.1):
            learning.learning_state(at)
        self.assertEqual(original, learning.learning_state(183.646))

    def test_vocal_windows_switch_at_start_and_end_within_one_frame(self):
        for start, end in VOCALS:
            for at, expected in ((start - 1/30, ''), (start, 'LOVE'),
                                 (start + 1/30, 'LOVE'), (end - 1/30, 'LOVE'),
                                 (end, ''), (end + 1/30, '')):
                with self.subTest(time=at):
                    state = learning.learning_state(at)
                    self.assertEqual(state.output, expected)
                    if expected:
                        self.assertEqual(state.phase, 'output')
                        self.assertEqual(state.selected, state.output)

    def test_question_changes_precede_each_answer_and_history_repeats(self):
        for at, question, count in ((179.929, 'HOW TO LOVE?', 1),
                                    (183.646, 'DO YOU LOVE ME?', 2),
                                    (187.665, 'CAN I LEAVE?', 3)):
            state = learning.learning_state(at)
            self.assertEqual(state.question, question)
            self.assertEqual(state.history, ('LOVE',) * count)
            canvas, _ = self.draw((128, 44), at)
            self.assertIn(question, canvas.plain())
            self.assertIn('OUT: LOVE', canvas.plain())

    def test_code_phase_and_primary_route_are_the_same_operation(self):
        for at, phase, route, prefix in PHASES:
            state = learning.learning_state(at)
            self.assertEqual(state.phase, phase)
            self.assertEqual(state.active_path, route)
            self.assertTrue(state.code_lines[state.active_code].startswith(prefix))
            for size in SIZES:
                with self.subTest(time=at, size=size):
                    canvas, _ = self.draw(size, at)
                    selected = [(x, y, text) for x, y, text, ink in canvas.requests
                                if text.startswith('> ') and ink == v.W]
                    self.assertEqual(len(selected), 1)
                    self.assertTrue(selected[0][2].startswith('> ' + prefix))
                    routes = [line for line in canvas.lines if line[4] == '=']
                    self.assertTrue(routes, phase)
                    att_box, net_box, out_box = canvas.rectangles[:3]
                    nodes = tuple((x, y) for x, y, text, color in canvas.requests
                                  if text == 'o' and color == v.ME)
                    if phase == 'forward':
                        self.assertEqual(tuple((line[2], line[3]) for line in routes), nodes)
                        a, b, choice = state.network_path
                        self.assertIn(f'w1={state.weights[0][b][a]:+.2f}', canvas.plain())
                        self.assertIn(f'w2={state.weights[1][choice][b]:+.2f}', canvas.plain())
                    elif phase == 'sample':
                        self.assertEqual(routes[0][:2], nodes[-1])
                        self.assertEqual(routes[-1][2:4], (out_box[0], out_box[1]+1))
                    elif phase == 'feedback':
                        self.assertEqual(routes[-1][2:4], nodes[-1])
                        self.assertEqual(routes[0][1], out_box[1]+out_box[3]-1)
                    elif phase == 'attention':
                        key_x = next(x for x, y, text, color in canvas.requests
                                     if y == att_box[1]+1 and color == v.ROSE_DIM)
                        query_y = max(y for x, y, text, color in canvas.requests
                                      if x == att_box[0]+1 and color == v.CYAN_DIM)
                        self.assertEqual(routes[-1][2:4], (key_x-1, query_y))
                        value = f'{round(state.attention[-1][state.attention_key]*100):02d}'
                        visible = ''.join(ch for ch, _ in canvas.cells[int(query_y)][int(key_x):int(key_x)+len(value)])
                        self.assertEqual(visible, value)
                    heads = [(x, y) for x, y, text, ink in canvas.requests
                             if text in ('>', '<') and ink != v.SHADE]
                    self.assertEqual(len(heads), 1, phase)
                    x, y = heads[0]
                    self.assertIn(canvas.cells[round(y)][round(x)][0], ('>', '<'))

    def test_forward_card_executes_last_query_projection_within_row_limit(self):
        class Matrix(tuple):
            def __matmul__(matrix, vector):
                self.assertEqual(len(vector), len(matrix[0]), 'matrix/vector dimensions')
                return tuple(sum(w*x for w, x in zip(row, vector)) for row in matrix)

            def __rmatmul__(matrix, vector):
                self.assertEqual(len(vector), len(matrix), 'query/value dimensions')
                return tuple(sum(x*row[j] for x, row in zip(vector, matrix))
                             for j in range(len(matrix[0])))

        for size in SIZES:
            for inset in (0, 2):
                for at in (178.8, 182.8, 186.7):
                    canvas, _ = self.draw(size, at, inset)
                    state = learning.learning_state(at)
                    card = [(x, y, text) for x, y, text, color in canvas.requests
                            if text.startswith(('> ', '  ')) and color in (v.W, v.SHADE)]
                    limit = 2 if size[0] < 100 or size[1] < 34 else 4
                    self.assertLessEqual(len(card), limit)
                    env = dict(A=Matrix(state.attention), W1=Matrix(state.weights[0]),
                               W2=Matrix(state.weights[1]),
                               V=Matrix(((1., 0., 0.), (0., 1., 0.), (0., 0., 1.),
                                         (0., 0., 1.), (0., 0., 1.), (0., 0., 1.))),
                               relu=lambda values: tuple(max(0., x) for x in values))
                    for x, y, text in card:
                        visible = ''.join(ch for ch, _ in canvas.cells[int(y)][int(x):int(x)+len(text)])
                        self.assertEqual(visible, text, (size, inset, at))
                        statements = [node for node in ast.parse(text[2:]).body
                                      if isinstance(node, ast.Assign) and any(
                                          isinstance(target, ast.Name) and target.id in ('q', 'x', 'h', 'z')
                                          for target in node.targets)]
                        program = ast.Module(body=statements, type_ignores=[])
                        exec(compile(program, '<forward-card>', 'exec'), {'__builtins__': {}}, env)
                    self.assertEqual(env['q'], -1)
                    self.assertEqual(env['x'], state.activations[0])
                    self.assertEqual(env['z'], state.activations[2])

    def test_probabilities_come_from_visible_weighted_layers(self):
        for index in range(338):
            at = min(188.482, 177.246 + index / 30)
            state = learning.learning_state(at)
            inputs, hidden, logits = state.activations
            self.assertEqual(inputs, (state.attention[-1][0], state.attention[-1][1],
                                      sum(state.attention[-1][2:])))
            for row, actual in zip(state.weights[0], hidden):
                self.assertAlmostEqual(max(0., sum(w*x for w, x in zip(row, inputs))), actual)
            for row, actual in zip(state.weights[1], logits):
                self.assertAlmostEqual(sum(w*x for w, x in zip(row, hidden)), actual)
            exps = tuple(math.exp(logit - max(logits)) for logit in logits)
            expected = tuple(value / sum(exps) for value in exps)
            self.assertAlmostEqual(sum(state.probabilities), 1.)
            for actual, probability in zip(state.probabilities, expected):
                self.assertGreater(actual, 0.)
                self.assertAlmostEqual(actual, probability)
            total = 0.
            for choice, probability in zip(state.choices, state.probabilities):
                total += probability
                if state.sample < total:
                    self.assertEqual(state.selected, choice)
                    break
            if state.output:
                self.assertEqual(state.output, state.selected)

    def test_attention_keeps_causal_mask_and_learns_the_love_key(self):
        for at in (177.246, 180.0, 181.0, 183.7, 184.9, 188.0):
            state = learning.learning_state(at)
            self.assertEqual(state.tokens[state.attention_key], 'LOVE')
            for i, row in enumerate(state.attention):
                self.assertEqual(len(row), len(state.tokens))
                self.assertAlmostEqual(sum(row), 1.)
                self.assertTrue(all(value == 0. for value in row[i+1:]))
        early = learning.learning_state(180.0)
        late = learning.learning_state(188.0)
        self.assertLess(early.attention[-1][early.attention_key], .7)
        self.assertGreater(late.attention[-1][late.attention_key], .97)

    def test_feedback_updates_weights_and_cross_entropy_then_holds_them(self):
        before = learning.learning_state(180.8)
        updating = learning.learning_state(181.0)
        trained = learning.learning_state(181.5)
        late = learning.learning_state(188.0)
        self.assertEqual(updating.phase, 'feedback')
        self.assertEqual(before.weights[0], late.weights[0])
        self.assertNotEqual(before.weights[1], updating.weights[1])
        self.assertNotEqual(updating.weights[1], trained.weights[1])
        self.assertEqual(trained.weights, learning.learning_state(183.6).weights)
        self.assertLess(trained.loss, before.loss)
        self.assertLess(late.loss, trained.loss)
        self.assertGreater(late.probabilities[0], .99)
        self.assertLess(late.probabilities[-1], .002)
        self.assertTrue(late.eos_blocked)
        self.assertFalse(before.eos_blocked)

    def test_feedback_keeps_answered_context_until_next_input(self):
        for start, end in ((180.857, 181.360), (184.540, 185.050)):
            answered = learning.learning_state(math.nextafter(start, -math.inf))
            for at in (start, start+1/30, end-1/30):
                with self.subTest(time=at):
                    state = learning.learning_state(at)
                    self.assertEqual(state.phase, 'feedback')
                    self.assertEqual(state.cycle, answered.cycle)
                    self.assertEqual(state.question, answered.question)
                    self.assertEqual(state.tokens, answered.tokens)
                    self.assertEqual(state.sample, answered.sample)
                    self.assertEqual(state.history, answered.history)
                    self.assertEqual(state.output, '')
                    for size in SIZES:
                        canvas, _ = self.draw(size, at)
                        self.assertIn('YOU: '+answered.question, canvas.plain())
            next_input = learning.learning_state(end)
            self.assertEqual(next_input.phase, 'input')
            self.assertEqual(next_input.cycle, answered.cycle+1)
            self.assertNotEqual(next_input.question, answered.question)
            self.assertEqual(next_input.history, answered.history)

    def test_each_feedback_sgd_step_uses_visible_hidden_and_probabilities(self):
        for start, end, base, count in ((180.857, 181.360, 0, 8),
                                        (184.540, 185.050, 8, 40)):
            with self.subTest(batch=start):
                for step in range(count):
                    before = learning.learning_state(start+(step+.25)*(end-start)/count)
                    at = end if step+1 == count else start+(step+1.25)*(end-start)/count
                    after = learning.learning_state(at)
                    self.assertEqual((before.updates, after.updates),
                                     (base+step, base+step+1))
                    self.assertEqual(before.weights[0], after.weights[0])
                    for row, word in enumerate(before.choices):
                        gradient = before.probabilities[row] - (word == 'LOVE')
                        for column, hidden in enumerate(before.activations[1]):
                            expected = before.weights[1][row][column] - 1.8*gradient*hidden
                            self.assertAlmostEqual(after.weights[1][row][column], expected,
                                                   places=14, msg=f'update {base+step+1}, {word}, {column}')

    def test_loss_graph_and_display_use_current_probabilities(self):
        for at, *_ in PHASES:
            state = learning.learning_state(at)
            self.assertAlmostEqual(state.loss, -math.log(state.probabilities[0]))
            self.assertAlmostEqual(state.exit_loss, -math.log(state.probabilities[-1]))
            self.assertAlmostEqual(state.loss_history[-1], state.loss)
            canvas, _ = self.draw((128, 44), at)
            self.assertIn(f'CE={state.loss:.3f}', canvas.plain())
            self.assertIn(f'EOS={state.exit_loss:.2f}', canvas.plain())
            self.assertIn(f'{state.probabilities[0]:.3f}', canvas.plain())

    def test_attention_numbers_survive_saturation_and_panel_footer(self):
        for size in SIZES:
            for at in (180., 188.):
                canvas, area = self.draw(size, at)
                for x, y, text, _ in canvas.requests:
                    if text.isdigit() and x < area[0]+(area[2]-area[0])*.35:
                        visible = ''.join(ch for ch, _ in canvas.cells[int(y)][int(x):int(x)+len(text)])
                        self.assertEqual(visible, text, (size, at, x, y, text))

    def test_all_five_grids_and_offset_small_areas_fit_before_clipping(self):
        times = tuple(at for at, *_ in PHASES) + tuple(
            start + offset for start, _ in VOCALS for offset in (-1/30, 0., 1/30))
        for size in SIZES:
            for inset in (0, 2):
                for at in times:
                    with self.subTest(size=size, inset=inset, time=at):
                        canvas, area = self.draw(size, at, inset)
                        self.assert_requests_in_area(canvas, area)
                        self.assertIn('ME', canvas.plain())
                        self.assertIn('YOU', canvas.plain())
                        self.assertIn('QK', canvas.plain())
                        self.assertIn('W1', canvas.plain())
                        self.assertIn('EOS', canvas.plain())

    def test_entire_vocal_windows_keep_output_and_numeric_model_visible(self):
        for size in SIZES:
            for start, end in VOCALS:
                for frame in range(math.ceil((end-start)*30)):
                    at = min(end - .000001, start + frame/30)
                    with self.subTest(size=size, time=at):
                        canvas, area = self.draw(size, at)
                        text = canvas.plain()
                        self.assertIn('OUT: LOVE', text)
                        self.assertIn('QK', text)
                        self.assertIn('W1', text)
                        self.assertIn('CE=', text)
                        self.assertIn('EOS', text)
                        # A five-row bitmap occupies its own output region.
                        l, top, r, bottom = area
                        rows = {y for x, y, value, ink in canvas.requests
                                if value and set(value) == {'#'} and x > l+(r-l)*.60
                                and ink in (v.ROSE, v.W, v.R)}
                        self.assertGreaterEqual(len(rows), 5)
                        matrix = [value for x, y, value, ink in canvas.requests
                                  if value.isdigit() and x < l+(r-l)*.35]
                        self.assertGreaterEqual(len(matrix), 10)

    def test_roles_targets_and_late_failure_keep_semantic_colors(self):
        for size in SIZES:
            for at in (178.0, 180.0, 184.0, 188.0):
                canvas, _ = self.draw(size, at)
                for label, color in (('ME', v.ME), ('YOU', v.YOU)):
                    x, y, _, ink = next(request for request in canvas.requests
                                        if request[2] == label)
                    self.assertEqual(ink, color)
                    self.assertEqual(canvas.cells[int(y)][int(x)][1], color)
                self.assertTrue(any(ink == v.ROSE and 'LOVE' in text
                                    for _, _, text, ink in canvas.requests))
                if at > 187:
                    self.assertTrue(any(ink == v.R and 'EOS' in text
                                        for _, _, text, ink in canvas.requests))

    def test_small_you_core_keeps_round_shoulders_beside_me_diamond(self):
        for size in ((64, 24), (80, 30)):
            canvas, _ = self.draw(size, 180.)
            shoulders = []
            for role, ink in (('ME', v.ME), ('YOU', v.YOU)):
                x, y, _, _ = next(request for request in canvas.requests if request[2] == role)
                shoulders.append(sum(canvas.cells[int(y)-1][column][1] == ink
                                     and canvas.cells[int(y)-1][column][0] == '#'
                                     for column in range(int(x)-1, int(x)+4)))
            self.assertGreater(shoulders[1], shoulders[0])

    def test_scene_raster_is_independent_of_seek_history_and_music_levels(self):
        for size in SIZES:
            first, _ = self.draw(size, 183.646)
            self.draw(size, 188.0)
            self.draw(size, 177.246)
            repeated, _ = self.draw(size, 183.646, music=MusicState(
                time=183.646, beat=1., energy=1., low=1., mid=1., high=1.,
                beat_position=999.))
            self.assertEqual(first.cells, repeated.cells)
            self.assertEqual(first.protected, repeated.protected)

    def test_renderer_leaves_parent_scene_boundaries_untouched(self):
        for at in (177.246 - .001, 188.483, 190.):
            canvas, _ = self.draw((64, 24), at)
            self.assertEqual(canvas.requests, [])
        for at in (float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                learning.learning_state(at)

    def test_module_can_import_without_player_or_scenes(self):
        result = subprocess.run([sys.executable, '-B', '-c', '''
import builtins
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name in ('player', 'scenes'):
        raise AssertionError('learning import cycle: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
import scenes_learning
assert scenes_learning.learning_state(180).output == 'LOVE'
'''], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
