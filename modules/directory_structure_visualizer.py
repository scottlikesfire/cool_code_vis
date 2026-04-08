import os
import sys
import time
import curses
from pathlib import Path

# Color pairs indexed by file category
COLOR_DIRECTORY = 1
COLOR_PYTHON = 2
COLOR_WEB = 3
COLOR_DATA = 4
COLOR_IMAGE = 5
COLOR_CONFIG = 6
COLOR_DOCS = 7
COLOR_DEFAULT = 8
COLOR_TREE_LINES = 9

EXTENSION_COLORS = {
    # Python
    ".py": COLOR_PYTHON,
    ".pyw": COLOR_PYTHON,
    ".pyx": COLOR_PYTHON,
    # Web
    ".js": COLOR_WEB,
    ".ts": COLOR_WEB,
    ".jsx": COLOR_WEB,
    ".tsx": COLOR_WEB,
    ".html": COLOR_WEB,
    ".css": COLOR_WEB,
    ".scss": COLOR_WEB,
    ".vue": COLOR_WEB,
    ".svelte": COLOR_WEB,
    # Data
    ".json": COLOR_DATA,
    ".yaml": COLOR_DATA,
    ".yml": COLOR_DATA,
    ".csv": COLOR_DATA,
    ".xml": COLOR_DATA,
    ".sql": COLOR_DATA,
    ".db": COLOR_DATA,
    # Images
    ".png": COLOR_IMAGE,
    ".jpg": COLOR_IMAGE,
    ".jpeg": COLOR_IMAGE,
    ".gif": COLOR_IMAGE,
    ".svg": COLOR_IMAGE,
    ".ico": COLOR_IMAGE,
    ".webp": COLOR_IMAGE,
    # Config
    ".toml": COLOR_CONFIG,
    ".ini": COLOR_CONFIG,
    ".cfg": COLOR_CONFIG,
    ".env": COLOR_CONFIG,
    ".gitignore": COLOR_CONFIG,
    ".dockerignore": COLOR_CONFIG,
    ".editorconfig": COLOR_CONFIG,
    # Docs
    ".md": COLOR_DOCS,
    ".txt": COLOR_DOCS,
    ".rst": COLOR_DOCS,
    ".pdf": COLOR_DOCS,
    ".doc": COLOR_DOCS,
    ".docx": COLOR_DOCS,
    ".LICENSE": COLOR_DOCS,
}


def get_color_for_entry(entry_path):
    if entry_path.is_dir():
        return COLOR_DIRECTORY
    ext = entry_path.suffix.lower()
    if ext in EXTENSION_COLORS:
        return EXTENSION_COLORS[ext]
    name = entry_path.name.lower()
    if name in ("license", "makefile", "dockerfile", "readme"):
        return COLOR_DOCS
    if name.startswith("."):
        return COLOR_CONFIG
    return COLOR_DEFAULT


def build_tree(root_path, prefix="", is_last=True, is_root=True, step_counter=None):
    """Build tree lines tagged with reveal steps for animation.

    Each line is (prefix, name, color, step). Step 0 is the root,
    step 1 is the root's immediate children, and each subsequent
    directory expansion gets its own step number.
    """
    if step_counter is None:
        step_counter = [0]

    root = Path(root_path)
    lines = []

    if is_root:
        lines.append(("", root.name + "/", COLOR_DIRECTORY, step_counter[0]))
        prefix = ""
    else:
        connector = "└── " if is_last else "├── "
        display_name = root.name + "/" if root.is_dir() else root.name
        color = get_color_for_entry(root)
        lines.append((prefix + connector, display_name, color, step_counter[0]))
        prefix += "    " if is_last else "│   "

    if root.is_dir():
        try:
            entries = sorted(root.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return lines

        step_counter[0] += 1

        for i, entry in enumerate(entries):
            is_last_entry = (i == len(entries) - 1)
            lines.extend(build_tree(entry, prefix, is_last_entry,
                                    is_root=False, step_counter=step_counter))

    return lines


def reverse_tree(tree_lines):
    """Reverse a tree so the root is at the bottom with branches growing up.

    Flips the line order and swaps connector characters so the visual
    structure remains correct.
    """
    reversed_lines = []
    for prefix, name, color, step in reversed(tree_lines):
        new_prefix = prefix.replace("└", "┌")
        reversed_lines.append((new_prefix, name, color, step))
    return reversed_lines


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_DIRECTORY, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_PYTHON, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_WEB, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_DATA, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_IMAGE, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_CONFIG, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_DOCS, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_DEFAULT, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_TREE_LINES, curses.COLOR_WHITE, -1)


