import curses
import math
import random
import time


COLOR_LABEL = 1
PALETTE = [
    curses.COLOR_BLUE, curses.COLOR_CYAN, curses.COLOR_GREEN,
    curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_MAGENTA,
    curses.COLOR_WHITE,
]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)
    for i, c in enumerate(PALETTE):
        curses.init_pair(i + 2, c, -1)


def has_neighbor(grid, r, c, rows, cols):
    """Inlined 8-neighbor check — avoids Python loop overhead. Returns True
    if any of the 8 surrounding cells is part of the cluster."""
    if r > 0:
        row_up = grid[r - 1]
        if row_up[c] > 0:
            return True
        if c > 0 and row_up[c - 1] > 0:
            return True
        if c < cols - 1 and row_up[c + 1] > 0:
            return True
    if r < rows - 1:
        row_dn = grid[r + 1]
        if row_dn[c] > 0:
            return True
        if c > 0 and row_dn[c - 1] > 0:
            return True
        if c < cols - 1 and row_dn[c + 1] > 0:
            return True
    row = grid[r]
    if c > 0 and row[c - 1] > 0:
        return True
    if c < cols - 1 and row[c + 1] > 0:
        return True
    return False


def spawn_near_cluster(min_r, max_r, min_c, max_c, spawn_buffer, rows, cols):
    """Spawn walker on a random side of the bounding box, expanded by
    spawn_buffer. Walkers therefore start a known short distance from the
    cluster and reach it in O(buffer²) steps instead of O(screen²)."""
    sb = spawn_buffer
    smin_r = max(0, min_r - sb)
    smax_r = min(rows - 1, max_r + sb)
    smin_c = max(0, min_c - sb)
    smax_c = min(cols - 1, max_c + sb)
    side = random.randint(0, 3)
    if side == 0:
        return smin_r, random.randint(smin_c, smax_c)
    if side == 1:
        return smax_r, random.randint(smin_c, smax_c)
    if side == 2:
        return random.randint(smin_r, smax_r), smin_c
    return random.randint(smin_r, smax_r), smax_c


def attr_for_seq(seq, particles_per_color):
    """Color bucket fixed at placement time, so an old particle's appearance
    never depends on how many newer ones have arrived."""
    bucket = ((seq - 1) // max(1, particles_per_color)) % len(PALETTE)
    return curses.color_pair(bucket + 2) | curses.A_BOLD


def run(stdscr, duration, frame_delay, walkers_per_frame, max_walker_steps,
        seed_mode, seed_count, particles_per_color, spawn_buffer,
        kill_buffer):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.clear()
    stdscr.refresh()
    stdscr.timeout(int(frame_delay * 1000))

    max_y, max_x = stdscr.getmaxyx()
    rows = max(8, max_y - 2)
    cols = max(8, max_x)

    grid = [[0] * cols for _ in range(rows)]
    placed = []
    last_drawn = 0
    next_seq = 1
    # Bounding box of the cluster in grid coordinates.
    min_r = rows
    max_r = -1
    min_c = cols
    max_c = -1

    def place(r, c):
        nonlocal next_seq, min_r, max_r, min_c, max_c
        grid[r][c] = next_seq
        placed.append((r, c, next_seq))
        next_seq += 1
        if r < min_r:
            min_r = r
        if r > max_r:
            max_r = r
        if c < min_c:
            min_c = c
        if c > max_c:
            max_c = c

    if seed_mode == "bottom":
        for c in range(cols):
            place(rows - 1, c)
    elif seed_mode == "random":
        for _ in range(seed_count):
            r = random.randint(0, rows - 1)
            c = random.randint(0, cols - 1)
            if grid[r][c] == 0:
                place(r, c)
    else:  # center default
        place(rows // 2, cols // 2)

    label_attr = (curses.color_pair(COLOR_LABEL)
                  | curses.A_BOLD | curses.A_REVERSE)
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
            new_grid = [[0] * new_cols for _ in range(new_rows)]
            new_placed = []
            min_r = new_rows; max_r = -1
            min_c = new_cols; max_c = -1
            for r, c, seq in placed:
                if 0 <= r < new_rows and 0 <= c < new_cols:
                    new_grid[r][c] = seq
                    new_placed.append((r, c, seq))
                    if r < min_r: min_r = r
                    if r > max_r: max_r = r
                    if c < min_c: min_c = c
                    if c > max_c: max_c = c
            grid = new_grid
            placed = new_placed
            rows, cols = new_rows, new_cols
            stdscr.clear()
            last_drawn = 0

        # Walker simulation: spawn near the cluster bounding box, kill if it
        # wanders too far. This is the standard DLA acceleration.
        kb = kill_buffer
        for _ in range(walkers_per_frame):
            kill_min_r = max(0, min_r - kb)
            kill_max_r = min(rows - 1, max_r + kb)
            kill_min_c = max(0, min_c - kb)
            kill_max_c = min(cols - 1, max_c + kb)

            r, c = spawn_near_cluster(min_r, max_r, min_c, max_c,
                                      spawn_buffer, rows, cols)
            if grid[r][c] != 0:
                continue
            for _ in range(max_walker_steps):
                if has_neighbor(grid, r, c, rows, cols):
                    place(r, c)
                    break
                dr = random.randint(-1, 1)
                dc = random.randint(-1, 1)
                nr = r + dr
                nc = c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    r, c = nr, nc
                if (r < kill_min_r or r > kill_max_r
                        or c < kill_min_c or c > kill_max_c):
                    break  # drifted outside the kill region — give up

        for i in range(last_drawn, len(placed)):
            r, c, seq = placed[i]
            try:
                stdscr.addstr(r, c, "*", attr_for_seq(seq, particles_per_color))
            except curses.error:
                pass
        last_drawn = len(placed)

        info = (f" Diffusion-Limited Aggregation   particles={next_seq - 1}   "
                f"seed={seed_mode}   spawn rate={walkers_per_frame}/frame ")
        info = info.ljust(max(0, max_x - 1))[:max(0, max_x - 1)]
        try:
            stdscr.addstr(max_y - 1, 0, info, label_attr)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=30, frame_delay=0.04, walkers_per_frame=8,
         max_walker_steps=1500, seed_mode="center", seed_count=5,
         particles_per_color=80, spawn_buffer=4, kill_buffer=20):
    duration = float(duration)
    frame_delay = float(frame_delay)
    walkers_per_frame = max(1, int(walkers_per_frame))
    max_walker_steps = max(100, int(max_walker_steps))
    if seed_mode not in ("center", "bottom", "random"):
        seed_mode = "center"
    seed_count = max(1, int(seed_count))
    particles_per_color = max(1, int(particles_per_color))
    spawn_buffer = max(1, int(spawn_buffer))
    kill_buffer = max(spawn_buffer + 1, int(kill_buffer))
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, walkers_per_frame, max_walker_steps,
        seed_mode, seed_count, particles_per_color, spawn_buffer,
        kill_buffer))


if __name__ == "__main__":
    main()
