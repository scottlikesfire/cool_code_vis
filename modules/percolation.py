import curses
import time

import numpy as np
from scipy import ndimage


P_CRITICAL = 0.5927

COLOR_OPEN = 1      # dim green: open but not connected to top
COLOR_WATER = 2     # bright cyan: cluster connected to the top row
COLOR_BIG1 = 3      # largest non-top clusters get their own colors
COLOR_BIG2 = 4
COLOR_BIG3 = 5
COLOR_FLASH = 6     # spanning-cluster flash
COLOR_LABEL = 7

# Cell class -> (character, base color pair). Class 0 (closed) is left blank.
CLS_CHARS = {1: "·", 2: "~", 3: "o", 4: "o", 5: "o", 6: "#"}


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_OPEN, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_WATER, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_BIG1, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_BIG2, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_BIG3, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_FLASH, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def cls_attr(cls, flash_white):
    if cls == 1:
        return curses.color_pair(COLOR_OPEN) | curses.A_DIM
    if cls == 2:
        return curses.color_pair(COLOR_WATER) | curses.A_BOLD
    if cls in (3, 4, 5):
        return curses.color_pair(cls)
    # Spanning cluster: alternate bold white / bold yellow.
    pair = COLOR_FLASH if flash_white else COLOR_BIG1
    return curses.color_pair(pair) | curses.A_BOLD


def classify(values, p):
    """Classify each site of the grid for the given occupation probability p.

    Returns (cls, spanning, largest_frac) where cls is an int8 array:
      0 closed, 1 open (unconnected), 2 top-connected "water",
      3-5 the largest non-top clusters, 6 spanning cluster.
    Fully vectorized via scipy.ndimage.label (4-connectivity).
    """
    open_mask = values < p
    cls = np.zeros(values.shape, dtype=np.int8)
    cls[open_mask] = 1
    if not open_mask.any():
        return cls, False, 0.0

    labels, num = ndimage.label(open_mask)  # default structure = 4-connectivity
    sizes = np.bincount(labels.ravel(), minlength=num + 1)
    sizes[0] = 0
    largest_frac = float(sizes.max()) / float(values.size)

    top = np.unique(labels[0])
    top = top[top > 0]
    bottom = np.unique(labels[-1])
    bottom = bottom[bottom > 0]
    span = np.intersect1d(top, bottom, assume_unique=True)

    if top.size:
        cls[np.isin(labels, top)] = 2

    # Color the 2-3 largest clusters that are NOT connected to the top.
    other_sizes = sizes.copy()
    other_sizes[top] = 0
    order = np.argsort(other_sizes)[::-1][:3]
    for i, lab in enumerate(order):
        if other_sizes[lab] >= 5:
            cls[labels == lab] = 3 + i

    spanning = span.size > 0
    if spanning:
        cls[np.isin(labels, span)] = 6
    return cls, spanning, largest_frac


def draw_grid(stdscr, cls, flash_white):
    """Render the class grid using run-length addstr calls (no per-cell loop)."""
    rows, cols = cls.shape
    for y in range(rows):
        row = cls[y]
        change = np.flatnonzero(np.diff(row)) + 1
        starts = np.concatenate(([0], change))
        ends = np.concatenate((change, [cols]))
        for s, e in zip(starts.tolist(), ends.tolist()):
            c = int(row[s])
            if c == 0:
                continue
            try:
                stdscr.addstr(y, s, CLS_CHARS[c] * (e - s),
                              cls_attr(c, flash_white))
            except curses.error:
                pass


def run(stdscr, duration, frame_delay, p_start, p_end, sweep_time,
        completion_pause):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    rng = np.random.default_rng()
    values = None
    sweep_start = time.monotonic()
    flash_until = 0.0
    perc_p = None
    frame = 0

    start = time.monotonic()
    while True:
        now = time.monotonic()
        if now - start >= duration:
            break
        frame += 1

        max_y, max_x = stdscr.getmaxyx()
        rows, cols = max(1, max_y - 1), max(1, max_x)
        if values is None or values.shape != (rows, cols):
            values = rng.random((rows, cols))
            sweep_start = now
            flash_until = 0.0
            perc_p = None

        flashing = now < flash_until
        if flashing:
            p = perc_p  # freeze p while celebrating the spanning cluster
        elif perc_p is not None:
            # Flash finished: reset with fresh random values and start over.
            values = rng.random((rows, cols))
            sweep_start = now
            perc_p = None
            p = p_start
        else:
            frac = (now - sweep_start) / max(1e-6, sweep_time)
            p = min(p_end, p_start + (p_end - p_start) * frac)

        cls, spanning, largest_frac = classify(values, p)
        if spanning and not flashing:
            perc_p = p
            flash_until = now + completion_pause
            flashing = True

        stdscr.erase()
        draw_grid(stdscr, cls, flash_white=(frame % 2 == 0))

        if flashing:
            msg = f" PERCOLATED at p={perc_p:.4f} "
            try:
                stdscr.addstr(max(0, rows // 2), max(0, (max_x - len(msg)) // 2),
                              msg[:max_x - 1],
                              curses.color_pair(COLOR_FLASH)
                              | curses.A_BOLD | curses.A_REVERSE)
            except curses.error:
                pass

        info = (f"Percolation  p={p:.4f}  p_c={P_CRITICAL}  "
                f"largest={largest_frac:.3f}  sweep={sweep_time:g}s")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def main(duration=28, frame_delay=0.04, p_start=0.35, p_end=0.75,
         sweep_time=12.0, completion_pause=1.5):
    duration = float(duration)
    frame_delay = float(frame_delay)
    p_start = float(p_start)
    p_end = float(p_end)
    sweep_time = float(sweep_time)
    completion_pause = float(completion_pause)
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, p_start, p_end, sweep_time,
        completion_pause))


if __name__ == "__main__":
    main()
