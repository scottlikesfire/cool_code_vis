import curses
import random
import shutil
import sys
import time

from modules._quit_helper import StdinPoller


COLOR_GREEN_BRIGHT = 1
COLOR_GREEN_DIM = 2
COLOR_WHITE_HEAD = 3


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_GREEN_BRIGHT, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_GREEN_DIM, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_WHITE_HEAD, curses.COLOR_WHITE, -1)


CHARS = "abcdefghijklmnopqrstuvwxyz0123456789@#$%&*+=?/<>"


def show_loading(loading_duration):
    term_width = shutil.get_terminal_size().columns
    term_height = shutil.get_terminal_size().lines
    bar_width = 40
    title = "loading matrix code"

    steps = 50
    interval = loading_duration / steps

    sys.stdout.write("\033[2J\033[H")
    with StdinPoller() as poller:
        for i in range(steps + 1):
            if poller.should_quit():
                sys.stdout.write("\033[2J\033[H")
                sys.stdout.flush()
                return True
            pct = i / steps
            filled = int(bar_width * pct)
            bar = "#" * filled + "-" * (bar_width - filled)
            pct_text = f"{int(pct * 100)}%"

            title_x = max(0, (term_width - len(title)) // 2)
            bar_str = f"[{bar}] {pct_text}"
            bar_x = max(0, (term_width - len(bar_str)) // 2)
            y = term_height // 2

            sys.stdout.write(f"\033[{y};{title_x + 1}H\033[32;1m{title}\033[0m")
            sys.stdout.write(f"\033[{y + 2};{bar_x + 1}H\033[32m{bar_str}\033[0m")
            sys.stdout.flush()
            time.sleep(interval)

    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()
    return False


def seed_initial_drops(columns, max_x, max_y, density):
    """Spawn drops already mid-screen so rain doesn't start empty."""
    for col in range(max_x):
        if random.random() < density * 8:
            trail_len = random.randint(5, max_y // 2)
            head_y = random.randint(0, max_y - 1)
            columns[col] = {
                "head_y": head_y,
                "trail_len": trail_len,
                "active": True,
                "speed": random.randint(1, 2),
                "tick": 0,
            }


def run(stdscr, duration, speed, density):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass

    max_y, max_x = stdscr.getmaxyx()
    frame_delay = 1.0 / speed

    # Seed some drops already mid-screen so it doesn't start empty
    columns = {}
    seed_initial_drops(columns, max_x, max_y, density)

    start_time = time.monotonic()
    stdscr.timeout(int(frame_delay * 1000))

    while True:
        now = time.monotonic()
        if now - start_time >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()

        # Spawn new drops based on density
        for col in range(max_x):
            if col not in columns or not columns[col]["active"]:
                if random.random() < density:
                    trail_len = random.randint(5, max_y // 2)
                    columns[col] = {
                        "head_y": 0,
                        "trail_len": trail_len,
                        "active": True,
                        "speed": random.randint(1, 2),
                        "tick": 0,
                    }

        stdscr.erase()

        for col, drop in list(columns.items()):
            if not drop["active"]:
                continue

            # Only advance on matching ticks (slower drops skip frames)
            drop["tick"] += 1
            if drop["tick"] < drop["speed"]:
                # Still draw but don't advance
                pass
            else:
                drop["tick"] = 0
                drop["head_y"] += 1

            head_y = drop["head_y"]
            trail_len = drop["trail_len"]

            if col >= max_x:
                continue

            # Draw the trail
            for i in range(trail_len + 1):
                y = head_y - i
                if y < 0 or y >= max_y - 1:
                    continue

                ch = random.choice(CHARS)

                if i == 0:
                    # Head: bright white
                    try:
                        stdscr.addstr(y, col, ch,
                                      curses.color_pair(COLOR_WHITE_HEAD) | curses.A_BOLD)
                    except curses.error:
                        pass
                elif i < 3:
                    # Near head: bright green
                    try:
                        stdscr.addstr(y, col, ch,
                                      curses.color_pair(COLOR_GREEN_BRIGHT) | curses.A_BOLD)
                    except curses.error:
                        pass
                else:
                    # Trail: dim green
                    try:
                        stdscr.addstr(y, col, ch,
                                      curses.color_pair(COLOR_GREEN_DIM) | curses.A_DIM)
                    except curses.error:
                        pass

            # Deactivate if trail has fully passed the screen
            if head_y - trail_len >= max_y:
                drop["active"] = False

        stdscr.refresh()

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            break


def main(duration=10, speed=20, density=0.05, loading_duration=3):
    duration = float(duration)
    speed = float(speed)
    density = float(density)
    loading_duration = float(loading_duration)
    if loading_duration > 0:
        if show_loading(loading_duration):
            return
    curses.wrapper(lambda stdscr: run(stdscr, duration, speed, density))


if __name__ == "__main__":
    main()
