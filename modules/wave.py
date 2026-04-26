import curses
import math
import random
import time


COLOR_TITLE = 7
COLOR_EQUATION = 8
COLOR_PARAMS = 9


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    palette = [
        curses.COLOR_RED,
        curses.COLOR_YELLOW,
        curses.COLOR_GREEN,
        curses.COLOR_CYAN,
        curses.COLOR_BLUE,
        curses.COLOR_MAGENTA,
    ]
    for i, c in enumerate(palette):
        curses.init_pair(i + 1, c, -1)
    curses.init_pair(COLOR_TITLE, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_EQUATION, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_PARAMS, curses.COLOR_WHITE, -1)
    return len(palette)


def _put(stdscr, y, x, ch, attr, max_y, max_x):
    if 0 <= x < max_x and 0 <= y < max_y - 1:
        try:
            stdscr.addstr(y, x, ch, attr)
        except curses.error:
            pass


# Each draw_* returns (title, equation, params_str)


def draw_sine(stdscr, t, num_waves, max_y, max_x, num_colors):
    cy = max_y / 2
    amplitude = max(1, (max_y - 4) / 3)
    for w in range(num_waves):
        freq = 0.05 + w * 0.04
        phase = t * (0.5 + w * 0.2)
        attr = curses.color_pair((w % num_colors) + 1) | curses.A_BOLD
        for x in range(max_x):
            y = int(cy + amplitude * math.sin(freq * x + phase))
            _put(stdscr, y, x, "#", attr, max_y, max_x)
    return ("Traveling sine waves",
            "y = A·sin(kx + ωt)",
            f"waves={num_waves}, k=0.05..0.21")


