import curses
import random
import time


COLOR_BAR = 1
COLOR_COMPARE = 2
COLOR_SWAP = 3
COLOR_SORTED = 4
COLOR_TITLE = 5


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_BAR, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_COMPARE, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_SWAP, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_SORTED, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_TITLE, curses.COLOR_CYAN, -1)


class SortRunner:
    """Renders an array as bars, with the ability to mark indices as
    comparing/swapping/sorted on each step."""

    def __init__(self, stdscr, arr, algo_name, step_delay):
        self.stdscr = stdscr
        self.arr = arr
        self.algo_name = algo_name
        self.step_delay = step_delay
        self.compare_idx = set()
        self.swap_idx = set()
        self.sorted_idx = set()
        self.comparisons = 0
        self.swaps = 0
        self.cancelled = False

    def draw(self):
        if self.cancelled:
            return
        stdscr = self.stdscr
        stdscr.erase()
        max_y, max_x = stdscr.getmaxyx()

        title = f"Sorting Visualizer — {self.algo_name}"
        try:
            stdscr.addstr(0, max(0, (max_x - len(title)) // 2), title[:max_x - 1],
                          curses.color_pair(COLOR_TITLE) | curses.A_BOLD | curses.A_REVERSE)
        except curses.error:
            pass

        n = len(self.arr)
        max_val = max(self.arr) if self.arr else 1
        chart_top = 2
        chart_bottom = max_y - 2
        chart_height = chart_bottom - chart_top
        bar_width = max(1, (max_x - 2) // n)

        for i, val in enumerate(self.arr):
            x = 2 + i * bar_width
            if x >= max_x - 1:
                break
            bar_h = int((val / max_val) * (chart_height - 1))
            bar_h = max(1, bar_h)

            if i in self.swap_idx:
                attr = curses.color_pair(COLOR_SWAP) | curses.A_BOLD
            elif i in self.compare_idx:
                attr = curses.color_pair(COLOR_COMPARE) | curses.A_BOLD
            elif i in self.sorted_idx:
                attr = curses.color_pair(COLOR_SORTED) | curses.A_BOLD
            else:
                attr = curses.color_pair(COLOR_BAR)

            for y in range(chart_bottom - bar_h, chart_bottom):
                try:
                    stdscr.addstr(y, x, "#" * bar_width, attr)
                except curses.error:
                    pass

        footer = f"Comparisons: {self.comparisons}  Swaps: {self.swaps}  | q to quit"
        try:
            stdscr.addstr(max_y - 1, 2, footer[:max_x - 4], curses.A_DIM)
        except curses.error:
            pass

        stdscr.refresh()

        stdscr.timeout(int(self.step_delay * 1000))
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            self.cancelled = True

    def compare(self, i, j):
        self.compare_idx = {i, j}
        self.swap_idx = set()
        self.comparisons += 1
        self.draw()

    def swap(self, i, j):
        self.arr[i], self.arr[j] = self.arr[j], self.arr[i]
        self.swap_idx = {i, j}
        self.compare_idx = set()
        self.swaps += 1
        self.draw()

    def mark_sorted(self, i):
        self.sorted_idx.add(i)


def bubble_sort(r):
    n = len(r.arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if r.cancelled:
                return
            r.compare(j, j + 1)
            if r.arr[j] > r.arr[j + 1]:
                r.swap(j, j + 1)
        r.mark_sorted(n - i - 1)


def insertion_sort(r):
    n = len(r.arr)
    r.mark_sorted(0)
    for i in range(1, n):
        if r.cancelled:
            return
        j = i
        while j > 0 and r.arr[j - 1] > r.arr[j]:
            if r.cancelled:
                return
            r.compare(j - 1, j)
            r.swap(j - 1, j)
            j -= 1
        r.mark_sorted(i)


def selection_sort(r):
    n = len(r.arr)
    for i in range(n):
        if r.cancelled:
            return
        min_idx = i
        for j in range(i + 1, n):
            if r.cancelled:
                return
            r.compare(min_idx, j)
            if r.arr[j] < r.arr[min_idx]:
                min_idx = j
        if min_idx != i:
            r.swap(i, min_idx)
        r.mark_sorted(i)


def quick_sort(r):
    def partition(low, high):
        pivot = r.arr[high]
        i = low - 1
        for j in range(low, high):
            if r.cancelled:
                return -1
            r.compare(j, high)
            if r.arr[j] <= pivot:
                i += 1
                if i != j:
                    r.swap(i, j)
        if i + 1 != high:
            r.swap(i + 1, high)
        return i + 1

    def qs(low, high):
        if r.cancelled or low >= high:
            return
        pi = partition(low, high)
        if pi < 0:
            return
        qs(low, pi - 1)
        qs(pi + 1, high)
        r.mark_sorted(pi)

    qs(0, len(r.arr) - 1)


ALGORITHMS = {
    "bubble": ("Bubble Sort", bubble_sort),
    "insertion": ("Insertion Sort", insertion_sort),
    "selection": ("Selection Sort", selection_sort),
    "quick": ("Quick Sort", quick_sort),
}


def run(stdscr, algo_key, n, step_delay, completion_pause):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass

    name, sort_fn = ALGORITHMS[algo_key]
    arr = list(range(1, n + 1))
    random.shuffle(arr)

    runner = SortRunner(stdscr, arr, name, step_delay)
    runner.draw()
    sort_fn(runner)

    if runner.cancelled:
        return

    # Mark all sorted
    for i in range(len(runner.arr)):
        runner.mark_sorted(i)
    runner.compare_idx = set()
    runner.swap_idx = set()
    runner.draw()

    stdscr.timeout(100)
    pause_start = time.monotonic()
    while time.monotonic() - pause_start < completion_pause:
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(algorithm="random", n=60, step_delay=0.02, completion_pause=3):
    if algorithm == "random":
        algorithm = random.choice(list(ALGORITHMS.keys()))
    if algorithm not in ALGORITHMS:
        print(f"Unknown algorithm: {algorithm}")
        return
    n = int(n)
    step_delay = float(step_delay)
    completion_pause = float(completion_pause)
    curses.wrapper(lambda stdscr: run(stdscr, algorithm, n, step_delay, completion_pause))


if __name__ == "__main__":
    main()
