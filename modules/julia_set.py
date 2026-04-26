import curses
import math
import random
import time


GRADIENT = " .:-=+*#%@"

# Interesting Julia set c values to start the animation from
# Each entry: (name, cr, ci)
JULIA_TARGETS = [
    ("Dendrite",         -0.7,      0.27015),
    ("Douady's Rabbit",  -0.8,      0.156),
    ("Spiral",            0.285,    0.01),
    ("Siegel Disk",      -0.4,      0.6),
    ("Twisted",          -0.835,   -0.2321),
    ("Feather",           0.45,     0.1428),
    ("Delicate",         -0.74543,  0.11301),
    ("Symmetric",         0.355,    0.355),
]


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
    return len(palette)


def render_frame(stdscr, cr, ci, max_iter, num_colors, target_name, max_y, max_x):
    """Render one Julia set frame for the constant c = cr + ci*i."""
    aspect = 2.0
    width = 3.5
    height = width / (max_x / max_y) / aspect

    stdscr.erase()
    for sy in range(max_y - 1):
        for sx in range(max_x - 1):
            x = (sx / max_x - 0.5) * width
            y = (sy / max_y - 0.5) * height
            i = 0
            while x * x + y * y <= 4 and i < max_iter:
                x, y = x * x - y * y + cr, 2 * x * y + ci
                i += 1
            if i >= max_iter:
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

    sign = "+" if ci >= 0 else "-"
    info = (f"Julia Set visualization with constant \"{target_name}\"  "
            f"|  c = {cr:.4f} {sign} {abs(ci):.4f}i  |  iter: {max_iter}")
    try:
        stdscr.addstr(max_y - 1, 2, info[:max_x - 4], curses.A_BOLD)
    except curses.error:
        pass
    stdscr.refresh()


def run(stdscr, duration, max_iter, frame_delay, morph_radius, morph_speed):
    num_colors = init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    max_y, max_x = stdscr.getmaxyx()
    target_name, base_cr, base_ci = random.choice(JULIA_TARGETS)
    start_time = time.monotonic()

    while True:
        elapsed = time.monotonic() - start_time
        if elapsed >= duration:
            break

        # Morph c around the base point in a smooth circular path
        angle = elapsed * morph_speed
        cr = base_cr + morph_radius * math.cos(angle)
        ci = base_ci + morph_radius * math.sin(angle)

        render_frame(stdscr, cr, ci, max_iter, num_colors, target_name, max_y, max_x)

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=20, max_iter=80, frame_delay=0.05,
         morph_radius=0.05, morph_speed=0.3):
    duration = float(duration)
    max_iter = int(max_iter)
    frame_delay = float(frame_delay)
    morph_radius = float(morph_radius)
    morph_speed = float(morph_speed)
    curses.wrapper(lambda stdscr: run(stdscr, duration, max_iter, frame_delay,
                                      morph_radius, morph_speed))


if __name__ == "__main__":
    main()
