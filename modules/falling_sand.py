import curses
import random
import time

import numpy as np


# Cell materials
EMPTY = 0
STONE = 1
SAND = 2
WATER = 3
FIRE = 4

# Color pair ids
COLOR_SAND = 1
COLOR_WATER = 2
COLOR_WATER_DEEP = 3
COLOR_STONE = 4
COLOR_FIRE = 5
COLOR_EMBER = 6
COLOR_LABEL = 7

EMITTER_CYCLE = [SAND, WATER, SAND, FIRE]
MATERIAL_NAMES = {SAND: "sand", WATER: "water", FIRE: "fire", STONE: "stone"}


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_SAND, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_WATER, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_WATER_DEEP, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_STONE, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_FIRE, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_EMBER, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def build_styles():
    """(char, attr) pairs per material, two texture variants each."""
    return {
        SAND: [(".", curses.color_pair(COLOR_SAND)),
               ("o", curses.color_pair(COLOR_SAND) | curses.A_BOLD)],
        WATER: [("~", curses.color_pair(COLOR_WATER)),
                ("~", curses.color_pair(COLOR_WATER_DEEP) | curses.A_BOLD)],
        STONE: [("#", curses.color_pair(COLOR_STONE) | curses.A_DIM),
                ("#", curses.color_pair(COLOR_STONE))],
        FIRE: [("*", curses.color_pair(COLOR_FIRE) | curses.A_BOLD),
               ("*", curses.color_pair(COLOR_EMBER) | curses.A_BOLD)],
    }


