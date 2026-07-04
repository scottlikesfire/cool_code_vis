import curses
import math
import random
import time


PALETTE = [
    curses.COLOR_RED, curses.COLOR_YELLOW, curses.COLOR_GREEN,
    curses.COLOR_CYAN, curses.COLOR_BLUE, curses.COLOR_MAGENTA,
]
COLOR_PEG = 7
COLOR_LABEL = 8

PEG_CHAR = "^"
BALL_CHAR = "o"
BIN_CHAR = "#"
CURVE_CHAR = "·"  # '·'


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    for i, c in enumerate(PALETTE):
        curses.init_pair(i + 1, c, -1)
    curses.init_pair(COLOR_PEG, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def compute_layout(max_y, max_x, rows):
    """Fit feeder + peg pyramid + histogram into the screen.

    Returns a dict of geometry, or None if the terminal is too small.
    Roughly 40% of the usable height is reserved for the histogram bins.
    """
    usable_h = max_y - 1  # bottom line reserved for the info label
    if usable_h < 8 or max_x < 12:
        return None
    hist_h = max(3, int(usable_h * 0.4))
    peg_top = 2  # feeder at y=0, one row of air below it
    peg_area = usable_h - hist_h - peg_top - 1  # -1: gap above the bins
    rows_eff = max(2, min(int(rows), peg_area, (max_x - 4) // 2))
    row_gap = max(1, peg_area // rows_eff)
    return {
        "cx": max_x // 2,
        "rows": rows_eff,
        "peg_top": peg_top,
        "row_gap": row_gap,
        "hist_top": usable_h - hist_h,
        "floor_y": usable_h - 1,
        "hist_h": hist_h,
    }


def new_ball(color):
    return {"y": 0.0, "offset": 0, "next_row": 0, "color": color}


def peg_y(layout, row):
    return layout["peg_top"] + row * layout["row_gap"]


def advance_ball(ball, layout, counts, divisor, dy):
    """Move a ball down by dy, deflecting at each peg row it crosses.

    Returns the bin index if the ball landed, else None.
    """
    rows = layout["rows"]
    ball["y"] += dy
    while ball["next_row"] < rows and ball["y"] >= peg_y(layout, ball["next_row"]):
        ball["offset"] += random.choice((-1, 1))
        ball["next_row"] += 1
    if ball["next_row"] >= rows:
        b = (ball["offset"] + rows) // 2
        b = max(0, min(rows, b))
        top_of_stack = layout["floor_y"] - (counts[b] // divisor)
        if ball["y"] >= top_of_stack:
            return b
    return None


def expected_fraction(rows, b):
    """Binomial(rows, 0.5) probability mass for bin b."""
    return math.comb(rows, b) / (2.0 ** rows)


def run(stdscr, duration, frame_delay, rows, ball_rate, fall_speed):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    layout = None
    counts = []
    divisor = 1
    total = 0
    balls = []
    frame = 0
    color_idx = 0

    start = time.monotonic()
    last_frame = start
    while True:
        now = time.monotonic()
        if now - start >= duration:
            break
        dt = min(now - last_frame, 0.1)
        last_frame = now
        frame += 1

        max_y, max_x = stdscr.getmaxyx()
        new_layout = compute_layout(max_y, max_x, rows)

        stdscr.erase()
        if new_layout is None:
            try:
                stdscr.addstr(0, 0, "too small",
                              curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
            except curses.error:
                pass
            stdscr.refresh()
            key = stdscr.getch()
            if key in (ord("q"), ord("Q"), 27):
                return
            continue

        if layout is None or new_layout["rows"] != layout["rows"]:
            # (Re)build the board — also handles resizes that change the row count.
            counts = [0] * (new_layout["rows"] + 1)
            divisor = 1
            total = 0
            balls = []
        layout = new_layout
        n_rows = layout["rows"]
        cx = layout["cx"]

        # Spawn a new ball every ball_rate frames.
        if frame % ball_rate == 0 and len(balls) < 300:
            balls.append(new_ball(color_idx % len(PALETTE) + 1))
            color_idx += 1

        # Physics: fall, jink at pegs, land in bins.
        dy = fall_speed * dt
        landed = []
        for ball in balls:
            b = advance_ball(ball, layout, counts, divisor, dy)
            if b is not None:
                counts[b] += 1
                total += 1
                landed.append(ball)
        for ball in landed:
            balls.remove(ball)

        # If any bin column reaches the top of the histogram area, rescale.
        while max(counts) // divisor >= layout["hist_h"]:
            divisor *= 2

        # Feeder.
        try:
            stdscr.addstr(0, cx, "v", curses.color_pair(COLOR_PEG) | curses.A_BOLD)
        except curses.error:
            pass

        # Pegs (dim white).
        peg_attr = curses.color_pair(COLOR_PEG) | curses.A_DIM
        for r in range(n_rows):
            y = peg_y(layout, r)
            for k in range(r + 1):
                x = cx - r + 2 * k
                if 0 <= x < max_x:
                    try:
                        stdscr.addstr(y, x, PEG_CHAR, peg_attr)
                    except curses.error:
                        pass

        # Histogram bins, colored per bin, stacked up from the floor.
        floor_y = layout["floor_y"]
        for b in range(n_rows + 1):
            h = counts[b] // divisor
            if h <= 0:
                continue
            x = cx - n_rows + 2 * b
            if not (0 <= x < max_x):
                continue
            attr = curses.color_pair(b % len(PALETTE) + 1)
            for i in range(h):
                try:
                    stdscr.addstr(floor_y - i, x, BIN_CHAR, attr)
                except curses.error:
                    pass

        # Balls in flight (bright rotating colors).
        for ball in balls:
            x = cx + ball["offset"]
            y = int(ball["y"])
            if 0 <= x < max_x and 0 <= y <= floor_y:
                try:
                    stdscr.addstr(y, x, BALL_CHAR,
                                  curses.color_pair(ball["color"]) | curses.A_BOLD)
                except curses.error:
                    pass

        # Expected binomial curve, once enough balls have landed.
        if total > 80:
            curve_attr = curses.color_pair(COLOR_PEG) | curses.A_DIM
            for b in range(n_rows + 1):
                exp_h = expected_fraction(n_rows, b) * total / divisor
                y = floor_y - int(round(exp_h))
                y = max(layout["hist_top"], min(floor_y, y))
                x = cx - n_rows + 2 * b
                if 0 <= x < max_x:
                    try:
                        stdscr.addstr(y, x, CURVE_CHAR, curve_attr)
                    except curses.error:
                        pass

        sigma = math.sqrt(n_rows) / 2.0
        info = (f"Galton Board  balls={total} rows={n_rows} "
                f"σ≈{sigma:.2f} bins  rate=1/{ball_rate}f fall={fall_speed}")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def main(duration=30, frame_delay=0.04, rows=10, ball_rate=3, fall_speed=14.0):
    """Galton board (bean machine) building a bell curve.

    ball_rate is the spawn interval in frames (one new ball every
    ball_rate frames); fall_speed is in terminal cells per second.
    """
    duration = float(duration)
    frame_delay = float(frame_delay)
    rows = max(2, int(rows))
    ball_rate = max(1, int(ball_rate))
    fall_speed = float(fall_speed)
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, rows, ball_rate, fall_speed))


if __name__ == "__main__":
    main()
