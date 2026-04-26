import curses
import math
import random
import time


COLOR_DIGIT = 1
COLOR_COLON = 2
COLOR_LABEL = 3
COLOR_RING_DIM = 4
COLOR_RING_MAJOR = 5
COLOR_HAND = 6
COLOR_TRAIL = 7
COLOR_MINUTE = 8
COLOR_SPARK = 9

DIGITS = {
    "0": ["#####", "#   #", "#   #", "#   #", "#####"],
    "1": ["  #  ", " ##  ", "  #  ", "  #  ", " ### "],
    "2": ["#####", "    #", "#####", "#    ", "#####"],
    "3": ["#####", "    #", " ####", "    #", "#####"],
    "4": ["#   #", "#   #", "#####", "    #", "    #"],
    "5": ["#####", "#    ", "#####", "    #", "#####"],
    "6": ["#####", "#    ", "#####", "#   #", "#####"],
    "7": ["#####", "    #", "    #", "    #", "    #"],
    "8": ["#####", "#   #", "#####", "#   #", "#####"],
    "9": ["#####", "#   #", "#####", "    #", "#####"],
    ":": ["     ", "  #  ", "     ", "  #  ", "     "],
    " ": ["     ", "     ", "     ", "     ", "     "],
}

DIGIT_W = 5
DIGIT_H = 5
NUM_TICKS = 60
TRAIL_SEGMENTS = 14


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_DIGIT, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_COLON, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_RING_DIM, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_RING_MAJOR, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_HAND, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_TRAIL, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_MINUTE, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_SPARK, curses.COLOR_WHITE, -1)


def draw_digit(stdscr, ch, top_y, left_x, scale, attr, max_y, max_x):
    pattern = DIGITS.get(ch)
    if pattern is None:
        return
    for ry, row in enumerate(pattern):
        for cx, p in enumerate(row):
            if p == " ":
                continue
            for sy in range(scale):
                y = top_y + ry * scale + sy
                if not (0 <= y < max_y - 1):
                    continue
                x_start = left_x + cx * scale
                x_end = min(x_start + scale, max_x - 1)
                if x_start < 0 or x_start >= max_x:
                    continue
                try:
                    stdscr.addstr(y, x_start, "#" * (x_end - x_start), attr)
                except curses.error:
                    pass


def ring_pos(cx, cy, rx, ry, angle):
    return cx + rx * math.cos(angle), cy + ry * math.sin(angle)


def draw_ring(stdscr, cx, cy, rx, ry, sec_smooth, min_smooth, max_y, max_x):
    """Draw the surrounding ring with ticks, second hand, minute marker."""
    # Static ticks
    for i in range(NUM_TICKS):
        angle = i / NUM_TICKS * math.tau - math.pi / 2
        x, y = ring_pos(cx, cy, rx, ry, angle)
        xi, yi = int(round(x)), int(round(y))
        if not (0 <= xi < max_x and 0 <= yi < max_y - 1):
            continue
        is_quarter = (i % 15 == 0)
        is_major = (i % 5 == 0)
        if is_quarter:
            ch = "+"
            attr = curses.color_pair(COLOR_RING_MAJOR) | curses.A_BOLD | curses.A_REVERSE
        elif is_major:
            ch = "+"
            attr = curses.color_pair(COLOR_RING_MAJOR) | curses.A_BOLD
        else:
            ch = "."
            attr = curses.color_pair(COLOR_RING_DIM) | curses.A_DIM
        try:
            stdscr.addstr(yi, xi, ch, attr)
        except curses.error:
            pass

    sec_angle = (sec_smooth / 60) * math.tau - math.pi / 2

    # Trail behind the second hand (fades)
    for i in range(TRAIL_SEGMENTS, 0, -1):
        trail_angle = sec_angle - i * (math.tau / NUM_TICKS / 2.5)
        x, y = ring_pos(cx, cy, rx, ry, trail_angle)
        xi, yi = int(round(x)), int(round(y))
        if not (0 <= xi < max_x and 0 <= yi < max_y - 1):
            continue
        intensity = 1 - (i / TRAIL_SEGMENTS)
        if intensity < 0.25:
            ch = "."
            attr = curses.color_pair(COLOR_TRAIL) | curses.A_DIM
        elif intensity < 0.55:
            ch = "*"
            attr = curses.color_pair(COLOR_TRAIL) | curses.A_DIM
        else:
            ch = "*"
            attr = curses.color_pair(COLOR_TRAIL) | curses.A_BOLD
        try:
            stdscr.addstr(yi, xi, ch, attr)
        except curses.error:
            pass

    # Current second hand (bright)
    hx, hy = ring_pos(cx, cy, rx, ry, sec_angle)
    xi, yi = int(round(hx)), int(round(hy))
    if 0 <= xi < max_x and 0 <= yi < max_y - 1:
        try:
            stdscr.addstr(yi, xi, "@",
                          curses.color_pair(COLOR_HAND)
                          | curses.A_BOLD | curses.A_REVERSE)
        except curses.error:
            pass

    # Minute hand at slightly inset radius
    min_angle = (min_smooth / 60) * math.tau - math.pi / 2
    mx, my = ring_pos(cx, cy, rx * 0.78, ry * 0.78, min_angle)
    xi, yi = int(round(mx)), int(round(my))
    if 0 <= xi < max_x and 0 <= yi < max_y - 1:
        try:
            stdscr.addstr(yi, xi, "M",
                          curses.color_pair(COLOR_MINUTE) | curses.A_BOLD)
        except curses.error:
            pass


