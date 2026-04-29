import curses
import math
import random
import time

import numpy as np


SHADE = " .:-=+*#%@"

PRESETS = {
    "spots":    {"F": 0.0367, "k": 0.0649, "Du": 0.16, "Dv": 0.08},
    "stripes":  {"F": 0.0220, "k": 0.0510, "Du": 0.16, "Dv": 0.08},
    "mazes":    {"F": 0.0290, "k": 0.0570, "Du": 0.16, "Dv": 0.08},
    "fingers":  {"F": 0.0540, "k": 0.0620, "Du": 0.16, "Dv": 0.08},
    "worms":    {"F": 0.0780, "k": 0.0610, "Du": 0.16, "Dv": 0.08},
    "ripples":  {"F": 0.0140, "k": 0.0450, "Du": 0.16, "Dv": 0.08},
}

PALETTE = [
    curses.COLOR_BLUE, curses.COLOR_CYAN, curses.COLOR_GREEN,
    curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_MAGENTA,
]
COLOR_LABEL = 7


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    for i, c in enumerate(PALETTE):
        curses.init_pair(i + 1, c, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def init_field(rows, cols):
    """U=1 everywhere, V=0 except a few small randomized seed patches."""
    U = np.ones((rows, cols), dtype=np.float64)
    V = np.zeros((rows, cols), dtype=np.float64)
    for _ in range(5):
        cy = random.randint(rows // 4, 3 * rows // 4)
        cx = random.randint(cols // 4, 3 * cols // 4)
        size = random.randint(3, 6)
        r0 = max(0, cy - size)
        r1 = min(rows, cy + size + 1)
        c0 = max(0, cx - size)
        c1 = min(cols, cx + size + 1)
        U[r0:r1, c0:c1] = 0.5
        V[r0:r1, c0:c1] = 0.25 + np.random.uniform(-0.05, 0.05,
                                                    (r1 - r0, c1 - c0))
    return U, V


def step(U, V, Du, Dv, F, k, dt):
    """Forward-Euler step with periodic-BC 5-point Laplacian, vectorized."""
    lap_U = (np.roll(U, 1, axis=0) + np.roll(U, -1, axis=0)
             + np.roll(U, 1, axis=1) + np.roll(U, -1, axis=1) - 4.0 * U)
    lap_V = (np.roll(V, 1, axis=0) + np.roll(V, -1, axis=0)
             + np.roll(V, 1, axis=1) + np.roll(V, -1, axis=1) - 4.0 * V)
    uvv = U * V * V
    new_U = U + dt * (Du * lap_U - uvv + F * (1.0 - U))
    new_V = V + dt * (Dv * lap_V + uvv - (F + k) * V)
    return new_U, new_V


def run(stdscr, duration, frame_delay, preset, sub_steps, dt, color_choice):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.clear()
    stdscr.refresh()
    stdscr.timeout(int(frame_delay * 1000))

    if preset == "random" or preset not in PRESETS:
        preset = random.choice(list(PRESETS.keys()))
    p = PRESETS[preset]
    Du, Dv, F, k = p["Du"], p["Dv"], p["F"], p["k"]

    if color_choice == "random":
        color_pair_idx = random.randint(1, len(PALETTE))
    else:
        color_pair_idx = max(1, min(len(PALETTE), int(color_choice)))

    max_y, max_x = stdscr.getmaxyx()
    rows = max(8, max_y - 2)
    cols = max(8, max_x)
    U, V = init_field(rows, cols)

    start = time.monotonic()
    while True:
        now = time.monotonic()
        elapsed = now - start
        if elapsed >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        if rows != max_y - 2 or cols != max_x:
            new_rows = max(8, max_y - 2)
            new_cols = max(8, max_x)
            U, V = init_field(new_rows, new_cols)
            rows, cols = new_rows, new_cols

        for _ in range(sub_steps):
            U, V = step(U, V, Du, Dv, F, k, dt)

        stdscr.erase()
        # Vectorized character index lookup. V typically lives in [0, 0.5];
        # clamp + scale to the gradient.
        n_chars = len(SHADE)
        idx = np.clip((V * 2.0 * n_chars).astype(np.int64), 0, n_chars - 1)
        # Render one row at a time as a single addstr — far fewer
        # curses calls than touching every cell individually.
        base_attr = curses.color_pair(color_pair_idx) | curses.A_BOLD
        char_lut = np.array(list(SHADE), dtype="<U1")
        for y in range(rows):
            row_chars = "".join(char_lut[idx[y]])
            try:
                stdscr.addstr(y, 0, row_chars[:max(0, cols)], base_attr)
            except curses.error:
                pass

        info = f" Gray-Scott reaction-diffusion   preset={preset}   F={F}   k={k}   Du={Du} Dv={Dv} "
        info = info.ljust(max(0, max_x - 1))[:max(0, max_x - 1)]
        try:
            stdscr.addstr(max_y - 1, 0, info,
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD | curses.A_REVERSE)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=30, frame_delay=0.04, preset="random", sub_steps=8,
         dt=1.0, color_choice="random"):
    duration = float(duration)
    frame_delay = float(frame_delay)
    sub_steps = max(1, int(sub_steps))
    dt = float(dt)
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, preset, sub_steps, dt, color_choice))


if __name__ == "__main__":
    main()
