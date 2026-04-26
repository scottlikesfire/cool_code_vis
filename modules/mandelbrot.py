import curses
import math
import random
import time


GRADIENT = " .:-=+*#%@"

# Well-known high-precision zoom targets that stay interesting at depth
# Each entry: (name, x, y)
ZOOM_TARGETS = [
    ("Seahorse Valley",   -0.743643887037158704752191506114774,
                           0.131825904205311970493132056385139),
    ("Misiurewicz Point", -0.77568377, 0.13646737),
    ("Triple Spiral",     -1.7400623825, 0.0028760626),
    ("Spiral Twist",       0.001643721971153, -0.822467633298876),
    ("Mini Mandelbrot",   -0.10109636384562, 0.95628651080914),
    ("Seahorse Detail",   -0.74364990, 0.13188204),
]

# Float64 precision starts breaking down past ~1e13
MAX_ZOOM = 1e13


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    palette = [
        curses.COLOR_BLUE,
        curses.COLOR_CYAN,
        curses.COLOR_GREEN,
        curses.COLOR_YELLOW,
        curses.COLOR_RED,
        curses.COLOR_MAGENTA,
    ]
    for i, color in enumerate(palette):
        curses.init_pair(i + 1, color, -1)
    curses.init_pair(len(palette) + 1, curses.COLOR_WHITE, -1)
    return len(palette)


def adaptive_iter(base_iter, zoom):
    """Increase iterations as zoom deepens to keep detail resolved."""
    return int(base_iter + math.log10(max(zoom, 1.0)) * 60)


def render_frame(stdscr, cx, cy, zoom, max_iter, num_colors, target_name, max_y, max_x):
    """Render one mandelbrot frame at the given center and zoom."""
    aspect = 2.0  # characters are taller than wide
    width = 3.0 / zoom
    height = width / (max_x / max_y) / aspect

    inside_count = 0
    total = 0

    stdscr.erase()
    for sy in range(max_y - 1):
        for sx in range(max_x - 1):
            x0 = cx + (sx / max_x - 0.5) * width
            y0 = cy + (sy / max_y - 0.5) * height
            x = y = 0.0
            i = 0
            while x * x + y * y <= 4 and i < max_iter:
                x, y = x * x - y * y + x0, 2 * x * y + y0
                i += 1
            total += 1
            if i >= max_iter:
                inside_count += 1
                ch = " "
                attr = 0
            else:
                ch = GRADIENT[i % len(GRADIENT)]
                color_pair = (i % num_colors) + 1
                attr = curses.color_pair(color_pair) | curses.A_BOLD
            try:
                stdscr.addstr(sy, sx, ch, attr)
            except curses.error:
                pass

    info = (f"Mandelbrot visualization with zoom target \"{target_name}\"  "
            f"|  zoom: {zoom:.2e}  |  iter: {max_iter}")
    try:
        stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                      curses.color_pair(num_colors + 1) | curses.A_BOLD)
    except curses.error:
        pass
    stdscr.refresh()

    inside_ratio = inside_count / total if total else 0
    return inside_ratio


def run(stdscr, duration, zoom_factor, base_iter, frame_delay):
    num_colors = init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    max_y, max_x = stdscr.getmaxyx()
    target_name, cx, cy = random.choice(ZOOM_TARGETS)
    zoom = 1.0
    start_time = time.monotonic()

    while True:
        if time.monotonic() - start_time >= duration:
            break

        max_iter = adaptive_iter(base_iter, zoom)
        inside_ratio = render_frame(stdscr, cx, cy, zoom, max_iter,
                                    num_colors, target_name, max_y, max_x)

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return

        zoom *= zoom_factor

        # Reset if we hit precision limit or the view collapses to a single value
        if zoom > MAX_ZOOM or inside_ratio > 0.95 or inside_ratio < 0.005:
            target_name, cx, cy = random.choice(ZOOM_TARGETS)
            zoom = 1.0


def main(duration=20, zoom_factor=1.15, base_iter=80, frame_delay=0.05):
    duration = float(duration)
    zoom_factor = float(zoom_factor)
    base_iter = int(base_iter)
    frame_delay = float(frame_delay)
    curses.wrapper(lambda stdscr: run(stdscr, duration, zoom_factor,
                                      base_iter, frame_delay))


if __name__ == "__main__":
    main()
