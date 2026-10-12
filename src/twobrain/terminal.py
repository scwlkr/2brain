"""Small native terminal adapter; restores modes and cursor on every exit."""

import codecs
import os
import select
import shutil
import sys
from contextlib import contextmanager

from .errors import BrainError

KEYS = {"\x1b[A": "up", "\x1b[B": "down", "\x1b[C": "right", "\x1b[D": "left",
        "\x1bOA": "up", "\x1bOB": "down", "\x1bOC": "right", "\x1bOD": "left",
        "\x1b[5~": "pageup", "\x1b[6~": "pagedown", "\x1b[H": "home", "\x1b[F": "end",
        "\x1b[1~": "home", "\x1b[4~": "end", "\x1bOH": "home", "\x1bOF": "end"}


class Terminal:
    def __init__(self):
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")

    def size(self):
        dimensions = shutil.get_terminal_size((80, 24))
        return dimensions.columns, dimensions.lines

    def draw(self, rows):
        sys.stdout.write("".join(f"\x1b[{index + 1};1H\x1b[2K{row}" for index, row in enumerate(rows)))
        sys.stdout.flush()

    def key(self):
        if os.name == "nt":
            import msvcrt
            if not msvcrt.kbhit():
                # Bounded polling also lets the browser respond to a resize.
                import time
                time.sleep(0.05)
                return None
            char = msvcrt.getwch()
            if char in ("\x00", "\xe0"):
                return {"H": "up", "P": "down", "K": "left", "M": "right", "I": "pageup",
                        "Q": "pagedown", "G": "home", "O": "end"}.get(msvcrt.getwch(), "unknown")
        else:
            descriptor = sys.stdin.fileno()
            if not select.select([descriptor], [], [], 0.1)[0]:
                return None
            raw = os.read(descriptor, 1)
            if not raw:
                return "quit"
            char = self.decoder.decode(raw)
            if not char:
                return None
            if char == "\x1b":
                sequence = char
                while select.select([descriptor], [], [], 0.03)[0]:
                    sequence += os.read(descriptor, 1).decode("ascii", "replace")
                    if sequence in KEYS:
                        return KEYS[sequence]
                    if not any(key.startswith(sequence) for key in KEYS):
                        break
                return "escape" if sequence == char else "unknown"
        return {"\r": "enter", "\n": "enter", "\x1b": "escape", "\x7f": "backspace",
                "\b": "backspace", "\t": "tab", "\x03": "quit", "\x04": "quit"}.get(char, char)


@contextmanager
def session():
    if not sys.stdin.isatty() or not sys.stdout.isatty() or os.environ.get("TERM") == "dumb":
        raise BrainError("The browser needs an interactive terminal. Use 2brain --list or --json for redirected output.", 2)
    restore = None
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.GetStdHandle.argtypes = [wintypes.DWORD]
            kernel.GetStdHandle.restype = wintypes.HANDLE
            kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            handle = kernel.GetStdHandle(-11)
            previous = wintypes.DWORD()
            if not kernel.GetConsoleMode(handle, ctypes.byref(previous)) or not kernel.SetConsoleMode(handle, previous.value | 4):
                raise BrainError("This Windows console cannot enable terminal styling. Use Windows Terminal or plain CLI output.")
            restore = lambda: kernel.SetConsoleMode(handle, previous.value)
        else:
            import termios
            import tty
            descriptor = sys.stdin.fileno()
            previous = termios.tcgetattr(descriptor)
            restore = lambda: termios.tcsetattr(descriptor, termios.TCSADRAIN, previous)
            tty.setcbreak(descriptor)
        sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[2J")
        sys.stdout.flush()
        yield Terminal()
    finally:
        if restore:
            try:
                sys.stdout.write("\x1b[0m\x1b[?25h\x1b[?1049l")
                sys.stdout.flush()
            finally:
                restore()
