"""Snapshots must work without a platform audio engine or an interactive console."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SnapshotTests(unittest.TestCase):
    def snapshot(self, *arguments):
        # Exercise UTF-8 resources even when Python's locale is a Windows code page.
        env = dict(os.environ, PYTHONUTF8='0', PYTHONIOENCODING='cp936')
        result = subprocess.run(
            [sys.executable, '-B', str(ROOT/'player.py'), '--plain', *arguments],
            cwd=ROOT.parent, env=env, capture_output=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_snapshots_keep_lyrics_and_scene_markers(self):
        for t, marker in [('67.3', 'If I can make you happy'), ('124.2', 'Then maybe'),
                          ('159.85', 'TROIS'), ('183.2', 'Question me')]:
            with self.subTest(time=t):
                result = self.snapshot('--snapshot', t, '--width', '125', '--height', '45')
                self.assertIn(marker, result)
                self.assertEqual(len(result.splitlines()), 45)

    def test_small_terminal_message_is_readable_utf8(self):
        result = self.snapshot('--snapshot', '0', '--width', '60', '--height', '20')
        self.assertIn('请放大窗口', result)

    def test_help_does_not_require_audio(self):
        result = self.snapshot('--help')
        self.assertIn('--audio', result)
        self.assertIn('--snapshot', result)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows launcher')
    def test_launcher_preserves_parentheses_in_audio_path(self):
        result = subprocess.run(
            [str(ROOT/'run.cmd'), '--audio', r'D:\music\world.execute(me).mp3',
             '--snapshot', '67.3', '--plain'],
            capture_output=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('If I can make you happy', result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
