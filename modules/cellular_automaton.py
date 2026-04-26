import curses
import random
import time


COLOR_ALIVE = 1
COLOR_NEW = 2
COLOR_DYING = 3
COLOR_TITLE = 4


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_ALIVE, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_NEW, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_DYING, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_TITLE, curses.COLOR_CYAN, -1)


def step_life(grid, rows, cols):
    """Returns (new_grid, born_set, died_set)."""
    new_grid = [[0] * cols for _ in range(rows)]
    born = set()
    died = set()
    for r in range(rows):
        for c in range(cols):
            neighbors = 0
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = (r + dr) % rows, (c + dc) % cols
                    neighbors += grid[nr][nc]
            alive = grid[r][c]
            if alive and neighbors in (2, 3):
                new_grid[r][c] = 1
            elif not alive and neighbors == 3:
                new_grid[r][c] = 1
                born.add((r, c))
            elif alive:
                died.add((r, c))
    return new_grid, born, died


def random_grid(rows, cols, density):
    return [[1 if random.random() < density else 0 for _ in range(cols)]
            for _ in range(rows)]


def run(stdscr, density, step_delay, duration, completion_pause):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(step_delay * 1000))

    max_y, max_x = stdscr.getmaxyx()
    grid_rows = max_y - 3
    grid_cols = max_x - 2
    if grid_rows < 5 or grid_cols < 5:
        return

    grid = random_grid(grid_rows, grid_cols, density)
    born = set()
    died = set()
    generation = 0
    start_time = time.monotonic()

    while True:
        if duration is not None and time.monotonic() - start_time >= duration:
            break

        stdscr.erase()
        title = f"Conway's Game of Life — Generation {generation}"
        try:
            stdscr.addstr(0, max(0, (max_x - len(title)) // 2), title[:max_x - 1],
                          curses.color_pair(COLOR_TITLE) | curses.A_BOLD | curses.A_REVERSE)
        except curses.error:
            pass

        alive_count = 0
        for r in range(grid_rows):
            for c in range(grid_cols):
                if grid[r][c]:
                    alive_count += 1
                    if (r, c) in born:
                        attr = curses.color_pair(COLOR_NEW) | curses.A_BOLD
                    else:
                        attr = curses.color_pair(COLOR_ALIVE) | curses.A_BOLD
                    try:
                        stdscr.addstr(r + 2, c + 1, "#", attr)
                    except curses.error:
                        pass
                elif (r, c) in died:
                    try:
                        stdscr.addstr(r + 2, c + 1, ".",
                                      curses.color_pair(COLOR_DYING) | curses.A_DIM)
                    except curses.error:
                        pass

        footer = f"Alive: {alive_count}  |  q to quit"
        try:
            stdscr.addstr(max_y - 1, 2, footer[:max_x - 4], curses.A_DIM)
        except curses.error:
            pass

        stdscr.refresh()

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return

        new_grid, born, died = step_life(grid, grid_rows, grid_cols)
        # If the population dies out or stagnates, reseed
        if alive_count == 0 or (new_grid == grid and not born and not died):
            grid = random_grid(grid_rows, grid_cols, density)
            born = set()
            died = set()
            generation = 0
        else:
            grid = new_grid
            generation += 1

    stdscr.timeout(100)
    pause_start = time.monotonic()
    while time.monotonic() - pause_start < completion_pause:
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(density=0.3, step_delay=0.1, duration=20, completion_pause=2):
    density = float(density)
    step_delay = float(step_delay)
    duration = float(duration) if duration is not None else None
    completion_pause = float(completion_pause)
    curses.wrapper(lambda stdscr: run(stdscr, density, step_delay, duration, completion_pause))


if __name__ == "__main__":
    main()
