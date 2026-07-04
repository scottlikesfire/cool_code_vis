import curses
import random
import time

import numpy as np


COLOR_H1 = 1      # height 1 -> blue
COLOR_H2 = 2      # height 2 -> green
COLOR_H3 = 3      # height 3 -> yellow
COLOR_H4 = 4      # height >= 4 (mid-avalanche) -> red
COLOR_FLASH = 5   # cells that toppled this frame -> white bold
COLOR_LABEL = 6

HEIGHT_CHARS = [" ", ".", "o", "#", "@"]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_H1, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_H2, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_H3, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_H4, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_FLASH, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def topple(grid, max_iters):
    """Vectorized toppling. Returns (topple_count_grid, num_topples, settled).

    Each iteration finds all cells with >= 4 grains, removes 4 grains from
    each, and gives 1 grain to each of the 4 neighbors. Grains that would
    leave the grid are lost (open boundary), as in the standard model.
    Stops after max_iters even if unstable cells remain, so huge avalanches
    animate across multiple frames instead of stalling one frame.
    """
    toppled = np.zeros(grid.shape, dtype=bool)
    num_topples = 0
    settled = True
    for _ in range(max_iters):
        unstable = grid >= 4
        n = int(np.count_nonzero(unstable))
        if n == 0:
            break
        num_topples += n
        toppled |= unstable
        grid[unstable] -= 4
        u = unstable.astype(grid.dtype)
        grid[1:, :] += u[:-1, :]
        grid[:-1, :] += u[1:, :]
        grid[:, 1:] += u[:, :-1]
        grid[:, :-1] += u[:, 1:]
    else:
        settled = not np.any(grid >= 4)
    return toppled, num_topples, settled


def pick_drop_sites(gh, gw, multi=False):
    """Center drop site, or 2-3 random interior sites when multi is True."""
    if not multi:
        return [(gh // 2, gw // 2)]
    k = random.randint(2, 3)
    sites = []
    for _ in range(k):
        sites.append((random.randint(gh // 6, gh - 1 - gh // 6),
                      random.randint(gw // 6, gw - 1 - gw // 6)))
    return sites


def edge_reached(grid):
    """True once the pile has grown out to any grid edge."""
    return bool(grid[0, :].any() or grid[-1, :].any()
                or grid[:, 0].any() or grid[:, -1].any())


def cell_attr(h, flashed):
    if flashed:
        return HEIGHT_CHARS[4], curses.color_pair(COLOR_FLASH) | curses.A_BOLD
    if h <= 0:
        return " ", 0
    if h == 1:
        return HEIGHT_CHARS[1], curses.color_pair(COLOR_H1)
    if h == 2:
        return HEIGHT_CHARS[2], curses.color_pair(COLOR_H2)
    if h == 3:
        return HEIGHT_CHARS[3], curses.color_pair(COLOR_H3) | curses.A_BOLD
    return HEIGHT_CHARS[4], curses.color_pair(COLOR_H4) | curses.A_BOLD


def run(stdscr, duration, frame_delay, grains_per_frame, topple_iters_per_frame):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    # Logical square grid: one sim cell per screen row, but each sim cell is
    # drawn 2 chars wide so the pile looks circular despite ~2:1 cells.
    max_y, max_x = stdscr.getmaxyx()
    gh = max(8, max_y - 1)
    gw = max(8, max_x // 2)
    grid = np.zeros((gh, gw), dtype=np.int32)

    total_dropped = 0
    largest_avalanche = 0
    multi_drop = False
    drop_sites = pick_drop_sites(gh, gw, multi_drop)

    start = time.monotonic()
    while True:
        if time.monotonic() - start >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        new_gh = max(8, max_y - 1)
        new_gw = max(8, max_x // 2)
        if (new_gh, new_gw) != grid.shape:
            # Terminal resized: rebuild the grid, keep the overlapping region.
            new_grid = np.zeros((new_gh, new_gw), dtype=np.int32)
            ch = min(new_gh, grid.shape[0])
            cw = min(new_gw, grid.shape[1])
            new_grid[:ch, :cw] = grid[:ch, :cw]
            grid = new_grid
            gh, gw = new_gh, new_gw
            drop_sites = pick_drop_sites(gh, gw, multi_drop)

        # Drop grains split across the active drop sites.
        for i in range(grains_per_frame):
            gy, gx = drop_sites[i % len(drop_sites)]
            grid[gy, gx] += 1
        total_dropped += grains_per_frame

        toppled, num_topples, settled = topple(grid, topple_iters_per_frame)
        if num_topples > largest_avalanche:
            largest_avalanche = num_topples

        # Once the pile reaches the edge, switch to a few random drop sites
        # for variety; when nearly saturated in multi mode, reset the pile.
        if settled:
            if not multi_drop and edge_reached(grid):
                multi_drop = True
                drop_sites = pick_drop_sites(gh, gw, multi_drop)
            elif multi_drop and grid.mean() > 2.4:
                grid[:, :] = 0
                multi_drop = False
                drop_sites = pick_drop_sites(gh, gw, multi_drop)

        stdscr.erase()
        heights = np.clip(grid, 0, 4)
        nonzero_rows, nonzero_cols = np.nonzero(heights | toppled)
        for gy, gx in zip(nonzero_rows.tolist(), nonzero_cols.tolist()):
            ch, attr = cell_attr(int(heights[gy, gx]), bool(toppled[gy, gx]))
            sy = gy
            sx = gx * 2
            if 0 <= sy < max_y - 1 and sx + 1 < max_x:
                try:
                    stdscr.addstr(sy, sx, ch + ch, attr)
                except curses.error:
                    pass

        info = (f"Sandpile  grains/frame={grains_per_frame}  "
                f"dropped={total_dropped}  max avalanche={largest_avalanche}"
                f"{'  [multi-drop]' if multi_drop else ''}")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def main(duration=30, frame_delay=0.04, grains_per_frame=8,
         topple_iters_per_frame=60):
    duration = float(duration)
    frame_delay = float(frame_delay)
    grains_per_frame = max(1, int(grains_per_frame))
    topple_iters_per_frame = max(1, int(topple_iters_per_frame))
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, grains_per_frame,
        topple_iters_per_frame))


if __name__ == "__main__":
    main()
