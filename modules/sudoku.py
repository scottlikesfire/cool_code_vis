import collections
import curses
import random
import time


COLOR_GIVEN = 1
COLOR_FILLED = 2
COLOR_TRYING = 3
COLOR_CONFLICT = 4
COLOR_GRID = 5
COLOR_TITLE = 6
COLOR_LABEL = 7
COLOR_PROGRESS = 8

MIN_CELL_W = 4
MIN_CELL_H = 2

PUZZLES = [
    [
        [5, 3, 0, 0, 7, 0, 0, 0, 0],
        [6, 0, 0, 1, 9, 5, 0, 0, 0],
        [0, 9, 8, 0, 0, 0, 0, 6, 0],
        [8, 0, 0, 0, 6, 0, 0, 0, 3],
        [4, 0, 0, 8, 0, 3, 0, 0, 1],
        [7, 0, 0, 0, 2, 0, 0, 0, 6],
        [0, 6, 0, 0, 0, 0, 2, 8, 0],
        [0, 0, 0, 4, 1, 9, 0, 0, 5],
        [0, 0, 0, 0, 8, 0, 0, 7, 9],
    ],
    [
        [0, 0, 0, 2, 6, 0, 7, 0, 1],
        [6, 8, 0, 0, 7, 0, 0, 9, 0],
        [1, 9, 0, 0, 0, 4, 5, 0, 0],
        [8, 2, 0, 1, 0, 0, 0, 4, 0],
        [0, 0, 4, 6, 0, 2, 9, 0, 0],
        [0, 5, 0, 0, 0, 3, 0, 2, 8],
        [0, 0, 9, 3, 0, 0, 0, 7, 4],
        [0, 4, 0, 0, 5, 0, 0, 3, 6],
        [7, 0, 3, 0, 1, 8, 0, 0, 0],
    ],
    [
        [0, 2, 0, 6, 0, 8, 0, 0, 0],
        [5, 8, 0, 0, 0, 9, 7, 0, 0],
        [0, 0, 0, 0, 4, 0, 0, 0, 0],
        [3, 7, 0, 0, 0, 0, 5, 0, 0],
        [6, 0, 0, 0, 0, 0, 0, 0, 4],
        [0, 0, 8, 0, 0, 0, 0, 1, 3],
        [0, 0, 0, 0, 2, 0, 0, 0, 0],
        [0, 0, 9, 8, 0, 0, 0, 3, 6],
        [0, 0, 0, 3, 0, 6, 0, 9, 0],
    ],
]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_GIVEN, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_FILLED, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_TRYING, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_CONFLICT, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_GRID, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_TITLE, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_PROGRESS, curses.COLOR_GREEN, -1)


