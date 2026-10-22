"""Interactive terminal setup and key input for Windows and macOS."""
import os
import sys
import time


class Terminal:
    def __enter__(self):
        if not sys.stdin.isatty():
            raise RuntimeError('请在 Windows Terminal、PowerShell 或 macOS 终端中运行。')
        self.stdout = sys.stdout
        self.output = None
        self.modes = []
        self.original = None
        self.active = False
        self.extended_key = False
        try:
            if sys.platform == 'win32':
                import ctypes
                from ctypes import wintypes
                import msvcrt
                self.output = open('CONOUT$', 'w', encoding='utf-8', buffering=1)
                self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                self.kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
                self.kernel.GetConsoleMode.restype = wintypes.BOOL
                self.kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
                self.kernel.SetConsoleMode.restype = wintypes.BOOL
                for stream, output in ((sys.stdin, False), (self.output, True)):
                    handle = msvcrt.get_osfhandle(stream.fileno())
                    mode = wintypes.DWORD()
                    if not self.kernel.GetConsoleMode(handle, ctypes.byref(mode)):
                        raise ctypes.WinError(ctypes.get_last_error())
                    self.modes.append((handle, mode.value))
                    # Enable ANSI output; disable line/echo, Quick Edit, and VT input.
                    flags = mode.value | 5 if output else (mode.value | 0x80) & ~(2 | 4 | 0x40 | 0x200)
                    if not self.kernel.SetConsoleMode(handle, flags):
                        raise ctypes.WinError(ctypes.get_last_error())
            else:
                import termios
                import tty
                self.output = open('/dev/tty', 'w', encoding='utf-8', buffering=1)
                self.original = termios.tcgetattr(sys.stdin.fileno())
                tty.setcbreak(sys.stdin.fileno())
            sys.stdout = self.output
            self.active = True
            self.output.write('\x1b[?1049h\x1b[?25l\x1b[?7l\x1b[2J')
            self.output.flush()
            return self
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise

    def __exit__(self, *_):
        try:
            if self.active:
                self.output.write('\x1b[0m\x1b[?7h\x1b[?25h\x1b[?1049l')
                self.output.flush()
        finally:
            try:
                if sys.platform == 'win32':
                    for handle, mode in reversed(self.modes):
                        self.kernel.SetConsoleMode(handle, mode)
                elif self.original is not None:
                    import termios
                    termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self.original)
            finally:
                sys.stdout = self.stdout
                if self.output is not None:
                    self.output.close()

    def size(self):
        stream = self.output if sys.platform == 'win32' else sys.stdin
        try:
            return os.get_terminal_size(stream.fileno())
        except OSError:
            return 100, 36

    def read_keys(self, timeout):
        if sys.platform == 'win32':
            import msvcrt
            deadline = time.monotonic()+timeout
            keys = []
            while True:
                while msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if self.extended_key:
                        keys.append({'K': '\x1b[D', 'M': '\x1b[C'}.get(ch, ''))
                        self.extended_key = False
                    elif ch in ('\x00', '\xe0'):
                        self.extended_key = True
                    else:
                        keys.append(ch)
                remaining = deadline-time.monotonic()
                if keys or remaining <= 0:
                    return ''.join(keys)
                time.sleep(min(.01, remaining))
        import select
        if not select.select([sys.stdin], [], [], timeout)[0]:
            return ''
        keys = os.read(sys.stdin.fileno(), 128).decode('utf-8', errors='ignore')
        if keys == '\x1b' and select.select([sys.stdin], [], [], .035)[0]:
            keys += os.read(sys.stdin.fileno(), 32).decode('utf-8', errors='ignore')
        return keys
