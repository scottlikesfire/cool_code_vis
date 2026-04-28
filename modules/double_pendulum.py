import curses
import math
import random
import time


COLOR_ARM = 1
COLOR_BOB = 2
COLOR_PIVOT = 3
COLOR_TRAIL = 4
COLOR_LABEL = 5


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_ARM, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_BOB, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_PIVOT, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_TRAIL, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def derivatives(state, m1, m2, l1, l2, g):
    """Return (dθ1, dω1, dθ2, dω2) for the double-pendulum equations."""
    t1, w1, t2, w2 = state
    dt = t1 - t2
    sin_dt = math.sin(dt)
    cos_dt = math.cos(dt)
    denom = 2 * m1 + m2 - m2 * math.cos(2 * t1 - 2 * t2)

    dt1 = w1
    dt2 = w2

    dw1 = (
        -g * (2 * m1 + m2) * math.sin(t1)
        - m2 * g * math.sin(t1 - 2 * t2)
        - 2 * sin_dt * m2 * (w2 * w2 * l2 + w1 * w1 * l1 * cos_dt)
    ) / (l1 * denom)

    dw2 = (
        2 * sin_dt * (
            w1 * w1 * l1 * (m1 + m2)
            + g * (m1 + m2) * math.cos(t1)
            + w2 * w2 * l2 * m2 * cos_dt
        )
    ) / (l2 * denom)

    return (dt1, dw1, dt2, dw2)


def rk4_step(state, dt, m1, m2, l1, l2, g):
    k1 = derivatives(state, m1, m2, l1, l2, g)
    s2 = tuple(s + 0.5 * dt * k for s, k in zip(state, k1))
    k2 = derivatives(s2, m1, m2, l1, l2, g)
    s3 = tuple(s + 0.5 * dt * k for s, k in zip(state, k2))
    k3 = derivatives(s3, m1, m2, l1, l2, g)
    s4 = tuple(s + dt * k for s, k in zip(state, k3))
    k4 = derivatives(s4, m1, m2, l1, l2, g)
    return tuple(s + (dt / 6) * (a + 2 * b + 2 * c + d)
                 for s, a, b, c, d in zip(state, k1, k2, k3, k4))


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


def run(stdscr, duration, frame_delay, m1, m2, l1, l2, g,
        sub_steps, trail_length, scale):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    state = (
        random.uniform(0.5, 2.5) * random.choice((-1, 1)),
        0.0,
        random.uniform(0.5, 2.5) * random.choice((-1, 1)),
        0.0,
    )

    trail = []
    start = time.monotonic()
    last_frame = start

    while True:
        now = time.monotonic()
        if now - start >= duration:
            break
        dt = min(now - last_frame, 0.1)
        last_frame = now

        # Sub-step the integrator for stability (RK4 each sub-step)
        sub_dt = dt / sub_steps
        for _ in range(sub_steps):
            state = rk4_step(state, sub_dt, m1, m2, l1, l2, g)

        t1, _, t2, _ = state
        x1 = l1 * math.sin(t1)
        y1 = l1 * math.cos(t1)
        x2 = x1 + l2 * math.sin(t2)
        y2 = y1 + l2 * math.cos(t2)

        max_y, max_x = stdscr.getmaxyx()
        cx = max_x / 2
        cy = max_y / 3  # pivot at upper third

        # World→screen with aspect correction
        sx = lambda wx: cx + scale * 2 * wx
        sy = lambda wy: cy + scale * wy

        trail.append((x2, y2))
        if len(trail) > trail_length:
            trail.pop(0)

        stdscr.erase()

        # Trail (oldest = dim, newest = bright)
        for i, (tx, ty) in enumerate(trail):
            age_ratio = i / max(1, len(trail))
            if age_ratio < 0.3:
                ch = "."
                attr = curses.color_pair(COLOR_TRAIL) | curses.A_DIM
            elif age_ratio < 0.7:
                ch = "*"
                attr = curses.color_pair(COLOR_TRAIL) | curses.A_DIM
            else:
                ch = "*"
                attr = curses.color_pair(COLOR_TRAIL) | curses.A_BOLD
            xi, yi = int(round(sx(tx))), int(round(sy(ty)))
            if 0 <= xi < max_x and 0 <= yi < max_y - 1:
                try:
                    stdscr.addstr(yi, xi, ch, attr)
                except curses.error:
                    pass

        # Arms
        arm_attr = curses.color_pair(COLOR_ARM) | curses.A_DIM
        draw_line(stdscr, cx, cy, sx(x1), sy(y1), "-", arm_attr, max_y, max_x)
        draw_line(stdscr, sx(x1), sy(y1), sx(x2), sy(y2), "-", arm_attr,
                  max_y, max_x)

        # Pivot
        try:
            stdscr.addstr(int(round(cy)), int(round(cx)), "+",
                          curses.color_pair(COLOR_PIVOT) | curses.A_BOLD)
        except curses.error:
            pass
        # Joint
        try:
            stdscr.addstr(int(round(sy(y1))), int(round(sx(x1))), "o",
                          curses.color_pair(COLOR_PIVOT) | curses.A_BOLD)
        except curses.error:
            pass
        # End bob
        try:
            stdscr.addstr(int(round(sy(y2))), int(round(sx(x2))), "@",
                          curses.color_pair(COLOR_BOB) | curses.A_BOLD)
        except curses.error:
            pass

        info = (f"Double pendulum  m=({m1},{m2}) l=({l1},{l2}) g={g}  "
                f"θ1={state[0]:+.2f} θ2={state[2]:+.2f}")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=25, frame_delay=0.04, m1=1.0, m2=1.0, l1=1.0, l2=1.0,
         g=9.81, sub_steps=8, trail_length=200, scale=4.0):
    duration = float(duration)
    frame_delay = float(frame_delay)
    m1, m2 = float(m1), float(m2)
    l1, l2 = float(l1), float(l2)
    g = float(g)
    sub_steps = max(1, int(sub_steps))
    trail_length = max(0, int(trail_length))
    scale = float(scale)
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, m1, m2, l1, l2, g,
        sub_steps, trail_length, scale))


if __name__ == "__main__":
    main()
