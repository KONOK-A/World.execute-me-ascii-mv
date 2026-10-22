"""Apply real Canvas output to a small terminal, including wide-cell erasure."""
import copy
import re
import unittest
import unicodedata

from player import BRIGHT, Canvas, DIM, NORMAL, RED, STYLES, WHITE
from render_output import FrameOutput, encode_frame


class TerminalState:
    """The CUP/SGR subset used by Canvas; autowrap is disabled by Terminal."""

    CSI = re.compile(r'\x1b\[([0-9;]*)([Hm])')

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.x = self.y = 0
        self.style = (False, None)
        self.cells = [[(' ', self.style) for _ in range(w)] for _ in range(h)]
        self.writes = []

    def feed(self, text):
        index = 0
        while index < len(text):
            if text[index] == '\x1b':
                match = self.CSI.match(text, index)
                if match is None:
                    raise AssertionError('Unsupported escape: ' + repr(text[index:]))
                params, command = match.groups()
                values = [int(value or '0') for value in params.split(';')]
                if command == 'H':
                    self.y = (values[0] or 1) - 1
                    self.x = ((values[1] if len(values) > 1 else 1) or 1) - 1
                    if not (0 <= self.x < self.w and 0 <= self.y < self.h):
                        raise AssertionError('Cursor moved outside the frame')
                else:
                    self.sgr(values)
                index = match.end()
                continue

            ch = text[index]
            if ord(ch) < 32:
                raise AssertionError('Unexpected control character: ' + repr(ch))
            size = 2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1
            if self.x + size > self.w:
                raise AssertionError('Glyph crosses the right edge')
            row = self.cells[self.y]
            # A terminal erases the other half when either half is overwritten.
            for x in range(self.x, self.x + size):
                if row[x][0] == '' and x > 0:
                    row[x - 1] = (' ', self.style)
                elif x + 1 < self.w and row[x + 1][0] == '':
                    row[x + 1] = (' ', self.style)
                row[x] = (' ', self.style)
            row[self.x] = (ch, self.style)
            if size == 2:
                row[self.x + 1] = ('', self.style)
            self.writes.append((self.x, self.y, ch, self.style))
            self.x = min(self.w - 1, self.x + size)
            index += 1

    def sgr(self, values):
        index = 0
        while index < len(values):
            value = values[index]
            if value == 0:
                self.style = (False, None)
            elif value == 1:
                self.style = (True, self.style[1])
            elif value == 38 and values[index + 1] == 5:
                self.style = (self.style[0], values[index + 2])
                index += 2
            else:
                raise AssertionError('Unsupported SGR: ' + repr(values))
            index += 1


