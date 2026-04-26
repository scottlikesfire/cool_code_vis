import curses
import time


COLOR_PEG = 1
COLOR_BASE = 2
COLOR_TITLE = 3
COLOR_LABEL = 4
COLOR_HISTORY = 5
COLOR_CURRENT_MOVE = 6
DISK_COLOR_BASE = 10  # disks use color pairs starting at 10

LABELS = ["A", "B", "C"]


def init_colors(num_disks):
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_PEG, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_BASE, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_TITLE, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_HISTORY, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_CURRENT_MOVE, curses.COLOR_YELLOW, -1)

    palette = [
        curses.COLOR_RED,
        curses.COLOR_YELLOW,
        curses.COLOR_GREEN,
        curses.COLOR_CYAN,
        curses.COLOR_BLUE,
        curses.COLOR_MAGENTA,
    ]
    for i in range(num_disks):
        curses.init_pair(DISK_COLOR_BASE + i, palette[i % len(palette)], -1)


def disk_attr(disk, base_attr=curses.A_BOLD):
    return curses.color_pair(DISK_COLOR_BASE + disk - 1) | base_attr


def write_segments(stdscr, y, x, segments, max_x):
    """Write a list of (text, attr) tuples sequentially on a line.
    Stops if it runs out of space. Returns the next x position."""
    for text, attr in segments:
        if x >= max_x - 1:
            return x
        avail = max_x - x - 1
        text = text[:avail]
        try:
            stdscr.addstr(y, x, text, attr)
        except curses.error:
            pass
        x += len(text)
    return x


def segment_total_len(segments):
    return sum(len(t) for t, _ in segments)


