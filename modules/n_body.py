import curses
import math
import random
import time


# Color pairs 1-7 are used for the bodies
PALETTE = [
    curses.COLOR_YELLOW,
    curses.COLOR_RED,
    curses.COLOR_GREEN,
    curses.COLOR_CYAN,
    curses.COLOR_BLUE,
    curses.COLOR_MAGENTA,
    curses.COLOR_WHITE,
]
COLOR_LABEL = 8


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    for i, c in enumerate(PALETTE):
        curses.init_pair(i + 1, c, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def make_solar_system(num_planets, G, sun_mass, velocity_jitter,
                      tangent_jitter, radius_jitter,
                      planet_mass_min, planet_mass_max):
    """Sun + several bodies on perturbed orbits.

    Each planet's velocity magnitude is sampled around the local circular
    speed by ±velocity_jitter (so factor < 1 → eccentric orbits diving
    closer to the sun, factor > 1 → wider or unbound orbits), and its
    direction is perturbed by ±tangent_jitter radians from purely
    tangential. Planet masses are drawn uniformly in
    [planet_mass_min, planet_mass_max] so heavier ones genuinely perturb
    each other and the system can evolve / decay rather than locking into
    perfect circles.
    """
    bodies = [{
        "x": 0.0, "y": 0.0, "vx": 0.0, "vy": 0.0,
        "mass": sun_mass, "color": 1, "trail": [], "name": "sun",
    }]
    for i in range(num_planets):
        r_base = 8.0 + i * 6.0
        r = max(2.0, r_base + random.uniform(-radius_jitter, radius_jitter))
        angle = random.uniform(0, math.tau)
        x = r * math.cos(angle)
        y = r * math.sin(angle)

        v_circ = math.sqrt(G * sun_mass / r)
        v_factor = 1.0 + random.uniform(-velocity_jitter, velocity_jitter)
        v = v_circ * v_factor
        # Tangential direction is angle + π/2, perturbed by tangent_jitter
        v_angle = angle + math.pi / 2 + random.uniform(-tangent_jitter, tangent_jitter)
        vx = v * math.cos(v_angle)
        vy = v * math.sin(v_angle)

        bodies.append({
            "x": x, "y": y, "vx": vx, "vy": vy,
            "mass": random.uniform(planet_mass_min, planet_mass_max),
            "color": (i + 1) % len(PALETTE) + 1,
            "trail": [], "name": f"p{i}",
        })
    return bodies


def step(bodies, dt, G, softening):
    n = len(bodies)
    ax = [0.0] * n
    ay = [0.0] * n
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            dx = bodies[j]["x"] - bodies[i]["x"]
            dy = bodies[j]["y"] - bodies[i]["y"]
            dist2 = dx * dx + dy * dy + softening
            inv = 1.0 / (dist2 * math.sqrt(dist2))
            ax[i] += G * bodies[j]["mass"] * dx * inv
            ay[i] += G * bodies[j]["mass"] * dy * inv

    for i, b in enumerate(bodies):
        b["vx"] += ax[i] * dt
        b["vy"] += ay[i] * dt
    for b in bodies:
        b["x"] += b["vx"] * dt
        b["y"] += b["vy"] * dt


def run(stdscr, duration, frame_delay, num_planets, sub_steps,
        trail_length, view_scale, G, softening, sun_mass,
        velocity_jitter, tangent_jitter, radius_jitter,
        planet_mass_min, planet_mass_max):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    bodies = make_solar_system(
        num_planets, G, sun_mass, velocity_jitter, tangent_jitter,
        radius_jitter, planet_mass_min, planet_mass_max,
    )
    start = time.monotonic()
    last_frame = start

    while True:
        now = time.monotonic()
        if now - start >= duration:
            break
        dt = min(now - last_frame, 0.1)
        last_frame = now

        # Sub-step for stability
        sub_dt = dt / sub_steps
        for _ in range(sub_steps):
            step(bodies, sub_dt, G, softening)

        for b in bodies:
            b["trail"].append((b["x"], b["y"]))
            if len(b["trail"]) > trail_length:
                b["trail"].pop(0)

        max_y, max_x = stdscr.getmaxyx()
        cx = max_x / 2
        cy = max_y / 2

        def project(wx, wy):
            return cx + view_scale * 2 * wx, cy + view_scale * wy

        stdscr.erase()

        for b in bodies:
            attr = curses.color_pair(b["color"]) | curses.A_DIM
            for i, (tx, ty) in enumerate(b["trail"]):
                xi, yi = project(tx, ty)
                xi, yi = int(round(xi)), int(round(yi))
                if not (0 <= xi < max_x and 0 <= yi < max_y - 1):
                    continue
                age_ratio = i / max(1, len(b["trail"]))
                if age_ratio < 0.4:
                    ch = "."
                else:
                    ch = "*"
                try:
                    stdscr.addstr(yi, xi, ch, attr)
                except curses.error:
                    pass
            xi, yi = project(b["x"], b["y"])
            xi, yi = int(round(xi)), int(round(yi))
            if 0 <= xi < max_x and 0 <= yi < max_y - 1:
                ch = "*" if b["name"] == "sun" else "@"
                try:
                    stdscr.addstr(yi, xi, ch,
                                  curses.color_pair(b["color"]) | curses.A_BOLD)
                except curses.error:
                    pass

        info = f"N-body simulation  bodies={len(bodies)} (1 sun + {num_planets} planets)  G={G}"
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=25, frame_delay=0.04, num_planets=4, sub_steps=4,
         trail_length=120, view_scale=1.2, G=1.0, softening=0.5,
         sun_mass=50000.0, velocity_jitter=0.3, tangent_jitter=0.25,
         radius_jitter=2.0, planet_mass_min=50.0, planet_mass_max=400.0):
    duration = float(duration)
    frame_delay = float(frame_delay)
    num_planets = max(1, int(num_planets))
    sub_steps = max(1, int(sub_steps))
    trail_length = max(0, int(trail_length))
    view_scale = float(view_scale)
    G = float(G)
    softening = float(softening)
    sun_mass = float(sun_mass)
    velocity_jitter = float(velocity_jitter)
    tangent_jitter = float(tangent_jitter)
    radius_jitter = float(radius_jitter)
    planet_mass_min = float(planet_mass_min)
    planet_mass_max = float(planet_mass_max)
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, num_planets, sub_steps,
        trail_length, view_scale, G, softening, sun_mass,
        velocity_jitter, tangent_jitter, radius_jitter,
        planet_mass_min, planet_mass_max))


if __name__ == "__main__":
    main()
