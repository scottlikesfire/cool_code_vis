import curses
import random
import time
from collections import deque

import numpy as np


# Ordered like a color wheel so cyclic states shade smoothly around it.
WHEEL_COLORS = [
    curses.COLOR_RED, curses.COLOR_YELLOW, curses.COLOR_GREEN,
    curses.COLOR_CYAN, curses.COLOR_BLUE, curses.COLOR_MAGENTA,
]
COLOR_LABEL = 7

# Texture ramp; combined with color+bold it keeps up to 16 states distinct.
STATE_CHARS = [".", "o", "#", "@"]

# If fewer than this fraction of cells change for RESEED_PATIENCE consecutive
# steps, the world is considered boring and gets reseeded.
BORING_FRACTION = 0.004
RESEED_PATIENCE = 40


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    for i, c in enumerate(WHEEL_COLORS):
        curses.init_pair(i + 1, c, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def build_styles(num_states):
    """Map each state to (char, curses attr) around a 12-step rainbow wheel:
    6 colors x (normal, bold), plus a char ramp for extra distinction."""
    styles = []
    n_wheel = len(WHEEL_COLORS) * 2  # 12 color/intensity steps
    for s in range(num_states):
        w = (s * n_wheel) // num_states
        color = curses.color_pair((w // 2) + 1)
        attr = color | (curses.A_BOLD if w % 2 else 0)
        ch = STATE_CHARS[(s * len(STATE_CHARS)) // num_states]
        styles.append((ch, attr))
    return styles


def make_grid(rows, cols, num_states, rng):
    return rng.integers(0, num_states, size=(rows, cols), dtype=np.int16)


def step_ca(grid, num_states, threshold, moore=False):
    """One cyclic-CA step, fully vectorized with np.roll.

    A cell in state s advances to (s+1) % num_states when at least
    `threshold` neighbors are already in state (s+1) % num_states.
    Returns (new_grid, number_of_cells_that_changed)."""
    nxt = (grid + 1) % num_states
    shifts = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if moore:
        shifts += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    count = np.zeros(grid.shape, dtype=np.int16)
    for dy, dx in shifts:
        count += np.roll(grid, (dy, dx), axis=(0, 1)) == nxt
    changed = count >= threshold
    return np.where(changed, nxt, grid), int(changed.sum())


def draw_grid(stdscr, grid, styles, max_x):
    rows, cols = grid.shape
    for y in range(rows):
        row = grid[y]
        breaks = np.flatnonzero(np.diff(row)) + 1
        starts = np.concatenate(([0], breaks))
        ends = np.concatenate((breaks, [cols]))
        for st, en in zip(starts, ends):
            if st >= max_x:
                break
            ch, attr = styles[int(row[st])]
            try:
                stdscr.addstr(y, int(st), ch * (int(en) - int(st)), attr)
            except curses.error:
                pass


def run(stdscr, duration, frame_delay, num_states, threshold, moore):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    rng = np.random.default_rng()
    max_y, max_x = stdscr.getmaxyx()
    rows, cols = max(1, max_y - 1), max(1, max_x)
    n = num_states
    grid = make_grid(rows, cols, n, rng)
    styles = build_styles(n)
    generation = 0
    reseeds = 0
    recent = deque(maxlen=RESEED_PATIENCE)

    start = time.monotonic()
    while True:
        if time.monotonic() - start >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        new_rows, new_cols = max(1, max_y - 1), max(1, max_x)
        if (new_rows, new_cols) != (rows, cols):
            rows, cols = new_rows, new_cols
            grid = make_grid(rows, cols, n, rng)
            recent.clear()

        grid, changed = step_ca(grid, n, threshold, moore)
        generation += 1
        recent.append(changed)

        # Reseed when the CA settles into a (near-)fixed point.
        boring_cutoff = max(1, int(grid.size * BORING_FRACTION))
        if len(recent) == RESEED_PATIENCE and max(recent) < boring_cutoff:
            n = random.randint(8, 16)
            grid = make_grid(rows, cols, n, rng)
            styles = build_styles(n)
            reseeds += 1
            recent.clear()

        stdscr.erase()
        draw_grid(stdscr, grid, styles, max_x)

        info = (f"Cyclic CA  gen={generation}  states={n}  "
                f"thresh={threshold}  {'moore' if moore else 'von Neumann'}"
                f"{f'  reseeds={reseeds}' if reseeds else ''}")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def main(duration=28, frame_delay=0.06, num_states=12, threshold=1,
         moore=False):
    duration = float(duration)
    frame_delay = float(frame_delay)
    num_states = max(3, int(num_states))
    threshold = max(1, int(threshold))
    moore = bool(moore) if not isinstance(moore, str) \
        else moore.strip().lower() in ("1", "true", "yes", "on")
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, num_states, threshold, moore))


if __name__ == "__main__":
    main()
