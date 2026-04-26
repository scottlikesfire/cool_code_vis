"""Non-blocking 'q'/ESC quit handling for modules that use raw stdout escapes
(rather than curses) and therefore can't get keys via stdscr.getch().

Usage:
    with StdinPoller() as poller:
        while running:
            ...
            if poller.should_quit():
                return
"""

import select
import sys
import termios
import tty


class StdinPoller:
    def __init__(self):
        self.fd = sys.stdin.fileno()
        self.old_attrs = None
        self.active = False

    def __enter__(self):
        try:
            self.old_attrs = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
            self.active = True
        except (termios.error, OSError, ValueError):
            self.active = False
        return self

    def __exit__(self, *exc):
        if self.old_attrs is not None:
            try:
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_attrs)
            except (termios.error, OSError):
                pass

    def should_quit(self):
        """Return True if 'q', 'Q', or ESC is pending on stdin."""
        if not self.active:
            return False
        try:
            ready, _, _ = select.select([sys.stdin], [], [], 0)
            if not ready:
                return False
            ch = sys.stdin.read(1)
            return ch in ("q", "Q", "\x1b")
        except (OSError, ValueError):
            return False
