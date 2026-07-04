import curses
import math
import time

import numpy as np


COLOR_RED = 1
COLOR_YELLOW = 2
COLOR_GREEN = 3
COLOR_CYAN = 4
COLOR_BLUE = 5
COLOR_MAGENTA = 6
COLOR_LABEL = 7

# Brightness ramp from faint to dense.
RAMP = [".", ":", "+", "*", "#", "@"]

# Per-attractor color schemes: one (color_pair_index, extra_attr) per ramp level.
SCHEME_CYAN = [
    (COLOR_BLUE, 0), (COLOR_BLUE, 0), (COLOR_BLUE, curses.A_BOLD),
    (COLOR_CYAN, 0), (COLOR_CYAN, curses.A_BOLD), (COLOR_CYAN, curses.A_BOLD),
]
SCHEME_MAGENTA = [
    (COLOR_BLUE, 0), (COLOR_MAGENTA, 0), (COLOR_MAGENTA, 0),
    (COLOR_MAGENTA, curses.A_BOLD), (COLOR_MAGENTA, curses.A_BOLD),
    (COLOR_MAGENTA, curses.A_BOLD),
]
SCHEME_GREEN = [
    (COLOR_GREEN, 0), (COLOR_GREEN, 0), (COLOR_GREEN, 0),
    (COLOR_GREEN, curses.A_BOLD), (COLOR_GREEN, curses.A_BOLD),
    (COLOR_YELLOW, curses.A_BOLD),
]
SCHEME_FIRE = [
    (COLOR_RED, 0), (COLOR_RED, 0), (COLOR_RED, curses.A_BOLD),
    (COLOR_YELLOW, 0), (COLOR_YELLOW, curses.A_BOLD),
    (COLOR_YELLOW, curses.A_BOLD),
]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_RED, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_YELLOW, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_GREEN, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_CYAN, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_BLUE, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_MAGENTA, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def ifs_from_maps(maps):
    """Build (A, T, cum_probs) arrays from a list of (a, b, c, d, e, f, p).

    Each map sends (x, y) -> (a*x + b*y + e, c*x + d*y + f) with probability p.
    """
    arr = np.array(maps, dtype=np.float64)
    A = arr[:, [0, 1, 2, 3]].reshape(-1, 2, 2)
    T = arr[:, [4, 5]]
    p = arr[:, 6]
    cum = np.cumsum(p / p.sum())
    return A, T, cum


def ifs_from_vertices(vertices, r):
    """Chaos-game IFS: jump fraction r toward each vertex, equal probability."""
    maps = []
    for vx, vy in vertices:
        maps.append((r, 0.0, 0.0, r, (1.0 - r) * vx, (1.0 - r) * vy, 1.0))
    return ifs_from_maps(maps)


def polygon_vertices(n, radius=1.0):
    verts = []
    for k in range(n):
        ang = math.pi / 2 + 2.0 * math.pi * k / n
        verts.append((radius * math.cos(ang), radius * math.sin(ang)))
    return verts


def build_attractors():
    attractors = []

    # 1) Sierpinski triangle: 3 vertices, jump 1/2.
    tri = [(0.0, 0.0), (1.0, 0.0), (0.5, math.sqrt(3.0) / 2.0)]
    A, T, cum = ifs_from_vertices(tri, 0.5)
    attractors.append({"name": "Sierpinski Triangle", "A": A, "T": T,
                       "cum": cum, "scheme": SCHEME_CYAN})

    # 2) Pentagon flake: 5 vertices, contraction r ~ 0.38.
    A, T, cum = ifs_from_vertices(polygon_vertices(5), 0.38)
    attractors.append({"name": "Pentagon Flake", "A": A, "T": T,
                       "cum": cum, "scheme": SCHEME_MAGENTA})

    # 3) Barnsley fern: the classic 4-map IFS with its probabilities.
    fern = [
        (0.00, 0.00, 0.00, 0.16, 0.0, 0.00, 0.01),
        (0.85, 0.04, -0.04, 0.85, 0.0, 1.60, 0.85),
        (0.20, -0.26, 0.23, 0.22, 0.0, 1.60, 0.07),
        (-0.15, 0.28, 0.26, 0.24, 0.0, 0.44, 0.07),
    ]
    A, T, cum = ifs_from_maps(fern)
    attractors.append({"name": "Barnsley Fern", "A": A, "T": T,
                       "cum": cum, "scheme": SCHEME_GREEN})

    # 4) Heighway dragon: two similarity maps at 45 degrees, scale 1/sqrt(2).
    dragon = [
        (0.5, -0.5, 0.5, 0.5, 0.0, 0.0, 0.5),
        (-0.5, -0.5, 0.5, -0.5, 1.0, 0.0, 0.5),
    ]
    A, T, cum = ifs_from_maps(dragon)
    attractors.append({"name": "Heighway Dragon", "A": A, "T": T,
                       "cum": cum, "scheme": SCHEME_FIRE})

    return attractors


