import curses
import math
import random
import time


COLOR_PALETTE = [
    curses.COLOR_RED,
    curses.COLOR_YELLOW,
    curses.COLOR_GREEN,
    curses.COLOR_CYAN,
    curses.COLOR_BLUE,
    curses.COLOR_MAGENTA,
    curses.COLOR_WHITE,
]

BURST_TYPES = ["simple", "fall", "ring", "willow", "multi"]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    for i, c in enumerate(COLOR_PALETTE):
        curses.init_pair(i + 1, c, -1)
    return len(COLOR_PALETTE)


def random_color():
    return random.randint(1, len(COLOR_PALETTE))


def random_color_excluding(exclude):
    c = random_color()
    while c == exclude and len(COLOR_PALETTE) > 1:
        c = random_color()
    return c


# ----- Burst patterns -----

def make_spark(x, y, vx, vy, color, lifetime, gravity_mult=1.0,
               parent_color=None, fade_duration=0.0):
    return {
        "type": "spark",
        "x": x, "y": y,
        "vx": vx, "vy": vy,
        "color": color,
        "lifetime": lifetime,
        "age": 0.0,
        "gravity_mult": gravity_mult,
        "parent_color": parent_color,
        "fade_duration": fade_duration,
    }


def burst_simple(particles, x, y, color, cfg):
    """Spherical burst — sparse particles flying outward."""
    count = cfg["simple_count"]
    smin, smax = cfg["simple_speed"]
    for _ in range(count):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(smin, smax)
        particles.append(make_spark(
            x, y,
            speed * math.cos(angle),
            speed * math.sin(angle) * 0.5,
            color,
            random.uniform(1.4, 2.0),
            gravity_mult=0.3,
        ))


def burst_fall(particles, x, y, color, cfg):
    """Burst whose pieces fall under full gravity after exploding outward."""
    count = cfg["fall_count"]
    smin, smax = cfg["fall_speed"]
    for _ in range(count):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(smin, smax)
        particles.append(make_spark(
            x, y,
            speed * math.cos(angle),
            speed * math.sin(angle) * 0.5,
            color,
            random.uniform(2.0, 2.8),
            gravity_mult=1.0,
        ))


def burst_ring(particles, x, y, color, cfg):
    """Tight ring — uniform spacing for a clean expanding circle."""
    count = cfg["ring_count"]
    smin, smax = cfg["ring_speed"]
    speed = random.uniform(smin, smax)
    for i in range(count):
        angle = i / count * math.tau
        particles.append(make_spark(
            x, y,
            speed * math.cos(angle),
            speed * math.sin(angle) * 0.5,
            color,
            random.uniform(1.6, 2.0),
            gravity_mult=0.4,
        ))


def burst_willow(particles, x, y, color, cfg):
    """Slow drooping particles that linger and fall."""
    count = cfg["willow_count"]
    smin, smax = cfg["willow_speed"]
    for _ in range(count):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(smin, smax)
        particles.append(make_spark(
            x, y,
            speed * math.cos(angle),
            speed * math.sin(angle) * 0.5 - 6,
            color,
            random.uniform(2.8, 4.0),
            gravity_mult=1.2,
        ))


def burst_multi(particles, x, y, color, cfg):
    """Initial seeds that re-explode in a single shared color."""
    count = cfg["multi_count"]
    smin, smax = cfg["multi_speed"]
    next_color = random_color_excluding(color)
    for _ in range(count):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(smin, smax)
        particles.append({
            "type": "seed",
            "x": x, "y": y,
            "vx": speed * math.cos(angle),
            "vy": speed * math.sin(angle) * 0.5,
            "color": color,
            "lifetime": random.uniform(0.7, 1.1),
            "age": 0.0,
            "gravity_mult": 0.6,
            "next_color": next_color,
            "secondary_count": cfg["multi_secondary_count"],
            "secondary_speed": cfg["multi_secondary_speed"],
            "fade_duration": cfg["multi_fade_duration"],
        })


def burst(particles, x, y, color, burst_type, cfg):
    if burst_type == "simple":
        burst_simple(particles, x, y, color, cfg)
    elif burst_type == "fall":
        burst_fall(particles, x, y, color, cfg)
    elif burst_type == "ring":
        burst_ring(particles, x, y, color, cfg)
    elif burst_type == "willow":
        burst_willow(particles, x, y, color, cfg)
    elif burst_type == "multi":
        burst_multi(particles, x, y, color, cfg)
    else:
        burst_simple(particles, x, y, color, cfg)


# ----- Spawning -----

def spawn_rocket(particles, max_x, max_y):
    x = random.uniform(max_x * 0.15, max_x * 0.85)
    color = random_color()
    target_y = random.uniform(2, max_y * 0.35)
    speed = random.uniform(18, 28)
    particles.append({
        "type": "rocket",
        "x": x, "y": max_y - 2,
        "vx": random.uniform(-2, 2),
        "vy": -speed,
        "target_y": target_y,
        "color": color,
        "burst_type": random.choice(BURST_TYPES),
        "lifetime": 5.0,
        "age": 0.0,
    })


# ----- Physics -----