def draw_lissajous(stdscr, t, max_y, max_x, num_colors):
    cx = max_x / 2
    cy = max_y / 2
    rx = (max_x - 4) / 2
    ry = (max_y - 4) / 2
    a, b = 3, 2
    delta = t * 0.5
    points = max_x * max_y // 4
    for i in range(points):
        u = i / points * math.tau
        x = int(cx + rx * math.sin(a * u + delta))
        y = int(cy + ry * math.sin(b * u))
        color = curses.color_pair((i * num_colors // max(1, points)) % num_colors + 1)
        _put(stdscr, y, x, "*", color | curses.A_BOLD, max_y, max_x)
    return ("Lissajous figure",
            "x = sin(at+φ),  y = sin(bt)",
            f"a={a}, b={b}, φ={delta:.2f}")


def draw_standing(stdscr, t, max_y, max_x, num_colors):
    cy = max_y / 2
    amplitude = max(1, (max_y - 4) / 3)
    k = 0.18
    omega = 2.0
    for x in range(max_x):
        y_val = math.sin(k * x) * math.cos(omega * t)
        y = int(cy + amplitude * y_val)
        color_idx = (int((x / max(1, max_x)) * num_colors)) % num_colors + 1
        attr = curses.color_pair(color_idx) | curses.A_BOLD
        _put(stdscr, y, x, "#", attr, max_y, max_x)
    return ("Standing wave",
            "y = A·sin(kx)·cos(ωt)",
            f"k={k}, ω={omega}")


def draw_beats(stdscr, t, max_y, max_x, num_colors):
    cy = max_y / 2
    amplitude = max(1, (max_y - 4) / 4)
    f1 = 0.10
    f2 = 0.12
    phase = t * 0.8
    for x in range(max_x):
        y_val = math.sin(f1 * x + phase) + math.sin(f2 * x + phase)
        y = int(cy + amplitude * y_val)
        attr = curses.color_pair(2) | curses.A_BOLD
        _put(stdscr, y, x, "#", attr, max_y, max_x)
    return ("Beats / interference",
            "y = sin(ω₁x) + sin(ω₂x)",
            f"ω₁={f1}, ω₂={f2}, Δ={abs(f2 - f1):.2f}")


def draw_packet(stdscr, t, max_y, max_x, num_colors):
    cy = max_y / 2
    amplitude = max(1, (max_y - 4) / 3)
    k = 0.4
    omega = 3.0
    v = 8.0
    sigma = max(4.0, max_x / 8)
    span = max_x + 4 * sigma
    center = (t * v) % span - 2 * sigma
    for x in range(max_x):
        env = math.exp(-((x - center) ** 2) / (2 * sigma * sigma))
        y_val = env * math.sin(k * x - omega * t)
        y = int(cy + amplitude * y_val)
        attr = curses.color_pair(4) | curses.A_BOLD
        _put(stdscr, y, x, "#", attr, max_y, max_x)
    return ("Wave packet",
            "y = e^(-(x-vt)²/2σ²) · sin(kx − ωt)",
            f"k={k}, ω={omega}, v={v}, σ={sigma:.1f}")


def draw_rose(stdscr, t, max_y, max_x, num_colors):
    cx = max_x / 2
    cy = max_y / 2
    ry = (min(max_x // 2, max_y) - 2) / 2
    rx = ry * 2
    # Smoothly morph k from 2 to 6 and back
    k_smooth = 4 + 2 * math.sin(t * 0.2)
    points = 800
    rotation = t * 0.3
    for i in range(points):
        theta = i / points * math.tau
        r = math.cos(k_smooth * theta + rotation)
        x = int(cx + rx * r * math.cos(theta))
        y = int(cy + ry * r * math.sin(theta))
        color = curses.color_pair((i * num_colors // points) % num_colors + 1)
        _put(stdscr, y, x, "*", color | curses.A_BOLD, max_y, max_x)
    return ("Rose curve (polar)",
            "r = cos(kθ)",
            f"k={k_smooth:.2f}")


def draw_spirograph(stdscr, t, max_y, max_x, num_colors):
    cx = max_x / 2
    cy = max_y / 2

    # Use the full screen with aspect correction (chars are ~2x taller than wide).
    # y-radius is the limit; x-radius will be 2x larger for a round shape.
    avail_y = (max_y - 4) / 2
    avail_x = (max_x - 4) / 4  # /4 so 2x scale fits
    R = max(6, min(avail_y, avail_x))

    # Slowly morph the gear ratios so the figure transforms over time
    ratio = 0.35 + 0.15 * math.sin(t * 0.12)
    r = R * ratio
    d_ratio = 0.7 + 0.5 * math.sin(t * 0.08)
    d = r * d_ratio

    points = 2400
    rev = 14
    rotation = t * 0.3
    color_offset = int(t * 12)

    for i in range(points):
        u = i / points * math.tau * rev + rotation
        x_local = (R - r) * math.cos(u) + d * math.cos((R - r) / r * u)
        y_local = (R - r) * math.sin(u) - d * math.sin((R - r) / r * u)
        sx = int(cx + x_local * 2)
        sy = int(cy + y_local)
        color_idx = ((i + color_offset) * num_colors // points) % num_colors + 1
        _put(stdscr, sy, sx, "*",
             curses.color_pair(color_idx) | curses.A_BOLD, max_y, max_x)

    # Animated "pen" cursor showing where the curve is currently being traced
    pen_u = (t * 2.5) % (math.tau * rev) + rotation
    px = (R - r) * math.cos(pen_u) + d * math.cos((R - r) / r * pen_u)
    py = (R - r) * math.sin(pen_u) - d * math.sin((R - r) / r * pen_u)
    _put(stdscr, int(cy + py), int(cx + px * 2), "@",
         curses.color_pair(num_colors) | curses.A_BOLD | curses.A_REVERSE,
         max_y, max_x)

    return ("Hypotrochoid (spirograph)",
            "x = (R−r)cos(t) + d·cos((R−r)/r · t)",
            f"R={R:.1f}, r={r:.1f}, d={d:.1f}")


def draw_damped(stdscr, t, max_y, max_x, num_colors):
    cy = max_y / 2
    amplitude = max(1, (max_y - 4) / 3)
    k = 0.2
    omega = 2.5
    L = max(8.0, max_x / 3)
    phase = t * omega
    for x in range(max_x):
        damp = math.exp(-x / L)
        y_val = damp * math.sin(k * x - phase)
        y = int(cy + amplitude * y_val)
        color_idx = min(max(0, int(damp * num_colors)), num_colors - 1)
        attr = curses.color_pair(color_idx + 1) | curses.A_BOLD
        _put(stdscr, y, x, "#", attr, max_y, max_x)
    return ("Damped traveling wave",
            "y = e^(-x/L) · sin(kx − ωt)",
            f"k={k}, ω={omega}, L={L:.1f}")


def draw_ekg(stdscr, t, max_y, max_x, num_colors):
    cy = max_y // 2
    amp = max(2, (max_y - 4) // 3)
    period = 50
    beat_speed = 25
    offset = (t * beat_speed) % period

    def heartbeat(p):
        # Smooth the discrete spikes a bit so each region transitions cleanly.
        if 0 <= p < 5:
            return 0.2 * math.sin((p / 5) * math.pi)              # P wave
        if 8 <= p < 10:
            return -0.15 * math.sin(((p - 8) / 2) * math.pi)      # Q dip
        if 10 <= p < 12:
            return math.sin(((p - 10) / 2) * math.pi)             # R spike
        if 12 <= p < 14:
            return -0.4 * math.sin(((p - 12) / 2) * math.pi)      # S dip
        if 18 <= p < 24:
            return 0.3 * math.sin(((p - 18) / 6) * math.pi)       # T wave
        return 0.0

    trace_attr = curses.color_pair(1) | curses.A_BOLD
    base_attr = curses.color_pair(1) | curses.A_DIM

    # Faint baseline across the screen
    for x in range(max_x):
        _put(stdscr, cy, x, "-", base_attr, max_y, max_x)

    # Trace, connecting consecutive samples with vertical lines so it reads
    # as a continuous waveform instead of disconnected dots.
    prev_y = None
    for x in range(max_x):
        p = (x + offset) % period
        y_val = heartbeat(p)
        y = int(cy - amp * y_val)
        y_min = max(0, min(y, prev_y) if prev_y is not None else y)
        y_max = min(max_y - 2, max(y, prev_y) if prev_y is not None else y)
        for fill_y in range(y_min, y_max + 1):
            _put(stdscr, fill_y, x, "#", trace_attr, max_y, max_x)
        prev_y = y

    return ("EKG heartbeat",
            "P-Q-R-S-T waveform",
            f"period={period}, speed={beat_speed} c/s")


WAVE_TYPES = {
    "sine": draw_sine,
    "lissajous": draw_lissajous,
    "standing": draw_standing,
    "beats": draw_beats,
    "packet": draw_packet,
    "rose": draw_rose,
    "spirograph": draw_spirograph,
    "damped": draw_damped,
    "ekg": draw_ekg,
}


def draw_status_bar(stdscr, title, equation, params, max_y, max_x):
    bottom_y = max_y - 1
    if bottom_y < 0:
        return
    sep = "  |  "
    sep_attr = curses.color_pair(COLOR_PARAMS) | curses.A_DIM
    title_attr = curses.color_pair(COLOR_TITLE) | curses.A_BOLD
    eq_attr = curses.color_pair(COLOR_EQUATION) | curses.A_BOLD
    param_attr = curses.color_pair(COLOR_PARAMS) | curses.A_DIM

    segments = [
        (title, title_attr),
        (sep, sep_attr),
        (equation, eq_attr),
        (sep, sep_attr),
        (params, param_attr),
    ]

    x = 2
    for text, attr in segments:
        if x >= max_x - 1:
            break
        avail = max_x - x - 1
        chunk = text[:avail]
        try:
            stdscr.addstr(bottom_y, x, chunk, attr)
        except curses.error:
            pass
        x += len(chunk)


def run(stdscr, duration, num_waves, mode, frame_delay):
    num_colors = init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.clear()
    stdscr.refresh()
    stdscr.timeout(int(frame_delay * 1000))

    if mode == "random" or mode not in WAVE_TYPES:
        mode = random.choice(list(WAVE_TYPES.keys()))
    draw_fn = WAVE_TYPES[mode]

    start = time.monotonic()
    while True:
        elapsed = time.monotonic() - start
        if elapsed >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        stdscr.erase()

        if mode == "sine":
            title, equation, params = draw_fn(stdscr, elapsed, num_waves,
                                              max_y, max_x, num_colors)
        else:
            title, equation, params = draw_fn(stdscr, elapsed,
                                              max_y, max_x, num_colors)

        draw_status_bar(stdscr, title, equation, params, max_y, max_x)
        stdscr.refresh()

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=20, num_waves=4, mode="random", frame_delay=0.05):
    duration = float(duration)
    num_waves = max(1, int(num_waves))
    if mode != "random" and mode not in WAVE_TYPES:
        mode = "random"
    frame_delay = float(frame_delay)
    curses.wrapper(lambda stdscr: run(stdscr, duration, num_waves, mode, frame_delay))


if __name__ == "__main__":
    main()
