import curses
import random
import time


COLOR_ON = 1
COLOR_FRESH = 2
COLOR_LABEL = 3


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_ON, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_FRESH, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


# Hand-picked rules with visually rich output
INTERESTING_RULES = [30, 45, 73, 90, 105, 110, 150, 184]


def step_row(row, rule):
    """Apply 1D Wolfram rule to a row (list of 0/1). Wraps at the edges."""
    n = len(row)
    new = [0] * n
    for i in range(n):
        left = row[(i - 1) % n]
        center = row[i]
        right = row[(i + 1) % n]
        idx = (left << 2) | (center << 1) | right
        new[i] = (rule >> idx) & 1
    return new


def run(stdscr, duration, frame_delay, rule, seed_mode):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    # Force a full physical clear so leftover characters from a previous
    # module aren't visible through the cells we never write to (the rule
    # only draws '#' for live cells; dead cells are skipped, so without this
    # erase() alone won't repaint their positions).
    stdscr.clear()
    stdscr.refresh()
    stdscr.timeout(int(frame_delay * 1000))

    if rule == "random":
        rule_num = random.choice(INTERESTING_RULES)
    else:
        rule_num = int(rule)

    max_y, max_x = stdscr.getmaxyx()
    width = max_x

    # Initial row
    if seed_mode == "single":
        row = [0] * width
        row[width // 2] = 1
    elif seed_mode == "random":
        row = [random.randint(0, 1) for _ in range(width)]
    else:
        row = [0] * width
        row[width // 2] = 1

    # Buffer of rows; oldest at top, newest at bottom
    buffer = [row]
    start = time.monotonic()

    while True:
        now = time.monotonic()
        if now - start >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        # Resize the buffer width if terminal changed
        if len(buffer[-1]) != max_x:
            new_width = max_x
            buffer = [r[:new_width] + [0] * (new_width - len(r))
                      if len(r) < new_width else r[:new_width] for r in buffer]

        # Generate one new row from the previous newest
        next_row = step_row(buffer[-1], rule_num)
        buffer.append(next_row)

        max_rows = max_y - 2
        if len(buffer) > max_rows:
            buffer = buffer[-max_rows:]

        stdscr.erase()
        for y, r in enumerate(buffer):
            is_newest = (y == len(buffer) - 1)
            attr = (curses.color_pair(COLOR_FRESH) | curses.A_BOLD if is_newest
                    else curses.color_pair(COLOR_ON))
            for x, v in enumerate(r):
                if v and 0 <= x < max_x:
                    try:
                        stdscr.addstr(y, x, "#", attr)
                    except curses.error:
                        pass

        info = f"Wolfram rule {rule_num}  seed={seed_mode}  generation {len(buffer)}"
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=20, frame_delay=0.04, rule="random", seed_mode="single"):
    duration = float(duration)
    frame_delay = float(frame_delay)
    if seed_mode not in ("single", "random"):
        seed_mode = "single"
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, rule, seed_mode))


if __name__ == "__main__":
    main()
