"""Check actual built resources and execution outside the project directory."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from test_windows_audio import silent_wav

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform in ('win32', 'darwin'), 'Supported playback platforms')
class BundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(prefix='mv-bundle-test-')
        cls.addClassCleanup(cls.folder.cleanup)
        cls.base = Path(cls.folder.name)
        cls.audio = cls.base/'静音 song.wav'
        silent_wav(cls.audio)
        cls.output = cls.base/'分发 bundle'
        result = subprocess.run(
            [sys.executable, '-B', '-X', 'utf8', str(ROOT/'tools/build_bundle.py'),
             '--audio', str(cls.audio), '--output', str(cls.output)],
            cwd=cls.base, capture_output=True, encoding='utf-8', timeout=120)
        if result.returncode:
            raise AssertionError('Bundle build failed: '+result.stdout+result.stderr)
        cls.bundle = cls.output/'world-execute-mv.pyz'

    def test_embedded_resources_match_source(self):
        with zipfile.ZipFile(self.bundle) as archive:
            manifest = json.loads(archive.read('bundle-manifest.json'))
            self.assertEqual(manifest['sys_platform'], sys.platform)
            self.assertIn('media/song.wav', manifest['files'])
            self.assertIn('terminal.py', manifest['files'])
            for required in ('music.py','render_output.py','music_features.json','score.json',
                             'visuals.py','scenes_organic.py','scenes_learning.py'):
                self.assertIn(required,manifest['files'])
            self.assertIn('windows_audio.ps1' if sys.platform == 'win32' else 'audio-clock', manifest['files'])
            for name, digest in manifest['files'].items():
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), digest)
                if name == 'media/song.wav':
                    self.assertEqual(archive.read(name), self.audio.read_bytes())
                elif name != 'config.json':
                    self.assertEqual(archive.read(name), (ROOT/name).read_bytes())
            config = json.loads(archive.read('config.json'))
            source_config = json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
            source_config['audio'] = 'media/song.wav'
            self.assertEqual(config, source_config)
            self.assertFalse(any(name.lower().endswith(('.mp4', '.png', '.jpg')) for name in archive.namelist()))

    def test_runs_from_an_empty_directory_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            work = base/'unrelated working directory'; work.mkdir()
            scratch = base/'scratch'; scratch.mkdir()
            env = dict(os.environ, TMPDIR=str(scratch), TMP=str(scratch), TEMP=str(scratch),
                       PYTHONUTF8='0', PYTHONIOENCODING='cp936')
            for t, expected in [(67.3, 'If I can make you happy'), (124.2, 'Then maybe'),
                                (159.85, 'TROIS'), (183.2, 'Question me')]:
                result = subprocess.run([sys.executable, '-B', str(self.bundle), '--snapshot', str(t),
                                         '--plain', '--width', '125', '--height', '45'],
                                        cwd=work, env=env, capture_output=True, encoding='utf-8', check=True, timeout=20)
                self.assertIn(expected, result.stdout)
                self.assertEqual(list(work.iterdir()), [])
                self.assertEqual(list(scratch.iterdir()), [])

    def test_corrupt_resource_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            bad = Path(folder)/'corrupt.pyz'
            with zipfile.ZipFile(self.bundle) as original, zipfile.ZipFile(bad, 'w') as changed:
                for name in original.namelist():
                    data = original.read(name)
                    changed.writestr(name, b'{}' if name == 'config.json' else data)
            result = subprocess.run([sys.executable, '-X', 'utf8', str(bad), '--snapshot', '67.3', '--plain'],
                                    capture_output=True, encoding='utf-8', timeout=20)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('资源校验失败', result.stderr)

    def test_windows_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            bad = Path(folder)/'escape.pyz'
            payload = b'escape'
            with zipfile.ZipFile(self.bundle) as original, zipfile.ZipFile(bad, 'w') as changed:
                manifest = json.loads(original.read('bundle-manifest.json'))
                manifest['files'] = {'..\\escaped.txt': hashlib.sha256(payload).hexdigest()}
                changed.writestr('__main__.py', original.read('__main__.py'))
                changed.writestr('bundle-manifest.json', json.dumps(manifest))
                changed.writestr('..\\escaped.txt', payload)
            scratch = Path(folder)/'scratch'; scratch.mkdir()
            env = dict(os.environ, TMPDIR=str(scratch), TMP=str(scratch), TEMP=str(scratch))
            result = subprocess.run([sys.executable, '-X', 'utf8', str(bad)], env=env,
                                    capture_output=True, encoding='utf-8', timeout=20)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('资源路径无效', result.stderr)
            self.assertEqual(list(scratch.iterdir()), [])

    def test_distribution_checksums_match(self):
        sums = (self.output/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()
        self.assertEqual(len(sums), 2)
        for line in sums:
            digest, name = line.split('  ', 1)
            self.assertEqual(hashlib.sha256((self.output/name).read_bytes()).hexdigest(), digest)
        suffix = 'windows' if sys.platform == 'win32' else 'macos'
        launcher = '运行单文件.cmd' if sys.platform == 'win32' else '运行单文件.command'
        with zipfile.ZipFile(self.output/f'world-execute-mv-{suffix}.zip') as archive:
            self.assertIn('world-execute-mv/'+launcher, archive.namelist())
            if sys.platform == 'win32':
                for name in ('ensure-runtime.ps1', 'python-runtime.json'):
                    self.assertEqual(archive.read('world-execute-mv/'+name), (ROOT/name).read_bytes())

    @unittest.skipUnless(sys.platform == 'win32', 'Windows launcher')
    def test_distribution_launcher_runs_with_special_paths(self):
        with tempfile.TemporaryDirectory(prefix='mv 启动 (test); ') as folder:
            with zipfile.ZipFile(self.output/'world-execute-mv-windows.zip') as archive:
                archive.extractall(folder)
            launcher = Path(folder)/'world-execute-mv/运行单文件.cmd'
            result = subprocess.run(
                [str(launcher), '--snapshot', '67.3', '--plain', '--audio',
                 r'D:\音乐\Mili - world.execute (me) ;.mp3'],
                input='', capture_output=True, encoding='utf-8', timeout=30,
                env=dict(os.environ, PYTHONHOME=str(Path(folder)/'missing Python')))
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertIn('If I can make you happy', result.stdout)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows console APIs')
    def test_bundled_audio_and_full_player(self):
        from test_windows_console import run_hidden_player
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder)/'bundled.json'
            result = run_hidden_player(self.bundle, None, report)
            self.assertEqual(result.returncode, 0, result.stderr)
            frames = json.loads(report.with_suffix('.frames.json').read_text(encoding='utf-8'))
            self.assertGreater(frames['frames'], 1)
            self.assertGreaterEqual(frames['last_time'], .4)


if __name__ == '__main__':
    unittest.main(verbosity=2)
