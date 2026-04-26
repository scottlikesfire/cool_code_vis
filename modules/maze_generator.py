import curses
import random
import time


COLOR_WALL = 1
COLOR_PATH = 2
COLOR_CURRENT = 3
COLOR_TITLE = 4


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_WALL, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_PATH, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_CURRENT, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_TITLE, curses.COLOR_CYAN, -1)


def draw_cell(stdscr, grid, r, c, max_y, max_x, current=None):
    if r >= max_y - 2 or c >= max_x - 1:
        return
    val = grid[r][c]
    if (r, c) == current:
        ch = "@"
        attr = curses.color_pair(COLOR_CURRENT) | curses.A_BOLD
    elif val == 1:  # wall
        ch = "#"
        attr = curses.color_pair(COLOR_WALL) | curses.A_BOLD
    else:
        ch = " "
        attr = curses.color_pair(COLOR_PATH)
    try:
        stdscr.addstr(r + 2, c + 1, ch, attr)
    except curses.error:
        pass


def draw_full(stdscr, grid, rows, cols, max_y, max_x, current=None):
    stdscr.erase()
    title = "Maze Generator (Recursive Backtracker)"
    try:
        stdscr.addstr(0, max(0, (max_x - len(title)) // 2), title[:max_x - 1],
                      curses.color_pair(COLOR_TITLE) | curses.A_BOLD | curses.A_REVERSE)
    except curses.error:
        pass
    for r in range(rows):
        for c in range(cols):
            draw_cell(stdscr, grid, r, c, max_y, max_x, current)
    stdscr.refresh()


def carve(stdscr, grid, rows, cols, step_delay, max_y, max_x):
    """Iterative recursive backtracker. Yields (r, c) of current cell each step."""
    stack = [(1, 1)]
    grid[1][1] = 0
    cancelled = [False]

    while stack:
        r, c = stack[-1]
        directions = [(0, 2), (0, -2), (2, 0), (-2, 0)]
        random.shuffle(directions)
        moved = False
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if 1 <= nr < rows - 1 and 1 <= nc < cols - 1 and grid[nr][nc] == 1:
                # Knock down wall between
                grid[r + dr // 2][c + dc // 2] = 0
                grid[nr][nc] = 0
                stack.append((nr, nc))

                # Update only the changed cells
                draw_cell(stdscr, grid, r + dr // 2, c + dc // 2, max_y, max_x)
                draw_cell(stdscr, grid, nr, nc, max_y, max_x, (nr, nc))
                draw_cell(stdscr, grid, r, c, max_y, max_x)
                stdscr.refresh()
                stdscr.timeout(int(step_delay * 1000))
                key = stdscr.getch()
                if key == ord("q") or key == 27:
                    cancelled[0] = True
                    return cancelled[0]
                moved = True
                break
        if not moved:
            stack.pop()

    return cancelled[0]


def run(stdscr, step_delay, completion_pause):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass

    max_y, max_x = stdscr.getmaxyx()
    rows = max_y - 3
    cols = max_x - 2
    # Ensure odd dimensions for proper maze generation
    if rows % 2 == 0:
        rows -= 1
    if cols % 2 == 0:
        cols -= 1
    if rows < 5 or cols < 5:
        return

    grid = [[1] * cols for _ in range(rows)]
    draw_full(stdscr, grid, rows, cols, max_y, max_x)
    cancelled = carve(stdscr, grid, rows, cols, step_delay, max_y, max_x)

    if cancelled:
        return

    stdscr.timeout(100)
    pause_start = time.monotonic()
    while time.monotonic() - pause_start < completion_pause:
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(step_delay=0.005, completion_pause=3):
    step_delay = float(step_delay)
    completion_pause = float(completion_pause)
    curses.wrapper(lambda stdscr: run(stdscr, step_delay, completion_pause))


if __name__ == "__main__":
    main()
