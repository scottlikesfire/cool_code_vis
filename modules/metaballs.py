import curses
import math
import random
import time

import numpy as np


# Hue cycle for the blob interior: blue -> cyan -> green -> yellow -> magenta
HUE_CYCLE = [
    curses.COLOR_BLUE, curses.COLOR_CYAN, curses.COLOR_GREEN,
    curses.COLOR_YELLOW, curses.COLOR_MAGENTA,
]
PAIR_HUE_BASE = 1                      # pairs 1..len(HUE_CYCLE) for interiors
PAIR_EDGE = PAIR_HUE_BASE + len(HUE_CYCLE)   # bright white contour band
PAIR_GLOW = PAIR_EDGE + 1                    # faint outer glow
PAIR_LABEL = PAIR_GLOW + 1                   # info label

HUE_PERIOD = 6.0        # seconds spent on each hue before shifting
EPS = 1e-6

# Character ramp
CH_DEEP = "@"
CH_CORE = "#"
CH_MID = "%"
CH_SOFT = "o"
CH_EDGE = "*"
CH_GLOW = "·"  # '·'


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    for i, c in enumerate(HUE_CYCLE):
        curses.init_pair(PAIR_HUE_BASE + i, c, -1)
    curses.init_pair(PAIR_EDGE, curses.COLOR_WHITE, -1)
    curses.init_pair(PAIR_GLOW, curses.COLOR_BLUE, -1)
    curses.init_pair(PAIR_LABEL, curses.COLOR_CYAN, -1)


def make_blob(rng):
    """A blob drifts on a sum of two sines per axis: organic, physics-free."""
    return {
        # normalized center offsets (fractions of screen size)
        "cx": rng.uniform(0.25, 0.75),
        "cy": rng.uniform(0.25, 0.75),
        # amplitudes of the two sine components per axis
        "ax1": rng.uniform(0.10, 0.30), "ax2": rng.uniform(0.05, 0.15),
        "ay1": rng.uniform(0.10, 0.30), "ay2": rng.uniform(0.05, 0.15),
        # frequencies (rad/s) and phases
        "fx1": rng.uniform(0.15, 0.45), "fx2": rng.uniform(0.5, 1.1),
        "fy1": rng.uniform(0.15, 0.45), "fy2": rng.uniform(0.5, 1.1),
        "px1": rng.uniform(0, 6.283), "px2": rng.uniform(0, 6.283),
        "py1": rng.uniform(0, 6.283), "py2": rng.uniform(0, 6.283),
        # radius as a fraction of the smaller screen dimension
        "r_frac": rng.uniform(0.14, 0.26),
        # life-cycle: scale ramps 0 -> 1 on spawn, 1 -> 0 when dying
        "scale": 1.0,
        "dying": False,
    }


def blob_position(b, t, w, h):
    """Smooth path: sum of two sines per axis, in screen coordinates."""
    x = (b["cx"] + b["ax1"] * math.sin(b["fx1"] * t + b["px1"])
         + b["ax2"] * math.sin(b["fx2"] * t + b["px2"])) * w
    y = (b["cy"] + b["ay1"] * math.sin(b["fy1"] * t + b["py1"])
         + b["ay2"] * math.sin(b["fy2"] * t + b["py2"])) * h
    return x, y


def compute_field(blobs, t, w, h):
    """Vectorized metaball field over the full grid.

    F = sum_i r_i^2 / ((x - x_i)^2 + (2 (y - y_i))^2 + eps)
    The y-axis is scaled by 2 so blobs render round in ~2:1 terminal cells.
    """
    ys = np.arange(h, dtype=np.float32)
    xs = np.arange(w, dtype=np.float32)
    gy, gx = np.meshgrid(ys, xs, indexing="ij")

    field = np.zeros((h, w), dtype=np.float32)
    min_dim = min(w, 2 * h)
    for b in blobs:
        r = b["r_frac"] * min_dim * b["scale"]
        if r <= 0.0:
            continue
        bx, by = blob_position(b, t, w, h)
        dx = gx - bx
        dy = 2.0 * (gy - by)
        field += (r * r) / (dx * dx + dy * dy + EPS)
    return field


