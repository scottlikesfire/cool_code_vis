import curses
import random
import time


CHARS = " .,;%#@"
MAX_HEAT = 36

COLOR_RED = 1
COLOR_YELLOW = 2
COLOR_WHITE = 3


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    # Heat gradient: red -> yellow -> white
    curses.init_pair(COLOR_RED, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_YELLOW, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_WHITE, curses.COLOR_WHITE, -1)


def heat_to_attr(heat):
    if heat <= 0:
        return " ", 0
    pct = heat / MAX_HEAT
    if pct < 0.4:
        color = curses.color_pair(COLOR_RED) | curses.A_DIM
    elif pct < 0.65:
        color = curses.color_pair(COLOR_RED) | curses.A_BOLD
    elif pct < 0.85:
        color = curses.color_pair(COLOR_YELLOW) | curses.A_BOLD
    else:
        color = curses.color_pair(COLOR_WHITE) | curses.A_BOLD
    char_idx = min(int(pct * len(CHARS)), len(CHARS) - 1)
    return CHARS[char_idx], color


def spawn_spark(sparks, fire, height, width):
    """Spawn a spark from a random hot column near the bottom."""
    x = random.randint(0, width - 1)
    # Find a y in the lower portion where heat is high enough
    spawn_y_max = max(1, height // 3)
    y = height - random.randint(1, max(1, spawn_y_max))
    if 0 <= y < height and fire[y][x] > MAX_HEAT // 2:
        sparks.append({
            "x": float(x),
            "y": float(y),
            "vx": random.uniform(-0.4, 0.4),
            "vy": -random.uniform(0.6, 1.6),  # negative = upward
            "age": 0.0,
            "lifetime": random.uniform(1.5, 3.5),
        })


def update_sparks(sparks, dt, width):
    """Advance spark physics. Sparks float up with slight horizontal drift."""
    for s in sparks:
        s["age"] += dt
        # Slight random horizontal drift each frame (like real embers in air currents)
        s["vx"] += random.uniform(-0.5, 0.5) * dt
        # Buoyancy: keep moving up; vy slightly accelerates negatively then dampens
        s["vy"] += random.uniform(-0.3, 0.0) * dt
        # Cap velocities
        s["vx"] = max(-2.0, min(2.0, s["vx"]))
        s["vy"] = max(-3.0, min(0.0, s["vy"]))
        s["x"] += s["vx"]
        s["y"] += s["vy"]

    # Cull sparks that left the screen or aged out
    sparks[:] = [
        s for s in sparks
        if s["age"] < s["lifetime"]
        and 0 <= s["x"] < width
        and s["y"] >= -2
    ]


def draw_sparks(stdscr, sparks, max_y, max_x):
    for s in sparks:
        xi, yi = int(round(s["x"])), int(round(s["y"]))
        if not (0 <= xi < max_x and 0 <= yi < max_y - 1):
            continue
        age_ratio = s["age"] / s["lifetime"]
        if age_ratio < 0.25:
            ch = "*"
            attr = curses.color_pair(COLOR_WHITE) | curses.A_BOLD
        elif age_ratio < 0.5:
            ch = "*"
            attr = curses.color_pair(COLOR_YELLOW) | curses.A_BOLD
        elif age_ratio < 0.75:
            ch = "."
            attr = curses.color_pair(COLOR_YELLOW) | curses.A_BOLD
        else:
            ch = "."
            attr = curses.color_pair(COLOR_RED) | curses.A_DIM
        try:
            stdscr.addstr(yi, xi, ch, attr)
        except curses.error:
            pass


def run(stdscr, duration, frame_delay, intensity, spark_rate):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    max_y, max_x = stdscr.getmaxyx()
    height = max_y - 1
    width = max_x
    fire = [[0] * width for _ in range(height)]
    for x in range(width):
        fire[height - 1][x] = MAX_HEAT

    sparks = []
    start_time = time.monotonic()
    last_frame = start_time

    while True:
        now = time.monotonic()
        if now - start_time >= duration:
            break
        dt = min(now - last_frame, 0.2)
        last_frame = now

        # Modulate the heat source
        for x in range(width):
            if random.random() < 0.95:
                fire[height - 1][x] = MAX_HEAT
            else:
                fire[height - 1][x] = max(0, MAX_HEAT - random.randint(0, intensity))

        # Propagate heat upward (Doom fire algorithm)
        for y in range(height - 2, -1, -1):
            for x in range(width):
                src_x = x + random.randint(-1, 1)
                src_x = max(0, min(width - 1, src_x))
                decay = random.randint(0, intensity)
                fire[y][x] = max(0, fire[y + 1][src_x] - decay)

        # Spawn new sparks
        for _ in range(spark_rate):
            if random.random() < 0.5:
                spawn_spark(sparks, fire, height, width)

        update_sparks(sparks, dt, width)

        stdscr.erase()
        for y in range(height):
            for x in range(width):
                ch, attr = heat_to_attr(fire[y][x])
                if ch == " ":
                    continue
                try:
                    stdscr.addstr(y, x, ch, attr)
                except curses.error:
                    pass

        draw_sparks(stdscr, sparks, max_y, max_x)
        stdscr.refresh()

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=15, frame_delay=0.04, intensity=3, spark_rate=4):
    duration = float(duration)
    frame_delay = float(frame_delay)
    intensity = max(1, int(intensity))
    spark_rate = max(0, int(spark_rate))
    curses.wrapper(lambda stdscr: run(stdscr, duration, frame_delay, intensity,
                                      spark_rate))


if __name__ == "__main__":
    main()
