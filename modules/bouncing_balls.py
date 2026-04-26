import curses
import random
import time


CHARS_TRAIL = ".oO@"


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
    return len(palette)


def run(stdscr, duration, num_balls, gravity, frame_delay, trail_length, damping):
    num_colors = init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    max_y, max_x = stdscr.getmaxyx()

    balls = []
    for i in range(num_balls):
        balls.append({
            "x": random.uniform(2, max(3, max_x - 2)),
            "y": random.uniform(1, max(2, max_y / 2)),
            "vx": random.uniform(-25, 25),
            "vy": random.uniform(-10, 10),
            "color": (i % num_colors) + 1,
            "trail": [],
        })

    start_time = time.monotonic()
    last_time = start_time

    while True:
        now = time.monotonic()
        if now - start_time >= duration:
            break
        dt = now - last_time
        last_time = now
        dt = min(dt, 0.1)  # cap dt to avoid teleport-on-pause

        max_y, max_x = stdscr.getmaxyx()

        # Physics step
        for ball in balls:
            ball["vy"] += gravity * dt
            ball["x"] += ball["vx"] * dt
            ball["y"] += ball["vy"] * dt

            if ball["x"] < 0:
                ball["x"] = 0
                ball["vx"] = -ball["vx"] * damping
            elif ball["x"] > max_x - 1:
                ball["x"] = max_x - 1
                ball["vx"] = -ball["vx"] * damping
            if ball["y"] < 0:
                ball["y"] = 0
                ball["vy"] = -ball["vy"] * damping
            elif ball["y"] > max_y - 2:
                ball["y"] = max_y - 2
                ball["vy"] = -ball["vy"] * damping
                ball["vx"] *= 0.99

            ball["trail"].append((ball["x"], ball["y"]))
            if len(ball["trail"]) > trail_length:
                ball["trail"].pop(0)

        stdscr.erase()

        # Draw trails (older = dimmer)
        for ball in balls:
            trail = ball["trail"]
            for i, (tx, ty) in enumerate(trail[:-1]):
                tx_i, ty_i = int(tx), int(ty)
                if not (0 <= tx_i < max_x and 0 <= ty_i < max_y - 1):
                    continue
                age_ratio = i / max(1, len(trail) - 1)
                ch = CHARS_TRAIL[min(int(age_ratio * len(CHARS_TRAIL)),
                                     len(CHARS_TRAIL) - 1)]
                attr = curses.color_pair(ball["color"]) | curses.A_DIM
                try:
                    stdscr.addstr(ty_i, tx_i, ch, attr)
                except curses.error:
                    pass

            x, y = int(ball["x"]), int(ball["y"])
            if 0 <= x < max_x and 0 <= y < max_y - 1:
                try:
                    stdscr.addstr(y, x, "@",
                                  curses.color_pair(ball["color"]) | curses.A_BOLD)
                except curses.error:
                    pass

        stdscr.refresh()
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=20, num_balls=6, gravity=25, frame_delay=0.04,
         trail_length=12, damping=0.92):
    duration = float(duration)
    num_balls = max(1, int(num_balls))
    gravity = float(gravity)
    frame_delay = float(frame_delay)
    trail_length = max(0, int(trail_length))
    damping = float(damping)
    curses.wrapper(lambda stdscr: run(stdscr, duration, num_balls, gravity,
                                      frame_delay, trail_length, damping))


if __name__ == "__main__":
    main()
