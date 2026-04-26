import curses
import shutil
import sys
import time
from random import choice
from asciimatics.event import KeyboardEvent
from asciimatics.renderers import Plasma, Rainbow, FigletText
from asciimatics.scene import Scene
from asciimatics.screen import Screen
from asciimatics.effects import Print
from asciimatics.exceptions import ResizeScreenError, StopApplication

from modules._quit_helper import StdinPoller



_original_curs_set = curses.curs_set
def _safe_curs_set(visibility):
    try:
        return _original_curs_set(visibility)
    except curses.error:
        pass
curses.curs_set = _safe_curs_set

_original_tigetstr = curses.tigetstr
def _safe_tigetstr(cap):
    result = _original_tigetstr(cap)
    if result is None:
        return b""
    return result
curses.tigetstr = _safe_tigetstr




class PlasmaScene(Scene):

    def __init__(self, screen, num_frames=500):
        self._screen = screen
        effects = [
            Print(screen,
                  Plasma(screen.height, screen.width, screen.colours),
                  0,
                  speed=1,
                  transparent=False),
        ]
        super().__init__(effects, num_frames, clear=False)


    def reset(self, old_scene=None, screen=None):
        # Avoid reseting the Plasma effect so that the animation continues across scenes.
        plasma = self._effects[0]
        self._effects = []
        super().reset(old_scene, screen)

        # Make sure that we only have the initial plasma Effect and a single cheesy comment.
        self._effects = [plasma]
        # self._add_cheesy_comment()


def show_loading(loading_duration):
    term_width = shutil.get_terminal_size().columns
    term_height = shutil.get_terminal_size().lines
    bar_width = 40
    title = "computing plasma simulation"

    steps = 50
    interval = loading_duration / steps

    sys.stdout.write("\033[2J\033[H")
    with StdinPoller() as poller:
        for i in range(steps + 1):
            if poller.should_quit():
                sys.stdout.write("\033[2J\033[H")
                sys.stdout.flush()
                return True
            pct = i / steps
            filled = int(bar_width * pct)
            bar = "█" * filled + "░" * (bar_width - filled)
            pct_text = f"{int(pct * 100)}%"

            title_x = max(0, (term_width - len(title)) // 2)
            bar_str = f"[{bar}] {pct_text}"
            bar_x = max(0, (term_width - len(bar_str)) // 2)
            y = term_height // 2

            sys.stdout.write(f"\033[{y};{title_x + 1}H{title}")
            sys.stdout.write(f"\033[{y + 2};{bar_x + 1}H{bar_str}")
            sys.stdout.flush()
            time.sleep(interval)

    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()
    return False


def _quit_on_q(event):
    if isinstance(event, KeyboardEvent):
        if event.key_code in (ord("q"), ord("Q"), Screen.KEY_ESCAPE):
            raise StopApplication("user quit")


def plasma_render(screen, duration):
    fps = 20
    num_frames = int(duration * fps) if duration else 500
    screen.play([PlasmaScene(screen, num_frames)],
                stop_on_resize=True, repeat=False,
                unhandled_input=_quit_on_q)


def main(duration=None, loading_duration=3):
    if duration is not None:
        duration = float(duration)
    loading_duration = float(loading_duration)
    if show_loading(loading_duration):
        return
    try:
        Screen.wrapper(plasma_render, arguments=[duration])
    except (ResizeScreenError, StopApplication):
        pass


if __name__ == "__main__":
    main()