def draw_legend(stdscr, y, max_x):
    legend = [
        (COLOR_DIRECTORY, "Directory"),
        (COLOR_PYTHON, "Python"),
        (COLOR_WEB, "Web"),
        (COLOR_DATA, "Data"),
        (COLOR_IMAGE, "Image"),
        (COLOR_CONFIG, "Config"),
        (COLOR_DOCS, "Docs"),
        (COLOR_DEFAULT, "Other"),
    ]
    x = 2
    label = " Legend: "
    if x + len(label) < max_x:
        stdscr.addstr(y, x, label, curses.A_DIM)
        x += len(label)
    for color_id, name in legend:
        token = f"■ {name}  "
        if x + len(token) >= max_x:
            break
        stdscr.addstr(y, x, token, curses.color_pair(color_id) | curses.A_BOLD)
        x += len(token)


def run(stdscr, target_path, duration=None, expand_interval=0.4, reverse=False):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(100)

    tree_lines = build_tree(target_path)
    if reverse:
        tree_lines = reverse_tree(tree_lines)
    max_step = max(line[3] for line in tree_lines)
    scroll_offset = 0
    current_step = 0
    last_expand_time = time.monotonic()
    animation_done = False
    done_time = None

    while True:
        now = time.monotonic()

        # Duration timer starts after animation completes
        if duration is not None and done_time is not None and now - done_time >= duration:
            break

        # Advance animation
        if not animation_done and now - last_expand_time >= expand_interval:
            current_step += 1
            last_expand_time = now
            if current_step >= max_step:
                animation_done = True
                done_time = now

        # Filter lines up to the current reveal step
        visible_tree = [line for line in tree_lines if line[3] <= current_step]
        total_lines = len(visible_tree)

        stdscr.erase()
        max_y, max_x = stdscr.getmaxyx()

        # Title bar
        title = f" Directory: {target_path} "
        stdscr.addstr(0, 0, title[:max_x - 1], curses.A_BOLD | curses.A_REVERSE)
        stdscr.addstr(0, min(len(title), max_x - 1), " " * max(0, max_x - len(title) - 1), curses.A_REVERSE)

        # Tree content area
        content_start = 2
        content_end = max_y - 3
        visible_count = content_end - content_start

        if visible_count <= 0:
            stdscr.refresh()
            key = stdscr.getch()
            if key == ord("q"):
                break
            continue

        # Auto-scroll to keep newly revealed lines visible during animation
        if not animation_done:
            if reverse and total_lines > visible_count:
                scroll_offset = 0  # new content appears at top
            elif total_lines > visible_count:
                scroll_offset = total_lines - visible_count  # new content at bottom

        for i in range(visible_count):
            line_idx = scroll_offset + i
            if line_idx >= total_lines:
                break
            prefix, name, color_id, _step = visible_tree[line_idx]
            y = content_start + i
            # Draw tree connector lines in dim gray
            if prefix and y < max_y - 1:
                stdscr.addstr(y, 0, prefix[:max_x - 1], curses.color_pair(COLOR_TREE_LINES) | curses.A_DIM)
            # Draw the file/dir name in its color
            name_x = len(prefix)
            remaining = max_x - name_x - 1
            if remaining > 0 and y < max_y - 1:
                attr = curses.color_pair(color_id)
                if color_id == COLOR_DIRECTORY:
                    attr |= curses.A_BOLD
                stdscr.addstr(y, name_x, name[:remaining], attr)

        # Scroll indicator
        if total_lines > visible_count:
            pct = int((scroll_offset / max(1, total_lines - visible_count)) * 100)
            indicator = f" [{scroll_offset + 1}-{min(scroll_offset + visible_count, total_lines)}/{total_lines}] {pct}% "
            bar_y = max_y - 2
            if bar_y > 0:
                stdscr.addstr(bar_y, 0, indicator[:max_x - 1], curses.A_DIM)

        # Legend
        draw_legend(stdscr, max_y - 1, max_x)

        stdscr.refresh()

        key = stdscr.getch()
        if key == ord("q") or key == 27:  # q or ESC
            break
        elif key == curses.KEY_UP or key == ord("k"):
            scroll_offset = max(0, scroll_offset - 1)
        elif key == curses.KEY_DOWN or key == ord("j"):
            scroll_offset = min(max(0, total_lines - visible_count), scroll_offset + 1)
        elif key == curses.KEY_PPAGE or key == ord("u"):
            scroll_offset = max(0, scroll_offset - visible_count)
        elif key == curses.KEY_NPAGE or key == ord("d"):
            scroll_offset = min(max(0, total_lines - visible_count), scroll_offset + visible_count)
        elif key == curses.KEY_HOME or key == ord("g"):
            scroll_offset = 0
        elif key == curses.KEY_END or key == ord("G"):
            scroll_offset = max(0, total_lines - visible_count)


def main(target_path=None, duration=None, expand_interval=0.4, reverse=False):
    if target_path is None:
        target_path = os.getcwd()
    target_path = os.path.abspath(target_path)
    if duration is not None:
        duration = float(duration)
    expand_interval = float(expand_interval)
    if not os.path.isdir(target_path):
        print(f"Error: '{target_path}' is not a valid directory.")
        sys.exit(1)
    curses.wrapper(lambda stdscr: run(stdscr, target_path, duration, expand_interval, reverse))


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    main(path)