def make_grid(h, w, rng):
    """Empty grid with a few random static stone ledges."""
    grid = np.zeros((h, w), dtype=np.int8)
    if h < 6 or w < 8:
        return grid
    n_ledges = max(3, w // 22)
    for _ in range(n_ledges):
        y = int(rng.integers(h // 4, max(h // 4 + 1, (3 * h) // 4)))
        length = int(rng.integers(max(4, w // 10), max(6, w // 4)))
        x0 = int(rng.integers(0, max(1, w - length)))
        grid[y, x0:x0 + length] = STONE
    return grid


def fall_straight(grid, mat):
    """Move every `mat` cell with an empty cell below it down one row."""
    ys, xs = np.nonzero((grid[:-1] == mat) & (grid[1:] == EMPTY))
    if len(ys):
        grid[ys, xs] = EMPTY
        grid[ys + 1, xs] = mat


def sink_sand_in_water(grid, rng):
    """Sand swaps with water directly below it (probabilistic, so it sinks slowly)."""
    ys, xs = np.nonzero((grid[:-1] == SAND) & (grid[1:] == WATER))
    if len(ys):
        keep = rng.random(len(ys)) < 0.4
        ys, xs = ys[keep], xs[keep]
        grid[ys, xs] = WATER
        grid[ys + 1, xs] = SAND


def slide_sand(grid, rng, max_cells=1500):
    """Blocked sand slides diagonally down; loop only over candidate edge cells."""
    h, w = grid.shape
    if h < 2 or w < 2:
        return
    below = grid[1:]
    blocked = (below != EMPTY) & (below != WATER)
    dl_empty = np.zeros((h - 1, w), dtype=bool)
    dl_empty[:, 1:] = below[:, :-1] == EMPTY
    dr_empty = np.zeros((h - 1, w), dtype=bool)
    dr_empty[:, :-1] = below[:, 1:] == EMPTY
    cand = np.argwhere((grid[:-1] == SAND) & blocked & (dl_empty | dr_empty))
    if len(cand) == 0:
        return
    if len(cand) > max_cells:
        cand = cand[rng.choice(len(cand), size=max_cells, replace=False)]
    for y, x in cand:
        if grid[y, x] != SAND:
            continue
        dirs = [-1, 1] if rng.random() < 0.5 else [1, -1]
        for d in dirs:
            nx = x + d
            if 0 <= nx < w and grid[y + 1, nx] == EMPTY:
                grid[y, x] = EMPTY
                grid[y + 1, nx] = SAND
                break


def spread_water(grid, rng, max_cells=1500):
    """Water blocked below flows sideways; loop only over pool-edge candidates."""
    h, w = grid.shape
    if h < 1 or w < 2:
        return
    below_full = np.ones((h, w), dtype=bool)
    if h > 1:
        below_full[:-1] = grid[1:] != EMPTY
    l_empty = np.zeros((h, w), dtype=bool)
    l_empty[:, 1:] = grid[:, :-1] == EMPTY
    r_empty = np.zeros((h, w), dtype=bool)
    r_empty[:, :-1] = grid[:, 1:] == EMPTY
    cand = np.argwhere((grid == WATER) & below_full & (l_empty | r_empty))
    if len(cand) == 0:
        return
    if len(cand) > max_cells:
        cand = cand[rng.choice(len(cand), size=max_cells, replace=False)]
    for y, x in cand:
        if grid[y, x] != WATER or rng.random() < 0.15:
            continue
        dirs = [-1, 1] if rng.random() < 0.5 else [1, -1]
        for d in dirs:
            nx = x + d
            if 0 <= nx < w and grid[y, nx] == EMPTY:
                grid[y, x] = EMPTY
                grid[y, nx] = WATER
                break


def step_fire(grid, rng):
    """Fire flickers upward through empty cells and dies out quickly."""
    ys, xs = np.nonzero(grid == FIRE)
    if len(ys):
        die = rng.random(len(ys)) < 0.18
        grid[ys[die], xs[die]] = EMPTY
    if grid.shape[0] < 2:
        return
    ys, xs = np.nonzero((grid[1:] == FIRE) & (grid[:-1] == EMPTY))
    if len(ys):
        rise = rng.random(len(ys)) < 0.7
        ys, xs = ys[rise], xs[rise]
        grid[ys + 1, xs] = EMPTY
        grid[ys, xs] = FIRE


def step_grid(grid, rng):
    """One simulation tick over the whole grid."""
    fall_straight(grid, SAND)
    fall_straight(grid, WATER)
    sink_sand_in_water(grid, rng)
    slide_sand(grid, rng)
    spread_water(grid, rng)
    step_fire(grid, rng)


def dissolve_step(grid, rng, frac=0.06):
    """Randomly delete a fraction of movable cells; True when nearly clear."""
    movable = (grid != EMPTY) & (grid != STONE)
    n = int(np.count_nonzero(movable))
    if n == 0:
        return True
    kill = movable & (rng.random(grid.shape) < frac)
    grid[kill] = EMPTY
    return n <= max(4, grid.size // 200)


def movable_fill(grid):
    return np.count_nonzero((grid != EMPTY) & (grid != STONE)) / max(1, grid.size)


def make_emitters(w, rng):
    ems = []
    for k in range(2):
        ems.append({
            "x": w * (0.3 + 0.4 * k) + rng.uniform(-3, 3),
            "vx": rng.choice([-1.0, 1.0]) * rng.uniform(4.0, 9.0),
            "mat_i": k % len(EMITTER_CYCLE),
            "next_cycle": time.monotonic() + rng.uniform(3.0, 5.0),
        })
    return ems


def step_emitters(emitters, grid, rng, spawn_rate, dt, now):
    h, w = grid.shape
    for em in emitters:
        em["x"] += em["vx"] * dt
        if em["x"] < 1:
            em["x"], em["vx"] = 1.0, abs(em["vx"])
        elif em["x"] > w - 2:
            em["x"], em["vx"] = float(w - 2), -abs(em["vx"])
        if now >= em["next_cycle"]:
            em["mat_i"] = (em["mat_i"] + 1) % len(EMITTER_CYCLE)
            em["next_cycle"] = now + rng.uniform(3.0, 5.0)
        mat = EMITTER_CYCLE[em["mat_i"]]
        n = spawn_rate if mat != FIRE else max(1, spawn_rate // 2)
        if h < 2:
            continue
        xs = np.clip(int(em["x"]) + rng.integers(-2, 3, size=n), 0, w - 1)
        for x in xs:
            if grid[1, x] == EMPTY:
                grid[1, x] = mat


def draw_grid(stdscr, grid, tex, styles):
    """Render with one addstr per run of identical (material, texture) cells."""
    h, w = grid.shape
    style = grid.astype(np.int16) * 2 + tex
    style[grid == EMPTY] = 0
    for y in range(h):
        row = style[y]
        if not row.any():
            continue
        bounds = np.nonzero(np.diff(row))[0] + 1
        starts = np.concatenate(([0], bounds))
        ends = np.concatenate((bounds, [w]))
        for s, e in zip(starts, ends):
            sid = int(row[s])
            if sid == 0:
                continue
            ch, attr = styles[sid // 2][sid % 2]
            try:
                stdscr.addstr(y, int(s), ch * int(e - s), attr)
            except curses.error:
                pass


def run(stdscr, duration, frame_delay, spawn_rate, fill_limit):
    init_colors()
    styles = build_styles()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    rng = np.random.default_rng()
    max_y, max_x = stdscr.getmaxyx()
    gh, gw = max(1, max_y - 1), max(1, max_x)
    grid = make_grid(gh, gw, rng)
    tex = rng.integers(0, 2, size=grid.shape).astype(np.int16)
    emitters = make_emitters(gw, rng)
    dissolving = False

    start = time.monotonic()
    last_frame = start
    while True:
        now = time.monotonic()
        if now - start >= duration:
            break
        dt = min(now - last_frame, 0.1)
        last_frame = now

        max_y, max_x = stdscr.getmaxyx()
        gh, gw = max(1, max_y - 1), max(1, max_x)
        if grid.shape != (gh, gw):
            grid = make_grid(gh, gw, rng)
            tex = rng.integers(0, 2, size=grid.shape).astype(np.int16)
            emitters = make_emitters(gw, rng)
            dissolving = False

        if dissolving:
            if dissolve_step(grid, rng):
                grid = make_grid(gh, gw, rng)
                dissolving = False
        else:
            step_emitters(emitters, grid, rng, spawn_rate, dt, now)
            if movable_fill(grid) >= fill_limit:
                dissolving = True
        step_grid(grid, rng)

        stdscr.erase()
        draw_grid(stdscr, grid, tex, styles)

        if not dissolving:
            for em in emitters:
                mat = EMITTER_CYCLE[em["mat_i"]]
                _, attr = styles[mat][1]
                try:
                    stdscr.addstr(0, int(em["x"]), "V", attr)
                except curses.error:
                    pass

        fill_pct = movable_fill(grid) * 100
        state = "dissolving" if dissolving else "+".join(
            MATERIAL_NAMES[EMITTER_CYCLE[e["mat_i"]]] for e in emitters)
        info = (f"Falling Sand  spawn={spawn_rate}/frame  "
                f"fill={fill_pct:.0f}%/{fill_limit * 100:.0f}%  [{state}]")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def main(duration=28, frame_delay=0.04, spawn_rate=3, fill_limit=0.7):
    duration = float(duration)
    frame_delay = float(frame_delay)
    spawn_rate = max(1, int(spawn_rate))
    fill_limit = min(0.95, max(0.05, float(fill_limit)))
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, spawn_rate, fill_limit))


if __name__ == "__main__":
    main()
