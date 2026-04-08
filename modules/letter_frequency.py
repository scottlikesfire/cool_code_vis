import curses
import locale
import os
import string
import time

locale.setlocale(locale.LC_ALL, "")


ALPHABET = string.ascii_lowercase

# Color pairs
COLOR_BAR = 1
COLOR_LABEL = 2
COLOR_WORD = 3
COLOR_TITLE = 4
COLOR_COUNT = 5


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_BAR, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_WORD, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_TITLE, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_COUNT, curses.COLOR_MAGENTA, -1)


def draw_chart(stdscr, counts, total_letters, words_processed, current_word):
    stdscr.erase()
    max_y, max_x = stdscr.getmaxyx()

    # Title
    title = "Letter Frequency Analysis"
    if max_x > len(title) + 2:
        stdscr.addstr(0, (max_x - len(title)) // 2, title,
                      curses.color_pair(COLOR_TITLE) | curses.A_BOLD | curses.A_REVERSE)

    # Current word display
    word_line = f"Word #{words_processed}: {current_word}"
    if max_x > len(word_line) + 2:
        stdscr.addstr(2, 2, word_line, curses.color_pair(COLOR_WORD) | curses.A_BOLD)

    stats = f"Total letters: {total_letters}  |  Words processed: {words_processed}"
    if max_x > len(stats) + 2:
        stdscr.addstr(3, 2, stats, curses.A_DIM)

    # Bar chart
    max_count = max(counts.values()) if max(counts.values()) > 0 else 1
    bar_max_width = max_x - 14
    chart_start_y = 5

    if chart_start_y + 26 < max_y:
        for i, ch in enumerate(ALPHABET):
            y = chart_start_y + i
            if y >= max_y - 1:
                break

            stdscr.addstr(y, 2, f"{ch}: ", curses.color_pair(COLOR_LABEL) | curses.A_BOLD)

            count_str = str(counts[ch])
            # Reserve space for the count number at the end
            available = max_x - 5 - len(count_str) - 2
            bar_len = int((counts[ch] / max_count) * bar_max_width) if max_count > 0 else 0
            bar_len = max(0, min(bar_len, available))
            if bar_len > 0:
                try:
                    stdscr.addstr(y, 5, "#" * bar_len, curses.color_pair(COLOR_BAR))
                except curses.error:
                    pass

            count_x = 5 + bar_len + 1
            if count_x + len(count_str) < max_x:
                try:
                    stdscr.addstr(y, count_x, count_str, curses.color_pair(COLOR_COUNT))
                except curses.error:
                    pass

    stdscr.refresh()


def run(stdscr, words, word_delay, duration, completion_pause):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(word_delay * 1000))

    counts = {ch: 0 for ch in ALPHABET}
    total_letters = 0
    words_processed = 0
    start_time = time.monotonic()

    for word in words:
        if duration is not None and time.monotonic() - start_time >= duration:
            return

        for ch in word.lower():
            if ch in counts:
                counts[ch] += 1
                total_letters += 1
        words_processed += 1

        draw_chart(stdscr, counts, total_letters, words_processed, word)

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return

    # Words exhausted — hold the final results for completion_pause,
    # but still respect duration if set
    stdscr.timeout(100)
    pause_start = time.monotonic()
    while True:
        elapsed_pause = time.monotonic() - pause_start
        if completion_pause is not None and elapsed_pause >= completion_pause:
            break
        if duration is not None and time.monotonic() - start_time >= duration:
            break

        draw_chart(stdscr, counts, total_letters, words_processed, "(complete)")

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(text_file="data/text/words.txt", word_delay=0.05, num_words=200,
         duration=None, completion_pause=5):
    text_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), text_file)
    if not os.path.isfile(text_file):
        print(f"Error: text file not found: {text_file}")
        return

    with open(text_file) as f:
        words = [line.strip() for line in f if line.strip()]

    num_words = int(num_words)
    if num_words > 0:
        words = words[:num_words]

    word_delay = float(word_delay)
    if duration is not None:
        duration = float(duration)
    completion_pause = float(completion_pause)
    curses.wrapper(lambda stdscr: run(stdscr, words, word_delay, duration, completion_pause))


if __name__ == "__main__":
    main()
