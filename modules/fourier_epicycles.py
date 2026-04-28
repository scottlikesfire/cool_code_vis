import curses
import math
import random
import time


COLOR_CIRCLE = 1
COLOR_RADIUS = 2
COLOR_TIP = 3
COLOR_WAVE = 4
COLOR_LABEL = 5


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_CIRCLE, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_RADIUS, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_TIP, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_WAVE, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def square_wave_terms(num_terms, base_amplitude=1.0):
    """Odd-harmonic square wave: a_n = 4/(n*pi) for odd n."""
    terms = []
    for k in range(num_terms):
        n = 2 * k + 1
        terms.append((base_amplitude * 4.0 / (n * math.pi), float(n)))
    return terms


def sawtooth_terms(num_terms, base_amplitude=1.0):
    """Sawtooth: a_n = -2/(n*pi)*(-1)^n for n>=1."""
    terms = []
    for n in range(1, num_terms + 1):
        amp = base_amplitude * (-2.0 / (n * math.pi)) * ((-1) ** n)
        terms.append((amp, float(n)))
    return terms


def triangle_terms(num_terms, base_amplitude=1.0):
    """Triangle wave: odd harmonics only, with sign alternating each
    odd harmonic and amplitude decaying as 1/n². Smoother than square."""
    terms = []
    for k in range(num_terms):
        n = 2 * k + 1
        amp = base_amplitude * ((-1) ** k) * 8.0 / (math.pi ** 2 * n * n)
        terms.append((amp, float(n)))
    return terms


def pulse_terms(num_terms, base_amplitude=1.0, duty=0.25):
    """Pulse train with configurable duty cycle. duty=0.5 reduces to a
    square wave; smaller duty values give narrow positive pulses."""
    terms = []
    for n in range(1, num_terms + 1):
        amp = base_amplitude * (2.0 / (n * math.pi)) * math.sin(math.pi * n * duty)
        terms.append((amp, float(n)))
    return terms


WAVE_GENERATORS = {
    "square": square_wave_terms,
    "sawtooth": sawtooth_terms,
    "triangle": triangle_terms,
    "pulse": pulse_terms,
}


def normalize_terms(terms, target_total):
    """Scale all term amplitudes so sum(|amp|) == target_total. This decouples
    on-screen size from waveform choice — different wave families have
    different intrinsic coefficient magnitudes (square's first term is
    4/π ≈ 1.27, triangle's is 8/π² ≈ 0.81, etc.), so without normalization
    the chain of epicycles ends up a different physical length per shape."""
    current = sum(abs(amp) for amp, _ in terms)
    if current < 1e-9:
        return terms
    factor = target_total / current
    return [(amp * factor, freq) for amp, freq in terms]


def _put(stdscr, y, x, ch, attr, max_y, max_x):
    if 0 <= x < max_x and 0 <= y < max_y - 1:
        try:
            stdscr.addstr(y, x, ch, attr)
        except curses.error:
            pass


def draw_circle(stdscr, cx, cy, r, attr, max_y, max_x):
    if r < 0.5:
        return
    n = max(8, int(r * 6))
    for i in range(n):
        angle = i * 2 * math.pi / n
        # x scaled 2× for terminal char aspect → on-screen circle
        x = cx + 2 * r * math.cos(angle)
        y = cy + r * math.sin(angle)
        _put(stdscr, int(round(y)), int(round(x)), ".", attr, max_y, max_x)


def draw_line(stdscr, x0, y0, x1, y1, ch, attr, max_y, max_x):
    dx = x1 - x0
    dy = y1 - y0
    steps = max(abs(int(round(dx))), abs(int(round(dy))))
    if steps == 0:
        _put(stdscr, int(round(y0)), int(round(x0)), ch, attr, max_y, max_x)
        return
    for i in range(steps + 1):
        t = i / steps
        _put(stdscr, int(round(y0 + t * dy)), int(round(x0 + t * dx)),
             ch, attr, max_y, max_x)


