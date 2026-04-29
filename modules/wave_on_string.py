import curses
import math
import random
import time


COLOR_WAVE = 1
COLOR_AXIS = 2
COLOR_LABEL = 3


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_WAVE, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_AXIS, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def step_wave(u, u_prev, c2, damping):
    """Discrete 1D wave equation step, fixed boundaries."""
    n = len(u)
    new_u = [0.0] * n
    for i in range(1, n - 1):
        lap = u[i + 1] - 2 * u[i] + u[i - 1]
        new_u[i] = (1.0 - damping) * (2 * u[i] - u_prev[i] + c2 * lap)
    return new_u


def run(stdscr, duration, frame_delay, c2, damping, pulse_interval,
        amplitude, pulse_strength, steps_per_frame):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.clear()
    stdscr.refresh()
    stdscr.timeout(int(frame_delay * 1000))

    max_y, max_x = stdscr.getmaxyx()
    n = max(8, max_x)
    u = [0.0] * n
    u_prev = [0.0] * n

    start = time.monotonic()
    last_pulse = -pulse_interval  # fire one immediately
    pulse_count = 0

    while True:
        now = time.monotonic()
        elapsed = now - start
        if elapsed >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        # Resize string buffer if terminal changed
        if n != max_x:
            new_n = max(8, max_x)
            scale = new_n / n
            new_u = [0.0] * new_n
            new_u_prev = [0.0] * new_n
            for i in range(min(n, new_n)):
                new_u[i] = u[i]
                new_u_prev[i] = u_prev[i]
            u = new_u
            u_prev = new_u_prev
            n = new_n
            _ = scale  # not used

        # Periodic pulse injection
        if elapsed - last_pulse > pulse_interval:
            last_pulse = elapsed
            pulse_count += 1
            center = random.randint(n // 5, 4 * n // 5)
            sigma = max(2.0, n / 30.0)
            sign = 1 if random.random() > 0.5 else -1
            for i in range(n):
                u[i] += sign * pulse_strength * math.exp(
                    -((i - center) ** 2) / (2 * sigma * sigma)
                )

        for _ in range(steps_per_frame):
            new_u = step_wave(u, u_prev, c2, damping)
            u_prev = u
            u = new_u

        stdscr.erase()
        cy = max_y // 2
        # Faint center axis
        axis_attr = curses.color_pair(COLOR_AXIS) | curses.A_DIM
        for x in range(n):
            try:
                stdscr.addstr(cy, x, "-", axis_attr)
            except curses.error:
                pass

        # Wave trace, connecting consecutive samples vertically. The display
        # maps |u| == amplitude to ±max_amp_rows from center; values larger
        # than that just clamp at the screen edge instead of being silently
        # rescaled, so changing `amplitude` actually changes how big the
        # wave looks on screen.
        wave_attr = curses.color_pair(COLOR_WAVE) | curses.A_BOLD
        max_amp_rows = max(2, (max_y - 4) // 2)
        prev_y = None
        for x in range(n):
            disp = u[x] / amplitude
            y = cy - int(round(disp * max_amp_rows))
            y = max(0, min(max_y - 2, y))
            if prev_y is not None and abs(y - prev_y) > 1:
                y0, y1 = (prev_y, y) if prev_y < y else (y, prev_y)
                for yi in range(y0, y1 + 1):
                    if 0 <= yi < max_y - 1:
                        try:
                            stdscr.addstr(yi, x, "#", wave_attr)
                        except curses.error:
                            pass
            else:
                try:
                    stdscr.addstr(y, x, "#", wave_attr)
                except curses.error:
                    pass
            prev_y = y

        info = (f"Wave on string  c²={c2}  damping={damping:.4f}  "
                f"length={n}  pulses sent={pulse_count}")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=25, frame_delay=0.04, c2=0.3, damping=0.0015,
         pulse_interval=4.0, amplitude=1.0, pulse_strength=0.4,
         steps_per_frame=2):
    duration = float(duration)
    frame_delay = float(frame_delay)
    c2 = float(c2)
    damping = float(damping)
    pulse_strength = float(pulse_strength)
    pulse_interval = float(pulse_interval)
    amplitude = float(amplitude)
    steps_per_frame = max(1, int(steps_per_frame))
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, c2, damping, pulse_interval,
        amplitude, pulse_strength, steps_per_frame))


if __name__ == "__main__":
    main()
