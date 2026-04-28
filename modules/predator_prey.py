import curses
import math
import time


COLOR_PREY = 1
COLOR_PRED = 2
COLOR_AXIS = 3
COLOR_LABEL = 4


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_PREY, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_PRED, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_AXIS, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def lv_step(x, y, dt, alpha, beta, delta, gamma):
    """Single RK4 step of the Lotka–Volterra equations."""
    def f(x, y):
        return (alpha * x - beta * x * y,
                delta * x * y - gamma * y)
    k1x, k1y = f(x, y)
    k2x, k2y = f(x + 0.5 * dt * k1x, y + 0.5 * dt * k1y)
    k3x, k3y = f(x + 0.5 * dt * k2x, y + 0.5 * dt * k2y)
    k4x, k4y = f(x + dt * k3x, y + dt * k3y)
    nx = x + (dt / 6) * (k1x + 2 * k2x + 2 * k3x + k4x)
    ny = y + (dt / 6) * (k1y + 2 * k2y + 2 * k3y + k4y)
    return nx, ny


def run(stdscr, duration, frame_delay, alpha, beta, delta, gamma, sim_speed,
        x0, y0, history_size):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    history = [(x0, y0)]
    x, y = x0, y0

    start = time.monotonic()
    last_frame = start

    while True:
        now = time.monotonic()
        if now - start >= duration:
            break
        dt = min(now - last_frame, 0.1)
        last_frame = now

        # Multiple sub-steps so the curve is smooth
        sub_dt = dt * sim_speed / 32
        for _ in range(32):
            x, y = lv_step(x, y, sub_dt, alpha, beta, delta, gamma)

        history.append((x, y))
        if len(history) > history_size:
            history.pop(0)

        max_y, max_x = stdscr.getmaxyx()
        stdscr.erase()

        # Layout: left half = time-series plot, right half = phase portrait
        split_x = max_x // 2
        plot_w = split_x - 4
        plot_h = max_y - 4

        max_pop = max(max(p[0], p[1]) for p in history) * 1.1 + 1e-6

        # --- Time series (left) ---
        # x-axis = time (newest on right), y-axis = population
        try:
            stdscr.addstr(1, 2, "Population vs time",
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        plot_x0 = 2
        plot_y0 = 3
        # Axis lines
        for r in range(plot_h):
            try:
                stdscr.addstr(plot_y0 + r, plot_x0, "|",
                              curses.color_pair(COLOR_AXIS) | curses.A_DIM)
            except curses.error:
                pass
        for c in range(plot_w):
            try:
                stdscr.addstr(plot_y0 + plot_h, plot_x0 + 1 + c, "-",
                              curses.color_pair(COLOR_AXIS) | curses.A_DIM)
            except curses.error:
                pass

        n = len(history)
        for i, (px, py) in enumerate(history):
            t_norm = i / max(1, n - 1)
            sx = plot_x0 + 1 + int(t_norm * (plot_w - 1))
            prey_y = plot_y0 + plot_h - int(px / max_pop * (plot_h - 1))
            pred_y = plot_y0 + plot_h - int(py / max_pop * (plot_h - 1))
            if 0 <= prey_y < max_y - 1:
                try:
                    stdscr.addstr(prey_y, sx, "*",
                                  curses.color_pair(COLOR_PREY) | curses.A_BOLD)
                except curses.error:
                    pass
            if 0 <= pred_y < max_y - 1:
                try:
                    stdscr.addstr(pred_y, sx, "*",
                                  curses.color_pair(COLOR_PRED) | curses.A_BOLD)
                except curses.error:
                    pass

        # --- Phase portrait (right) ---
        try:
            stdscr.addstr(1, split_x + 2, "Phase portrait (prey vs predator)",
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass
        phase_x0 = split_x + 2
        phase_y0 = 3
        phase_w = max_x - phase_x0 - 2
        phase_h = max_y - 4
        for r in range(phase_h):
            try:
                stdscr.addstr(phase_y0 + r, phase_x0, "|",
                              curses.color_pair(COLOR_AXIS) | curses.A_DIM)
            except curses.error:
                pass
        for c in range(phase_w):
            try:
                stdscr.addstr(phase_y0 + phase_h, phase_x0 + 1 + c, "-",
                              curses.color_pair(COLOR_AXIS) | curses.A_DIM)
            except curses.error:
                pass

        for i, (px, py) in enumerate(history):
            sx = phase_x0 + 1 + int(px / max_pop * (phase_w - 1))
            sy = phase_y0 + phase_h - int(py / max_pop * (phase_h - 1))
            if not (0 <= sx < max_x and 0 <= sy < max_y - 1):
                continue
            age = i / max(1, len(history))
            attr = curses.color_pair(COLOR_PREY)
            if age < 0.5:
                attr |= curses.A_DIM
                ch = "."
            else:
                attr |= curses.A_BOLD
                ch = "*"
            try:
                stdscr.addstr(sy, sx, ch, attr)
            except curses.error:
                pass

        # Current state head
        sx = phase_x0 + 1 + int(x / max_pop * (phase_w - 1))
        sy = phase_y0 + phase_h - int(y / max_pop * (phase_h - 1))
        if 0 <= sx < max_x and 0 <= sy < max_y - 1:
            try:
                stdscr.addstr(sy, sx, "@",
                              curses.color_pair(COLOR_PRED)
                              | curses.A_BOLD | curses.A_REVERSE)
            except curses.error:
                pass

        info = (f"Lotka-Volterra  α={alpha} β={beta} δ={delta} γ={gamma}  "
                f"prey={x:.1f} pred={y:.1f}  green=prey red=pred")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=25, frame_delay=0.05, alpha=1.0, beta=0.4, delta=0.1,
         gamma=0.4, sim_speed=2.0, x0=10.0, y0=5.0, history_size=400):
    duration = float(duration)
    frame_delay = float(frame_delay)
    alpha = float(alpha)
    beta = float(beta)
    delta = float(delta)
    gamma = float(gamma)
    sim_speed = float(sim_speed)
    x0, y0 = float(x0), float(y0)
    history_size = max(2, int(history_size))
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, alpha, beta, delta, gamma,
        sim_speed, x0, y0, history_size))


if __name__ == "__main__":
    main()