def iterate_batch(pts, A, T, cum, rng):
    """Advance every point in the batch through one randomly chosen map."""
    idx = np.searchsorted(cum, rng.random(pts.shape[0]))
    return np.einsum("kij,kj->ki", A[idx], pts) + T[idx]


def estimate_bbox(attractor, rng, n_points=2000, iters=60, pad=0.02):
    """Estimate the attractor's bounding box by running the IFS briefly."""
    pts = rng.random((n_points, 2))
    for _ in range(10):  # settle onto the attractor before measuring
        pts = iterate_batch(pts, attractor["A"], attractor["T"],
                            attractor["cum"], rng)
    lo = np.full(2, np.inf)
    hi = np.full(2, -np.inf)
    for _ in range(iters):
        pts = iterate_batch(pts, attractor["A"], attractor["T"],
                            attractor["cum"], rng)
        lo = np.minimum(lo, pts.min(axis=0))
        hi = np.maximum(hi, pts.max(axis=0))
    span = np.maximum(hi - lo, 1e-9)
    return lo - pad * span, hi + pad * span


def deposit(density, pts, lo, hi):
    """Accumulate points into the density grid, x scaled 2:1 vs y."""
    rows, cols = density.shape
    span = np.maximum(hi - lo, 1e-9)
    # Terminal cells are ~2:1 tall, so x gets twice the cells-per-unit of y.
    scale = min(rows / span[1], cols / (2.0 * span[0]))
    sx, sy = 2.0 * scale, scale
    ox = (cols - span[0] * sx) / 2.0
    oy = (rows - span[1] * sy) / 2.0
    cx = ((pts[:, 0] - lo[0]) * sx + ox).astype(np.intp)
    cy = (rows - 1 - ((pts[:, 1] - lo[1]) * sy + oy)).astype(np.intp)
    mask = (cx >= 0) & (cx < cols) & (cy >= 0) & (cy < rows)
    np.add.at(density, (cy[mask], cx[mask]), 1)


def draw_density(stdscr, density, scheme):
    """Render the density grid through the brightness ramp."""
    dmax = density.max()
    if dmax <= 0:
        return
    levels = (np.log1p(density) / math.log1p(dmax) * len(RAMP)).astype(np.intp)
    np.clip(levels, 0, len(RAMP) - 1, out=levels)
    ys, xs = np.nonzero(density)
    for y, x, lv in zip(ys, xs, levels[ys, xs]):
        pair, extra = scheme[lv]
        try:
            stdscr.addstr(int(y), int(x), RAMP[lv],
                          curses.color_pair(pair) | extra)
        except curses.error:
            pass


def run(stdscr, duration, frame_delay, points_per_frame, switch_time):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    rng = np.random.default_rng()
    attractors = build_attractors()
    att_i = 0
    att = attractors[att_i]
    lo, hi = estimate_bbox(att, rng)
    # Start from scratch: raw random points that visibly condense into shape.
    pts = lo + rng.random((points_per_frame, 2)) * (hi - lo)
    density = None
    total_points = 0
    att_start = time.monotonic()

    start = time.monotonic()
    while True:
        now = time.monotonic()
        if now - start >= duration:
            break

        if now - att_start >= switch_time:
            att_i = (att_i + 1) % len(attractors)
            att = attractors[att_i]
            lo, hi = estimate_bbox(att, rng)
            pts = lo + rng.random((points_per_frame, 2)) * (hi - lo)
            density = None  # clear: each attractor emerges from scratch
            total_points = 0
            att_start = now

        max_y, max_x = stdscr.getmaxyx()
        rows, cols = max(1, max_y - 1), max(1, max_x)
        if density is None or density.shape != (rows, cols):
            density = np.zeros((rows, cols), dtype=np.int64)

        pts = iterate_batch(pts, att["A"], att["T"], att["cum"], rng)
        deposit(density, pts, lo, hi)
        total_points += pts.shape[0]

        stdscr.erase()
        draw_density(stdscr, density, att["scheme"])

        info = (f"Chaos Game  {att['name']}  points={total_points}  "
                f"ppf={points_per_frame}  switch={switch_time:g}s")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def main(duration=30, frame_delay=0.03, points_per_frame=2000, switch_time=8):
    duration = float(duration)
    frame_delay = float(frame_delay)
    points_per_frame = max(1, int(points_per_frame))
    switch_time = float(switch_time)
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, points_per_frame, switch_time))


if __name__ == "__main__":
    main()
