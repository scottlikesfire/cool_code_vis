import ast
import curses
import os
import time


COLOR_BAR = 1
COLOR_LABEL = 2
COLOR_FILE = 3
COLOR_TITLE = 4
COLOR_COUNT = 5
COLOR_STATS = 6


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_BAR, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_FILE, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_TITLE, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_COUNT, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_STATS, curses.COLOR_WHITE, -1)


def find_python_files(repo_root):
    py_files = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in (
            ".git", "__pycache__", ".venv", "venv", "node_modules",
            ".mypy_cache", ".pytest_cache", ".tox",
        )]
        for f in sorted(filenames):
            if f.endswith(".py"):
                py_files.append(os.path.join(dirpath, f))
    return py_files


def extract_imports(filepath):
    """Extract top-level import names from a Python file using AST."""
    imports = []
    try:
        with open(filepath) as f:
            tree = ast.parse(f.read(), filename=filepath)
    except (SyntaxError, UnicodeDecodeError):
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])
    return imports


def get_file_details(filepath):
    """Return line count, function count, and file size for a Python file."""
    file_size = os.path.getsize(filepath)
    num_lines = 0
    num_functions = 0
    try:
        with open(filepath) as f:
            source = f.read()
        num_lines = source.count("\n") + 1
        tree = ast.parse(source, filename=filepath)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                num_functions += 1
    except (SyntaxError, UnicodeDecodeError):
        pass
    return num_lines, num_functions, file_size


def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def draw_chart(stdscr, counts, total_imports, files_processed, current_file,
               file_details=None):
    stdscr.erase()
    max_y, max_x = stdscr.getmaxyx()

    # Title
    title = "Python Import Frequency Analysis"
    if max_x > len(title) + 2:
        try:
            stdscr.addstr(0, (max_x - len(title)) // 2, title,
                          curses.color_pair(COLOR_TITLE) | curses.A_BOLD | curses.A_REVERSE)
        except curses.error:
            pass

    # Current file
    display_file = current_file
    if len(display_file) > max_x - 20:
        display_file = "..." + display_file[-(max_x - 23):]
    file_line = f"File #{files_processed}: {display_file}"
    if max_x > len(file_line) + 2:
        try:
            stdscr.addstr(2, 2, file_line[:max_x - 4],
                          curses.color_pair(COLOR_FILE) | curses.A_BOLD)
        except curses.error:
            pass

    stats = f"Total imports: {total_imports}  |  Files scanned: {files_processed}  |  Unique modules: {len(counts)}"
    if max_x > len(stats) + 2:
        try:
            stdscr.addstr(3, 2, stats[:max_x - 4], curses.A_DIM)
        except curses.error:
            pass

    # Reserve bottom rows for file details
    detail_rows = 4 if file_details else 0

    # Bar chart — show top N imports that fit on screen
    chart_start_y = 5
    available_rows = max_y - chart_start_y - detail_rows - 1
    if available_rows <= 0:
        stdscr.refresh()
        return

    sorted_imports = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    top_imports = sorted_imports[:available_rows]

    if not top_imports:
        stdscr.refresh()
        return

    max_count = top_imports[0][1] if top_imports else 1
    max_name_len = max(len(name) for name, _ in top_imports)
    label_width = max_name_len + 4
    bar_max_width = max_x - label_width - 10

    for i, (module_name, count) in enumerate(top_imports):
        y = chart_start_y + i
        if y >= max_y - detail_rows - 1:
            break

        label = f"{module_name:>{max_name_len}}: "
        try:
            stdscr.addstr(y, 2, label, curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        count_str = str(count)
        available = bar_max_width - len(count_str) - 2
        bar_len = int((count / max_count) * available) if max_count > 0 and available > 0 else 0
        bar_len = max(0, bar_len)
        bar_x = 2 + len(label)
        if bar_len > 0:
            try:
                stdscr.addstr(y, bar_x, "#" * bar_len, curses.color_pair(COLOR_BAR))
            except curses.error:
                pass

        count_x = bar_x + bar_len + 1
        if count_x + len(count_str) < max_x:
            try:
                stdscr.addstr(y, count_x, count_str, curses.color_pair(COLOR_COUNT))
            except curses.error:
                pass

    # File details section
    if file_details:
        num_lines, num_functions, file_size = file_details
        detail_y = max_y - detail_rows
        separator = "-" * (max_x - 4)
        details = [
            separator,
            f"Lines: {num_lines}    Functions: {num_functions}    Size: {format_size(file_size)}",
        ]
        for i, line in enumerate(details):
            y = detail_y + i
            if y < max_y - 1:
                attr = curses.A_DIM if i == 0 else curses.color_pair(COLOR_STATS)
                try:
                    stdscr.addstr(y, 2, line[:max_x - 4], attr)
                except curses.error:
                    pass

    stdscr.refresh()


def run(stdscr, py_files, repo_root, file_delay, duration, completion_pause):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(file_delay * 1000))

    counts = {}
    total_imports = 0
    files_processed = 0
    start_time = time.monotonic()

    for filepath in py_files:
        if duration is not None and time.monotonic() - start_time >= duration:
            return

        imports = extract_imports(filepath)
        for mod in imports:
            counts[mod] = counts.get(mod, 0) + 1
            total_imports += 1
        files_processed += 1

        rel_path = os.path.relpath(filepath, repo_root)
        details = get_file_details(filepath)
        draw_chart(stdscr, counts, total_imports, files_processed, rel_path,
                   file_details=details)

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return

    # Files exhausted — hold results
    stdscr.timeout(100)
    pause_start = time.monotonic()
    while True:
        elapsed_pause = time.monotonic() - pause_start
        if completion_pause is not None and elapsed_pause >= completion_pause:
            break
        if duration is not None and time.monotonic() - start_time >= duration:
            break

        draw_chart(stdscr, counts, total_imports, files_processed, "(complete)")

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(file_delay=0.3, duration=None, completion_pause=5):
    repo_root = os.path.dirname(os.path.dirname(__file__))
    py_files = find_python_files(repo_root)

    if not py_files:
        print("No Python files found.")
        return

    file_delay = float(file_delay)
    if duration is not None:
        duration = float(duration)
    completion_pause = float(completion_pause)
    curses.wrapper(lambda stdscr: run(stdscr, py_files, repo_root, file_delay, duration, completion_pause))


if __name__ == "__main__":
    main()
