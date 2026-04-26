import curses
import random
import time


COLOR_VISITED = 1
COLOR_KNIGHT = 2
COLOR_RECENT = 3
COLOR_GRID = 4
COLOR_TITLE = 5
COLOR_LIGHT = 6
COLOR_DARK = 7

MIN_CELL_H = 2

KNIGHT_MOVES = [
    (-2, -1), (-2, 1), (-1, -2), (-1, 2),
    (1, -2), (1, 2), (2, -1), (2, 1),
]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_VISITED, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_KNIGHT, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_RECENT, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_GRID, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_TITLE, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_LIGHT, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_DARK, curses.COLOR_BLUE, -1)


def compute_cell_size(n, target_size, max_y, max_x):
    """Pick cell size, ensuring cell_w fits the largest move number."""
    min_cell_w = len(str(n * n)) + 2  # number + 1 char padding on each side
    cell_w = max(min_cell_w, target_size // n)
    cell_h = max(MIN_CELL_H, (target_size // 2) // n)
    cell_w = min(cell_w, max(min_cell_w, (max_x - 4) // n))
    cell_h = min(cell_h, max(MIN_CELL_H, (max_y - 4) // n))
    return cell_w, cell_h


def draw_grid(stdscr, n, start_x, start_y, cell_w, cell_h):
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


def draw_board(stdscr, n, board, knight_pos, move_count, max_y, max_x, cell_w, cell_h):
    stdscr.erase()
    title = f"Knight's Tour (N={n}, Warnsdorff's heuristic)  Move: {move_count}/{n*n}"
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

    # Checkerboard background
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

    draw_grid(stdscr, n, start_x, start_y, cell_w, cell_h)

    for r in range(n):
        for c in range(n):
            v = board[r][c]
            if v == 0:
                continue
            cy = start_y + r * cell_h + cell_h // 2
            cx = start_x + c * cell_w + 1
            label = f"{v:>{cell_w - 1}}"
            if (r, c) == knight_pos:
                attr = curses.color_pair(COLOR_KNIGHT) | curses.A_BOLD | curses.A_REVERSE
            elif v == move_count - 1 and move_count > 1:
                attr = curses.color_pair(COLOR_RECENT) | curses.A_BOLD
            else:
                attr = curses.color_pair(COLOR_VISITED) | curses.A_BOLD
            try:
                stdscr.addstr(cy, cx, label[:cell_w - 1], attr)
            except curses.error:
                pass

    stdscr.refresh()


def count_onward(board, n, r, c):
    count = 0
    for dr, dc in KNIGHT_MOVES:
        nr, nc = r + dr, c + dc
        if 0 <= nr < n and 0 <= nc < n and board[nr][nc] == 0:
            count += 1
    return count


def warnsdorff_tour(stdscr, n, start, step_delay, max_y, max_x, cell_w, cell_h):
    board = [[0] * n for _ in range(n)]
    r, c = start
    board[r][c] = 1

    for move in range(2, n * n + 1):
        draw_board(stdscr, n, board, (r, c), move - 1, max_y, max_x, cell_w, cell_h)
        stdscr.timeout(int(step_delay * 1000))
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return False, True

        candidates = []
        for dr, dc in KNIGHT_MOVES:
            nr, nc = r + dr, c + dc
            if 0 <= nr < n and 0 <= nc < n and board[nr][nc] == 0:
                onward = count_onward(board, n, nr, nc)
                candidates.append((onward, nr, nc))

        if not candidates:
            return False, False

        candidates.sort()
        best_onward = candidates[0][0]
        best = [cand for cand in candidates if cand[0] == best_onward]
        _, nr, nc = random.choice(best)

        r, c = nr, nc
        board[r][c] = move

    draw_board(stdscr, n, board, (r, c), n * n, max_y, max_x, cell_w, cell_h)
    return True, False


def run(stdscr, n, step_delay, completion_pause, target_size):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass

    max_y, max_x = stdscr.getmaxyx()
    cell_w, cell_h = compute_cell_size(n, target_size, max_y, max_x)
    start = (random.randint(0, n - 1), random.randint(0, n - 1))

    _, cancelled = warnsdorff_tour(stdscr, n, start, step_delay, max_y, max_x,
                                   cell_w, cell_h)
    if cancelled:
        return

    stdscr.timeout(100)
    pause_start = time.monotonic()
    while time.monotonic() - pause_start < completion_pause:
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(n=8, step_delay=0.15, completion_pause=3, target_size=60):
    n = int(n)
    step_delay = float(step_delay)
    completion_pause = float(completion_pause)
    target_size = int(target_size)
    curses.wrapper(lambda stdscr: run(stdscr, n, step_delay, completion_pause, target_size))


if __name__ == "__main__":
    main()
