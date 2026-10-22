"""Exercise real console APIs in a separate, hidden Windows console."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def run_hidden_player(target, audio, report):
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    return subprocess.run(
        [sys.executable, '-B', str(Path(__file__).resolve()), '--player-probe',
         str(report), str(target), str(audio) if audio else ''],
        creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup,
        capture_output=True, encoding='utf-8', timeout=20)


@unittest.skipUnless(sys.platform == 'win32', 'Windows console APIs')
class ConsoleTests(unittest.TestCase):
    def test_full_player_autoplay_and_shutdown(self):
        from test_windows_audio import silent_wav
        with tempfile.TemporaryDirectory() as folder:
            audio = Path(folder)/'静音 smoke.wav'
            silent_wav(audio)
            report = Path(folder)/'player.json'
            result = run_hidden_player(ROOT/'player.py', audio, report)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(report.read_text(encoding='utf-8'))
            self.assertEqual(data['before'], data['after'])
            self.assertTrue(data['stdout_restored'])
            frames = json.loads(report.with_suffix('.frames.json').read_text(encoding='utf-8'))
            self.assertEqual(frames['fps'], 30)
            self.assertGreater(frames['frames'], 1)
            self.assertGreaterEqual(frames['last_time'], .4)
            self.assertGreater(frames['output_bytes'],0)
            self.assertEqual(sum(frames['frame_kinds'].values()),frames['frames'])
            for stage in ('draw','encode','write','total'):
                self.assertGreaterEqual(frames['timings_ms'][stage]['p95'],0)
            audio.unlink()  # The helper must release the file before the player returns.

    def test_keys_timeout_and_console_restoration(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder)/'console.json'
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = subprocess.SW_HIDE
            result = subprocess.run(
                [sys.executable, '-B', str(Path(__file__).resolve()), '--probe', str(report)],
                creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup,
                capture_output=True, encoding='utf-8', timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(report.read_text(encoding='utf-8'))
            self.assertEqual(data['keys'], '\x1b[D\x1b[C hq')
            self.assertEqual(data['empty'], '')
            self.assertGreaterEqual(data['wait_seconds'], .025)
            self.assertTrue(data['vt_enabled'])
            self.assertTrue(data['raw_input'])
            self.assertEqual(data['before'], data['after'])
            self.assertTrue(data['stdout_restored'])


def console_probe(report, target=None, audio=None):
    import ctypes
    from ctypes import wintypes
    import msvcrt
    import time
    sys.path.insert(0, str(ROOT))

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    user = ctypes.WinDLL('user32', use_last_error=True)
    kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetConsoleMode.restype = wintypes.BOOL
    original_in, original_out = sys.stdin, sys.stdout
    sys.stdin = open('CONIN$', encoding='utf-8')
    sys.stdout = open('CONOUT$', 'w', encoding='utf-8')
    console_in, console_out = sys.stdin, sys.stdout
    input_handle = msvcrt.get_osfhandle(sys.stdin.fileno())
    output_handle = msvcrt.get_osfhandle(sys.stdout.fileno())

    def mode(handle):
        value = wintypes.DWORD()
        if not kernel.GetConsoleMode(handle, ctypes.byref(value)):
            raise ctypes.WinError(ctypes.get_last_error())
        return value.value

    class KeyEvent(ctypes.Structure):
        _fields_ = [('down', wintypes.BOOL), ('repeat', wintypes.WORD),
                    ('key', wintypes.WORD), ('scan', wintypes.WORD),
                    ('char', wintypes.WCHAR), ('control', wintypes.DWORD)]

    class Event(ctypes.Union):
        _fields_ = [('key', KeyEvent), ('padding', ctypes.c_byte * 16)]

    class InputRecord(ctypes.Structure):
        _fields_ = [('type', wintypes.WORD), ('event', Event)]

    kernel.WriteConsoleInputW.argtypes = [wintypes.HANDLE, ctypes.POINTER(InputRecord),
                                         wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    kernel.WriteConsoleInputW.restype = wintypes.BOOL
    before = [mode(input_handle), mode(output_handle)]
    try:
        if target:
            import runpy
            sys.argv = [target, '--autoplay', '--stop-after', '.4', '--report',
                        str(Path(report).with_suffix('.frames.json'))]
            if audio:
                sys.argv.extend(['--audio', audio])
            runpy.run_path(target, run_name='__main__')
            Path(report).write_text(json.dumps(dict(
                before=before, after=[mode(input_handle), mode(output_handle)],
                stdout_restored=sys.stdout is console_out)), encoding='utf-8')
            return
        from terminal import Terminal
        with Terminal() as terminal:
            records = (InputRecord * 12)()
            for i, (key, char) in enumerate([(0x25, '\0'), (0x27, '\0'), (0x26, '\0'),
                                             (0x20, ' '), (0x48, 'h'), (0x51, 'q')]):
                for j in range(2):
                    records[i*2+j].type = 1
                    records[i*2+j].event.key = KeyEvent(
                        j == 0, 1, key, user.MapVirtualKeyW(key, 0), char, 0)
            written = wintypes.DWORD()
            if not kernel.WriteConsoleInputW(input_handle, records, len(records), ctypes.byref(written)):
                raise ctypes.WinError(ctypes.get_last_error())
            keys = terminal.read_keys(.2)
            begin = time.monotonic()
            empty = terminal.read_keys(.03)
            wait = time.monotonic()-begin
            vt_enabled = bool(mode(output_handle) & 4)
            raw_input = not bool(mode(input_handle) & (2 | 4 | 0x40 | 0x200))
        data = dict(keys=keys, empty=empty, wait_seconds=wait,
                    vt_enabled=vt_enabled, raw_input=raw_input,
                    before=before, after=[mode(input_handle), mode(output_handle)],
                    stdout_restored=sys.stdout is console_out)
        Path(report).write_text(json.dumps(data), encoding='utf-8')
    finally:
        sys.stdin, sys.stdout = original_in, original_out
        console_in.close()
        console_out.close()


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--player-probe':
        console_probe(sys.argv[2], sys.argv[3], sys.argv[4])
    elif len(sys.argv) > 1 and sys.argv[1] == '--probe':
        console_probe(sys.argv[2])
    else:
        unittest.main(verbosity=2)