def update_lifecycle(blobs, dt, rng):
    """Grow spawning blobs, shrink dying ones; respawn the fully-shrunk.
    Occasionally pick a healthy blob to shrink away."""
    for i, b in enumerate(blobs):
        if b["dying"]:
            b["scale"] -= dt / 3.0
            if b["scale"] <= 0.0:
                nb = make_blob(rng)
                nb["scale"] = 0.0
                blobs[i] = nb
        elif b["scale"] < 1.0:
            b["scale"] = min(1.0, b["scale"] + dt / 3.0)
    # ~ one death every ~12 seconds on average
    if rng.random() < dt / 12.0:
        alive = [b for b in blobs if not b["dying"] and b["scale"] >= 1.0]
        if len(alive) > 1:
            rng.choice(alive)["dying"] = True


def run(stdscr, duration, frame_delay, num_blobs, threshold):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    rng = random.Random()
    blobs = [make_blob(rng) for _ in range(num_blobs)]

    thr = threshold
    band = 0.12 * thr          # half-width of the contour band around F = thr

    start = time.monotonic()
    last_frame = start
    while True:
        now = time.monotonic()
        if now - start >= duration:
            break
        dt = min(now - last_frame, 0.1)
        last_frame = now
        t = now - start

        max_y, max_x = stdscr.getmaxyx()
        h = max(1, max_y - 1)   # bottom line reserved for the label
        w = max(1, max_x)

        update_lifecycle(blobs, dt, rng)
        field = compute_field(blobs, t, w, h)

        # Hue-shift the interior palette over time.
        hue_i = int(t / HUE_PERIOD) % len(HUE_CYCLE)
        hot = curses.color_pair(PAIR_HUE_BASE + hue_i) | curses.A_BOLD
        med = curses.color_pair(PAIR_HUE_BASE + hue_i)
        edge = curses.color_pair(PAIR_EDGE) | curses.A_BOLD
        glow = curses.color_pair(PAIR_GLOW) | curses.A_DIM

        # Classify zones (vectorized). Priority: contour band wins its zone.
        on_edge = np.abs(field - thr) < band
        deep = (field >= 2.5 * thr) & ~on_edge          # F >> threshold
        core = (field >= 1.6 * thr) & ~deep & ~on_edge
        mid = (field >= 1.25 * thr) & ~core & ~deep & ~on_edge
        soft = (field > thr) & ~mid & ~core & ~deep & ~on_edge
        halo = (field >= 0.5 * thr) & (field <= thr) & ~on_edge

        stdscr.erase()
        zones = (
            (deep, CH_DEEP, hot),
            (core, CH_CORE, hot),
            (mid, CH_MID, med),
            (soft, CH_SOFT, med),
            (on_edge, CH_EDGE, edge),
            (halo, CH_GLOW, glow),
        )
        for mask, ch, attr in zones:
            rows, cols = np.nonzero(mask)
            for yi, xi in zip(rows.tolist(), cols.tolist()):
                try:
                    stdscr.addstr(yi, xi, ch, attr)
                except curses.error:
                    pass

        info = f"Metaballs  blobs={num_blobs}  threshold={threshold}"
        try:
            stdscr.addstr(max_y - 1, 2, info[:max(0, max_x - 4)],
                          curses.color_pair(PAIR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def main(duration=25, frame_delay=0.04, num_blobs=5, threshold=1.0):
    duration = float(duration)
    frame_delay = float(frame_delay)
    num_blobs = max(1, int(num_blobs))
    threshold = float(threshold)
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, num_blobs, threshold))


if __name__ == "__main__":
    main()
