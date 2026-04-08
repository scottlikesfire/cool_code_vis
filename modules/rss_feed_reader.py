import curses
import re
import shutil
import sys
import time

import feedparser


COLOR_BAR = 1
COLOR_LABEL = 2
COLOR_FEED = 3
COLOR_TITLE = 4
COLOR_COUNT = 5
COLOR_LOADING = 6
COLOR_ERROR = 7

# Common words to skip
STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "as", "was", "are", "be",
    "has", "had", "have", "will", "been", "would", "could", "should",
    "may", "can", "do", "did", "not", "no", "so", "if", "its", "this",
    "that", "than", "then", "them", "they", "their", "there", "these",
    "those", "he", "she", "his", "her", "him", "we", "our", "us", "you",
    "your", "i", "my", "me", "who", "what", "when", "where", "how", "why",
    "all", "each", "which", "about", "up", "out", "over", "after", "into",
    "more", "new", "also", "just", "any", "some", "other", "one", "two",
    "first", "said", "says", "s", "t", "re", "ve", "d", "ll", "m",
}


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_BAR, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_FEED, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_TITLE, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_COUNT, curses.COLOR_MAGENTA, -1)


def extract_words(text):
    """Extract lowercase words from text, filtering stop words and short words."""
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return [w for w in words if len(w) > 2 and w not in STOP_WORDS]


def draw_chart(stdscr, counts, total_words, entries_processed, current_entry,
               current_feed, max_y, max_x):
    stdscr.erase()

    # Title
    title = "RSS Feed Word Frequency"
    if max_x > len(title) + 2:
        try:
            stdscr.addstr(0, (max_x - len(title)) // 2, title,
                          curses.color_pair(COLOR_TITLE) | curses.A_BOLD | curses.A_REVERSE)
        except curses.error:
            pass

    # Current feed and entry
    feed_line = f"Feed: {current_feed}"
    if len(feed_line) > max_x - 4:
        feed_line = feed_line[:max_x - 7] + "..."
    try:
        stdscr.addstr(2, 2, feed_line, curses.color_pair(COLOR_FEED) | curses.A_BOLD)
    except curses.error:
        pass

    entry_line = f"Entry #{entries_processed}: {current_entry}"
    if len(entry_line) > max_x - 4:
        entry_line = entry_line[:max_x - 7] + "..."
    try:
        stdscr.addstr(3, 2, entry_line, curses.color_pair(COLOR_FEED))
    except curses.error:
        pass

    stats = f"Total words: {total_words}  |  Entries: {entries_processed}  |  Unique: {len(counts)}"
    try:
        stdscr.addstr(4, 2, stats[:max_x - 4], curses.A_DIM)
    except curses.error:
        pass

    # Bar chart — top N words
    chart_start_y = 6
    available_rows = max_y - chart_start_y - 1
    if available_rows <= 0:
        stdscr.refresh()
        return

    sorted_words = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    top_words = sorted_words[:available_rows]

    if not top_words:
        stdscr.refresh()
        return

    max_count = top_words[0][1]
    max_name_len = max(len(w) for w, _ in top_words)
    bar_max_width = max_x - max_name_len - 14

    for i, (word, count) in enumerate(top_words):
        y = chart_start_y + i
        if y >= max_y - 1:
            break

        label = f"{word:>{max_name_len}}: "
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

    stdscr.refresh()


