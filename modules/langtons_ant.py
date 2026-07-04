import curses
import random
import time


ANT_PALETTE = [
    curses.COLOR_RED, curses.COLOR_YELLOW, curses.COLOR_GREEN,
    curses.COLOR_MAGENTA, curses.COLOR_CYAN, curses.COLOR_WHITE,
]
STATE_PALETTE = [
    curses.COLOR_BLUE, curses.COLOR_GREEN, curses.COLOR_YELLOW,
    curses.COLOR_MAGENTA, curses.COLOR_RED, curses.COLOR_CYAN,
]
COLOR_LABEL = 15

# Chars for cell states; state 0 = blank, nonzero states get denser glyphs.
STATE_CHARS = [" ", ".", ":", "#", "@", "%", "&"]

# Headings: 0=up, 1=right, 2=down, 3=left  -> (dy, dx)
HEADINGS = [(-1, 0), (0, 1), (1, 0), (0, -1)]
ANT_CHARS = ["^", ">", "v", "<"]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    for i, c in enumerate(ANT_PALETTE):
        curses.init_pair(i + 1, c, -1)
    for i, c in enumerate(STATE_PALETTE):
        curses.init_pair(len(ANT_PALETTE) + i + 1, c, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def ant_attr(idx):
    return curses.color_pair((idx % len(ANT_PALETTE)) + 1) | curses.A_BOLD


def state_char(state):
    if state <= 0:
        return " "
    return STATE_CHARS[(state - 1) % (len(STATE_CHARS) - 1) + 1]


def state_attr(state):
    if state <= 0:
        return curses.A_NORMAL
    return curses.color_pair(len(ANT_PALETTE) + ((state - 1) % len(STATE_PALETTE)) + 1)


def random_rule():
    length = random.randint(2, 6)
    rule = [random.choice("LR") for _ in range(length)]
    # Guarantee at least one of each turn so the ant isn't just spinning.
    if "L" not in rule:
        rule[random.randrange(length)] = "L"
    if "R" not in rule:
        rule[random.randrange(length)] = "R"
    return "".join(rule)


def make_ants(num_ants, h, w):
    ants = []
    for i in range(num_ants):
        ants.append({
            "y": random.randrange(h),
            "x": random.randrange(w),
            "dir": random.randrange(4),
            "color": i,
        })
    return ants


def step_ant(ant, grid, rule, h, w, dirty):
    """Advance one ant a single step on the wrapping grid.

    Records the mutated cell in `dirty` (a set of (y, x) tuples).
    """
    y, x = ant["y"], ant["x"]
    state = grid[y][x]
    turn = rule[state % len(rule)]
    if turn == "L":
        ant["dir"] = (ant["dir"] - 1) % 4
    else:
        ant["dir"] = (ant["dir"] + 1) % 4
    grid[y][x] = (state + 1) % len(rule)
    dirty.add((y, x))
    dy, dx = HEADINGS[ant["dir"]]
    ant["y"] = (y + dy) % h
    ant["x"] = (x + dx) % w


def run(stdscr, duration, frame_delay, num_ants, rule, steps_per_frame):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    max_y, max_x = stdscr.getmaxyx()
    h = max(1, max_y - 1)  # bottom line reserved for label
    w = max(1, max_x)
    grid = [[0] * w for _ in range(h)]
    ants = make_ants(num_ants, h, w)

    stdscr.erase()
    label_drawn = False
    prev_ant_cells = set()
    start = time.monotonic()
    while True:
        if time.monotonic() - start >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        new_h = max(1, max_y - 1)
        new_w = max(1, max_x)
        if new_h != h or new_w != w:
            # Terminal resized: rebuild the world and repaint from scratch.
            h, w = new_h, new_w
            grid = [[0] * w for _ in range(h)]
            ants = make_ants(num_ants, h, w)
            prev_ant_cells = set()
            stdscr.erase()
            label_drawn = False

        dirty = set(prev_ant_cells)
        for i in range(steps_per_frame):
            step_ant(ants[i % num_ants], grid, rule, h, w, dirty)

        # Redraw only cells that changed (plus cells ants vacated).
        for (cy, cx) in dirty:
            if cy < h and cx < w:
                try:
                    stdscr.addstr(cy, cx, state_char(grid[cy][cx]),
                                  state_attr(grid[cy][cx]))
                except curses.error:
                    pass

        ant_cells = set()
        for ant in ants:
            ay, ax = ant["y"], ant["x"]
            ant_cells.add((ay, ax))
            if ay < h and ax < w:
                try:
                    stdscr.addstr(ay, ax, ANT_CHARS[ant["dir"]],
                                  ant_attr(ant["color"]))
                except curses.error:
                    pass
        prev_ant_cells = ant_cells

        if not label_drawn:
            info = (f"Langton's Ant  rule={rule}  ants={num_ants}  "
                    f"steps/frame={steps_per_frame}")
            try:
                stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                              curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
            except curses.error:
                pass
            label_drawn = True

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def main(duration=30, frame_delay=0.04, num_ants=3, rule="LR",
         steps_per_frame=120):
    duration = float(duration)
    frame_delay = float(frame_delay)
    num_ants = max(1, int(num_ants))
    steps_per_frame = max(1, int(steps_per_frame))
    rule = str(rule).strip().upper()
    if rule == "RANDOM":
        rule = random_rule()
    if len(rule) < 2 or any(c not in "LR" for c in rule):
        rule = "LR"
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, num_ants, rule, steps_per_frame))


if __name__ == "__main__":
    main()