def draw(stdscr, pegs, num_disks, current_move, history, move_count, total_moves,
         history_lines, max_y, max_x):
    stdscr.erase()
    title = f"Tower of Hanoi (N={num_disks})  Moves: {move_count}/{total_moves}"
    try:
        stdscr.addstr(0, max(0, (max_x - len(title)) // 2), title[:max_x - 1],
                      curses.color_pair(COLOR_TITLE) | curses.A_BOLD | curses.A_REVERSE)
    except curses.error:
        pass

    # --- Text readout above the puzzle ---

    # Current move (color-coded disk)
    move_attr = curses.color_pair(COLOR_CURRENT_MOVE) | curses.A_BOLD
    if current_move:
        disk, src, dst = current_move
        segs = [
            (">>>  ", move_attr),
            (f"Move {move_count}: ", move_attr),
            ("disk ", move_attr),
            (str(disk), disk_attr(disk) | curses.A_REVERSE),
            (f"  {LABELS[src]} --> {LABELS[dst]}  ", move_attr),
            ("<<<", move_attr),
        ]
        total = segment_total_len(segs)
        x = max(0, (max_x - total) // 2)
        write_segments(stdscr, 2, x, segs, max_x)
    else:
        line = "(starting position)" if move_count == 0 else "(complete)"
        try:
            stdscr.addstr(2, max(0, (max_x - len(line)) // 2), line[:max_x - 1],
                          move_attr)
        except curses.error:
            pass

    # Move history
    try:
        stdscr.addstr(4, 4, "Recent moves:",
                      curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
    except curses.error:
        pass

    visible_history = history[-history_lines:]
    for i, entry in enumerate(visible_history):
        m_num, disk, src, dst = entry
        is_latest = (i == len(visible_history) - 1)
        text_base = curses.color_pair(COLOR_HISTORY) | curses.A_BOLD if is_latest \
            else curses.A_DIM
        d_attr = disk_attr(disk) | (curses.A_BOLD if is_latest else curses.A_DIM)
        segs = [
            (f"  {m_num:>4}.  disk ", text_base),
            (str(disk), d_attr),
            (f"  {LABELS[src]} -> {LABELS[dst]}", text_base),
        ]
        write_segments(stdscr, 5 + i, 4, segs, max_x // 2)

    # Peg state on the right
    state_x = max_x // 2 + 4
    try:
        stdscr.addstr(4, state_x, "Peg state:",
                      curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
    except curses.error:
        pass

    for p in range(3):
        contents = pegs[p]
        y = 5 + p
        if not contents:
            try:
                stdscr.addstr(y, state_x, f"Peg {LABELS[p]}: empty",
                              curses.color_pair(COLOR_LABEL) | curses.A_DIM)
            except curses.error:
                pass
            continue

        top = contents[-1]
        label_attr = curses.color_pair(COLOR_LABEL)
        segs = [
            (f"Peg {LABELS[p]}: top=", label_attr),
            (f"{top:<3}", disk_attr(top)),
            (f" count={len(contents):<3}  [", label_attr),
        ]
        # Add each disk number color-coded
        for idx, d in enumerate(reversed(contents)):
            segs.append((str(d), disk_attr(d)))
            if idx < len(contents) - 1:
                segs.append((", ", label_attr | curses.A_DIM))
        segs.append(("]", label_attr))
        write_segments(stdscr, y, state_x, segs, max_x)

    # --- Animated puzzle below ---

    max_disk_width = 2 * num_disks - 1
    peg_spacing = max_disk_width + 6
    total_width = peg_spacing * 3
    margin = max(0, (max_x - total_width) // 2)
    peg_centers = [margin + max_disk_width // 2 + 3 + p * peg_spacing for p in range(3)]

    base_y = max_y - 3
    peg_height = num_disks + 2
    puzzle_top = base_y - peg_height

    # Bottom of the readout area
    readout_bottom = 5 + max(history_lines, 3)
    if puzzle_top <= readout_bottom:
        stdscr.refresh()
        return

    for p in range(3):
        peg_x = peg_centers[p]
        # Pole
        for h in range(peg_height):
            y = base_y - h
            if y > readout_bottom:
                try:
                    stdscr.addstr(y, peg_x, "|",
                                  curses.color_pair(COLOR_PEG) | curses.A_BOLD)
                except curses.error:
                    pass
        # Base
        base_left = peg_x - max_disk_width // 2 - 1
        base_len = max_disk_width + 2
        if 0 <= base_left and base_left + base_len < max_x:
            try:
                stdscr.addstr(base_y + 1, base_left, "=" * base_len,
                              curses.color_pair(COLOR_BASE) | curses.A_BOLD)
            except curses.error:
                pass
        # Label
        try:
            stdscr.addstr(base_y + 2, peg_x, LABELS[p],
                          curses.color_pair(COLOR_TITLE) | curses.A_BOLD)
        except curses.error:
            pass

        # Disks
        current_disk = current_move[0] if current_move else None
        for level, disk in enumerate(pegs[p]):
            disk_width = 2 * disk - 1
            y = base_y - level
            x_start = peg_x - disk_width // 2
            attr = disk_attr(disk)
            if disk == current_disk:
                attr |= curses.A_REVERSE
            if x_start >= 0 and x_start + disk_width < max_x:
                try:
                    stdscr.addstr(y, x_start, "#" * disk_width, attr)
                except curses.error:
                    pass

    stdscr.refresh()


def hanoi(stdscr, n, step_delay, history_lines, max_y, max_x):
    pegs = [list(range(n, 0, -1)), [], []]
    moves = [0]
    history = []
    cancelled = [False]
    total_moves = (1 << n) - 1

    def render(current_move=None):
        if cancelled[0]:
            return
        draw(stdscr, pegs, n, current_move, history, moves[0], total_moves,
             history_lines, max_y, max_x)
        stdscr.timeout(int(step_delay * 1000))
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            cancelled[0] = True

    def move_disk(src, dst):
        if cancelled[0]:
            return
        disk = pegs[src].pop()
        pegs[dst].append(disk)
        moves[0] += 1
        history.append((moves[0], disk, src, dst))
        render(current_move=(disk, src, dst))

    def solve(num, src, aux, dst):
        if cancelled[0] or num == 0:
            return
        solve(num - 1, src, dst, aux)
        move_disk(src, dst)
        solve(num - 1, aux, src, dst)

    render()
    solve(n, 0, 1, 2)
    if not cancelled[0]:
        render()
    return cancelled[0]


def run(stdscr, n, step_delay, completion_pause, history_lines):
    init_colors(n)
    try:
        curses.curs_set(0)
    except curses.error:
        pass

    max_y, max_x = stdscr.getmaxyx()
    cancelled = hanoi(stdscr, n, step_delay, history_lines, max_y, max_x)
    if cancelled:
        return

    stdscr.timeout(100)
    pause_start = time.monotonic()
    while time.monotonic() - pause_start < completion_pause:
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(num_disks=8, step_delay=0.15, completion_pause=3, history_lines=6):
    num_disks = int(num_disks)
    step_delay = float(step_delay)
    completion_pause = float(completion_pause)
    history_lines = max(1, int(history_lines))
    curses.wrapper(lambda stdscr: run(stdscr, num_disks, step_delay,
                                      completion_pause, history_lines))


if __name__ == "__main__":
    main()