def run_from_parsed(stdscr, all_entries, entry_delay, duration, completion_pause):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(entry_delay * 1000))

    max_y, max_x = stdscr.getmaxyx()
    counts = {}
    total_words = 0
    entries_processed = 0
    start_time = time.monotonic()

    for feed_title, entry in all_entries:
        if duration is not None and time.monotonic() - start_time >= duration:
            break

        title = entry.get("title", "")
        summary = entry.get("summary", "")
        text = title + " " + summary
        words = extract_words(text)

        for w in words:
            counts[w] = counts.get(w, 0) + 1
            total_words += 1
        entries_processed += 1

        max_y, max_x = stdscr.getmaxyx()
        draw_chart(stdscr, counts, total_words, entries_processed,
                   title[:60], feed_title, max_y, max_x)

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return

    # Hold final results
    stdscr.timeout(100)
    pause_start = time.monotonic()
    while True:
        elapsed_pause = time.monotonic() - pause_start
        if completion_pause is not None and elapsed_pause >= completion_pause:
            break
        if duration is not None and time.monotonic() - start_time >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        draw_chart(stdscr, counts, total_words, entries_processed,
                   "(complete)", "", max_y, max_x)

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def fetch_feeds_with_loading(feeds):
    """Fetch all feeds, showing a progress bar. Returns (parsed_feeds, success)."""
    term_width = shutil.get_terminal_size().columns
    term_height = shutil.get_terminal_size().lines
    bar_width = 40
    title = "connecting to RSS feeds"
    y = term_height // 2

    sys.stdout.write("\033[2J\033[H")

    parsed_feeds = []
    total = len(feeds)

    for i, feed_url in enumerate(feeds):
        pct = i / total
        filled = int(bar_width * pct)
        bar = "#" * filled + "-" * (bar_width - filled)
        pct_text = f"{int(pct * 100)}%"

        title_x = max(0, (term_width - len(title)) // 2)
        bar_str = f"[{bar}] {pct_text}"
        bar_x = max(0, (term_width - len(bar_str)) // 2)

        # Show which feed we're fetching
        short_url = feed_url if len(feed_url) < term_width - 10 else "..." + feed_url[-(term_width - 13):]
        url_x = max(0, (term_width - len(short_url)) // 2)

        sys.stdout.write(f"\033[{y};{title_x + 1}H\033[96;1m{title}\033[0m")
        sys.stdout.write(f"\033[{y + 2};{bar_x + 1}H\033[96m{bar_str}\033[0m")
        sys.stdout.write(f"\033[{y + 4};1H" + " " * term_width)
        sys.stdout.write(f"\033[{y + 4};{url_x + 1}H\033[37m{short_url}\033[0m")
        sys.stdout.flush()

        feed = feedparser.parse(feed_url)
        if feed.entries:
            parsed_feeds.append(feed)

    # Final state: 100%
    filled = bar_width
    bar = "#" * filled
    pct_text = "100%"
    bar_str = f"[{bar}] {pct_text}"
    bar_x = max(0, (term_width - len(bar_str)) // 2)
    sys.stdout.write(f"\033[{y + 2};{bar_x + 1}H\033[96m{bar_str}\033[0m")
    sys.stdout.flush()
    time.sleep(0.5)

    return parsed_feeds


def show_error_screen(completion_pause):
    """Show a red error screen for feeds unavailable."""
    term_width = shutil.get_terminal_size().columns
    term_height = shutil.get_terminal_size().lines
    bar_width = 40
    y = term_height // 2

    msg = "FEEDS UNAVAILABLE, CHECK NETWORK"
    msg_x = max(0, (term_width - len(msg)) // 2)

    bar = "#" * bar_width
    bar_str = f"[{bar}] FAILED"
    bar_x = max(0, (term_width - len(bar_str)) // 2)

    sys.stdout.write("\033[2J\033[H")
    sys.stdout.write(f"\033[{y};{msg_x + 1}H\033[31;1m{msg}\033[0m")
    sys.stdout.write(f"\033[{y + 2};{bar_x + 1}H\033[31m{bar_str}\033[0m")
    sys.stdout.flush()
    time.sleep(completion_pause)
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def main(feeds=None, entry_delay=0.3, duration=None, completion_pause=5):
    if feeds is None:
        feeds = [
            "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
            "https://feeds.bbci.co.uk/news/rss.xml",
            "https://rss.cnn.com/rss/edition.rss",
        ]
    entry_delay = float(entry_delay)
    if duration is not None:
        duration = float(duration)
    completion_pause = float(completion_pause)

    parsed_feeds = fetch_feeds_with_loading(feeds)

    if not parsed_feeds:
        show_error_screen(completion_pause)
        return

    # Flatten into (feed_title, entries) for the run loop
    all_entries = []
    for feed in parsed_feeds:
        feed_title = feed.feed.get("title", "Unknown")
        for entry in feed.entries:
            all_entries.append((feed_title, entry))

    curses.wrapper(lambda stdscr: run_from_parsed(
        stdscr, all_entries, entry_delay, duration, completion_pause))


if __name__ == "__main__":
    main()
