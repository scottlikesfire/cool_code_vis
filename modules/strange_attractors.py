import curses
import time

import numpy as np


COLOR_BLUE = 1
COLOR_MAGENTA = 2
COLOR_RED = 3
COLOR_YELLOW = 4
COLOR_WHITE = 5
COLOR_LABEL = 6

# Brightness ramp: (char, color_pair_id, bold) from faint deep blue up to white.
RAMP = [
    (".", COLOR_BLUE, False),
    (":", COLOR_BLUE, True),
    ("-", COLOR_MAGENTA, False),
    ("=", COLOR_MAGENTA, True),
    ("+", COLOR_RED, False),
    ("*", COLOR_RED, True),
    ("#", COLOR_YELLOW, False),
    ("%", COLOR_YELLOW, True),
    ("@", COLOR_WHITE, False),
    ("@", COLOR_WHITE, True),
]

# Per-parameter drift oscillation frequencies (rad/s), deliberately incommensurate.
DRIFT_OMEGAS = np.array([0.31, 0.23, 0.17, 0.41])


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_BLUE, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_MAGENTA, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_RED, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_YELLOW, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_WHITE, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def step_de_jong(x, y, p):
    a, b, c, d = p
    return np.sin(a * y) - np.cos(b * x), np.sin(c * x) - np.cos(d * y)


def step_clifford(x, y, p):
    a, b, c, d = p
    return (np.sin(a * y) + c * np.cos(a * x),
            np.sin(b * x) + d * np.cos(b * y))


def step_hopalong(x, y, p):
    a, b, c = p[:3]
    return y - np.sign(x) * np.sqrt(np.abs(b * x - c)), a - x


# Gallery: (type name, step function, base parameter set)
ATTRACTORS = [
    ("de Jong", step_de_jong, (-2.24, 0.43, -0.65, -2.43)),
    ("de Jong", step_de_jong, (2.01, -2.53, 1.61, -0.33)),
    ("de Jong", step_de_jong, (-2.70, -0.09, -0.86, -2.20)),
    ("Clifford", step_clifford, (-1.40, 1.60, 1.00, 0.70)),
    ("Clifford", step_clifford, (1.70, 1.70, 0.60, 1.20)),
    ("Clifford", step_clifford, (-1.70, 1.30, -0.10, -1.21)),
    ("Hopalong", step_hopalong, (2.00, 1.00, 0.00)),
    ("Hopalong", step_hopalong, (-1.10, 0.50, 1.00)),
]


def drifted_params(base, drift, t):
    base = np.asarray(base, dtype=float)
    return base + drift * np.sin(t * DRIFT_OMEGAS[:len(base)])


def new_points(batch, rng):
    return (rng.uniform(-0.5, 0.5, batch), rng.uniform(-0.5, 0.5, batch))


def iterate_batch(step_fn, x, y, params, iters):
    """Advance every point `iters` steps. Returns new (x, y)."""
    for _ in range(iters):
        x, y = step_fn(x, y, params)
    return x, y


def splat(grid, x, y, view):
    """Deposit points into the density grid using the current view bounds.

    view = (xmin, xmax, ymin, ymax). Terminal cells are ~2:1 tall, so x is
    scaled by 2 relative to y while preserving the attractor's aspect ratio.
    """
    h, w = grid.shape
    xmin, xmax, ymin, ymax = view
    spanx = max(xmax - xmin, 1e-9)
    spany = max(ymax - ymin, 1e-9)
    scale = min((w - 1) / (2.0 * spanx), (h - 1) / spany)
    cx, cy = (xmin + xmax) / 2.0, (ymin + ymax) / 2.0
    cols = ((x - cx) * scale * 2.0 + w / 2.0).astype(np.int64)
    rows = ((y - cy) * scale + h / 2.0).astype(np.int64)
    mask = (cols >= 0) & (cols < w) & (rows >= 0) & (rows < h)
    np.add.at(grid, (rows[mask], cols[mask]), 1.0)


def level_grid(grid):
    """Map density to ramp level indices (-1 = empty) with log brightness."""
    dmax = grid.max()
    if dmax <= 0:
        return np.full(grid.shape, -1, dtype=np.int64)
    norm = np.log1p(grid) / np.log1p(dmax)
    idx = np.minimum((norm * len(RAMP)).astype(np.int64), len(RAMP) - 1)
    idx[grid <= 0] = -1
    return idx


def run(stdscr, duration, frame_delay, batch, iters_per_frame, drift,
        switch_time):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    rng = np.random.default_rng()
    attr_i = 0
    name, step_fn, base = ATTRACTORS[attr_i]
    x, y = new_points(batch, rng)
    grid = None
    view = None
    attr_start = time.monotonic()
    start = attr_start

    while True:
        now = time.monotonic()
        if now - start >= duration:
            break

        if now - attr_start >= switch_time:
            attr_i = (attr_i + 1) % len(ATTRACTORS)
            name, step_fn, base = ATTRACTORS[attr_i]
            x, y = new_points(batch, rng)
            grid = None
            view = None
            attr_start = now
            stdscr.clear()

        max_y, max_x = stdscr.getmaxyx()
        h, w = max(1, max_y - 1), max(1, max_x)
        if grid is None or grid.shape != (h, w):
            grid = np.zeros((h, w), dtype=float)

        params = drifted_params(base, drift, now - attr_start)
        x, y = iterate_batch(step_fn, x, y, params, iters_per_frame)

        if not (np.all(np.isfinite(x)) and np.all(np.isfinite(y))):
            # Blow-up: reset to the base parameter set and fresh points.
            attr_start = now
            x, y = new_points(batch, rng)
            x, y = iterate_batch(step_fn, x, y, np.asarray(base, float), 10)
            view = None
            grid.fill(0.0)

        # Smoothly auto-fit the view to the running extent of the points.
        target = np.array([x.min(), x.max(), y.min(), y.max()])
        if view is None:
            view = target
        else:
            view = 0.92 * view + 0.08 * target

        grid *= 0.985
        splat(grid, x, y, view)

        stdscr.erase()
        levels = level_grid(grid)
        rows, cols = np.nonzero(levels >= 0)
        for r, c, lv in zip(rows.tolist(), cols.tolist(),
                            levels[rows, cols].tolist()):
            ch, pair, bold = RAMP[lv]
            attr = curses.color_pair(pair)
            if bold:
                attr |= curses.A_BOLD
            try:
                stdscr.addstr(r, c, ch, attr)
            except curses.error:
                pass

        pstr = ", ".join(f"{v:.2f}" for v in params)
        info = (f"Strange Attractors  [{name}]  params=({pstr})  "
                f"batch={batch} drift={drift}")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def main(duration=30, frame_delay=0.04, batch=2000, iters_per_frame=3,
         drift=0.15, switch_time=10.0):
    duration = float(duration)
    frame_delay = float(frame_delay)
    batch = max(10, int(batch))
    iters_per_frame = max(1, int(iters_per_frame))
    drift = float(drift)
    switch_time = max(1.0, float(switch_time))
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, batch, iters_per_frame, drift,
        switch_time))


if __name__ == "__main__":
    main()
