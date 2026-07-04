import curses
import time

import numpy as np


COLOR_BLUE = 1
COLOR_CYAN = 2
COLOR_WHITE = 3
COLOR_YELLOW = 4
COLOR_LABEL = 5

# Density ramp: char + (color pair, extra attr) from sparse to dense.
RAMP_CHARS = [".", ":", "*", "#", "@"]

# Notable r values: (r, tiny label)
NOTABLE = [
    (3.0, "r=3"),
    (3.4495, "3.4495"),
    (3.5699, "chaos"),
    (3.8284, "per-3"),
]

# Zoom targets cycled through after the initial full sweep.
ZOOM_TARGETS = [
    (3.81, 3.87),    # period-3 window around r ~ 3.83
    (3.435, 3.60),   # first period-doubling cascade into chaos
]

BURN_IN = 200
N_X0 = 24            # number of random initial conditions iterated together
ZOOM_FRAMES = 24     # frames for the zoom interpolation animation
HOLD_SECONDS = 1.6   # pause on a finished diagram before zooming


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_BLUE, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_CYAN, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_WHITE, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_YELLOW, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def ramp_attr(level):
    """Attribute for a density level 0 (sparse) .. 4 (dense)."""
    if level <= 0:
        return curses.color_pair(COLOR_BLUE) | curses.A_DIM
    if level == 1:
        return curses.color_pair(COLOR_BLUE)
    if level == 2:
        return curses.color_pair(COLOR_CYAN)
    if level == 3:
        return curses.color_pair(COLOR_CYAN) | curses.A_BOLD
    return curses.color_pair(COLOR_WHITE) | curses.A_BOLD


