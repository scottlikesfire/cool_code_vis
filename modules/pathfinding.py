import curses
import heapq
import random
import time


COLOR_WALL = 1
COLOR_OPEN = 2
COLOR_FRONTIER = 3
COLOR_VISITED = 4
COLOR_PATH = 5
COLOR_START = 6
COLOR_GOAL = 7
COLOR_TITLE = 8


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_WALL, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_OPEN, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_FRONTIER, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_VISITED, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_PATH, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_START, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_GOAL, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_TITLE, curses.COLOR_CYAN, -1)


def generate_maze(rows, cols):
    """Recursive backtracker. rows and cols should be odd."""
    grid = [[1] * cols for _ in range(rows)]
    stack = [(1, 1)]
    grid[1][1] = 0
    while stack:
        r, c = stack[-1]
        directions = [(0, 2), (0, -2), (2, 0), (-2, 0)]
        random.shuffle(directions)
        moved = False
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if 1 <= nr < rows - 1 and 1 <= nc < cols - 1 and grid[nr][nc] == 1:
                grid[r + dr // 2][c + dc // 2] = 0
                grid[nr][nc] = 0
                stack.append((nr, nc))
                moved = True
                break
        if not moved:
            stack.pop()
    return grid


def heuristic(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def draw_cell(stdscr, r, c, ch, attr, max_y, max_x):
    if r + 2 >= max_y - 1 or c + 1 >= max_x - 1:
        return
    try:
        stdscr.addstr(r + 2, c + 1, ch, attr)
    except curses.error:
        pass


def draw_static(stdscr, grid, rows, cols, start, goal, max_y, max_x):
    stdscr.erase()
    title = "A* Pathfinding"
    try:
        stdscr.addstr(0, max(0, (max_x - len(title)) // 2), title[:max_x - 1],
                      curses.color_pair(COLOR_TITLE) | curses.A_BOLD | curses.A_REVERSE)
    except curses.error:
        pass

    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 1:
                draw_cell(stdscr, r, c, "#",
                          curses.color_pair(COLOR_WALL) | curses.A_BOLD,
                          max_y, max_x)

    sr, sc = start
    gr, gc = goal
    draw_cell(stdscr, sr, sc, "S",
              curses.color_pair(COLOR_START) | curses.A_BOLD, max_y, max_x)
    draw_cell(stdscr, gr, gc, "G",
              curses.color_pair(COLOR_GOAL) | curses.A_BOLD, max_y, max_x)
    stdscr.refresh()


def astar(stdscr, grid, rows, cols, start, goal, step_delay, max_y, max_x):
    """A* search with animated frontier and visited cells.

    Returns (path, cancelled). path is a list of (r, c) or None if no path.
    """
    open_set = []
    heapq.heappush(open_set, (0, 0, start))
    came_from = {}
    g_score = {start: 0}
    counter = 1
    visited = set()
    in_open = {start}

    nodes_explored = 0

    while open_set:
        _, _, current = heapq.heappop(open_set)
        in_open.discard(current)
        if current in visited:
            continue
        visited.add(current)
        nodes_explored += 1

        if current == goal:
            # Reconstruct path
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path, False

        if current != start:
            draw_cell(stdscr, current[0], current[1], "+",
                      curses.color_pair(COLOR_VISITED) | curses.A_DIM,
                      max_y, max_x)

        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = current[0] + dr, current[1] + dc
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue
            if grid[nr][nc] == 1 or (nr, nc) in visited:
                continue
            tentative_g = g_score[current] + 1
            if tentative_g < g_score.get((nr, nc), float("inf")):
                came_from[(nr, nc)] = current
                g_score[(nr, nc)] = tentative_g
                f = tentative_g + heuristic((nr, nc), goal)
                heapq.heappush(open_set, (f, counter, (nr, nc)))
                counter += 1
                in_open.add((nr, nc))
                if (nr, nc) != goal:
                    draw_cell(stdscr, nr, nc, ".",
                              curses.color_pair(COLOR_FRONTIER) | curses.A_BOLD,
                              max_y, max_x)

        # Status footer
        footer = f"Explored: {nodes_explored}  Frontier: {len(in_open)}  | q to quit"
        try:
            stdscr.addstr(max_y - 1, 2, footer[:max_x - 4], curses.A_DIM)
        except curses.error:
            pass

        stdscr.refresh()
        stdscr.timeout(int(step_delay * 1000))
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return None, True

    return None, False


def run(stdscr, step_delay, completion_pause):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass

    max_y, max_x = stdscr.getmaxyx()
    rows = max_y - 3
    cols = max_x - 2
    if rows % 2 == 0:
        rows -= 1
    if cols % 2 == 0:
        cols -= 1
    if rows < 5 or cols < 5:
        return

    grid = generate_maze(rows, cols)
    start = (1, 1)
    goal = (rows - 2, cols - 2)
    # Make sure goal is reachable open space
    grid[goal[0]][goal[1]] = 0

    draw_static(stdscr, grid, rows, cols, start, goal, max_y, max_x)
    path, cancelled = astar(stdscr, grid, rows, cols, start, goal,
                            step_delay, max_y, max_x)
    if cancelled:
        return

    if path:
        for r, c in path:
            if (r, c) == start or (r, c) == goal:
                continue
            draw_cell(stdscr, r, c, "*",
                      curses.color_pair(COLOR_PATH) | curses.A_BOLD,
                      max_y, max_x)
            stdscr.refresh()
            stdscr.timeout(int(step_delay * 1000))
            key = stdscr.getch()
            if key == ord("q") or key == 27:
                return

    stdscr.timeout(100)
    pause_start = time.monotonic()
    while time.monotonic() - pause_start < completion_pause:
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(step_delay=0.01, completion_pause=3):
    step_delay = float(step_delay)
    completion_pause = float(completion_pause)
    curses.wrapper(lambda stdscr: run(stdscr, step_delay, completion_pause))


if __name__ == "__main__":
    main()
