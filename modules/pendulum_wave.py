import curses
import math
import time


PALETTE = [
    curses.COLOR_RED, curses.COLOR_YELLOW, curses.COLOR_GREEN,
    curses.COLOR_CYAN, curses.COLOR_BLUE, curses.COLOR_MAGENTA,
]
COLOR_ARM = 7
COLOR_LABEL = 8


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    for i, c in enumerate(PALETTE):
        curses.init_pair(i + 1, c, -1)
    curses.init_pair(COLOR_ARM, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def draw_line(stdscr, x0, y0, x1, y1, ch, attr, max_y, max_x):
    dx = x1 - x0
    dy = y1 - y0
    steps = max(abs(int(round(dx))), abs(int(round(dy))))
    if steps == 0:
        xi, yi = int(round(x0)), int(round(y0))
        if 0 <= xi < max_x and 0 <= yi < max_y - 1:
            try:
                stdscr.addstr(yi, xi, ch, attr)
            except curses.error:
                pass
        return
    for i in range(steps + 1):
        t = i / steps
        xi = int(round(x0 + t * dx))
        yi = int(round(y0 + t * dy))
        if 0 <= xi < max_x and 0 <= yi < max_y - 1:
            try:
                stdscr.addstr(yi, xi, ch, attr)
            except curses.error:
                pass


def run(stdscr, duration, frame_delay, num_pendulums, T_beat,
        period_offset, amplitude_deg):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.clear()
    stdscr.refresh()
    stdscr.timeout(int(frame_delay * 1000))

    amplitude_rad = math.radians(amplitude_deg)
    # Period of pendulum i so all sync after T_beat seconds:
    #   T_i = T_beat / (period_offset + i)
    # i.e. the i-th pendulum completes (period_offset + i) cycles in T_beat.
    periods = [T_beat / (period_offset + i) for i in range(num_pendulums)]

    start = time.monotonic()
    while True:
        now = time.monotonic()
        elapsed = now - start
        if elapsed >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        # Layout
        margin = 2
        spacing = (max_x - 2 * margin) / max(1, num_pendulums - 1) \
            if num_pendulums > 1 else 0
        L = max_y - 4  # arm length in screen rows
        pivot_y = 1
        if L < 4:
            stdscr.refresh()
            stdscr.timeout(int(frame_delay * 1000))
            key = stdscr.getch()
            if key == ord("q") or key == 27:
                return
            continue

        stdscr.erase()

        # Pivot bar across the top
        for x in range(margin, max_x - margin):
            try:
                stdscr.addstr(0, x, "=",
                              curses.color_pair(COLOR_ARM) | curses.A_DIM)
            except curses.error:
                pass

        # Each pendulum
        for i in range(num_pendulums):
            T = periods[i]
            omega = 2 * math.pi / T
            theta = amplitude_rad * math.cos(omega * elapsed)

            px = margin + i * spacing
            # 2× x scale compensates for terminal char aspect so the pendulum
            # actually swings visibly side-to-side.
            bob_x = px + 2 * L * math.sin(theta)
            bob_y = pivot_y + L * math.cos(theta)

            color = (i % len(PALETTE)) + 1
            # String shares the bob's hue (dimmed) so each pendulum is
            # one continuous color from pivot to bob.
            arm_attr = curses.color_pair(color) | curses.A_DIM
            draw_line(stdscr, px, pivot_y, bob_x, bob_y, "|", arm_attr,
                      max_y, max_x)

            bob_attr = curses.color_pair(color) | curses.A_BOLD
            xi, yi = int(round(bob_x)), int(round(bob_y))
            if 0 <= xi < max_x and 0 <= yi < max_y - 1:
                try:
                    stdscr.addstr(yi, xi, "@", bob_attr)
                except curses.error:
                    pass

            # Pivot marker at top
            pxi = int(round(px))
            if 0 <= pxi < max_x:
                try:
                    stdscr.addstr(pivot_y, pxi, "+",
                                  curses.color_pair(COLOR_ARM) | curses.A_BOLD)
                except curses.error:
                    pass

        info = (f"Pendulum wave  N={num_pendulums}  T_beat={T_beat}s  "
                f"periods: T_min={periods[-1]:.2f}s T_max={periods[0]:.2f}s  "
                f"t={elapsed:.1f}s")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=30, frame_delay=0.04, num_pendulums=14, T_beat=30.0,
         period_offset=20, amplitude_deg=18.0):
    duration = float(duration)
    frame_delay = float(frame_delay)
    num_pendulums = max(2, int(num_pendulums))
    T_beat = float(T_beat)
    period_offset = max(1, int(period_offset))
    amplitude_deg = float(amplitude_deg)
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, num_pendulums, T_beat,
        period_offset, amplitude_deg))


if __name__ == "__main__":
    main()
