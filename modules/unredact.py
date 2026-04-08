import curses
import os
import random
import textwrap
import time


COLOR_NORMAL = 1
COLOR_REDACTED = 2
COLOR_REVEALED = 3
COLOR_TITLE = 4
COLOR_PROGRESS = 5


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_NORMAL, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_REDACTED, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_REVEALED, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_TITLE, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_PROGRESS, curses.COLOR_GREEN, -1)


def load_paragraphs(filepath, num_paragraphs=3):
    """Load text, split into paragraphs, return a random contiguous group.

    Guarantees at least 3 non-empty paragraphs (or all available if fewer).
    """
    with open(filepath) as f:
        text = f.read()

    raw_paragraphs = text.split("\n\n")
    paragraphs = [p.strip() for p in raw_paragraphs if len(p.strip()) > 80]

    if not paragraphs:
        return []

    num_paragraphs = max(num_paragraphs, 3)
    num_paragraphs = min(num_paragraphs, len(paragraphs))
    start = random.randint(0, len(paragraphs) - num_paragraphs)
    return paragraphs[start:start + num_paragraphs]


def build_word_list(paragraphs, wrap_width, redact_probability=0.2):
    """Build structured lines with each word having a probability of being redacted.

    Returns structured_lines (list of list of (word, is_redacted))
    and redacted_indices (list of (line_idx, word_idx) positions).
    """
    lines = []
    for i, para in enumerate(paragraphs):
        wrapped = textwrap.fill(para, width=wrap_width)
        lines.extend(wrapped.split("\n"))
        if i < len(paragraphs) - 1:
            lines.append("")  # blank line between paragraphs

    redacted_indices = []
    structured_lines = []

    for line in lines:
        if not line.strip():
            structured_lines.append([])
            continue
        words = line.split(" ")
        line_words = []
        for w in words:
            if not w:
                line_words.append(("", False))
                continue
            is_redacted = random.random() < redact_probability
            if is_redacted:
                redacted_indices.append((len(structured_lines), len(line_words)))
            line_words.append((w, is_redacted))
        structured_lines.append(line_words)

    return structured_lines, redacted_indices


def draw_screen(stdscr, structured_lines, revealed_positions,
                total_redacted, num_revealed, max_y, max_x):
    stdscr.erase()

    # Title
    if num_revealed >= total_redacted:
        title = "[ DOCUMENT DECRYPTED ]"
    else:
        title = "[ ENCRYPTED DOCUMENT - DECRYPTION IN PROGRESS ]"
    try:
        stdscr.addstr(0, max(0, (max_x - len(title)) // 2), title[:max_x - 1],
                      curses.color_pair(COLOR_TITLE) | curses.A_BOLD)
    except curses.error:
        pass

    # Draw text
    text_start_y = 2
    for line_idx, line_words in enumerate(structured_lines):
        y = text_start_y + line_idx
        if y >= max_y - 4:
            break

        x = 4
        for word_idx, (word, is_redacted) in enumerate(line_words):
            if not word:
                x += 1
                continue
            if x + len(word) >= max_x - 1:
                break

            if is_redacted and (line_idx, word_idx) not in revealed_positions:
                block = "#" * len(word)
                try:
                    stdscr.addstr(y, x, block,
                                  curses.color_pair(COLOR_REDACTED) | curses.A_BOLD)
                except curses.error:
                    pass
            elif is_redacted:
                try:
                    stdscr.addstr(y, x, word,
                                  curses.color_pair(COLOR_REVEALED) | curses.A_BOLD)
                except curses.error:
                    pass
            else:
                try:
                    stdscr.addstr(y, x, word, curses.color_pair(COLOR_NORMAL))
                except curses.error:
                    pass

            x += len(word) + 1

    # Progress bar
    pct = num_revealed / total_redacted if total_redacted > 0 else 1.0
    bar_y = max_y - 2
    bar_width = max_x - 30
    if bar_y > 0 and bar_width > 0:
        filled = int(bar_width * pct)
        pct_text = f" {int(pct * 100)}%"
        try:
            stdscr.addstr(bar_y, 2, "Decrypting: [", curses.A_DIM)
            stdscr.addstr(bar_y, 15, "#" * filled,
                          curses.color_pair(COLOR_PROGRESS) | curses.A_BOLD)
            stdscr.addstr(bar_y, 15 + filled, "-" * (bar_width - filled), curses.A_DIM)
            stdscr.addstr(bar_y, 15 + bar_width, "]" + pct_text, curses.A_DIM)
        except curses.error:
            pass

    stdscr.refresh()


def run(stdscr, paragraphs, duration, redact_probability, completion_pause):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(100)

    max_y, max_x = stdscr.getmaxyx()
    wrap_width = max_x - 8

    structured_lines, redacted_indices = build_word_list(
        paragraphs, wrap_width, redact_probability)
    total_redacted = len(redacted_indices)

    if total_redacted == 0:
        return

    # Shuffle reveal order so words unredact in random positions
    reveal_order = list(redacted_indices)
    random.shuffle(reveal_order)

    revealed_positions = set()
    reveal_interval = duration / total_redacted
    start_time = time.monotonic()

    while True:
        now = time.monotonic()
        elapsed = now - start_time

        if elapsed >= duration:
            revealed_positions = set(redacted_indices)
            draw_screen(stdscr, structured_lines, revealed_positions,
                        total_redacted, total_redacted, max_y, max_x)
            # Hold the fully revealed text for completion_pause
            pause_start = time.monotonic()
            stdscr.timeout(100)
            while time.monotonic() - pause_start < completion_pause:
                key = stdscr.getch()
                if key == ord("q") or key == 27:
                    return
            break

        # Reveal words based on elapsed time
        target_reveals = min(int(elapsed / reveal_interval), total_redacted)
        while len(revealed_positions) < target_reveals:
            idx = len(revealed_positions)
            revealed_positions.add(reveal_order[idx])

        draw_screen(stdscr, structured_lines, revealed_positions,
                    total_redacted, len(revealed_positions), max_y, max_x)

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            break


def main(text_file="data/text/moby_dick.txt", duration=15, num_paragraphs=3,
         redact_probability=0.2, completion_pause=3):
    filepath = os.path.join(os.path.dirname(os.path.dirname(__file__)), text_file)
    if not os.path.isfile(filepath):
        print(f"Error: text file not found: {filepath}")
        return

    duration = float(duration)
    num_paragraphs = int(num_paragraphs)
    redact_probability = float(redact_probability)
    completion_pause = float(completion_pause)
    paragraphs = load_paragraphs(filepath, num_paragraphs)

    if not paragraphs:
        print("No suitable paragraphs found.")
        return

    curses.wrapper(lambda stdscr: run(stdscr, paragraphs, duration, redact_probability,
                                      completion_pause))


if __name__ == "__main__":
    main()
