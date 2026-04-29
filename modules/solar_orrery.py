import curses
import math
import random
import time


# (name, color_pair, orbital_period_years, display_radius, char)
PLANETS = [
    ("Mercury", 1, 0.2408,  4.0, "M"),
    ("Venus",   2, 0.6152,  5.5, "V"),
    ("Earth",   3, 1.0000,  7.0, "E"),
    ("Mars",    4, 1.8809,  8.5, "m"),
    ("Jupiter", 5, 11.862, 11.0, "J"),
    ("Saturn",  6, 29.457, 13.5, "S"),
    ("Uranus",  7, 84.011, 16.0, "U"),
    ("Neptune", 8, 164.79, 18.5, "N"),
]

COLOR_SUN = 9
COLOR_ORBIT = 10
COLOR_LABEL = 11

PALETTE = [
    curses.COLOR_WHITE,    # Mercury (gray-ish)
    curses.COLOR_YELLOW,   # Venus
    curses.COLOR_BLUE,     # Earth
    curses.COLOR_RED,      # Mars
    curses.COLOR_MAGENTA,  # Jupiter
    curses.COLOR_YELLOW,   # Saturn
    curses.COLOR_CYAN,     # Uranus
    curses.COLOR_BLUE,     # Neptune
]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    for i, c in enumerate(PALETTE):
        curses.init_pair(i + 1, c, -1)
    curses.init_pair(COLOR_SUN, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_ORBIT, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def draw_orbit(stdscr, cx, cy, r, attr, max_y, max_x):
    """Draw a faint dotted ellipse — x scaled 2× for terminal char aspect."""
    n_pts = max(24, int(r * 8))
    for i in range(n_pts):
        a = i / n_pts * math.tau
        x = int(round(cx + 2 * r * math.cos(a)))
        y = int(round(cy + r * math.sin(a)))
        if 0 <= x < max_x and 0 <= y < max_y - 1:
            try:
                stdscr.addstr(y, x, ".", attr)
            except curses.error:
                pass


def run(stdscr, duration, frame_delay, time_scale, show_outer, show_labels,
        time_jitter):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.clear()
    stdscr.refresh()
    stdscr.timeout(int(frame_delay * 1000))

    # Random starting phase per planet so each run looks different
    start_phases = [random.uniform(0, math.tau) for _ in PLANETS]

    bodies = PLANETS if show_outer else PLANETS[:4]

    start = time.monotonic()
    while True:
        now = time.monotonic()
        elapsed = now - start
        if elapsed >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        cx = max_x / 2
        cy = (max_y - 2) / 2

        # Year of simulation time elapsed
        sim_years = elapsed * time_scale

        stdscr.erase()

        # Orbits
        orbit_attr = curses.color_pair(COLOR_ORBIT) | curses.A_DIM
        for (name, _color, _period, r, _ch) in bodies:
            draw_orbit(stdscr, cx, cy, r, orbit_attr, max_y, max_x)

        # Sun at center
        try:
            stdscr.addstr(int(round(cy)), int(round(cx)), "*",
                          curses.color_pair(COLOR_SUN)
                          | curses.A_BOLD | curses.A_REVERSE)
        except curses.error:
            pass

        # Planets
        for i, (name, color, period, r, ch) in enumerate(bodies):
            angle = start_phases[i] + sim_years / period * math.tau
            # Optional small radial wobble so planets aren't on perfect circles
            if time_jitter > 0:
                wobble_r = r * (1.0 + time_jitter * math.sin(angle * 1.3 + i))
            else:
                wobble_r = r
            x = int(round(cx + 2 * wobble_r * math.cos(angle)))
            y = int(round(cy + wobble_r * math.sin(angle)))
            attr = curses.color_pair(color) | curses.A_BOLD
            if 0 <= x < max_x and 0 <= y < max_y - 1:
                try:
                    stdscr.addstr(y, x, ch, attr)
                except curses.error:
                    pass
                if show_labels:
                    label_x = x + 2
                    if 0 <= label_x < max_x - len(name):
                        try:
                            stdscr.addstr(y, label_x, name,
                                          curses.color_pair(color) | curses.A_DIM)
                        except curses.error:
                            pass

        info = (f" Solar system orrery   simulated time: {sim_years:7.2f} years   "
                f"(Earth periods)   speedup: {time_scale:.1f} yr/s ")
        info = info.ljust(max(0, max_x - 1))[:max(0, max_x - 1)]
        try:
            stdscr.addstr(max_y - 1, 0, info,
                          curses.color_pair(COLOR_LABEL)
                          | curses.A_BOLD | curses.A_REVERSE)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=25, frame_delay=0.04, time_scale=4.0, show_outer=True,
         show_labels=True, time_jitter=0.0):
    duration = float(duration)
    frame_delay = float(frame_delay)
    time_scale = float(time_scale)
    show_outer = bool(show_outer)
    show_labels = bool(show_labels)
    time_jitter = float(time_jitter)
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, time_scale, show_outer,
        show_labels, time_jitter))


if __name__ == "__main__":
    main()
