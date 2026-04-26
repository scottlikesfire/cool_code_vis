import curses
import time


COLOR_LIGHT = 1
COLOR_DARK = 2
COLOR_QUEEN_OK = 3
COLOR_QUEEN_TRY = 4
COLOR_CONFLICT = 5
COLOR_TITLE = 6
COLOR_GRID = 7

MIN_CELL_W = 3
MIN_CELL_H = 2


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_LIGHT, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_DARK, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_QUEEN_OK, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_QUEEN_TRY, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_CONFLICT, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_TITLE, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_GRID, curses.COLOR_BLUE, -1)


def compute_cell_size(n, target_size, max_y, max_x):
    """Pick cell dimensions so the board roughly fills target_size chars wide,
    while never overflowing the terminal."""
    cell_w = max(MIN_CELL_W, target_size // n)
    cell_h = max(MIN_CELL_H, (target_size // 2) // n)
    # Don't exceed terminal bounds (leave margins for title/footer)
    cell_w = min(cell_w, max(MIN_CELL_W, (max_x - 4) // n))
    cell_h = min(cell_h, max(MIN_CELL_H, (max_y - 4) // n))
    return cell_w, cell_h


def draw_board(stdscr, n, placed, trial, trial_color, attempts, solved,
               max_y, max_x, cell_w, cell_h):
    stdscr.erase()
    status = "SOLVED!" if solved else f"Attempts: {attempts}"
    title = f"N-Queens (N={n})  {status}"
    try:
        stdscr.addstr(0, max(0, (max_x - len(title)) // 2), title[:max_x - 1],
                      curses.color_pair(COLOR_TITLE) | curses.A_BOLD | curses.A_REVERSE)
    except curses.error:
        pass

    board_w = n * cell_w + 1
    board_h = n * cell_h + 1
    start_x = max(0, (max_x - board_w) // 2)
    start_y = 2
    if start_y + board_h >= max_y:
        return

    # Checker pattern
    for r in range(n):
        for c in range(n):
            cell_x = start_x + c * cell_w
            cy = start_y + r * cell_h
            color = COLOR_LIGHT if (r + c) % 2 == 0 else COLOR_DARK
            ch = " " if color == COLOR_LIGHT else "."
            for dy in range(1, cell_h):
                for dx in range(1, cell_w):
                    try:
                        stdscr.addstr(cy + dy, cell_x + dx, ch,
                                      curses.color_pair(color) | curses.A_DIM)
                    except curses.error:
                        pass

    # Grid lines
    grid_attr = curses.color_pair(COLOR_GRID) | curses.A_DIM
    for r in range(n + 1):
        y = start_y + r * cell_h
        try:
            stdscr.addstr(y, start_x, "+", grid_attr)
        except curses.error:
            pass
        for c in range(n):
            x = start_x + c * cell_w
            try:
                stdscr.addstr(y, x + 1, "-" * (cell_w - 1), grid_attr)
                stdscr.addstr(y, x + cell_w, "+", grid_attr)
            except curses.error:
                pass
    for r in range(n):
        for c in range(n + 1):
            x = start_x + c * cell_w
            for dy in range(1, cell_h):
                y = start_y + r * cell_h + dy
                try:
                    stdscr.addstr(y, x, "|", grid_attr)
                except curses.error:
                    pass

    # Queens
    for r, c in placed:
        cy = start_y + r * cell_h + cell_h // 2
        cx = start_x + c * cell_w + cell_w // 2
        try:
            stdscr.addstr(cy, cx, "Q",
                          curses.color_pair(COLOR_QUEEN_OK) | curses.A_BOLD)
        except curses.error:
            pass

    if trial is not None:
        r, c = trial
        cy = start_y + r * cell_h + cell_h // 2
        cx = start_x + c * cell_w + cell_w // 2
        try:
            stdscr.addstr(cy, cx, "Q",
                          curses.color_pair(trial_color) | curses.A_BOLD)
        except curses.error:
            pass

    stdscr.refresh()


def conflicts(placed, row, col):
    for r, c in placed:
        if c == col:
            return True
        if abs(r - row) == abs(c - col):
            return True
    return False


def solve_animated(stdscr, n, step_delay, max_y, max_x, cell_w, cell_h):
    placed = []
    attempts = [0]
    cancelled = [False]

    def step(trial=None, trial_color=COLOR_QUEEN_TRY, solved=False):
        if cancelled[0]:
            return
        draw_board(stdscr, n, placed, trial, trial_color, attempts[0], solved,
                   max_y, max_x, cell_w, cell_h)
        stdscr.timeout(int(step_delay * 1000))
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            cancelled[0] = True

    def solve(row):
        if cancelled[0]:
            return False
        if row == n:
            return True
        for col in range(n):
            if cancelled[0]:
                return False
            attempts[0] += 1
            if conflicts(placed, row, col):
                step(trial=(row, col), trial_color=COLOR_CONFLICT)
            else:
                step(trial=(row, col), trial_color=COLOR_QUEEN_TRY)
                placed.append((row, col))
                step()
                if solve(row + 1):
                    return True
                placed.pop()
                step()
        return False

    solved = solve(0)
    if not cancelled[0]:
        step(solved=solved)
    return solved, cancelled[0]


def run(stdscr, n, step_delay, completion_pause, target_size):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass

    max_y, max_x = stdscr.getmaxyx()
    cell_w, cell_h = compute_cell_size(n, target_size, max_y, max_x)
    _, cancelled = solve_animated(stdscr, n, step_delay, max_y, max_x, cell_w, cell_h)
    if cancelled:
        return

    stdscr.timeout(100)
    pause_start = time.monotonic()
    while time.monotonic() - pause_start < completion_pause:
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(n=8, step_delay=0.05, completion_pause=3, target_size=60):
    n = int(n)
    step_delay = float(step_delay)
    completion_pause = float(completion_pause)
    target_size = int(target_size)
    curses.wrapper(lambda stdscr: run(stdscr, n, step_delay, completion_pause, target_size))


if __name__ == "__main__":
    main()
