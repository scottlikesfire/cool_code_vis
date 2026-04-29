import curses
import random
import time


COLOR_S = 1   # susceptible — green
COLOR_I = 2   # infected — red
COLOR_R = 3   # recovered — blue
COLOR_AXIS = 4
COLOR_LABEL = 5

S, I, R = 0, 1, 2


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_S, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_I, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_R, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_AXIS, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def init_grid(rows, cols, initial_infected):
    grid = [[S] * cols for _ in range(rows)]
    n = max(1, int(initial_infected))
    placed = 0
    while placed < n:
        r = random.randint(0, rows - 1)
        c = random.randint(0, cols - 1)
        if grid[r][c] == S:
            grid[r][c] = I
            placed += 1
    return grid


def step(grid, rows, cols, beta, gamma):
    """One time step. β = per-infected-neighbor infection probability,
    γ = recovery probability per step."""
    new_grid = [row[:] for row in grid]
    for r in range(rows):
        for c in range(cols):
            state = grid[r][c]
            if state == S:
                # Count infected Moore neighbors
                inf_neigh = 0
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            if grid[nr][nc] == I:
                                inf_neigh += 1
                if inf_neigh > 0:
                    p = 1.0 - (1.0 - beta) ** inf_neigh
                    if random.random() < p:
                        new_grid[r][c] = I
            elif state == I:
                if random.random() < gamma:
                    new_grid[r][c] = R
    return new_grid


def run(stdscr, duration, frame_delay, beta, gamma, initial_infected,
        history_size, grid_fraction):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.clear()
    stdscr.refresh()
    stdscr.timeout(int(frame_delay * 1000))

    max_y, max_x = stdscr.getmaxyx()

    # Layout: top portion = grid, bottom portion = curves, last row = status
    grid_rows = max(4, int((max_y - 2) * grid_fraction))
    curve_rows = max(2, max_y - 2 - grid_rows)
    cols = max(8, max_x)

    grid = init_grid(grid_rows, cols, initial_infected)
    history = []
    total = grid_rows * cols
    started_at = time.monotonic()

    while True:
        now = time.monotonic()
        elapsed = now - started_at
        if elapsed >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        new_grid_rows = max(4, int((max_y - 2) * grid_fraction))
        new_curve_rows = max(2, max_y - 2 - new_grid_rows)
        new_cols = max(8, max_x)
        if (new_grid_rows, new_curve_rows, new_cols) != (grid_rows, curve_rows, cols):
            grid_rows, curve_rows, cols = new_grid_rows, new_curve_rows, new_cols
            grid = init_grid(grid_rows, cols, initial_infected)
            history = []
            total = grid_rows * cols

        grid = step(grid, grid_rows, cols, beta, gamma)

        s_count = i_count = r_count = 0
        for row in grid:
            for v in row:
                if v == S: s_count += 1
                elif v == I: i_count += 1
                else: r_count += 1
        history.append((s_count, i_count, r_count))
        if len(history) > history_size:
            history.pop(0)

        stdscr.erase()

        # --- Top: agent grid ---
        for r in range(grid_rows):
            row = grid[r]
            for c in range(cols):
                v = row[c]
                if v == S:
                    ch, attr = ".", curses.color_pair(COLOR_S) | curses.A_DIM
                elif v == I:
                    ch, attr = "@", curses.color_pair(COLOR_I) | curses.A_BOLD
                else:
                    ch, attr = "#", curses.color_pair(COLOR_R)
                try:
                    stdscr.addstr(r, c, ch, attr)
                except curses.error:
                    pass

        # --- Middle: separator + curves ---
        sep_row = grid_rows
        try:
            stdscr.addstr(sep_row, 0, "-" * (max_x - 1),
                          curses.color_pair(COLOR_AXIS) | curses.A_DIM)
        except curses.error:
            pass

        plot_top = sep_row + 1
        plot_h = curve_rows - 1
        if plot_h > 0 and len(history) > 1:
            n_hist = len(history)
            # Plot S (green dim), I (red bold), R (blue) over time
            for i in range(n_hist):
                t_norm = i / max(1, n_hist - 1)
                x = int(round(t_norm * (max_x - 1)))
                if x >= max_x:
                    continue
                s, ii, rr = history[i]
                sy = plot_top + plot_h - int(round(s / total * (plot_h - 1)))
                iy = plot_top + plot_h - int(round(ii / total * (plot_h - 1)))
                ry = plot_top + plot_h - int(round(rr / total * (plot_h - 1)))
                for y, color, ch in (
                    (sy, COLOR_S, "."),
                    (ry, COLOR_R, "#"),
                    (iy, COLOR_I, "*"),
                ):
                    if 0 <= y < max_y - 1:
                        try:
                            stdscr.addstr(y, x, ch,
                                          curses.color_pair(color) | curses.A_BOLD)
                        except curses.error:
                            pass

        # --- Status bar ---
        s_pct = 100.0 * s_count / total
        i_pct = 100.0 * i_count / total
        r_pct = 100.0 * r_count / total
        info = (f" SIR epidemic   β={beta:.3f}  γ={gamma:.3f}   "
                f"S={s_pct:5.1f}%  I={i_pct:5.1f}%  R={r_pct:5.1f}% ")
        info = info.ljust(max(0, max_x - 1))[:max(0, max_x - 1)]
        try:
            stdscr.addstr(max_y - 1, 0, info,
                          curses.color_pair(COLOR_LABEL)
                          | curses.A_BOLD | curses.A_REVERSE)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return

        # If the epidemic burned out, hold for a bit then exit early
        if i_count == 0 and len(history) > 5:
            time.sleep(min(2.0, max(0.0, duration - elapsed)))
            break


def main(duration=30, frame_delay=0.05, beta=0.18, gamma=0.04,
         initial_infected=3, history_size=400, grid_fraction=0.65):
    duration = float(duration)
    frame_delay = float(frame_delay)
    beta = float(beta)
    gamma = float(gamma)
    initial_infected = max(1, int(initial_infected))
    history_size = max(2, int(history_size))
    grid_fraction = float(grid_fraction)
    grid_fraction = max(0.3, min(0.85, grid_fraction))
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, beta, gamma, initial_infected,
        history_size, grid_fraction))


if __name__ == "__main__":
    main()
