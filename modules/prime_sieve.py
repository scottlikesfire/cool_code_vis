import curses
import time


COLOR_UNMARKED = 1
COLOR_PRIME = 2
COLOR_COMPOSITE = 3
COLOR_CURRENT = 4
COLOR_TITLE = 5


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_UNMARKED, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_PRIME, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_COMPOSITE, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_CURRENT, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_TITLE, curses.COLOR_CYAN, -1)


def draw(stdscr, n, status, current, max_y, max_x, cell_w):
    stdscr.erase()
    title = f"Sieve of Eratosthenes (n={n})"
    try:
        stdscr.addstr(0, max(0, (max_x - len(title)) // 2), title[:max_x - 1],
                      curses.color_pair(COLOR_TITLE) | curses.A_BOLD | curses.A_REVERSE)
    except curses.error:
        pass

    cols = max(1, (max_x - 2) // cell_w)
    start_y = 2
    for num in range(2, n + 1):
        idx = num - 2
        row = start_y + idx // cols
        col = 2 + (idx % cols) * cell_w
        if row >= max_y - 2:
            break

        s = status[num]
        if num == current:
            attr = curses.color_pair(COLOR_CURRENT) | curses.A_BOLD | curses.A_REVERSE
        elif s == "prime":
            attr = curses.color_pair(COLOR_PRIME) | curses.A_BOLD
        elif s == "composite":
            attr = curses.color_pair(COLOR_COMPOSITE) | curses.A_DIM
        else:
            attr = curses.color_pair(COLOR_UNMARKED)
        try:
            stdscr.addstr(row, col, f"{num:>{cell_w - 1}}", attr)
        except curses.error:
            pass

    primes_found = sum(1 for s in status if s == "prime")
    footer = f"Primes found: {primes_found}  |  Press q to quit"
    try:
        stdscr.addstr(max_y - 1, 2, footer[:max_x - 4], curses.A_DIM)
    except curses.error:
        pass

    stdscr.refresh()


def run(stdscr, n, step_delay, completion_pause):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(step_delay * 1000))

    max_y, max_x = stdscr.getmaxyx()
    cell_w = len(str(n)) + 1

    status = ["unmarked"] * (n + 1)
    status[0] = status[1] = "composite"

    p = 2
    while p * p <= n:
        if status[p] != "composite":
            status[p] = "prime"
            for multiple in range(p * p, n + 1, p):
                if status[multiple] != "composite":
                    status[multiple] = "composite"
                    draw(stdscr, n, status, multiple, max_y, max_x, cell_w)
                    key = stdscr.getch()
                    if key == ord("q") or key == 27:
                        return
        p += 1

    # Mark remaining unmarked as primes
    for i in range(2, n + 1):
        if status[i] == "unmarked":
            status[i] = "prime"

    draw(stdscr, n, status, -1, max_y, max_x, cell_w)

    stdscr.timeout(100)
    pause_start = time.monotonic()
    while time.monotonic() - pause_start < completion_pause:
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(n=300, step_delay=0.02, completion_pause=3):
    n = int(n)
    step_delay = float(step_delay)
    completion_pause = float(completion_pause)
    curses.wrapper(lambda stdscr: run(stdscr, n, step_delay, completion_pause))


if __name__ == "__main__":
    main()
