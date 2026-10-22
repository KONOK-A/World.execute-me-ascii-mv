"""Stateless ANSI frame encoding for Canvas-compatible frames."""
from dataclasses import dataclass


@dataclass(frozen=True)
class FrameOutput:
    """Encoded output and cost; changed_cells counts repainted terminal cells."""

    text: str
    full: bool
    changed_cells: int
    byte_count: int


def _full_frame(frame):
    text = frame.ansi()
    return FrameOutput(text, True, frame.w * frame.h, len(text.encode('utf-8')))


def encode_frame(current, previous=None, *, styles, force_full=False) -> FrameOutput:
    """Encode a frame without modifying it or retaining any rendering state.

    ``styles`` is the same style-to-SGR mapping used by the frame's ``ansi()``.
    Cells use an empty string for the second column of a wide glyph. Delta
    spans include complete wide pairs from both frames, including any overlap.
    ``changed_cells`` includes those expanded cells, or the whole area for a
    full redraw. Nonempty output ends with an SGR reset; an unchanged frame
    emits nothing. Pass ``force_full=True`` after external screen changes.
    """
    if (force_full or previous is None or
            (current.w, current.h) != (previous.w, previous.h)):
        return _full_frame(current)

    parts = []
    last_style = None
    changed_cells = 0
    for y, row in enumerate(current.cells):
        old_row = previous.cells[y]
        x = 0
        while x < current.w:
            if row[x] == old_row[x]:
                x += 1
                continue

            start = x
            # Moving onto an old or new continuation must repaint its lead.
            while start > 0 and (row[start][0] == '' or old_row[start][0] == ''):
                start -= 1
            x += 1
            # Include changed neighbors and follow overlapping wide pairs to
            # a boundary that is safe in BOTH frames, not just the new frame.
            while x < current.w and (row[x] != old_row[x] or
                                     row[x][0] == '' or old_row[x][0] == ''):
                x += 1

            changed_cells += x - start
            parts.append(f'\x1b[{y + 1};{start + 1}H')
            for ch, style in row[start:x]:
                if not ch:
                    continue
                if style != last_style:
                    parts.append(styles[style])
                    last_style = style
                # Spaces are intentional writes: they clear old glyphs.
                parts.append(ch)

    if not parts:
        return FrameOutput('', False, 0, 0)

    parts.append('\x1b[0m')
    text = ''.join(parts)
    byte_count = len(text.encode('utf-8'))
    full = _full_frame(current)
    if full.byte_count <= byte_count:
        return full
    return FrameOutput(text, False, changed_cells, byte_count)
