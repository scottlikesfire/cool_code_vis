import curses
import math
import random
import time
from collections import deque


PALETTE = [
    curses.COLOR_RED, curses.COLOR_YELLOW, curses.COLOR_GREEN,
    curses.COLOR_CYAN, curses.COLOR_BLUE, curses.COLOR_MAGENTA,
]
COLOR_LABEL = 7
COLOR_BRIGHT = 8

X_SCALE = 2.0  # terminal cells are ~2:1 tall, stretch x so curves look round

TRAIL_CHARS = [".", "*", "o"]  # dim -> mid -> bright body chars
PEN_CHAR = "@"


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    for i, c in enumerate(PALETTE):
        curses.init_pair(i + 1, c, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_BRIGHT, curses.COLOR_WHITE, -1)


def new_curve(prev_kind=None):
    """Pick random spirograph parameters with an integer R/r ratio so the
    curve closes.  Alternates hypotrochoid / epitrochoid."""
    if prev_kind == "hypo":
        kind = "epi"
    elif prev_kind == "epi":
        kind = "hypo"
    else:
        kind = random.choice(["hypo", "epi"])

    R = random.randint(5, 12)
    r = random.randint(1, max(1, R - 1))
    # keep the ratio interesting (avoid degenerate circles when R == r)
    while r == R:
        r = random.randint(1, max(1, R - 1))
    d = round(random.uniform(0.5, 1.6) * r, 1)
    period = 2 * math.pi * r / math.gcd(R, r)
    color = random.randint(1, len(PALETTE))
    return {"kind": kind, "R": R, "r": r, "d": d,
            "period": period, "color": color}


def curve_point(curve, t):
    """Return (x, y) on the curve at parameter t (unscaled model coords)."""
    R, r, d = curve["R"], curve["r"], curve["d"]
    if curve["kind"] == "hypo":
        a = R - r
        k = a / r
        x = a * math.cos(t) + d * math.cos(k * t)
        y = a * math.sin(t) - d * math.sin(k * t)
    else:
        a = R + r
        k = a / r
        x = a * math.cos(t) + d * math.cos(k * t)
        y = a * math.sin(t) - d * math.sin(k * t)
    return x, y


def curve_extent(curve):
    """Maximum radius the curve can reach, for fitting to the screen."""
    R, r, d = curve["R"], curve["r"], curve["d"]
    if curve["kind"] == "hypo":
        return (R - r) + d
    return (R + r) + d


def project(x, y, max_x, max_y, extent):
    """Map model coords to screen cell, keeping aspect roughly round."""
    usable_h = max(1, max_y - 1)
    scale = min((max_x - 2) / (2.0 * extent * X_SCALE),
                (usable_h - 1) / (2.0 * extent))
    scale = max(scale, 0.01)
    cx = max_x / 2.0
    cy = usable_h / 2.0
    sx = int(round(cx + x * scale * X_SCALE))
    sy = int(round(cy + y * scale))
    return sx, sy


def trail_attr(age_frac, color):
    """Attribute for a trail point given its age fraction (0=newest)."""
    if age_frac < 0.15:
        return curses.color_pair(COLOR_BRIGHT) | curses.A_BOLD, TRAIL_CHARS[2]
    if age_frac < 0.55:
        return curses.color_pair(color) | curses.A_BOLD, TRAIL_CHARS[2]
    if age_frac < 0.85:
        return curses.color_pair(color), TRAIL_CHARS[1]
    return curses.color_pair(color) | curses.A_DIM, TRAIL_CHARS[0]


def run(stdscr, duration, frame_delay, speed, trail_len, hold_time):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    curve = new_curve()
    trail = deque(maxlen=trail_len)
    t = 0.0
    holding_until = None  # monotonic time when hold ends, or None

    start = time.monotonic()
    last_frame = start
    while True:
        now = time.monotonic()
        if now - start >= duration:
            break
        dt = min(now - last_frame, 0.1)
        last_frame = now

        max_y, max_x = stdscr.getmaxyx()
        extent = curve_extent(curve)

        if holding_until is not None:
            if now >= holding_until:
                curve = new_curve(curve["kind"])
                trail = deque(maxlen=trail_len)
                t = 0.0
                holding_until = None
        else:
            # advance the pen, interpolating sub-steps so the line is solid
            t_new = t + speed * dt
            # enough sub-steps that consecutive points are < ~1 cell apart
            steps = max(1, int(speed * dt / 0.01))
            for i in range(1, steps + 1):
                ti = t + (t_new - t) * i / steps
                trail.append(curve_point(curve, ti))
            t = t_new
            if t >= curve["period"]:
                holding_until = now + hold_time

        stdscr.erase()

        n = len(trail)
        complete = holding_until is not None
        for idx, (px, py) in enumerate(trail):
            sx, sy = project(px, py, max_x, max_y, extent)
            if 0 <= sx < max_x and 0 <= sy < max_y - 1:
                if complete:
                    attr = curses.color_pair(curve["color"]) | curses.A_BOLD
                    ch = TRAIL_CHARS[2]
                else:
                    age_frac = 1.0 - (idx + 1) / n
                    attr, ch = trail_attr(age_frac, curve["color"])
                try:
                    stdscr.addstr(sy, sx, ch, attr)
                except curses.error:
                    pass

        if not complete and n > 0:
            px, py = trail[-1]
            sx, sy = project(px, py, max_x, max_y, extent)
            if 0 <= sx < max_x and 0 <= sy < max_y - 1:
                try:
                    stdscr.addstr(sy, sx, PEN_CHAR,
                                  curses.color_pair(COLOR_BRIGHT)
                                  | curses.A_BOLD)
                except curses.error:
                    pass

        kind_name = ("hypotrochoid" if curve["kind"] == "hypo"
                     else "epitrochoid")
        info = (f"Spirograph  {kind_name}  R={curve['R']} r={curve['r']} "
                f"d={curve['d']}  speed={speed}")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max(0, max_x - 4)],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def main(duration=30, frame_delay=0.03, speed=2.5, trail_len=1200,
         hold_time=2.0):
    duration = float(duration)
    frame_delay = float(frame_delay)
    speed = float(speed)
    trail_len = max(10, int(trail_len))
    hold_time = float(hold_time)
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, speed, trail_len, hold_time))


if __name__ == "__main__":
    main()
