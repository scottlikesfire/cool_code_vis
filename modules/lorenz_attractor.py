import curses
import math
import time


COLOR_TRAIL = 1
COLOR_HEAD = 2
COLOR_LABEL = 3
PALETTE = [
    curses.COLOR_BLUE, curses.COLOR_CYAN, curses.COLOR_GREEN,
    curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_MAGENTA,
]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    for i, c in enumerate(PALETTE):
        curses.init_pair(i + 1, c, -1)
    curses.init_pair(COLOR_HEAD, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def lorenz_step(state, dt, sigma, rho, beta):
    """Single RK4 step of the Lorenz system."""
    def f(s):
        x, y, z = s
        return (sigma * (y - x), x * (rho - z) - y, x * y - beta * z)
    k1 = f(state)
    s2 = tuple(s + 0.5 * dt * k for s, k in zip(state, k1))
    k2 = f(s2)
    s3 = tuple(s + 0.5 * dt * k for s, k in zip(state, k2))
    k3 = f(s3)
    s4 = tuple(s + dt * k for s, k in zip(state, k3))
    k4 = f(s4)
    return tuple(s + (dt / 6) * (a + 2 * b + 2 * c + d)
                 for s, a, b, c, d in zip(state, k1, k2, k3, k4))


def run(stdscr, duration, frame_delay, sigma, rho, beta, sub_steps,
        sub_dt, trail_length, scale, view_rotation_speed):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    state = (0.1, 0.0, 0.0)  # near a fixed point — will spiral out
    trail = []
    start = time.monotonic()

    while True:
        now = time.monotonic()
        elapsed = now - start
        if elapsed >= duration:
            break

        for _ in range(sub_steps):
            state = lorenz_step(state, sub_dt, sigma, rho, beta)
        trail.append(state)
        if len(trail) > trail_length:
            trail.pop(0)

        max_y, max_x = stdscr.getmaxyx()
        cx = max_x / 2
        cy = max_y / 2

        # Slow rotation around the z axis to give a 3D feel
        ang = elapsed * view_rotation_speed
        cos_a = math.cos(ang)
        sin_a = math.sin(ang)

        def project(s):
            x, y, z = s
            xr = x * cos_a - y * sin_a
            yr = x * sin_a + y * cos_a
            sx = cx + scale * 2 * xr
            sy = cy + scale * (z - 25)  # center the attractor vertically
            return int(round(sx)), int(round(sy))

        stdscr.erase()
        for i, s in enumerate(trail):
            xi, yi = project(s)
            if not (0 <= xi < max_x and 0 <= yi < max_y - 1):
                continue
            age_ratio = i / max(1, len(trail))
            color = PALETTE[int(age_ratio * len(PALETTE))
                            if age_ratio < 1 else len(PALETTE) - 1]
            color_pair_idx = (int(age_ratio * len(PALETTE))
                              if age_ratio < 1 else len(PALETTE) - 1) + 1
            attr = curses.color_pair(color_pair_idx)
            if age_ratio < 0.4:
                attr |= curses.A_DIM
                ch = "."
            else:
                attr |= curses.A_BOLD
                ch = "*"
            try:
                stdscr.addstr(yi, xi, ch, attr)
            except curses.error:
                pass

        # Bright head
        xi, yi = project(state)
        if 0 <= xi < max_x and 0 <= yi < max_y - 1:
            try:
                stdscr.addstr(yi, xi, "@",
                              curses.color_pair(COLOR_HEAD)
                              | curses.A_BOLD | curses.A_REVERSE)
            except curses.error:
                pass

        info = f"Lorenz attractor  σ={sigma} ρ={rho} β={beta:.3f}  pos=({state[0]:+.2f},{state[1]:+.2f},{state[2]:+.2f})"
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=25, frame_delay=0.04, sigma=10.0, rho=28.0, beta=8.0/3.0,
         sub_steps=10, sub_dt=0.005, trail_length=400, scale=0.5,
         view_rotation_speed=0.15):
    duration = float(duration)
    frame_delay = float(frame_delay)
    sigma = float(sigma)
    rho = float(rho)
    beta = float(beta)
    sub_steps = max(1, int(sub_steps))
    sub_dt = float(sub_dt)
    trail_length = max(0, int(trail_length))
    scale = float(scale)
    view_rotation_speed = float(view_rotation_speed)
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, sigma, rho, beta,
        sub_steps, sub_dt, trail_length, scale, view_rotation_speed))


if __name__ == "__main__":
    main()
