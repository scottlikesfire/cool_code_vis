import curses
import random
import time


CHARS = ".·*+oO#@"


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    palette = [
        curses.COLOR_BLUE,
        curses.COLOR_CYAN,
        curses.COLOR_WHITE,
        curses.COLOR_YELLOW,
    ]
    for i, c in enumerate(palette):
        curses.init_pair(i + 1, c, -1)
    return len(palette)


def run(stdscr, duration, num_stars, speed, frame_delay):
    num_colors = init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    max_y, max_x = stdscr.getmaxyx()
    cx = max_x / 2
    cy = max_y / 2
    focal = max_x / 2

    extent = max_x * 2.0
    far_z = 100.0
    near_z = 1.0

    stars = [
        [random.uniform(-extent, extent),
         random.uniform(-extent, extent),
         random.uniform(near_z, far_z)]
        for _ in range(num_stars)
    ]

    start_time = time.monotonic()
    while True:
        if time.monotonic() - start_time >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        cx = max_x / 2
        cy = max_y / 2
        focal = max_x / 2

        stdscr.erase()
        for star in stars:
            star[2] -= speed
            if star[2] <= near_z:
                star[0] = random.uniform(-extent, extent)
                star[1] = random.uniform(-extent, extent)
                star[2] = far_z

            sx = int(cx + star[0] / star[2] * focal)
            sy = int(cy + star[1] / star[2] * focal / 2)

            if 0 <= sx < max_x and 0 <= sy < max_y - 1:
                depth_ratio = 1 - (star[2] / far_z)
                ch_idx = min(int(depth_ratio * len(CHARS)), len(CHARS) - 1)
                ch = CHARS[ch_idx]
                color_idx = min(int(depth_ratio * num_colors), num_colors - 1)
                attr = curses.color_pair(color_idx + 1) | curses.A_BOLD
                try:
                    stdscr.addstr(sy, sx, ch, attr)
                except curses.error:
                    pass

        stdscr.refresh()
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=20, num_stars=200, speed=0.4, frame_delay=0.04):
    duration = float(duration)
    num_stars = int(num_stars)
    speed = float(speed)
    frame_delay = float(frame_delay)
    curses.wrapper(lambda stdscr: run(stdscr, duration, num_stars, speed, frame_delay))


if __name__ == "__main__":
    main()
