import curses
import math
import random
import time


COLOR_UP = 1
COLOR_DOWN = 2
COLOR_LABEL = 3


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_UP, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_DOWN, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def run(stdscr, duration, frame_delay, J, sweeps_per_frame,
        T_min, T_max, T_period):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.clear()
    stdscr.refresh()
    stdscr.timeout(int(frame_delay * 1000))

    max_y, max_x = stdscr.getmaxyx()
    # Leave one blank separator row + one status row at the bottom so the
    # status bar isn't visually merged with the lattice.
    rows = max(2, max_y - 2)
    cols = max(2, max_x)
    grid = [[random.choice([-1, 1]) for _ in range(cols)] for _ in range(rows)]

    start = time.monotonic()
    while True:
        now = time.monotonic()
        elapsed = now - start
        if elapsed >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        # Resize lattice if terminal changed
        if rows != max_y - 2 or cols != max_x:
            new_rows = max(2, max_y - 2)
            new_cols = max(2, max_x)
            new_grid = [[random.choice([-1, 1]) for _ in range(new_cols)]
                        for _ in range(new_rows)]
            for r in range(min(rows, new_rows)):
                for c in range(min(cols, new_cols)):
                    new_grid[r][c] = grid[r][c]
            grid = new_grid
            rows, cols = new_rows, new_cols

        # Sinusoidal temperature sweep across the critical point
        phase = (elapsed / T_period) * 2 * math.pi
        T = T_min + (T_max - T_min) * 0.5 * (1.0 + math.sin(phase))
        T = max(0.1, T)
        inv_T = 1.0 / T

        N = rows * cols
        for _ in range(sweeps_per_frame):
            for _ in range(N):
                i = random.randint(0, rows - 1)
                j = random.randint(0, cols - 1)
                spin = grid[i][j]
                neigh = (
                    grid[(i - 1) % rows][j] + grid[(i + 1) % rows][j]
                    + grid[i][(j - 1) % cols] + grid[i][(j + 1) % cols]
                )
                dE = 2.0 * J * spin * neigh
                if dE <= 0 or random.random() < math.exp(-dE * inv_T):
                    grid[i][j] = -spin

        stdscr.erase()
        up_attr = curses.color_pair(COLOR_UP) | curses.A_BOLD
        down_attr = curses.color_pair(COLOR_DOWN) | curses.A_DIM
        mag_total = 0
        for y in range(rows):
            row = grid[y]
            for x in range(cols):
                s = row[x]
                mag_total += s
                if s > 0:
                    try:
                        stdscr.addstr(y, x, "#", up_attr)
                    except curses.error:
                        pass
                else:
                    try:
                        stdscr.addstr(y, x, ".", down_attr)
                    except curses.error:
                        pass

        mag = mag_total / N
        info = f" 2D Ising model   J={J}   T={T:.3f}   M={mag:+.3f}   Tc≈2.269 "
        # Pad to full width so the status reads as a solid reverse-video bar
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


def main(duration=30, frame_delay=0.05, J=1.0, sweeps_per_frame=1,
         T_min=1.5, T_max=4.0, T_period=20.0):
    duration = float(duration)
    frame_delay = float(frame_delay)
    J = float(J)
    sweeps_per_frame = max(1, int(sweeps_per_frame))
    T_min = float(T_min)
    T_max = float(T_max)
    T_period = float(T_period)
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, J, sweeps_per_frame,
        T_min, T_max, T_period))


if __name__ == "__main__":
    main()
