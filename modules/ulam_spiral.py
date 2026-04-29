import curses
import time


COLOR_PRIME = 1
COLOR_NONPRIME = 2
COLOR_CURRENT = 3
COLOR_LABEL = 4


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_PRIME, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_NONPRIME, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_CURRENT, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def sieve(n):
    """Sieve of Eratosthenes up to n. Returns a boolean list of length n+1."""
    is_prime = [False, False] + [True] * max(0, n - 1)
    for i in range(2, int(n ** 0.5) + 1):
        if is_prime[i]:
            for j in range(i * i, n + 1, i):
                is_prime[j] = False
    return is_prime


# Spiral direction sequence: R, U, L, D in screen coords (y down).
# Pattern of step counts: 1, 1, 2, 2, 3, 3, 4, 4, ...
def spiral_steps():
    dirs = [(1, 0), (0, -1), (-1, 0), (0, 1)]
    di = 0
    leg = 1
    while True:
        for _ in range(2):
            for _ in range(leg):
                yield dirs[di]
            di = (di + 1) % 4
        leg += 1


def run(stdscr, duration, frame_delay, max_n, numbers_per_frame,
        completion_pause):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.clear()
    stdscr.refresh()
    stdscr.timeout(int(frame_delay * 1000))

    primes = sieve(max_n)

    max_y, max_x = stdscr.getmaxyx()
    cx = max_x // 2
    cy = (max_y - 1) // 2
    x, y = cx, cy
    walker = spiral_steps()

    n = 1
    start = time.monotonic()
    finished = False
    finished_at = 0.0

    while True:
        now = time.monotonic()
        elapsed = now - start
        if elapsed >= duration:
            break
        if finished and now - finished_at >= completion_pause:
            break

        max_y, max_x = stdscr.getmaxyx()

        # Plot up to numbers_per_frame integers this frame
        if not finished:
            for _ in range(numbers_per_frame):
                if 0 <= x < max_x and 0 <= y < max_y - 1:
                    if n == 1:
                        ch = "1"
                        attr = curses.color_pair(COLOR_PRIME) | curses.A_BOLD | curses.A_REVERSE
                    elif primes[n]:
                        ch = "#"
                        attr = curses.color_pair(COLOR_PRIME) | curses.A_BOLD
                    else:
                        ch = "."
                        attr = curses.color_pair(COLOR_NONPRIME) | curses.A_DIM
                    try:
                        stdscr.addstr(y, x, ch, attr)
                    except curses.error:
                        pass

                if n >= max_n:
                    finished = True
                    finished_at = now
                    break

                dx, dy = next(walker)
                x += dx
                y += dy
                n += 1

                # Stop early if we've spiraled completely off the screen
                # (no point computing further)
                if x < -2 or x > max_x + 2 or y < -2 or y > max_y + 1:
                    finished = True
                    finished_at = now
                    break

        # Mark current head with a bright marker (overdrawn each frame)
        if not finished and 0 <= x < max_x and 0 <= y < max_y - 1:
            try:
                stdscr.addstr(y, x, "@",
                              curses.color_pair(COLOR_CURRENT)
                              | curses.A_BOLD | curses.A_REVERSE)
            except curses.error:
                pass

        prime_count = sum(1 for k in range(2, min(n + 1, max_n + 1)) if primes[k])
        info = (f"Ulam prime spiral  walked n={n}/{max_n}  "
                f"primes plotted={prime_count}")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=25, frame_delay=0.03, max_n=4000, numbers_per_frame=8,
         completion_pause=4):
    duration = float(duration)
    frame_delay = float(frame_delay)
    max_n = max(2, int(max_n))
    numbers_per_frame = max(1, int(numbers_per_frame))
    completion_pause = float(completion_pause)
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, max_n, numbers_per_frame,
        completion_pause))


if __name__ == "__main__":
    main()
