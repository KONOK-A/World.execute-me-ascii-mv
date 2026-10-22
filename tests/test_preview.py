"""Exercise the developer preview CLI with real Film snapshots and FFmpeg."""
from array import array
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'tools/render_preview.py'
BASELINE = ROOT/'.build/crt-enhancement/baseline'
SOURCE = BASELINE if BASELINE.is_dir() else ROOT
FFMPEG = shutil.which('ffmpeg')
FFPROBE = shutil.which('ffprobe')
HAS_PILLOW = importlib.util.find_spec('PIL') is not None
FONT_DIR = Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts'
HAS_FONTS = all((FONT_DIR/name).is_file() for name in ('consola.ttf', 'msyh.ttc'))


class PreviewCase(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='preview test ')
        self.addCleanup(self.folder.cleanup)
        self.work = Path(self.folder.name)
        self.output = self.work/'preview.mp4'

    def preview(self, *arguments, env=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), '--source-dir', str(SOURCE),
             '--start', '67.3', '--duration', '0.2', '--fps', '30',
             '--width', '128', '--height', '44', '--output', str(self.output),
             *map(str, arguments)], cwd=self.work, env=env,
            capture_output=True, encoding='utf-8', timeout=60)

    def assert_error(self, result, message):
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(message.lower(), result.stderr.lower())
        self.assertNotIn('Traceback', result.stderr)
        self.assertFalse(self.output.exists())


class PreviewErrors(PreviewCase):
    def test_missing_source_and_audio_are_actionable_errors(self):
        self.assert_error(self.preview('--source-dir', self.work/'missing'), 'player.py')
        self.assert_error(self.preview('--audio', self.work/'missing.mp3'), 'audio')

    def test_missing_ffmpeg_is_an_actionable_error(self):
        self.assert_error(self.preview(env=dict(os.environ, PATH=str(self.work))), 'ffmpeg')

    def test_invalid_intervals_and_grid_fail_before_output(self):
        for option, value in [('--start', '-1'), ('--start', 'nan'),
                              ('--duration', '0'), ('--duration', 'inf'),
                              ('--fps', '0'), ('--width', '0'), ('--height', '-1')]:
            with self.subTest(option=option, value=value):
                self.assert_error(self.preview(option, value), option)


@unittest.skipUnless(FFMPEG and FFPROBE and HAS_PILLOW and HAS_FONTS,
                     'Preview smoke tests need Pillow, FFmpeg, ffprobe and Windows fonts')
class PreviewSmoke(PreviewCase):
    def probe(self):
        result = subprocess.run(
            [FFPROBE, '-v', 'error', '-show_streams', '-show_format',
             '-of', 'json', str(self.output)], capture_output=True,
            encoding='utf-8', check=True, timeout=20)
        return json.loads(result.stdout)

    def decode(self, path, *arguments):
        result = subprocess.run(
            [FFMPEG, '-v', 'error', '-i', str(path), *arguments, 'pipe:1'],
            capture_output=True, check=True, timeout=20)
        return result.stdout

    def test_selected_snapshot_renders_real_cells_and_local_imports(self):
        from PIL import Image

        # Copy an actual source snapshot; never replace Film or scene rendering.
        source = self.work/'chosen source [中文]'
        source.mkdir()
        for pattern in ('*.py', '*.json'):
            for path in SOURCE.glob(pattern):
                shutil.copy2(path, source/path.name)
        lyrics = json.loads((source/'lyrics.json').read_text(encoding='utf-8'))
        cue = next(c for c in lyrics if c['time'] <= 67.3 < c['end'])
        cue['en'] = 'SELECTED SNAPSHOT / source resources'
        (source/'lyrics.json').write_text(json.dumps(lyrics), encoding='utf-8')

        # Imports through the working directory/PYTHONPATH must not win over source.
        for name in ('player', 'scenes', 'terminal'):
            (self.work/(name+'.py')).write_text(
                "raise RuntimeError('wrong source import')\n", encoding='utf-8')
        env = dict(os.environ, PYTHONPATH=str(self.work), PYTHONIOENCODING='utf-8')
        original = {p.name: p.read_bytes() for p in source.iterdir()}
        result = self.preview('--source-dir', source, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({p.name: p.read_bytes() for p in source.iterdir()}, original)

        info = self.probe()
        video, = info['streams']
        self.assertEqual((video['width'], video['height']), (1280, 880))
        self.assertEqual(video['r_frame_rate'], '30/1')
        self.assertEqual(int(video['nb_frames']), 6)
        self.assertAlmostEqual(float(info['format']['duration']), 0.2, delta=0.002)

        # Independently ask the selected player for its real Canvas snapshot.
        reference = subprocess.run(
            [sys.executable, '-B', '-c',
             'import json, player; c=player.Film().render(67.3,128,44); '
             'print(json.dumps([[(ch,player.cw(ch) if ch else 0) '
             'for ch,style in row] for row in c.cells]))'],
            cwd=source, capture_output=True, encoding='utf-8', check=True, timeout=20)
        cells = json.loads(reference.stdout)
        self.assertIn('SELECTED SNAPSHOT', ''.join(ch for row in cells for ch, _ in row))
        pixels = self.decode(self.output, '-frames:v', '1', '-f', 'rawvideo',
                             '-pix_fmt', 'rgb24')
        frame = Image.frombytes('RGB', (1280, 880), pixels)
        expected = set()
        wide = 0
        for y, row in enumerate(cells):
            for x, (ch, columns) in enumerate(row):
                if ch and not ch.isspace():
                    expected.update((xx, y) for xx in range(x, min(128, x+columns)))
                    wide += columns == 2
        self.assertGreater(wide, 0, 'The snapshot must exercise Chinese glyphs')
        actual = set()
        for y in range(44):
            for x in range(128):
                tile = frame.crop((x*10, y*20, (x+1)*10, (y+1)*20))
                if max(high for low, high in tile.getextrema()) > 40:
                    actual.add((x, y))
        self.assertLess(len(actual ^ expected), 8,
                        f'Wrong occupied cells: {sorted(actual ^ expected)[:20]}')

    @unittest.skipUnless((ROOT/'media/song.mp3').is_file(), 'Local song is optional')
    def test_audio_is_the_requested_song_segment_without_extra_offset(self):
        audio = ROOT/'media/song.mp3'
        result = self.preview('--audio', audio, '--duration', '0.205')
        self.assertEqual(result.returncode, 0, result.stderr)
        info = self.probe()
        streams = {s['codec_type']: s for s in info['streams']}
        self.assertEqual(set(streams), {'audio', 'video'})
        self.assertAlmostEqual(float(streams['audio']['start_time']), 0, delta=0.001)
        self.assertAlmostEqual(float(streams['audio']['duration']), 0.205, delta=0.002)
        self.assertAlmostEqual(float(info['format']['duration']), 0.205, delta=1/30)
        actual = array('f', self.decode(self.output, '-vn', '-ac', '1', '-ar', '16000',
                                       '-f', 'f32le'))
        expected = array('f', self.decode(audio, '-ss', '67.3', '-t', '0.205', '-vn',
                                         '-ac', '1', '-ar', '16000', '-f', 'f32le'))
        pairs = list(zip(actual[200:2800], expected[200:2800]))
        self.assertEqual(len(pairs), 2600)
        correlation = sum(a*b for a, b in pairs)/math.sqrt(
            sum(a*a for a, b in pairs)*sum(b*b for a, b in pairs))
        self.assertGreater(correlation, 0.97, 'Audio must match source time 67.3s')


if __name__ == '__main__':
    unittest.main(verbosity=2)