def run(stdscr, duration, frame_delay, num_terms, total_amplitude,
        omega, scale, wave_history, wave_type):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    if wave_type == "random" or wave_type not in WAVE_GENERATORS:
        wave_type = random.choice(list(WAVE_GENERATORS.keys()))
    terms = WAVE_GENERATORS[wave_type](num_terms, 1.0)
    terms = normalize_terms(terms, total_amplitude)

    history = []  # tip y-positions over time
    start = time.monotonic()

    while True:
        now = time.monotonic()
        if now - start >= duration:
            break
        elapsed = now - start

        max_y, max_x = stdscr.getmaxyx()
        epi_cx = max_x * 0.22
        cy = max_y / 2

        # Width of the epicycle stack (chained circle radii, in screen x).
        max_x_extent = sum(2 * scale * abs(amp) for amp, _ in terms)
        wave_x0 = int(epi_cx + max_x_extent + 2)
        wave_x0 = max(wave_x0, int(epi_cx + 4))
        wave_x0 = min(wave_x0, max_x - 6)
        wave_w = max_x - wave_x0 - 2

        # Compute the epicycle chain
        x = epi_cx
        y = cy
        positions = [(x, y)]
        for amp, freq in terms:
            r = scale * abs(amp)
            sign = 1.0 if amp >= 0 else -1.0
            angle = freq * omega * elapsed
            nx = x + 2 * r * math.cos(angle) * sign
            ny = y + r * math.sin(angle) * sign
            positions.append((nx, ny))
            x, y = nx, ny

        history.append(y)
        if len(history) > wave_history:
            history.pop(0)

        stdscr.erase()

        # Draw the circles
        for (cx_i, cy_i), (amp, _) in zip(positions[:-1], terms):
            r = scale * abs(amp)
            draw_circle(stdscr, cx_i, cy_i, r,
                        curses.color_pair(COLOR_CIRCLE) | curses.A_DIM,
                        max_y, max_x)

        # Draw the radii connecting consecutive circle centers
        for (x0, y0), (x1, y1) in zip(positions[:-1], positions[1:]):
            draw_line(stdscr, x0, y0, x1, y1, "+",
                      curses.color_pair(COLOR_RADIUS) | curses.A_DIM,
                      max_y, max_x)

        # The tip itself — bright marker
        tip_x, tip_y = positions[-1]
        _put(stdscr, int(round(tip_y)), int(round(tip_x)), "@",
             curses.color_pair(COLOR_TIP) | curses.A_BOLD | curses.A_REVERSE,
             max_y, max_x)

        # Connector from tip across to the wave plot start
        draw_line(stdscr, tip_x, tip_y, wave_x0, tip_y, "-",
                  curses.color_pair(COLOR_TIP) | curses.A_DIM, max_y, max_x)

        # Wave plot — newest sample on the LEFT (right next to the tip),
        # oldest scrolling off to the right.
        wave_attr = curses.color_pair(COLOR_WAVE) | curses.A_BOLD
        n = len(history)
        if wave_w > 0 and n > 1:
            for i, py in enumerate(history):
                # i=0 oldest, i=n-1 newest. Newest at wave_x0; older to the
                # right.
                offset = (n - 1 - i)
                sx = wave_x0 + offset
                if sx >= max_x - 1:
                    break
                yi = int(round(py))
                _put(stdscr, yi, sx, "*", wave_attr, max_y, max_x)

        info = (f"Fourier {wave_type} synthesis  N={num_terms}  ω={omega}  "
                f"sum amp = {sum(amp for amp, _ in terms):.3f}")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=25, frame_delay=0.04, num_terms=8, total_amplitude=5.0,
         omega=0.8, scale=2.0, wave_history=120, wave_type="random"):
    duration = float(duration)
    frame_delay = float(frame_delay)
    num_terms = max(1, int(num_terms))
    total_amplitude = float(total_amplitude)
    omega = float(omega)
    scale = float(scale)
    wave_history = max(2, int(wave_history))
    if wave_type != "random" and wave_type not in WAVE_GENERATORS:
        wave_type = "random"
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, num_terms, total_amplitude,
        omega, scale, wave_history, wave_type))


if __name__ == "__main__":
    main()
