import curses
import random
import time


COLOR_GREEN_BAR = 1
COLOR_BLUE_BAR = 2
COLOR_TITLE = 3
COLOR_LABEL = 4
COLOR_DIM = 5
COLOR_DONE = 6


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_GREEN_BAR, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_BLUE_BAR, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_TITLE, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_DIM, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_DONE, curses.COLOR_GREEN, -1)


def generate_hex_title():
    return "0x" + "".join(random.choice("0123456789ABCDEF") for _ in range(12))


def run(stdscr, num_bars, duration, completion_pause):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(50)

    # Each bar finishes at a random fraction of the total duration
    bars = []
    for _ in range(num_bars):
        finish_frac = random.uniform(0.15, 0.95)
        finish_time = duration * finish_frac
        title = generate_hex_title()
        bars.append({"title": title, "finish_time": finish_time})

    # Sort by finish time so they complete in a staggered order
    bars.sort(key=lambda b: b["finish_time"])

    start_time = time.monotonic()

    while True:
        now = time.monotonic()
        elapsed = now - start_time

        stdscr.erase()
        max_y, max_x = stdscr.getmaxyx()

        # Title
        title = "[ SYSTEM PROCESSES ]"
        try:
            stdscr.addstr(0, max(0, (max_x - len(title)) // 2), title[:max_x - 1],
                          curses.color_pair(COLOR_TITLE) | curses.A_BOLD)
        except curses.error:
            pass

        # Individual progress bars
        bar_width = max_x - 30
        if bar_width < 10:
            bar_width = 10

        y = 2
        for bar in bars:
            if y >= max_y - 5:
                break

            pct = min(1.0, elapsed / bar["finish_time"])
            filled = int(bar_width * pct)
            pct_text = f"{int(pct * 100):>3}%"
            is_done = pct >= 1.0

            # Title label
            label = bar["title"]
            try:
                stdscr.addstr(y, 2, label[:max_x - 4],
                              curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
            except curses.error:
                pass

            # Bar
            bar_y = y + 1
            try:
                stdscr.addstr(bar_y, 2, "[", curses.A_DIM)
                if filled > 0:
                    bar_color = COLOR_DONE if is_done else COLOR_GREEN_BAR
                    stdscr.addstr(bar_y, 3, "#" * filled,
                                  curses.color_pair(bar_color) | curses.A_BOLD)
                remaining = bar_width - filled
                if remaining > 0:
                    stdscr.addstr(bar_y, 3 + filled, "-" * remaining, curses.A_DIM)
                stdscr.addstr(bar_y, 3 + bar_width, "] " + pct_text, curses.A_DIM)
                if is_done:
                    stdscr.addstr(bar_y, 3 + bar_width + len("] " + pct_text) + 1,
                                  "DONE", curses.color_pair(COLOR_DONE) | curses.A_BOLD)
            except curses.error:
                pass

            y += 3

        # Overall progress bar at bottom (blue)
        overall_pct = min(1.0, elapsed / duration)
        overall_filled = int(bar_width * overall_pct)
        overall_pct_text = f"{int(overall_pct * 100):>3}%"
        overall_y = max_y - 3

        if overall_y > y:
            try:
                separator = "-" * (max_x - 4)
                stdscr.addstr(overall_y - 1, 2, separator, curses.A_DIM)
                stdscr.addstr(overall_y, 2, "[", curses.A_DIM)
                if overall_filled > 0:
                    stdscr.addstr(overall_y, 3, "#" * overall_filled,
                                  curses.color_pair(COLOR_BLUE_BAR) | curses.A_BOLD)
                overall_remaining = bar_width - overall_filled
                if overall_remaining > 0:
                    stdscr.addstr(overall_y, 3 + overall_filled,
                                  "-" * overall_remaining, curses.A_DIM)
                stdscr.addstr(overall_y, 3 + bar_width,
                              "] " + overall_pct_text + "  OVERALL",
                              curses.color_pair(COLOR_BLUE_BAR) | curses.A_BOLD)
            except curses.error:
                pass

        stdscr.refresh()

        # Check if duration reached
        if elapsed >= duration:
            # Completion pause
            pause_start = time.monotonic()
            stdscr.timeout(100)
            while time.monotonic() - pause_start < completion_pause:
                key = stdscr.getch()
                if key == ord("q") or key == 27:
                    return
            break

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            break


def main(num_bars=8, duration=10, completion_pause=3):
    num_bars = int(num_bars)
    duration = float(duration)
    completion_pause = float(completion_pause)
    curses.wrapper(lambda stdscr: run(stdscr, num_bars, duration, completion_pause))


if __name__ == "__main__":
    main()