def iterate_columns(rs, height, burn_in, samples, n_x0, rng):
    """Iterate the logistic map for each r in `rs` (vectorized over a batch
    of random initial conditions) and histogram the attractor samples into
    `height` rows. Returns an int array of shape (len(rs), height); row 0
    corresponds to x = 1 (top of screen)."""
    rs = np.asarray(rs, dtype=np.float64)
    k = rs.size
    if k == 0 or height <= 0:
        return np.zeros((k, max(height, 0)), dtype=np.int64)
    x = rng.uniform(0.05, 0.95, size=(k, n_x0))
    r = rs[:, None]
    for _ in range(burn_in):
        x = r * x * (1.0 - x)
    hist = np.zeros((k, height), dtype=np.int64)
    col_idx = np.repeat(np.arange(k), n_x0)
    n_collect = max(1, -(-int(samples) // n_x0))
    for _ in range(n_collect):
        x = r * x * (1.0 - x)
        rows = ((1.0 - x) * (height - 1)).astype(np.int64)
        np.clip(rows, 0, height - 1, out=rows)
        np.add.at(hist, (col_idx, rows.ravel()), 1)
    return hist


def hist_to_levels(hist):
    """Convert per-column histograms to density levels -1 (empty) .. 4."""
    hist = np.asarray(hist)
    levels = np.full(hist.shape, -1, dtype=np.int8)
    if hist.size == 0:
        return levels
    colmax = hist.max(axis=1, keepdims=True)
    colmax = np.maximum(colmax, 1)
    frac = hist / colmax
    lv = np.minimum((frac * 5.0).astype(np.int8), 4)
    levels[hist > 0] = lv[hist > 0]
    return levels


def column_rs(lo, hi, width):
    """r value for each terminal column."""
    if width <= 1:
        return np.array([lo], dtype=np.float64)
    return lo + (hi - lo) * np.arange(width) / (width - 1)


def draw_grid(stdscr, levels, width, plot_h):
    for col in range(min(width, levels.shape[0])):
        for row in range(min(plot_h, levels.shape[1])):
            lv = levels[col, row]
            if lv < 0:
                continue
            try:
                stdscr.addstr(row + 1, col, RAMP_CHARS[lv], ramp_attr(lv))
            except curses.error:
                pass


def draw_markers(stdscr, lo, hi, width, plot_h):
    span = hi - lo
    if span <= 0:
        return
    for rv, name in NOTABLE:
        if not (lo < rv < hi):
            continue
        col = int(round((rv - lo) / span * (width - 1)))
        tick_attr = curses.color_pair(COLOR_WHITE) | curses.A_DIM
        for row in range(1, min(4, plot_h + 1)):
            try:
                stdscr.addstr(row, col, "|", tick_attr)
            except curses.error:
                pass
        label_col = min(max(0, col - len(name) // 2), max(0, width - len(name) - 1))
        try:
            stdscr.addstr(0, label_col, name,
                          curses.color_pair(COLOR_WHITE) | curses.A_DIM)
        except curses.error:
            pass


def run(stdscr, duration, frame_delay, r_min, r_max, cols_per_frame, samples):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))
    rng = np.random.default_rng()

    lo, hi = r_min, r_max
    phase = "draw"
    draw_col = 0
    hold_until = 0.0
    zoom_step = 0
    zoom_from = (r_min, r_max)
    zoom_to = ZOOM_TARGETS[0]
    target_idx = 0
    levels = None
    prev_dims = (-1, -1)

    start = time.monotonic()
    while True:
        now = time.monotonic()
        if now - start >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        width = max_x
        plot_h = max(1, max_y - 2)  # row 0: marker labels, last row: info

        if (width, plot_h) != prev_dims:
            prev_dims = (width, plot_h)
            levels = np.full((width, plot_h), -1, dtype=np.int8)
            if phase in ("draw", "hold"):
                phase = "draw"
                draw_col = 0

        cursor_col = -1
        cursor_r = None

        if phase == "draw":
            n = min(int(cols_per_frame), width - draw_col)
            if n > 0:
                rs_all = column_rs(lo, hi, width)
                rs = rs_all[draw_col:draw_col + n]
                hist = iterate_columns(rs, plot_h, BURN_IN, samples, N_X0, rng)
                levels[draw_col:draw_col + n, :] = hist_to_levels(hist)
                cursor_col = min(draw_col + n - 1, width - 1)
                cursor_r = rs[-1]
                draw_col += n
            if draw_col >= width:
                phase = "hold"
                hold_until = now + HOLD_SECONDS
        elif phase == "hold":
            if now >= hold_until:
                zoom_from = (lo, hi)
                if target_idx < len(ZOOM_TARGETS):
                    zoom_to = ZOOM_TARGETS[target_idx]
                else:
                    zoom_to = (r_min, r_max)  # zoom back out
                target_idx = (target_idx + 1) % (len(ZOOM_TARGETS) + 1)
                zoom_step = 0
                phase = "zoom"
        elif phase == "zoom":
            zoom_step += 1
            t = min(1.0, zoom_step / float(ZOOM_FRAMES))
            te = t * t * (3.0 - 2.0 * t)  # smoothstep ease
            lo = zoom_from[0] + (zoom_to[0] - zoom_from[0]) * te
            hi = zoom_from[1] + (zoom_to[1] - zoom_from[1]) * te
            # Coarse quick preview of the whole diagram at this scale.
            rs = column_rs(lo, hi, width)
            hist = iterate_columns(rs, plot_h, 60, 80, 12, rng)
            levels = hist_to_levels(hist)
            if t >= 1.0:
                lo, hi = zoom_to
                phase = "draw"
                draw_col = 0
                levels = np.full((width, plot_h), -1, dtype=np.int8)

        stdscr.erase()
        draw_grid(stdscr, levels, width, plot_h)
        draw_markers(stdscr, lo, hi, width, plot_h)

        if cursor_col >= 0:
            attr = curses.color_pair(COLOR_YELLOW) | curses.A_BOLD
            for row in range(1, plot_h + 1):
                try:
                    stdscr.addstr(row, cursor_col, "|", attr)
                except curses.error:
                    pass
            if cursor_r is not None:
                txt = f"r={cursor_r:.4f}"
                tc = min(max(0, cursor_col + 2), max(0, width - len(txt) - 1))
                try:
                    stdscr.addstr(1, tc, txt, attr)
                except curses.error:
                    pass

        info = (f"Bifurcation  r=[{lo:.4f}, {hi:.4f}]  phase:{phase}  "
                f"cols/frame={cols_per_frame}  samples={samples}  q:quit")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def main(duration=28, frame_delay=0.03, r_min=2.8, r_max=4.0,
         cols_per_frame=2, samples=300):
    duration = float(duration)
    frame_delay = float(frame_delay)
    r_min = float(r_min)
    r_max = float(r_max)
    if r_max <= r_min:
        r_min, r_max = 2.8, 4.0
    r_min = max(0.0, r_min)
    r_max = min(4.0, r_max)
    cols_per_frame = max(1, int(cols_per_frame))
    samples = max(N_X0, int(samples))
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, r_min, r_max, cols_per_frame, samples))


if __name__ == "__main__":
    main()
