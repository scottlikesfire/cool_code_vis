import curses
import math
import time


CHARS = " ..::##@@"


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
    for i, c in enumerate(palette):
        curses.init_pair(i + 1, c, -1)
    return len(palette)


def run(stdscr, duration, frame_delay, speed, depth_scale):
    num_colors = init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    start = time.monotonic()
    while True:
        elapsed = time.monotonic() - start
        if elapsed >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        cx = max_x / 2
        cy = max_y / 2
        # Aspect-correct scale (chars are roughly twice as tall as wide)
        x_scale = 2.0 / max_x
        y_scale = 4.0 / max_y

        stdscr.erase()
        for y in range(max_y - 1):
            for x in range(max_x):
                dx = (x - cx) * x_scale
                dy = (y - cy) * y_scale
                d = math.sqrt(dx * dx + dy * dy)
                if d < 0.05:
                    continue

                # Tunnel depth: bands receding into the distance
                depth = depth_scale / d - elapsed * speed

                ch_idx = int(depth) % len(CHARS)
                ch = CHARS[ch_idx]
                if ch == " ":
                    continue
                color_idx = (int(depth / 2) % num_colors) + 1
                attr = curses.color_pair(color_idx) | curses.A_BOLD
                try:
                    stdscr.addstr(y, x, ch, attr)
                except curses.error:
                    pass

        stdscr.refresh()
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=20, frame_delay=0.06, speed=4.0, depth_scale=2.0):
    duration = float(duration)
    frame_delay = float(frame_delay)
    speed = float(speed)
    depth_scale = float(depth_scale)
    curses.wrapper(lambda stdscr: run(stdscr, duration, frame_delay, speed, depth_scale))


if __name__ == "__main__":
    main()
