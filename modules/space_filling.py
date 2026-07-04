"""Space-filling curves drawn stroke by stroke.

Hilbert curves (order 3 -> 4 -> 5) and dragon curves (iteration 8 -> 10 -> 12)
are traced segment by segment with a moving draw-head, then the module pauses,
clears, and deepens to the next order.  The finished path is colored as a
rainbow gradient of traversal order.
"""

import curses
import time


PALETTE = [
    curses.COLOR_RED, curses.COLOR_YELLOW, curses.COLOR_GREEN,
    curses.COLOR_CYAN, curses.COLOR_BLUE, curses.COLOR_MAGENTA,
]
COLOR_LABEL = 7

HILBERT_ORDERS = [3, 4, 5]
DRAGON_ITERS = [8, 10, 12]
MAX_HILBERT_ORDER = 6
MIN_DRAGON_ITER = 4

# Box-drawing char keyed by the frozenset of "openings" (directions in which
# the path leaves this cell), in grid coords where y grows downward.
UP, DOWN, LEFT, RIGHT = (0, -1), (0, 1), (-1, 0), (1, 0)
JOINT_CHARS = {
    frozenset((LEFT, RIGHT)): "─",
    frozenset((UP, DOWN)): "│",
    frozenset((UP, RIGHT)): "└",
    frozenset((UP, LEFT)): "┘",
    frozenset((DOWN, RIGHT)): "┌",
    frozenset((DOWN, LEFT)): "┐",
    frozenset((LEFT,)): "─",
    frozenset((RIGHT,)): "─",
    frozenset((UP,)): "│",
    frozenset((DOWN,)): "│",
}


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    for i, c in enumerate(PALETTE):
        curses.init_pair(i + 1, c, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def hilbert_points(order):
    """Point sequence of the Hilbert curve at the given order (d2xy)."""
    n = 1 << order
    pts = []
    for d in range(n * n):
        x = y = 0
        t = d
        s = 1
        while s < n:
            rx = 1 & (t >> 1)
            ry = 1 & (t ^ rx)
            if ry == 0:
                if rx == 1:
                    x = s - 1 - x
                    y = s - 1 - y
                x, y = y, x
            x += s * rx
            y += s * ry
            t >>= 2
            s <<= 1
        pts.append((x, y))
    return pts


def dragon_turns(iterations):
    """L/R turn sequence (+1 = left, -1 = right) after `iterations` folds."""
    turns = []
    for _ in range(iterations):
        turns = turns + [1] + [-t for t in reversed(turns)]
    return turns


def dragon_points(iterations):
    """Point sequence of the dragon curve, normalized to start at (0, 0)."""
    x, y = 0, 0
    dx, dy = 1, 0
    pts = [(x, y)]
    x, y = x + dx, y + dy
    pts.append((x, y))
    for turn in dragon_turns(iterations):
        if turn == 1:
            dx, dy = dy, -dx
        else:
            dx, dy = -dy, dx
        x, y = x + dx, y + dy
        pts.append((x, y))
    min_x = min(p[0] for p in pts)
    min_y = min(p[1] for p in pts)
    return [(px - min_x, py - min_y) for px, py in pts]


def point_chars(pts):
    """Final joint char for each point, from its incoming/outgoing dirs."""
    chars = []
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        openings = set()
        if i > 0:
            px, py = pts[i - 1]
            openings.add((px - x, py - y))
        if i < n - 1:
            nx, ny = pts[i + 1]
            openings.add((nx - x, ny - y))
        chars.append(JOINT_CHARS.get(frozenset(openings), "+"))
    return chars


def band_color(i, total):
    """Rainbow color pair (1..6) for position i of total along the curve."""
    band = i * len(PALETTE) // max(1, total)
    return curses.color_pair(min(band, len(PALETTE) - 1) + 1)


def fit_hilbert_order(order, max_x, max_y):
    """Largest order <= requested whose 2^o x 2^o grid fits the terminal."""
    order = min(order, MAX_HILBERT_ORDER)
    while order > 1:
        side = 1 << order
        if 2 * side - 1 <= max_x and side <= max_y - 1:
            break
        order -= 1
    return order


def fit_dragon_iter(iterations, max_x, max_y):
    """Reduce iterations until the dragon's bounding box fits the terminal."""
    while iterations > MIN_DRAGON_ITER:
        pts = dragon_points(iterations)
        gw = max(p[0] for p in pts) + 1
        gh = max(p[1] for p in pts) + 1
        if 2 * gw - 1 <= max_x and gh <= max_y - 1:
            break
        iterations -= 1
    return iterations


def build_stages(curve):
    stages = []
    if curve in ("both", "hilbert"):
        stages += [("hilbert", k) for k in HILBERT_ORDERS]
    if curve in ("both", "dragon"):
        stages += [("dragon", k) for k in DRAGON_ITERS]
    return stages


def draw_curve(stdscr, pts, chars, revealed, label, show_head):
    """Redraw the first `revealed` segments of the curve, centered."""
    max_y, max_x = stdscr.getmaxyx()
    gw = max(p[0] for p in pts) + 1
    gh = max(p[1] for p in pts) + 1
    off_x = max(0, (max_x - (2 * gw - 1)) // 2)
    off_y = max(0, (max_y - 1 - gh) // 2)
    total = len(pts) - 1

    stdscr.erase()
    for i in range(revealed + 1):
        x, y = pts[i]
        sy, sx = off_y + y, off_x + 2 * x
        if not (0 <= sy < max_y - 1 and 0 <= sx < max_x):
            continue
        attr = band_color(i, total + 1)
        try:
            stdscr.addstr(sy, sx, chars[i], attr)
        except curses.error:
            pass
        # Fill the in-between cell of a horizontal segment (cells are 2:1).
        if i < revealed:
            x2, y2 = pts[i + 1]
            if y2 == y:
                mx = off_x + 2 * min(x, x2) + 1
                if 0 <= mx < max_x:
                    try:
                        stdscr.addstr(sy, mx, "─", attr)
                    except curses.error:
                        pass

    if show_head:
        hx, hy = pts[revealed]
        sy, sx = off_y + hy, off_x + 2 * hx
        if 0 <= sy < max_y - 1 and 0 <= sx < max_x:
            try:
                stdscr.addstr(sy, sx, "@",
                              band_color(revealed, total + 1) | curses.A_BOLD)
            except curses.error:
                pass

    try:
        stdscr.addstr(max_y - 1, 2, label[:max_x - 4],
                      curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
    except curses.error:
        pass
    stdscr.refresh()


def run(stdscr, duration, frame_delay, segments_per_frame, curve, pause_time):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    stages = build_stages(curve)
    start = time.monotonic()
    stage_idx = 0
    pts = chars = None
    stage_key = None  # (name, depth, term size) that pts were built for
    revealed = 0
    pause_until = None

    while True:
        if time.monotonic() - start >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        name, depth = stages[stage_idx % len(stages)]

        # (Re)build the point sequence on stage change or terminal resize.
        if name == "hilbert":
            eff = fit_hilbert_order(depth, max_x, max_y)
            kind = "order"
        else:
            eff = fit_dragon_iter(depth, max_x, max_y)
            kind = "iter"
        key = (name, eff, max_x, max_y)
        if key != stage_key:
            if stage_key is not None and stage_key[:2] != (name, eff):
                revealed = 0
                pause_until = None
            stage_key = key
            if name == "hilbert":
                pts = hilbert_points(eff)
            else:
                pts = dragon_points(eff)
            chars = point_chars(pts)
            revealed = min(revealed, len(pts) - 1)

        total = len(pts) - 1
        if pause_until is None:
            revealed = min(total, revealed + segments_per_frame)
        drawing = revealed < total

        label = (f"Space-Filling  {name.capitalize()} {kind}={eff}  "
                 f"segments={revealed}/{total}  spf={segments_per_frame}")
        draw_curve(stdscr, pts, chars, revealed, label, show_head=drawing)

        key_in = stdscr.getch()
        if key_in in (ord("q"), ord("Q"), 27):
            return
        if key_in == curses.KEY_RESIZE:
            continue

        if not drawing:
            now = time.monotonic()
            if pause_until is None:
                pause_until = now + pause_time
            elif now >= pause_until:
                stage_idx += 1
                stage_key = None
                revealed = 0
                pause_until = None


def main(duration=30, frame_delay=0.02, segments_per_frame=20,
         curve="both", pause_time=1.5):
    duration = float(duration)
    frame_delay = float(frame_delay)
    segments_per_frame = max(1, int(segments_per_frame))
    curve = str(curve).strip().lower()
    if curve not in ("both", "hilbert", "dragon"):
        curve = "both"
    pause_time = max(0.0, float(pause_time))
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, segments_per_frame, curve, pause_time))


if __name__ == "__main__":
    main()