def update_particles(particles, dt, max_x, max_y, gravity, cfg):
    new_particles = []
    for p in particles:
        p["age"] += dt
        ptype = p["type"]

        if ptype == "rocket":
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] += gravity * 0.4 * dt
            if p["y"] <= p["target_y"] or p["vy"] >= 0 or p["age"] >= p["lifetime"]:
                burst(new_particles, p["x"], p["y"], p["color"], p["burst_type"], cfg)
                continue

        elif ptype == "spark":
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] += gravity * p.get("gravity_mult", 1.0) * dt
            drag = 0.92 ** dt
            p["vx"] *= drag
            p["vy"] *= drag
            if p["age"] >= p["lifetime"]:
                continue

        elif ptype == "seed":
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] += gravity * p.get("gravity_mult", 1.0) * dt
            p["vx"] *= 0.88 ** dt
            if p["age"] >= p["lifetime"]:
                # Secondary burst — all sparks share the same next_color and
                # fade in from the seed's own color over fade_duration.
                smin, smax = p["secondary_speed"]
                for _ in range(p["secondary_count"]):
                    angle = random.uniform(0, math.tau)
                    speed = random.uniform(smin, smax)
                    new_particles.append(make_spark(
                        p["x"], p["y"],
                        speed * math.cos(angle),
                        speed * math.sin(angle) * 0.5,
                        p["next_color"],
                        random.uniform(1.0, 1.4),
                        gravity_mult=0.5,
                        parent_color=p["color"],
                        fade_duration=p["fade_duration"],
                    ))
                continue

        if -2 <= p["x"] < max_x + 2 and -5 <= p["y"] < max_y + 2:
            new_particles.append(p)

    particles.extend(new_particles)
    return [p for p in particles
            if not (p["type"] in ("spark", "seed") and p["age"] >= p["lifetime"])]


# ----- Drawing -----

def _put(stdscr, y, x, ch, attr, max_y, max_x):
    if 0 <= x < max_x and 0 <= y < max_y - 1:
        try:
            stdscr.addstr(y, x, ch, attr)
        except curses.error:
            pass


def spark_color(p):
    """Return the color id this spark should render with this frame.

    If the spark has a parent color and is still within its fade window,
    pick parent vs final color stochastically with a probability that drops
    linearly from 1 → 0 over the fade duration. Across many particles and
    many frames this looks like a smooth color transition.
    """
    parent = p.get("parent_color")
    fade = p.get("fade_duration", 0)
    if parent and fade > 0 and p["age"] < fade:
        parent_prob = 1.0 - (p["age"] / fade)
        if random.random() < parent_prob:
            return parent
    return p["color"]


def draw_particles(stdscr, particles, max_y, max_x):
    for p in particles:
        ptype = p["type"]
        if ptype == "rocket":
            xi, yi = int(round(p["x"])), int(round(p["y"]))
            _put(stdscr, yi, xi, "^",
                 curses.color_pair(p["color"]) | curses.A_BOLD | curses.A_REVERSE,
                 max_y, max_x)
        elif ptype in ("spark", "seed"):
            xi, yi = int(round(p["x"])), int(round(p["y"]))
            age_ratio = p["age"] / p["lifetime"]
            color_id = spark_color(p)
            if age_ratio < 0.35:
                ch = "*"
                attr = curses.color_pair(color_id) | curses.A_BOLD
            elif age_ratio < 0.7:
                ch = "+"
                attr = curses.color_pair(color_id) | curses.A_BOLD
            else:
                ch = "."
                attr = curses.color_pair(color_id) | curses.A_DIM
            _put(stdscr, yi, xi, ch, attr, max_y, max_x)


# ----- Main loop -----

def run(stdscr, duration, frame_delay, gravity, launch_rate, cfg):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.clear()
    stdscr.refresh()
    stdscr.timeout(int(frame_delay * 1000))

    particles = []
    start = time.monotonic()
    last_frame = start

    while True:
        now = time.monotonic()
        if now - start >= duration:
            break
        dt = min(now - last_frame, 0.1)
        last_frame = now

        max_y, max_x = stdscr.getmaxyx()

        if random.random() < launch_rate * dt:
            spawn_rocket(particles, max_x, max_y)

        particles = update_particles(particles, dt, max_x, max_y, gravity, cfg)

        stdscr.erase()
        draw_particles(stdscr, particles, max_y, max_x)
        stdscr.refresh()

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=20, frame_delay=0.04, gravity=15, launch_rate=1.5,
         simple_count=8, fall_count=8, ring_count=12, willow_count=6,
         multi_count=3, multi_secondary_count=6, multi_fade_duration=0.15,
         simple_speed=None, fall_speed=None, ring_speed=None,
         willow_speed=None, multi_speed=None, multi_secondary_speed=None):
    cfg = {
        "simple_count": int(simple_count),
        "fall_count": int(fall_count),
        "ring_count": int(ring_count),
        "willow_count": int(willow_count),
        "multi_count": int(multi_count),
        "multi_secondary_count": int(multi_secondary_count),
        "multi_fade_duration": float(multi_fade_duration),
        "simple_speed": tuple(simple_speed) if simple_speed else (45, 65),
        "fall_speed": tuple(fall_speed) if fall_speed else (45, 60),
        "ring_speed": tuple(ring_speed) if ring_speed else (50, 65),
        "willow_speed": tuple(willow_speed) if willow_speed else (25, 35),
        "multi_speed": tuple(multi_speed) if multi_speed else (30, 42),
        "multi_secondary_speed": tuple(multi_secondary_speed) if multi_secondary_speed else (70, 90),
    }
    duration = float(duration)
    frame_delay = float(frame_delay)
    gravity = float(gravity)
    launch_rate = float(launch_rate)
    curses.wrapper(lambda stdscr: run(stdscr, duration, frame_delay, gravity,
                                      launch_rate, cfg))


if __name__ == "__main__":
    main()
