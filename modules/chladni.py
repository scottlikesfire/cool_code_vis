import curses
import random
import time

import numpy as np


COLOR_SAND_BRIGHT = 1   # bright white sand ridge core
COLOR_SAND = 2          # yellow sand
COLOR_MID = 3           # dim transition
COLOR_BG = 4            # dark blue background
COLOR_LABEL = 5

# ascii ramp from background (faint) to sand ridge (dense)
RAMP = " .:-=+*#%@"


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_SAND_BRIGHT, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_SAND, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_MID, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_BG, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def make_grid(cols, rows):
    """Coordinate meshgrid over the plate x,y in [-1, 1].

    Terminal cells are ~2:1 (tall), so the x extent uses ~2x the cells
    of the y extent to render a square-ish plate.
    """
    x = np.linspace(-1.0, 1.0, max(2, cols))
    y = np.linspace(-1.0, 1.0, max(2, rows))
    return np.meshgrid(x, y)


def chladni_field(m, n, xx, yy):
    """Classic square-plate Chladni figure for mode pair (m, n)."""
    return (np.cos(n * np.pi * xx) * np.cos(m * np.pi * yy)
            - np.cos(m * np.pi * xx) * np.cos(n * np.pi * yy))


def random_mode_pair(max_mode, exclude=None):
    """Random (m, n) with 1 <= m,n <= max_mode and m != n."""
    while True:
        m = random.randint(1, max_mode)
        n = random.randint(1, max_mode)
        if m != n and (m, n) != exclude:
            return (m, n)


def smoothstep(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def field_to_cells(z, shimmer):
    """Map |Z| to (ramp index, color, bold) arrays. Sand at nodal lines."""
    az = np.abs(z)
    # brightness inversely proportional to |Z|: 1 at nodes, ~0 at antinodes
    thresh = 0.45 * shimmer
    bright = np.clip(1.0 - az / thresh, 0.0, 1.0)
    idx = (bright * (len(RAMP) - 1)).astype(np.int32)
    return idx, bright


def run(stdscr, duration, frame_delay, max_mode, morph_time, hold_time):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    cur = random_mode_pair(max_mode)
    nxt = random_mode_pair(max_mode, exclude=cur)
    phase_start = time.monotonic()
    morphing = False

    grid_shape = None
    xx = yy = None
    z_cur = z_nxt = None

    n_levels = len(RAMP)
    hi = int(n_levels * 0.85)
    mid_hi = int(n_levels * 0.6)
    mid_lo = int(n_levels * 0.3)

    start = time.monotonic()
    while True:
        now = time.monotonic()
        if now - start >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        rows = max(1, max_y - 1)   # bottom line reserved for label
        cols = max(2, max_x - 1)   # avoid writing the last cell of a row

        # square-ish plate: x spans ~2x the y range in cells
        plate_h = rows
        plate_w = min(cols, 2 * rows)
        x_off = (cols - plate_w) // 2

        if grid_shape != (plate_h, plate_w):
            grid_shape = (plate_h, plate_w)
            xx, yy = make_grid(plate_w, plate_h)
            z_cur = chladni_field(cur[0], cur[1], xx, yy)
            z_nxt = chladni_field(nxt[0], nxt[1], xx, yy)

        # morph / hold state machine
        elapsed = now - phase_start
        if morphing:
            if elapsed >= morph_time:
                cur = nxt
                z_cur = z_nxt
                nxt = random_mode_pair(max_mode, exclude=cur)
                z_nxt = chladni_field(nxt[0], nxt[1], xx, yy)
                morphing = False
                phase_start = now
                t = 0.0
            else:
                t = smoothstep(elapsed / morph_time)
        else:
            t = 0.0
            if elapsed >= hold_time:
                morphing = True
                phase_start = now

        z = (1.0 - t) * z_cur + t * z_nxt

        # subtle global shimmer on the nodal threshold
        shimmer = 1.0 + 0.05 * np.sin(2.0 * np.pi * 0.8 * (now - start))
        idx, bright = field_to_cells(z, shimmer)

        stdscr.erase()
        for row in range(plate_h):
            irow = idx[row]
            # build the row string once, then paint attr bands
            line = "".join(RAMP[i] for i in irow)
            # background band (dim blue)
            try:
                stdscr.addstr(row, x_off, line,
                              curses.color_pair(COLOR_BG) | curses.A_DIM)
            except curses.error:
                pass
            # overpaint brighter bands character-by-character in runs
            c = 0
            w = len(irow)
            while c < w:
                v = irow[c]
                if v < mid_lo:
                    c += 1
                    continue
                c2 = c
                if v >= hi:
                    while c2 < w and irow[c2] >= hi:
                        c2 += 1
                    attr = curses.color_pair(COLOR_SAND_BRIGHT) | curses.A_BOLD
                elif v >= mid_hi:
                    while c2 < w and mid_hi <= irow[c2] < hi:
                        c2 += 1
                    attr = curses.color_pair(COLOR_SAND) | curses.A_BOLD
                else:
                    while c2 < w and mid_lo <= irow[c2] < mid_hi:
                        c2 += 1
                    attr = curses.color_pair(COLOR_MID)
                try:
                    stdscr.addstr(row, x_off + c, line[c:c2], attr)
                except curses.error:
                    pass
                c = c2

        # frequency-ish label: f ~ m^2 + n^2 (plate mode scaling)
        freq = 110.0 * (cur[0] ** 2 + cur[1] ** 2)
        info = (f"Chladni  ({cur[0]},{cur[1]}) -> ({nxt[0]},{nxt[1]})  "
                f"~{freq:.0f} Hz  max_mode={max_mode}  "
                f"morph={morph_time}s hold={hold_time}s")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def main(duration=30, frame_delay=0.04, max_mode=7, morph_time=2.5,
         hold_time=2.0):
    duration = float(duration)
    frame_delay = float(frame_delay)
    max_mode = max(2, int(max_mode))
    morph_time = max(0.1, float(morph_time))
    hold_time = max(0.0, float(hold_time))
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, max_mode, morph_time, hold_time))


if __name__ == "__main__":
    main()
