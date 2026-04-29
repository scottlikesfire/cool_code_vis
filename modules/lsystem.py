import curses
import math
import random
import time


COLOR_DRAW = 1
COLOR_TURTLE = 2
COLOR_LABEL = 3
PALETTE = [
    curses.COLOR_GREEN, curses.COLOR_CYAN, curses.COLOR_YELLOW,
    curses.COLOR_MAGENTA, curses.COLOR_RED, curses.COLOR_BLUE,
]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    for i, c in enumerate(PALETTE):
        curses.init_pair(i + 1, c, -1)
    curses.init_pair(len(PALETTE) + 1, curses.COLOR_WHITE, -1)
    curses.init_pair(len(PALETTE) + 2, curses.COLOR_CYAN, -1)


# (axiom, rules, angle_deg, iterations, step_factor, start_heading_deg, name)
PRESETS = {
    "fractal_tree":   ("F", {"F": "FF+[+F-F-F]-[-F+F+F]"}, 22.5, 4,  0.45,  90, "Fractal tree"),
    "koch":           ("F", {"F": "F+F-F-F+F"},             90.0, 4,  0.55,   0, "Koch curve"),
    "koch_snowflake": ("F++F++F", {"F": "F-F++F-F"},        60.0, 4,  0.55,   0, "Koch snowflake"),
    "sierpinski":     ("A", {"A": "B-A-B", "B": "A+B+A"},   60.0, 6,  0.55,   0, "Sierpinski triangle"),
    "dragon":         ("FX", {"X": "X+YF+", "Y": "-FX-Y"},  90.0, 11, 0.55,   0, "Dragon curve"),
    "plant":          ("X", {"X": "F+[[X]-X]-F[-FX]+X",
                             "F": "FF"},                     25.0, 5,  0.45,  90, "Bushy plant"),
    "sierpinski_arrowhead": ("A", {"A": "B-A-B", "B": "A+B+A"}, 60.0, 6, 0.55, 0, "Sierpinski arrowhead"),
}


def expand(axiom, rules, iterations):
    s = axiom
    for _ in range(iterations):
        out = []
        for ch in s:
            out.append(rules.get(ch, ch))
        s = "".join(out)
    return s


def compute_path(s, angle_deg, start_heading_deg):
    """Walk the L-system instructions and return:
      - segments: list of ((x0,y0),(x1,y1)) line segments to draw
      - bbox: (xmin, ymin, xmax, ymax)
    """
    angle = math.radians(angle_deg)
    heading = math.radians(start_heading_deg)
    x = y = 0.0
    segments = []
    stack = []
    xmin = xmax = ymin = ymax = 0.0
    for ch in s:
        if ch in ("F", "A", "B"):
            nx = x + math.cos(heading)
            ny = y - math.sin(heading)  # screen y is down
            segments.append(((x, y), (nx, ny)))
            x, y = nx, ny
            xmin = min(xmin, x); xmax = max(xmax, x)
            ymin = min(ymin, y); ymax = max(ymax, y)
        elif ch == "f":
            x += math.cos(heading)
            y -= math.sin(heading)
        elif ch == "+":
            heading += angle
        elif ch == "-":
            heading -= angle
        elif ch == "[":
            stack.append((x, y, heading))
        elif ch == "]":
            if stack:
                x, y, heading = stack.pop()
    return segments, (xmin, ymin, xmax, ymax)


def draw_segment(stdscr, x0, y0, x1, y1, ch, attr, max_y, max_x):
    dx = x1 - x0
    dy = y1 - y0
    steps = max(1, int(round(max(abs(dx), abs(dy)))))
    for k in range(steps + 1):
        t = k / steps
        xi = int(round(x0 + t * dx))
        yi = int(round(y0 + t * dy))
        if 0 <= xi < max_x and 0 <= yi < max_y - 1:
            try:
                stdscr.addstr(yi, xi, ch, attr)
            except curses.error:
                pass


def run(stdscr, duration, frame_delay, preset, segments_per_frame,
        completion_pause):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.clear()
    stdscr.refresh()
    stdscr.timeout(int(frame_delay * 1000))

    if preset == "random" or preset not in PRESETS:
        preset = random.choice(list(PRESETS.keys()))

    axiom, rules, angle_deg, iters, step_factor, heading0, label = PRESETS[preset]
    s = expand(axiom, rules, iters)
    segments, (xmin, ymin, xmax, ymax) = compute_path(s, angle_deg, heading0)

    max_y, max_x = stdscr.getmaxyx()
    canvas_w = max_x - 4
    canvas_h = max_y - 3
    extent_x = max(1e-6, xmax - xmin)
    extent_y = max(1e-6, ymax - ymin)
    # x scaled 2× for terminal char aspect (chars are ~2× tall as wide)
    scale = min(canvas_w / (extent_x * 2), canvas_h / extent_y) * step_factor
    cx = (max_x / 2) - (xmin + xmax) * scale
    cy = (max_y / 2) - (ymin + ymax) * scale * 0.5

    def project(p):
        return cx + p[0] * scale * 2, cy + p[1] * scale

    color = random.randint(1, len(PALETTE))
    line_attr = curses.color_pair(color) | curses.A_BOLD
    head_attr = curses.color_pair(len(PALETTE) + 1) | curses.A_BOLD | curses.A_REVERSE
    label_attr = curses.color_pair(len(PALETTE) + 2) | curses.A_BOLD | curses.A_REVERSE

    drawn = 0
    total = len(segments)
    finished = False
    finished_at = 0.0
    start = time.monotonic()

    while True:
        now = time.monotonic()
        elapsed = now - start
        if elapsed >= duration:
            break
        if finished and now - finished_at >= completion_pause:
            break

        # Add up to segments_per_frame more segments to the canvas
        end = drawn + segments_per_frame
        if end >= total:
            end = total
            finished = True
            finished_at = now

        # We don't redraw from scratch each frame — we just append.
        for i in range(drawn, end):
            (p0, p1) = segments[i]
            sx0, sy0 = project(p0)
            sx1, sy1 = project(p1)
            draw_segment(stdscr, sx0, sy0, sx1, sy1, "*", line_attr,
                         max_y, max_x)
        drawn = end

        # Highlight the current "turtle" position briefly each frame
        if drawn < total and drawn > 0:
            (_, p1) = segments[drawn - 1]
            sx, sy = project(p1)
            xi, yi = int(round(sx)), int(round(sy))
            if 0 <= xi < max_x and 0 <= yi < max_y - 1:
                try:
                    stdscr.addstr(yi, xi, "@", head_attr)
                except curses.error:
                    pass

        info = (f" L-system: {label}   axiom={axiom!r}   iters={iters}   "
                f"angle={angle_deg}°   {drawn}/{total} segments ")
        info = info.ljust(max(0, max_x - 1))[:max(0, max_x - 1)]
        try:
            stdscr.addstr(max_y - 1, 0, info, label_attr)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=25, frame_delay=0.03, preset="random",
         segments_per_frame=80, completion_pause=4):
    duration = float(duration)
    frame_delay = float(frame_delay)
    segments_per_frame = max(1, int(segments_per_frame))
    completion_pause = float(completion_pause)
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, preset, segments_per_frame,
        completion_pause))


if __name__ == "__main__":
    main()
