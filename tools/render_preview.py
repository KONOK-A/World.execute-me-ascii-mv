"""Render a bounded developer preview, separate from the product playback CLI.

Requires Pillow, FFmpeg on PATH, and Windows Consolas / Microsoft YaHei fonts.
--width and --height are terminal columns/rows; each cell is 10 x 20 pixels.
Frames sample start + n/fps. The last video frame may extend by less than 1/fps;
optional audio starts at exactly --start and is trimmed to --duration.
Run each source snapshot in a separate CLI invocation to isolate its imports.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import importlib
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


CELL_WIDTH, CELL_HEIGHT = 10, 20


def load_player(source):
    # Film reads resources relative to player.__file__. Its deferred scenes imports
    # must use this same directory, even when invoked from another checkout.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(source))
    return importlib.import_module('player')


def palette(styles):
    result = {}
    for style, escape in styles.items():
        match = re.fullmatch(r'\x1b\[([01]);38;5;(\d+)m', escape)
        if not match:
            raise ValueError(f'Unsupported source ANSI style: {escape!r}')
        bold, index = int(match[1]), int(match[2])
        if 16 <= index <= 231:
            index -= 16
            rgb = tuple(0 if n == 0 else 55+40*n
                        for n in (index//36, index//6 % 6, index % 6))
        elif 232 <= index <= 255:
            rgb = (8+10*(index-232),)*3
        else:
            raise ValueError(f'Unsupported source 256-color index: {index}')
        result[style] = (rgb, bold)
    return result


class Rasterizer:
    def __init__(self, player):
        from PIL import Image, ImageDraw, ImageFont

        self.Image = Image
        self.ImageDraw = ImageDraw
        self.cw = player.cw
        self.styles = palette(player.STYLES)
        font_dir = Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts'
        self.fonts = {}
        for wide, regular, bold in [(False, 'consola.ttf', 'consolab.ttf'),
                                    (True, 'msyh.ttc', 'msyhbd.ttc')]:
            for weight, name in [(0, regular), (1, bold)]:
                path = font_dir/name
                if not path.is_file():
                    path = font_dir/regular
                if not path.is_file():
                    raise FileNotFoundError(f'Preview font missing: {path}')
                self.fonts[wide, weight] = ImageFont.truetype(str(path), 16)

    @lru_cache(maxsize=4096)
    def glyph(self, ch, style):
        columns = self.cw(ch)
        rgb, bold = self.styles[style]
        font = self.fonts[columns == 2, bold]
        tile = self.Image.new('RGB', (columns*CELL_WIDTH, CELL_HEIGHT), 'black')
        draw = self.ImageDraw.Draw(tile)
        left, _, right, _ = font.getbbox(ch, anchor='ls')
        x = (tile.width-(right-left))//2-left
        draw.text((x, 16), ch, font=font, fill=rgb, anchor='ls')
        return tile

    def render(self, canvas):
        frame = self.Image.new('RGB', (canvas.w*CELL_WIDTH, canvas.h*CELL_HEIGHT), 'black')
        for y, row in enumerate(canvas.cells):
            for x, (ch, style) in enumerate(row):
                # Empty strings are continuation cells, not extra character advances.
                if ch and not ch.isspace() and self.cw(ch) > 0:
                    frame.paste(self.glyph(ch, style), (x*CELL_WIDTH, y*CELL_HEIGHT))
        return frame


def encode(args, player, ffmpeg):
    film = player.Film()
    if args.start+args.duration > float(film.config['duration'])+1e-6:
        raise ValueError('--start + --duration exceeds the source film duration')
    raster = Rasterizer(player)
    size = (args.width*CELL_WIDTH, args.height*CELL_HEIGHT)
    frame_count = math.ceil(args.duration*args.fps)
    command = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
               '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s:v', f'{size[0]}x{size[1]}',
               '-r', str(args.fps), '-i', 'pipe:0']
    if args.audio:
        # Input seeking discards preroll when transcoding. No -itsoffset or subtitle
        # offset is applied: the first video frame and audio sample share --start.
        command += ['-ss', str(args.start), '-i', str(args.audio)]
    command += ['-map', '0:v:0', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
                '-pix_fmt', 'yuv420p']
    if args.audio:
        command += ['-map', '1:a:0', '-c:a', 'aac', '-b:a', '192k']
    command += ['-t', str(args.duration), '-movflags', '+faststart']

    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Publish only a completed MP4; a failed encoder must not replace an old clip.
    handle, name = tempfile.mkstemp(suffix='.mp4', prefix='.preview-', dir=args.output.parent)
    os.close(handle)
    staging = Path(name)
    try:
        # A file prevents FFmpeg's stderr pipe filling while Python streams frames.
        with tempfile.TemporaryFile() as errors:
            process = subprocess.Popen(command+[str(staging)], stdin=subprocess.PIPE,
                                       stdout=subprocess.DEVNULL, stderr=errors)
            try:
                try:
                    for index in range(frame_count):
                        canvas = film.render(args.start+index/args.fps, args.width, args.height)
                        process.stdin.write(raster.render(canvas).tobytes())
                    process.stdin.close()
                except BrokenPipeError:
                    # Read the encoder's actual diagnostic below.
                    pass
                status = process.wait()
                if status:
                    errors.seek(0)
                    raise RuntimeError('FFmpeg failed: '+errors.read().decode('utf-8', errors='replace').strip())
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                try:
                    process.stdin.close()
                except BrokenPipeError:
                    pass
        staging.replace(args.output)
    finally:
        staging.unlink(missing_ok=True)
    return frame_count, size


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True, help='Checkout/snapshot containing player.py')
    parser.add_argument('--start', type=float, required=True, help='Source time in seconds (>= 0)')
    parser.add_argument('--duration', type=float, required=True, help='Positive, finite clip length in seconds')
    parser.add_argument('--fps', type=int, default=30)
    parser.add_argument('--width', type=int, default=128, help='Terminal columns (10 pixels each)')
    parser.add_argument('--height', type=int, default=44, help='Terminal rows (20 pixels each)')
    parser.add_argument('--audio', type=Path, help='Optional audio; omit for silent video')
    parser.add_argument('--output', type=Path, required=True, help='Destination .mp4 (replaced on success)')
    args = parser.parse_args()
    if not math.isfinite(args.start) or args.start < 0:
        parser.error('--start must be finite and >= 0')
    if not math.isfinite(args.duration) or args.duration <= 0:
        parser.error('--duration must be finite and > 0')
    for name in ('fps', 'width', 'height'):
        if getattr(args, name) <= 0:
            parser.error(f'--{name} must be > 0')
    args.source_dir = args.source_dir.expanduser().resolve()
    args.output = args.output.expanduser().resolve()
    if not (args.source_dir/'player.py').is_file():
        parser.error(f'--source-dir must contain player.py: {args.source_dir}')
    if args.output.suffix.lower() != '.mp4':
        parser.error('--output must end in .mp4')
    if args.audio:
        args.audio = args.audio.expanduser().resolve()
        if not args.audio.is_file():
            parser.error(f'--audio file not found: {args.audio}')
        if args.audio == args.output:
            parser.error('--output must not overwrite --audio')
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        parser.error('FFmpeg not found on PATH; install FFmpeg to render previews')
    try:
        import PIL
    except ImportError:
        parser.error('Pillow is required: python -m pip install Pillow')
    try:
        player = load_player(args.source_dir)
        count, size = encode(args, player, ffmpeg)
    except (OSError, ImportError, ValueError, RuntimeError) as exc:
        parser.exit(1, f'render_preview: {exc}\n')
    print(f'{args.output}\nsource={args.source_dir} frames={count} '
          f'fps={args.fps} pixels={size[0]}x{size[1]} '
          f'start={args.start:g} duration={args.duration:g}')


if __name__ == '__main__':
    main()
