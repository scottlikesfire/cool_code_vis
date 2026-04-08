import curses
import os
import random
import time


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    rainbow = [
        curses.COLOR_RED,
        curses.COLOR_YELLOW,
        curses.COLOR_GREEN,
        curses.COLOR_CYAN,
        curses.COLOR_BLUE,
        curses.COLOR_MAGENTA,
    ]
    for i, color in enumerate(rainbow):
        curses.init_pair(i + 1, color, -1)
    return len(rainbow)


def find_python_files(repo_root):
    py_files = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in (
            ".git", "__pycache__", ".venv", "venv", "node_modules",
        )]
        for f in sorted(filenames):
            if f.endswith(".py"):
                py_files.append(os.path.join(dirpath, f))
    return py_files


def run(stdscr, filepath, repo_root, duration, cycle_length):
    num_colors = init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass

    max_y, max_x = stdscr.getmaxyx()
    rel_path = os.path.relpath(filepath, repo_root)

    try:
        with open(filepath) as f:
            source = f.read()
    except (OSError, UnicodeDecodeError):
        return

    # Calculate delay per character to spread the file across the full duration
    printable_chars = sum(1 for ch in source if ch not in ("\n", "\t"))
    char_delay = duration / printable_chars if printable_chars > 0 else 0.01
    stdscr.timeout(max(1, int(char_delay * 1000)))

    header = f"--- {rel_path} ---"
    stdscr.erase()
    try:
        stdscr.addstr(0, max(0, (max_x - len(header)) // 2), header[:max_x - 1],
                      curses.A_BOLD | curses.A_REVERSE)
    except curses.error:
        pass
    stdscr.refresh()

    start_time = time.monotonic()
    global_char_idx = 0
    row = 2
    col = 0

    for ch in source:
        if time.monotonic() - start_time >= duration:
            return

        if ch == "\n":
            row += 1
            col = 0
            if row >= max_y - 1:
                stdscr.refresh()
                time.sleep(0.3)
                stdscr.erase()
                try:
                    stdscr.addstr(0, max(0, (max_x - len(header)) // 2),
                                  header[:max_x - 1],
                                  curses.A_BOLD | curses.A_REVERSE)
                except curses.error:
                    pass
                row = 2
                col = 0
            continue

        if ch == "\t":
            col += 4
            continue

        if col >= max_x - 1:
            continue

        color_idx = int((global_char_idx % cycle_length) / cycle_length * num_colors)
        color_pair = (color_idx % num_colors) + 1
        global_char_idx += 1

        try:
            stdscr.addstr(row, col, ch, curses.color_pair(color_pair) | curses.A_BOLD)
        except curses.error:
            pass

        col += 1
        stdscr.refresh()

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return

    # File finished before duration — hold the display
    stdscr.timeout(100)
    while time.monotonic() - start_time < duration:
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=15, cycle_length=100):
    repo_root = os.path.dirname(os.path.dirname(__file__))
    py_files = [f for f in find_python_files(repo_root) if os.path.getsize(f) >= 100]

    if not py_files:
        print("No Python files found.")
        return

    duration = float(duration)
    cycle_length = int(cycle_length)
    filepath = random.choice(py_files)
    curses.wrapper(lambda stdscr: run(stdscr, filepath, repo_root, duration, cycle_length))


if __name__ == "__main__":
    main()