class FrameOutputTests(unittest.TestCase):
    def assert_screen(self, result, current, previous=None):
        terminal = TerminalState(current.w, current.h)
        if previous is not None:
            terminal.feed(previous.ansi())
        # Updates cannot rely on the cursor or active SGR from a previous write.
        terminal.feed('\x1b[1;38;5;196m\x1b[1;1H')
        terminal.writes.clear()
        terminal.feed(result.text)
        expected = TerminalState(current.w, current.h)
        expected.feed(current.ansi())
        self.assertEqual(terminal.cells, expected.cells)
        self.assertEqual(terminal.style, (False, None))
        self.assertEqual(result.byte_count, len(result.text.encode('utf-8')))
        return terminal

    def test_first_frame_is_full_with_utf8_byte_count(self):
        current = Canvas(16, 3)
        current.put(2, 1, '界é', BRIGHT)
        result = encode_frame(current, styles=STYLES)
        self.assertIsInstance(result, FrameOutput)
        self.assertTrue(result.full)
        self.assertEqual(result.text, current.ansi())
        self.assertEqual(result.changed_cells, 48)
        self.assertGreater(result.byte_count, len(result.text))
        self.assert_screen(result, current)

    def test_identical_frames_emit_nothing(self):
        previous = Canvas(80, 4)
        previous.put(3, 2, '界A', WHITE)
        current = copy.deepcopy(previous)
        result = encode_frame(current, previous, styles=STYLES)
        self.assertEqual(result, FrameOutput('', False, 0, 0))
        terminal = TerminalState(80, 4)
        terminal.feed(previous.ansi())
        before = copy.deepcopy((terminal.cells, terminal.x, terminal.y, terminal.style))
        terminal.feed(result.text)
        self.assertEqual((terminal.cells, terminal.x, terminal.y, terminal.style), before)

    def test_sparse_change_uses_absolute_cursor_and_one_cell(self):
        previous = Canvas(80, 4)
        current = copy.deepcopy(previous)
        current.put(17, 2, '@', RED)
        result = encode_frame(current, previous, styles=STYLES)
        self.assertFalse(result.full)
        self.assertEqual(result.changed_cells, 1)
        self.assertLess(result.byte_count, len(current.ansi().encode('utf-8')))
        terminal = self.assert_screen(result, current, previous)
        self.assertEqual([(x, y, ch) for x, y, ch, _ in terminal.writes], [(17, 2, '@')])

    def test_shortened_text_clears_stale_characters(self):
        previous = Canvas(80, 4)
        previous.put(10, 1, 'LONG TEXT', NORMAL)
        current = Canvas(80, 4)
        current.put(10, 1, 'HI', NORMAL)
        result = encode_frame(current, previous, styles=STYLES)
        self.assertFalse(result.full)
        self.assertEqual(result.changed_cells, 9)
        self.assert_screen(result, current, previous)

    def test_style_only_changes_include_spaces(self):
        previous = Canvas(80, 4)
        previous.put(10, 1, 'A B', DIM)
        current = copy.deepcopy(previous)
        current.put(10, 1, 'A B', BRIGHT)
        result = encode_frame(current, previous, styles=STYLES)
        self.assertFalse(result.full)
        self.assertEqual(result.changed_cells, 3)
        self.assert_screen(result, current, previous)

    def test_separate_runs_and_rows_preserve_styles(self):
        previous = Canvas(80, 6)
        current = copy.deepcopy(previous)
        for x, y, text, style in [(2, 1, 'A', RED), (40, 1, 'B', RED),
                                   (2, 4, 'C', DIM), (3, 4, 'D', WHITE)]:
            current.put(x, y, text, style)
        result = encode_frame(current, previous, styles=STYLES)
        self.assertFalse(result.full)
        self.assertEqual(result.changed_cells, 4)
        self.assert_screen(result, current, previous)

    def test_wide_to_narrow_clears_the_continuation(self):
        previous = Canvas(80, 4)
        previous.put(12, 1, '界', WHITE)
        current = Canvas(80, 4)
        current.put(12, 1, 'x', NORMAL)
        result = encode_frame(current, previous, styles=STYLES)
        self.assertFalse(result.full)
        self.assertEqual(result.changed_cells, 2)
        self.assert_screen(result, current, previous)

    def test_narrow_to_wide_replaces_both_cells(self):
        previous = Canvas(80, 4)
        previous.put(12, 1, 'ab', RED)
        current = Canvas(80, 4)
        current.put(12, 1, '界', WHITE)
        result = encode_frame(current, previous, styles=STYLES)
        self.assertFalse(result.full)
        self.assertEqual(result.changed_cells, 2)
        self.assert_screen(result, current, previous)

    def test_wide_glyph_change_includes_unchanged_continuation(self):
        previous = Canvas(80, 4)
        previous.put(12, 1, '界', NORMAL)
        current = Canvas(80, 4)
        current.put(12, 1, '語', NORMAL)
        result = encode_frame(current, previous, styles=STYLES)
        self.assertFalse(result.full)
        self.assertEqual(result.changed_cells, 2)
        self.assert_screen(result, current, previous)

    def test_wide_style_change_repaints_the_complete_pair(self):
        previous = Canvas(80, 4)
        previous.put(12, 1, '界', DIM)
        current = Canvas(80, 4)
        current.put(12, 1, '界', BRIGHT)
        result = encode_frame(current, previous, styles=STYLES)
        self.assertFalse(result.full)
        self.assertEqual(result.changed_cells, 2)
        self.assert_screen(result, current, previous)

    def test_shifted_wide_runs_clear_old_and_new_boundaries(self):
        for old_x, new_x in [(10, 11), (11, 10)]:
            with self.subTest(old_x=old_x, new_x=new_x):
                previous = Canvas(80, 4)
                previous.put(old_x, 1, '界語界', WHITE)
                current = Canvas(80, 4)
                current.put(new_x, 1, '界語界', NORMAL)
                result = encode_frame(current, previous, styles=STYLES)
                self.assertFalse(result.full)
                self.assertEqual(result.changed_cells, 7)
                self.assert_screen(result, current, previous)

    def test_edits_next_to_wide_glyphs_leave_them_intact(self):
        previous = Canvas(80, 4)
        previous.put(10, 1, '界', WHITE)
        previous.put(13, 1, '語', BRIGHT)
        for x in (9, 12, 15):
            with self.subTest(column=x):
                current = copy.deepcopy(previous)
                current.put(x, 1, '@', RED)
                result = encode_frame(current, previous, styles=STYLES)
                self.assertFalse(result.full)
                self.assertEqual(result.changed_cells, 1)
                self.assert_screen(result, current, previous)

    def test_wide_transitions_at_both_row_edges(self):
        for x in (0, 78):
            for old, new in [('界', 'a'), ('ab', '界'), ('界', '')]:
                with self.subTest(column=x, old=old, new=new):
                    previous = Canvas(80, 4)
                    previous.put(x, 3, old, WHITE)
                    current = Canvas(80, 4)
                    current.put(x, 3, new, BRIGHT)
                    result = encode_frame(current, previous, styles=STYLES)
                    self.assertFalse(result.full)
                    self.assert_screen(result, current, previous)

    def test_resize_in_either_dimension_uses_full_output(self):
        previous = Canvas(80, 4)
        for w, h in [(79, 4), (81, 4), (80, 3), (80, 5)]:
            with self.subTest(width=w, height=h):
                current = Canvas(w, h)
                current.put(w - 2, h - 1, '界', WHITE)
                result = encode_frame(current, previous, styles=STYLES)
                self.assertTrue(result.full)
                self.assertEqual(result.text, current.ansi())
                self.assertEqual(result.changed_cells, w * h)
                self.assert_screen(result, current)

    def test_force_full_repairs_an_externally_changed_screen(self):
        current = Canvas(80, 4)
        current.put(6, 2, '界A', WHITE)
        corrupt = Canvas(80, 4)
        corrupt.put(1, 1, 'EXTERNAL OUTPUT', RED)
        result = encode_frame(current, copy.deepcopy(current), styles=STYLES, force_full=True)
        self.assertTrue(result.full)
        self.assertEqual(result.text, current.ansi())
        self.assertEqual(result.changed_cells, 320)
        self.assert_screen(result, current, corrupt)

    def test_dense_changes_choose_the_shorter_full_stream(self):
        previous = Canvas(40, 4)
        current = Canvas(40, 4)
        # Twenty separated updates per row cost more CUP bytes than a full row.
        for y in range(4):
            for x in range(0, 40, 2):
                current.put(x, y, '@', DIM)
        result = encode_frame(current, previous, styles=STYLES)
        self.assertTrue(result.full)
        self.assertEqual(result.text, current.ansi())
        self.assertEqual(result.changed_cells, 160)
        self.assert_screen(result, current, previous)

    def test_dense_contiguous_changes_can_still_use_a_shorter_delta(self):
        previous = Canvas(40, 4)
        current = Canvas(40, 4)
        for y in range(4):
            current.put(0, y, '@' * 40, DIM)
        result = encode_frame(current, previous, styles=STYLES)
        self.assertFalse(result.full)
        self.assertLess(result.byte_count, len(current.ansi().encode('utf-8')))
        self.assert_screen(result, current, previous)

    def test_stream_selection_compares_utf8_bytes_not_character_count(self):
        previous = Canvas(10, 1)
        previous.put(0, 0, 'é' * 10, DIM)
        current = copy.deepcopy(previous)
        current.put(0, 0, 'a', DIM)
        current.put(4, 0, 'b', DIM)
        current.put(8, 0, 'c', DIM)
        # This valid delta is 38 characters / bytes; full is 36 characters / 43 bytes.
        candidate = '\x1b[1;1H' + STYLES[DIM] + 'a\x1b[1;5Hb\x1b[1;9Hc\x1b[0m'
        self.assertGreater(len(candidate), len(current.ansi()))
        self.assertLess(len(candidate.encode('utf-8')), len(current.ansi().encode('utf-8')))
        result = encode_frame(current, previous, styles=STYLES)
        self.assertFalse(result.full)
        self.assertLessEqual(result.byte_count, len(candidate.encode('utf-8')))
        self.assert_screen(result, current, previous)

    def test_frame_sequence_resets_styles_and_has_no_hidden_history(self):
        first = Canvas(80, 4)
        second = Canvas(80, 4)
        second.put(4, 1, '界', WHITE)
        third = Canvas(80, 4)
        third.put(5, 1, 'Z', DIM)
        terminal = TerminalState(80, 4)
        previous = None
        for current in [first, second, third, second, second, first]:
            result = encode_frame(current, previous, styles=STYLES)
            terminal.feed(result.text)
            expected = TerminalState(80, 4)
            expected.feed(current.ansi())
            self.assertEqual(terminal.cells, expected.cells)
            self.assertEqual(terminal.style, (False, None))
            previous = current
        self.assertEqual(encode_frame(second, first, styles=STYLES),
                         encode_frame(second, first, styles=STYLES))

    def test_encoding_does_not_mutate_either_canvas_or_styles(self):
        previous = Canvas(80, 4)
        previous.put(9, 1, '界', RED)
        current = Canvas(80, 4)
        current.put(10, 1, '語', WHITE)
        styles = dict(STYLES)
        before = copy.deepcopy((vars(current), vars(previous), styles))
        encode_frame(current, previous, styles=styles)
        self.assertEqual((vars(current), vars(previous), styles), before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