def update_sparks(sparks, sec_smooth, sec_angle, cx, cy, rx, ry, dt):
    """Spawn new sparks near the second hand and age existing ones."""
    # Spawn a few sparks each frame near the hand position
    for _ in range(2):
        sparks.append({
            "x": cx + rx * math.cos(sec_angle) + random.uniform(-1, 1),
            "y": cy + ry * math.sin(sec_angle) + random.uniform(-0.5, 0.5),
            "vx": random.uniform(-3, 3),
            "vy": random.uniform(-2, 2),
            "age": 0.0,
        })

    # Update existing sparks
    for s in sparks:
        s["age"] += dt
        s["x"] += s["vx"] * dt
        s["y"] += s["vy"] * dt
        s["vy"] += 1.5 * dt  # gentle gravity

    # Remove old ones
    sparks[:] = [s for s in sparks if s["age"] < 1.2]


def draw_sparks(stdscr, sparks, max_y, max_x):
    for s in sparks:
        xi, yi = int(round(s["x"])), int(round(s["y"]))
        if not (0 <= xi < max_x and 0 <= yi < max_y - 1):
            continue
        age_ratio = s["age"] / 1.2
        if age_ratio < 0.3:
            ch = "*"
            attr = curses.color_pair(COLOR_SPARK) | curses.A_BOLD
        elif age_ratio < 0.7:
            ch = "."
            attr = curses.color_pair(COLOR_TRAIL) | curses.A_BOLD
        else:
            ch = "."
            attr = curses.color_pair(COLOR_RING_DIM) | curses.A_DIM
        try:
            stdscr.addstr(yi, xi, ch, attr)
        except curses.error:
            pass


def run(stdscr, duration, frame_delay, time_format, scale):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    sparks = []
    start = time.monotonic()
    last_frame = start

    while True:
        now_mono = time.monotonic()
        if now_mono - start >= duration:
            break
        dt = min(now_mono - last_frame, 0.2)
        last_frame = now_mono

        max_y, max_x = stdscr.getmaxyx()

        # Sub-second precision time
        t_now = time.time()
        local_now = time.localtime(t_now)
        frac = t_now - int(t_now)

        sec_smooth = local_now.tm_sec + frac
        min_smooth = local_now.tm_min + sec_smooth / 60

        if time_format == "12":
            disp_hour = local_now.tm_hour % 12
            if disp_hour == 0:
                disp_hour = 12
            time_str = f"{disp_hour:2d}:{local_now.tm_min:02d}:{local_now.tm_sec:02d}"
            ampm = "AM" if local_now.tm_hour < 12 else "PM"
        else:
            time_str = (f"{local_now.tm_hour:02d}:"
                        f"{local_now.tm_min:02d}:{local_now.tm_sec:02d}")
            ampm = ""

        # Auto-scale down if needed (leave room for ring + date)
        eff_scale = scale
        while eff_scale > 1 and (
            len(time_str) * DIGIT_W * eff_scale > max_x - 24
            or DIGIT_H * eff_scale > max_y - 10
        ):
            eff_scale -= 1

        total_w = len(time_str) * DIGIT_W * eff_scale
        total_h = DIGIT_H * eff_scale
        start_x = max(0, (max_x - total_w) // 2)
        start_y = max(2, (max_y - total_h) // 2)

        stdscr.erase()

        # Date label above the ring
        date_str = time.strftime("%A, %B %d, %Y", local_now)
        try:
            stdscr.addstr(max(0, start_y - 4),
                          max(0, (max_x - len(date_str)) // 2),
                          date_str[:max_x - 1],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        # Ring around the digits
        cx = max_x // 2
        cy = (start_y + start_y + total_h) // 2
        ring_ry = (total_h // 2) + 3
        ring_rx = max(total_w // 2 + 8, ring_ry * 2)
        draw_ring(stdscr, cx, cy, ring_rx, ring_ry, sec_smooth, min_smooth,
                  max_y, max_x)

        # Sparks emitted from the second hand position
        sec_angle = (sec_smooth / 60) * math.tau - math.pi / 2
        update_sparks(sparks, sec_smooth, sec_angle, cx, cy, ring_rx, ring_ry, dt)
        draw_sparks(stdscr, sparks, max_y, max_x)

        # Draw the digits on top
        x = start_x
        for ch in time_str:
            attr = curses.color_pair(COLOR_DIGIT) | curses.A_BOLD
            if ch == ":":
                # Pulse with sub-second smoothness
                if frac < 0.5:
                    attr = curses.color_pair(COLOR_COLON) | curses.A_BOLD
                else:
                    attr = curses.color_pair(COLOR_COLON) | curses.A_DIM
            draw_digit(stdscr, ch, start_y, x, eff_scale, attr, max_y, max_x)
            x += DIGIT_W * eff_scale

        if ampm:
            ampm_y = start_y + total_h + 1
            try:
                stdscr.addstr(ampm_y, max(0, (max_x - len(ampm)) // 2), ampm,
                              curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
            except curses.error:
                pass

        stdscr.refresh()
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=20, frame_delay=0.04, time_format="24", scale=2):
    duration = float(duration)
    frame_delay = float(frame_delay)
    scale = max(1, int(scale))
    if time_format not in ("12", "24"):
        time_format = "24"
    curses.wrapper(lambda stdscr: run(stdscr, duration, frame_delay, time_format, scale))


if __name__ == "__main__":
    main()