def compute_cell_size(target_size, max_y, max_x, log_lines):
    """Pick cell dimensions so the 9x9 board fills roughly target_size chars wide."""
    n = 9
    cell_w = max(MIN_CELL_W, target_size // n)
    cell_h = max(MIN_CELL_H, (target_size // 2) // n)
    # Don't overflow horizontally (leave 4 char margin)
    cell_w = min(cell_w, max(MIN_CELL_W, (max_x - 4) // n))
    # Don't overflow vertically — must leave room for title (2) + log panel + 1 margin
    reserved_v = 2 + log_lines + 4
    cell_h = min(cell_h, max(MIN_CELL_H, (max_y - reserved_v) // n))
    return cell_w, cell_h


def draw_board(stdscr, board, given, trying, trying_color, attempts, total_steps,
               step_idx, cell_w, cell_h, max_x):
    title = f"Sudoku Solver  Step: {step_idx}/{total_steps}  Attempts: {attempts}"
    try:
        stdscr.addstr(0, max(0, (max_x - len(title)) // 2), title[:max_x - 1],
                      curses.color_pair(COLOR_TITLE) | curses.A_BOLD | curses.A_REVERSE)
    except curses.error:
        pass

    board_w = 9 * cell_w + 1
    board_h = 9 * cell_h + 1
    start_x = max(0, (max_x - board_w) // 2)
    start_y = 2

    grid_dim = curses.color_pair(COLOR_GRID) | curses.A_DIM
    grid_bold = curses.color_pair(COLOR_GRID) | curses.A_BOLD

    for r in range(10):
        y = start_y + r * cell_h
        attr = grid_bold if r % 3 == 0 else grid_dim
        try:
            stdscr.addstr(y, start_x, "+", attr)
        except curses.error:
            pass
        for c in range(9):
            x = start_x + c * cell_w
            try:
                stdscr.addstr(y, x + 1, "-" * (cell_w - 1), attr)
                col_attr = grid_bold if (c + 1) % 3 == 0 else attr
                stdscr.addstr(y, x + cell_w, "+", col_attr)
            except curses.error:
                pass

    for r in range(9):
        for c in range(10):
            x = start_x + c * cell_w
            attr = grid_bold if c % 3 == 0 else grid_dim
            for dy in range(1, cell_h):
                y = start_y + r * cell_h + dy
                try:
                    stdscr.addstr(y, x, "|", attr)
                except curses.error:
                    pass

    for r in range(9):
        for c in range(9):
            v = board[r][c]
            if v == 0:
                continue
            cy = start_y + r * cell_h + cell_h // 2
            cx = start_x + c * cell_w + cell_w // 2

            if trying is not None and trying[0] == r and trying[1] == c:
                attr = curses.color_pair(trying_color) | curses.A_BOLD | curses.A_REVERSE
            elif given[r][c]:
                attr = curses.color_pair(COLOR_GIVEN) | curses.A_BOLD
            else:
                attr = curses.color_pair(COLOR_FILLED) | curses.A_BOLD
            try:
                stdscr.addstr(cy, cx, str(v), attr)
            except curses.error:
                pass

    return start_y + board_h  # bottom of board for log placement


def draw_status_panel(stdscr, recent_events, cells_filled, total_cells,
                      backtracks, in_backtrack, panel_y, log_lines, max_y, max_x):
    """Draw a status panel with progress bar + recent events list."""
    if panel_y >= max_y - 2:
        return

    pct = cells_filled / total_cells if total_cells else 0
    state_label = "BACKTRACKING" if in_backtrack else "PLACING"
    state_color = COLOR_CONFLICT if in_backtrack else COLOR_FILLED

    # Status line: [progress bar] X/81 (Y%)  |  Backtracks: N  |  STATE
    bar_w = max(10, min(30, max_x // 4))
    filled = int(bar_w * pct)
    line_y = panel_y + 1
    if line_y >= max_y - 1:
        return

    x = 2
    try:
        stdscr.addstr(line_y, x, "[", curses.A_DIM)
        x += 1
        if filled > 0:
            stdscr.addstr(line_y, x, "#" * filled,
                          curses.color_pair(COLOR_PROGRESS) | curses.A_BOLD)
        x += filled
        if filled < bar_w:
            stdscr.addstr(line_y, x, "-" * (bar_w - filled), curses.A_DIM)
        x += (bar_w - filled)
        stdscr.addstr(line_y, x, "]", curses.A_DIM)
        x += 2
        stdscr.addstr(line_y, x,
                      f" {cells_filled}/{total_cells} ({pct * 100:5.1f}%)  ",
                      curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        x += len(f" {cells_filled}/{total_cells} ({pct * 100:5.1f}%)  ")
        stdscr.addstr(line_y, x, "|  Backtracks: ", curses.A_DIM)
        x += len("|  Backtracks: ")
        stdscr.addstr(line_y, x, f"{backtracks}",
                      curses.color_pair(COLOR_CONFLICT) | curses.A_BOLD)
        x += len(f"{backtracks}")
        stdscr.addstr(line_y, x, "  |  ", curses.A_DIM)
        x += len("  |  ")
        stdscr.addstr(line_y, x, state_label,
                      curses.color_pair(state_color) | curses.A_BOLD)
    except curses.error:
        pass

    # Recent events label
    events_label_y = panel_y + 3
    if events_label_y >= max_y - 1:
        return
    try:
        stdscr.addstr(events_label_y, 2, "Recent activity:",
                      curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
    except curses.error:
        pass

    # Recent events list
    visible = list(recent_events)[-log_lines:]
    base_y = events_label_y + 1
    for i, ev in enumerate(visible):
        y = base_y + i
        if y >= max_y - 1:
            break
        step_idx, action, r, c, val = ev
        is_latest = (i == len(visible) - 1)
        dim_or_bold = curses.A_BOLD if is_latest else curses.A_DIM
        if action == "place":
            verb = "PLACE"
            verb_color = curses.color_pair(COLOR_FILLED) | dim_or_bold
            value_text = str(val)
            value_color = curses.color_pair(COLOR_FILLED) | dim_or_bold
        else:
            verb = "UNDO "
            verb_color = curses.color_pair(COLOR_CONFLICT) | dim_or_bold
            value_text = "_"
            value_color = curses.color_pair(COLOR_CONFLICT) | dim_or_bold

        coord_text = f"R{r + 1}C{c + 1}"
        prefix_text = f"  step {step_idx:>5}.  "

        x = 2
        try:
            stdscr.addstr(y, x, prefix_text, curses.A_DIM)
            x += len(prefix_text)
            stdscr.addstr(y, x, verb + " ", verb_color)
            x += len(verb) + 1
            stdscr.addstr(y, x, value_text, value_color)
            x += len(value_text)
            stdscr.addstr(y, x, " at ", dim_or_bold)
            x += 4
            stdscr.addstr(y, x, coord_text,
                          curses.color_pair(COLOR_TITLE) | dim_or_bold)
        except curses.error:
            pass


def draw_loading(stdscr, max_filled, attempts, max_y, max_x):
    stdscr.erase()
    cy = max_y // 2

    title = "Sudoku Solver"
    try:
        stdscr.addstr(cy - 4, max(0, (max_x - len(title)) // 2), title,
                      curses.color_pair(COLOR_TITLE) | curses.A_BOLD | curses.A_REVERSE)
    except curses.error:
        pass

    msg = "computing solution..."
    try:
        stdscr.addstr(cy - 2, max(0, (max_x - len(msg)) // 2), msg,
                      curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
    except curses.error:
        pass

    bar_width = min(50, max_x - 8)
    pct = max_filled / 81
    filled = int(bar_width * pct)
    bar_x = max(0, (max_x - bar_width - 2) // 2)
    try:
        stdscr.addstr(cy, bar_x, "[", curses.A_DIM)
        if filled > 0:
            stdscr.addstr(cy, bar_x + 1, "#" * filled,
                          curses.color_pair(COLOR_FILLED) | curses.A_BOLD)
        if filled < bar_width:
            stdscr.addstr(cy, bar_x + 1 + filled, "-" * (bar_width - filled),
                          curses.A_DIM)
        stdscr.addstr(cy, bar_x + 1 + bar_width, "]", curses.A_DIM)
    except curses.error:
        pass

    info = f"cells solved: {max_filled}/81  |  attempts: {attempts}"
    try:
        stdscr.addstr(cy + 2, max(0, (max_x - len(info)) // 2), info, curses.A_DIM)
    except curses.error:
        pass
    stdscr.refresh()


def is_valid(board, r, c, val):
    for i in range(9):
        if board[r][i] == val or board[i][c] == val:
            return False
    br, bc = (r // 3) * 3, (c // 3) * 3
    for i in range(br, br + 3):
        for j in range(bc, bc + 3):
            if board[i][j] == val:
                return False
    return True


def solve_with_progress(board, on_progress=None):
    """Solve a sudoku, recording every place/undo into a trace.

    Returns (trace, attempts, cancelled).
    """
    trace = []
    cells_filled = [sum(1 for row in board for v in row if v != 0)]
    max_filled = [cells_filled[0]]
    attempts = [0]
    last_progress = [time.monotonic()]
    cancelled = [False]

    def find_empty():
        for r in range(9):
            for c in range(9):
                if board[r][c] == 0:
                    return r, c
        return None

    def maybe_progress():
        now = time.monotonic()
        if now - last_progress[0] > 0.05:
            if on_progress is not None:
                if on_progress(max_filled[0], attempts[0]):
                    cancelled[0] = True
            last_progress[0] = now

    def solve():
        if cancelled[0]:
            return False
        spot = find_empty()
        if spot is None:
            return True
        r, c = spot
        for val in range(1, 10):
            if cancelled[0]:
                return False
            attempts[0] += 1
            if is_valid(board, r, c, val):
                board[r][c] = val
                cells_filled[0] += 1
                if cells_filled[0] > max_filled[0]:
                    max_filled[0] = cells_filled[0]
                trace.append(("place", r, c, val))
                maybe_progress()
                if solve():
                    return True
                board[r][c] = 0
                cells_filled[0] -= 1
                trace.append(("undo", r, c, 0))
        return False

    solve()
    return trace, attempts[0], cancelled[0]


def loading_phase(stdscr, puzzle):
    max_y, max_x = stdscr.getmaxyx()
    stdscr.timeout(0)

    work_board = [row[:] for row in puzzle]

    def on_progress(max_filled, attempts):
        nonlocal_cancel = False
        try:
            key = stdscr.getch()
            if key == ord("q") or key == 27:
                nonlocal_cancel = True
        except curses.error:
            pass
        draw_loading(stdscr, max_filled, attempts, max_y, max_x)
        return nonlocal_cancel

    initial_filled = sum(1 for row in puzzle for v in row if v != 0)
    draw_loading(stdscr, initial_filled, 0, max_y, max_x)

    trace, attempts, cancelled = solve_with_progress(work_board, on_progress)
    return trace, attempts, cancelled


def replay_trace(stdscr, puzzle, given, trace, attempts_total, duration,
                 target_size, log_lines):
    """Replay the recorded trace in `duration` seconds total."""
    max_y, max_x = stdscr.getmaxyx()
    cell_w, cell_h = compute_cell_size(target_size, max_y, max_x, log_lines)
    board = [row[:] for row in puzzle]
    total_steps = len(trace)

    if total_steps == 0:
        return False

    step_delay = duration / total_steps
    stdscr.timeout(int(step_delay * 1000))

    initial_filled = sum(1 for row in puzzle for v in row if v != 0)
    cells_filled = initial_filled
    backtracks = 0
    recent_events = collections.deque(maxlen=max(log_lines, 1))

    for idx, event in enumerate(trace):
        action, r, c, val = event
        if action == "place":
            board[r][c] = val
            cells_filled += 1
            color = COLOR_TRYING
            in_backtrack = False
            recent_events.append((idx + 1, action, r, c, val))
        else:
            removed_val = board[r][c]
            board[r][c] = 0
            cells_filled -= 1
            color = COLOR_CONFLICT
            in_backtrack = True
            backtracks += 1
            recent_events.append((idx + 1, action, r, c, removed_val))

        stdscr.erase()
        bottom = draw_board(stdscr, board, given,
                            trying=(r, c) if action == "place" else None,
                            trying_color=color,
                            attempts=attempts_total,
                            total_steps=total_steps,
                            step_idx=idx + 1,
                            cell_w=cell_w, cell_h=cell_h, max_x=max_x)
        draw_status_panel(stdscr, recent_events, cells_filled, 81,
                          backtracks, in_backtrack, bottom, log_lines,
                          max_y, max_x)
        stdscr.refresh()

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return True

    # Final clean draw
    stdscr.erase()
    bottom = draw_board(stdscr, board, given, None, COLOR_TRYING, attempts_total,
                        total_steps, total_steps, cell_w, cell_h, max_x)
    draw_status_panel(stdscr, recent_events, cells_filled, 81,
                      backtracks, False, bottom, log_lines, max_y, max_x)
    stdscr.refresh()
    return False


def run(stdscr, duration, completion_pause, target_size, log_lines):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass

    puzzle = [row[:] for row in random.choice(PUZZLES)]
    given = [[v != 0 for v in row] for row in puzzle]

    trace, attempts, cancelled = loading_phase(stdscr, puzzle)
    if cancelled:
        return

    cancelled = replay_trace(stdscr, puzzle, given, trace, attempts, duration,
                             target_size, log_lines)
    if cancelled:
        return

    stdscr.timeout(100)
    pause_start = time.monotonic()
    while time.monotonic() - pause_start < completion_pause:
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=15, completion_pause=3, target_size=60, log_lines=8):
    duration = float(duration)
    completion_pause = float(completion_pause)
    target_size = int(target_size)
    log_lines = max(1, int(log_lines))
    curses.wrapper(lambda stdscr: run(stdscr, duration, completion_pause,
                                      target_size, log_lines))


if __name__ == "__main__":
    main()
