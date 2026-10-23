"""Real Windows audio-clock checks using silent audio, without external packages."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import wave


ROOT = Path(__file__).resolve().parents[1]


def silent_wav(path, seconds=4):
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(44100)
        audio.writeframes(b'\0\0' * (44100*seconds))


@unittest.skipUnless(sys.platform == 'win32', 'Windows audio backend')
class WindowsAudioTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name)/'静音 audio.wav'
        silent_wav(self.path)

    def start(self, path=None):
        sys.path.insert(0, str(ROOT))
        from player import Audio
        self.audio = Audio(path or self.path)
        self.proc = self.audio.proc
        self.last_seen = 0
        self.addCleanup(self.stop)

    def stop(self):
        self.audio.close()

    def command(self, text):
        self.proc.stdin.write(text+'\n')
        self.proc.stdin.flush()

    def state(self, predicate=lambda state: True):
        deadline = time.monotonic()+8
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                self.fail('Audio helper exited: '+self.proc.stderr.read())
            self.assertFalse(self.audio.error, self.audio.error)
            updated = self.audio.last
            state = self.audio.state.copy()
            if updated > self.last_seen and predicate(state):
                self.last_seen = updated
                return state
            time.sleep(.005)
        self.fail('Audio state never reached the requested condition')

    def test_play_pause_seek_volume_and_quit(self):
        self.start()
        initial = self.state()
        self.assertAlmostEqual(initial['duration'], 4, delta=.1)
        self.assertFalse(initial['playing'])
        self.command('volume 0')
        self.command('play')
        self.state(lambda s: s['playing'] and s['time'] > .15)
        self.command('pause')
        paused = self.state(lambda s: not s['playing'])
        time.sleep(.12)
        self.assertAlmostEqual(self.state()['time'], paused['time'], delta=.03)
        self.command('seek 1.5')
        seeked = self.state(lambda s: s['time'] >= 1.49)
        self.assertFalse(seeked['playing'])
        self.assertAlmostEqual(seeked['time'], 1.5, delta=.03)
        self.command('play')
        self.state(lambda s: s['playing'] and s['time'] > 1.6)
        self.command('seek 2.5')
        playing = self.state(lambda s: s['time'] >= 2.5)
        self.assertTrue(playing['playing'])
        self.command('volume 1')
        self.command('seek 3.8')
        ended = self.state(lambda s: not s['playing'] and s['time'] >= 3.9)
        self.assertLessEqual(ended['time'], ended['duration']+.02)
        self.command('seek 0')
        restarted = self.state(lambda s: s['time'] < .02)
        self.assertFalse(restarted['playing'])
        time.sleep(.15)
        self.assertAlmostEqual(self.state()['time'], 0, delta=.03)
        self.command('play')
        self.state(lambda s: s['playing'] and s['time'] > .1)
        self.command('quit')
        self.assertEqual(self.proc.wait(timeout=5), 0)

    def test_eof_exits_and_releases_audio_file(self):
        self.start()
        self.state()
        self.proc.stdin.close()
        self.assertEqual(self.proc.wait(timeout=5), 0)
        self.path.unlink()
        self.assertFalse(self.path.exists())

    def test_stereo_pcm_keeps_fractional_duration_and_last_second(self):
        frames = 216384
        with wave.open(str(self.path), 'wb') as audio:
            audio.setnchannels(2)
            audio.setsampwidth(2)
            audio.setframerate(44100)
            audio.writeframes(b'\0'*(frames*4))
        self.start()
        duration = frames/44100
        self.assertAlmostEqual(self.state()['duration'], duration, delta=1/44100)
        self.command('volume 0')
        self.command(f'seek {duration-.3}')
        seeked = self.state(lambda s: s['time'] >= duration-.31)
        self.assertFalse(seeked['playing'])
        self.command('play')
        self.state(lambda s: s['playing'] and s['time'] > duration-.2)
        ended = self.state(lambda s: not s['playing'] and s['time'] >= duration-.01)
        self.assertAlmostEqual(ended['time'], duration, delta=1/44100)

    def test_invalid_file_reports_error(self):
        sys.path.insert(0, str(ROOT))
        from player import Audio
        with self.assertRaises(RuntimeError):
            Audio(self.path.with_suffix('.missing'))

    def test_player_selects_windows_helper_and_reaps_it(self):
        sys.path.insert(0, str(ROOT))
        from player import Audio
        audio = Audio(self.path)
        self.addCleanup(audio.close)
        self.assertAlmostEqual(audio.state['duration'], 4, delta=.1)
        audio.command('play')
        deadline = time.monotonic()+5
        while audio.state['time'] < .1 and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertTrue(audio.state['playing'])
        self.assertGreater(audio.state['time'], .05)
        audio.close()
        self.assertEqual(audio.proc.returncode, 0)
        self.assertTrue(audio.proc.stdout.closed)

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg needed to generate a VBR MP3 fixture')
    def test_vbr_mp3_clock_reaches_the_end_of_the_audio(self):
        mp3 = self.path.with_suffix('.mp3')
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(self.path),
                        '-codec:a', 'libmp3lame', '-q:a', '2', str(mp3)],
                       check=True, capture_output=True, timeout=20)
        self.start(mp3)
        initial = self.state()
        self.assertAlmostEqual(initial['duration'], 4, delta=.15)
        self.command('seek 3.2')
        self.state(lambda s: s['time'] >= 3.15)
        self.command('play')
        self.state(lambda s: s['playing'] and s['time'] > 3.4)
        self.state(lambda s: not s['playing'] and s['time'] > 3.8)


if __name__ == '__main__':
    unittest.main(verbosity=2)
