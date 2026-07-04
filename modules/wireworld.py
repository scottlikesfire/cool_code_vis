import curses
import time

import numpy as np


# Cell states
EMPTY, CONDUCTOR, HEAD, TAIL = 0, 1, 2, 3

# Color pair ids
PAIR_CONDUCTOR = 1
PAIR_HEAD = 2
PAIR_TAIL = 3
PAIR_LABEL = 4

STATE_CHARS = {CONDUCTOR: ".", HEAD: "@", TAIL: "o"}
CHAR_TO_STATE = {" ": EMPTY, ".": CONDUCTOR, "H": HEAD, "T": TAIL}

# Seconds spent on each circuit before cycling to the next one.
CIRCUIT_SECONDS = 10.0

# ---------------------------------------------------------------------------
# Circuit templates.  '.' conductor, 'H' electron head, 'T' electron tail,
# ' ' empty.
#
# The diode used below (pass left-to-right):
#          ..
#     ...... .....      wire, pairs above/below last wire cell + gap, resume
#          ..
# Reversed (wide side facing the incoming wire) it blocks: the cell after the
# structure sees 3 electron heads at once and never fires.
# ---------------------------------------------------------------------------

# (a) Two clock loops of different periods.  The fast clock (top) fires down a
# wire through a forward diode: pulses pass.  The slow clock (bottom) fires
# into a reversed diode: every pulse dies there and the right-hand wire stays
# dark.
TEMPLATE_CLOCKS = """\
.TH...                        ..
.    .......................... ........................
.    .                        ..
......


.TH.....                       ..
.      ........................ ........................
.      .                       ..
.      .
.      .
........
"""

# (b) A big raceway loop with four electrons chasing each other clockwise
# through an inline diode on the top straight.
TEMPLATE_RACEWAY = """\
                      ..
.....TH................ ......................
.                     ..                     .
.                                            T
.                                            H
H                                            .
T                                            .
.                                            .
.                                            .
.                                            .
..............................HT..............
"""

# (c) Two clocks merged onto one output wire.  Each branch goes through a
# forward diode, then the branches join at a Y junction; the diodes stop the
# junction's backwash pulses from reaching the opposite clock.
TEMPLATE_MERGE = """\
.TH...              ..
.    ................ .................
.    .              ..                 .
......                                  .
                                         ...............
                                        .
.TH.....            ..                 .
.      .............. .................
.      .            ..
.      .
.      .
........
"""

CIRCUITS = [
    ("clocks + diodes", TEMPLATE_CLOCKS),
    ("electron raceway", TEMPLATE_RACEWAY),
    ("diode OR-merge", TEMPLATE_MERGE),
]

_NEIGHBOR_OFFSETS = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                     if (dy, dx) != (0, 0)]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(PAIR_CONDUCTOR, curses.COLOR_YELLOW, -1)
    curses.init_pair(PAIR_HEAD, curses.COLOR_BLUE, -1)
    curses.init_pair(PAIR_TAIL, curses.COLOR_RED, -1)
    curses.init_pair(PAIR_LABEL, curses.COLOR_CYAN, -1)


def parse_template(template, pad=1):
    """Turn an ASCII template into a padded numpy state grid."""
    lines = template.strip("\n").split("\n")
    height = len(lines)
    width = max(len(line) for line in lines)
    grid = np.zeros((height + 2 * pad, width + 2 * pad), dtype=np.uint8)
    for y, line in enumerate(lines):
        for x, ch in enumerate(line):
            grid[y + pad, x + pad] = CHAR_TO_STATE.get(ch, EMPTY)
    return grid


def step(grid):
    """One Wireworld generation, fully vectorized.

    head -> tail, tail -> conductor, conductor -> head iff exactly 1 or 2 of
    its 8 neighbors are heads (neighbor counts via np.roll).
    """
    heads = grid == HEAD
    counts = np.zeros(grid.shape, dtype=np.uint8)
    for dy, dx in _NEIGHBOR_OFFSETS:
        counts += np.roll(np.roll(heads, dy, axis=0), dx, axis=1)
    new = grid.copy()
    new[grid == HEAD] = TAIL
    new[grid == TAIL] = CONDUCTOR
    new[(grid == CONDUCTOR) & ((counts == 1) | (counts == 2))] = HEAD
    return new


def run(stdscr, duration, frame_delay, generations_per_frame):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    parsed = [(name, parse_template(tpl)) for name, tpl in CIRCUITS]
    smallest = min(range(len(parsed)), key=lambda i: parsed[i][1].size)

    attrs = {
        CONDUCTOR: curses.color_pair(PAIR_CONDUCTOR) | curses.A_DIM,
        HEAD: curses.color_pair(PAIR_HEAD) | curses.A_BOLD,
        TAIL: curses.color_pair(PAIR_TAIL),
    }

    active = -1
    grid = None
    gen = 0
    start = time.monotonic()
    while True:
        now = time.monotonic()
        if now - start >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        view_h, view_w = max(1, max_y - 1), max_x

        desired = int((now - start) // CIRCUIT_SECONDS) % len(parsed)
        gh, gw = parsed[desired][1].shape
        idx = desired
        if gh > view_h or gw > view_w:
            idx = smallest  # terminal too small: fall back to smallest circuit
        if idx != active:
            active = idx
            grid = parsed[idx][1].copy()
            gen = 0
        name = parsed[active][0]

        for _ in range(generations_per_frame):
            grid = step(grid)
            gen += 1

        stdscr.erase()
        gh, gw = grid.shape
        off_y = (view_h - gh) // 2
        off_x = (view_w - gw) // 2
        for y, x in np.argwhere(grid != EMPTY):
            sy, sx = y + off_y, x + off_x
            if 0 <= sy < view_h and 0 <= sx < view_w:
                state = int(grid[y, x])
                try:
                    stdscr.addstr(sy, sx, STATE_CHARS[state], attrs[state])
                except curses.error:
                    pass

        info = (f"Wireworld  [{name}]  gen={gen}  "
                f"delay={frame_delay:g}s gpf={generations_per_frame}  q:quit")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(PAIR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def main(duration=28, frame_delay=0.08, generations_per_frame=1):
    duration = float(duration)
    frame_delay = float(frame_delay)
    generations_per_frame = max(1, int(generations_per_frame))
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, generations_per_frame))


if __name__ == "__main__":
    main()
