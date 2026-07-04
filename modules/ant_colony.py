import curses
import locale
import math
import time

import numpy as np


COLOR_FAINT = 1    # weak pheromone trail (dim blue)
COLOR_MID = 2      # medium pheromone trail (cyan)
COLOR_STRONG = 3   # strong pheromone trail (bright white)
COLOR_BEST = 4     # best-so-far tour (yellow)
COLOR_FLASH = 5    # "new best!" flash (green)
COLOR_CITY = 6     # cities (red)
COLOR_LABEL = 7    # info label (cyan)

ASPECT = 2.0       # terminal cells are ~2x taller than wide
STALE_LIMIT = 60   # iterations without improvement before restart
FLASH_FRAMES = 12  # how long the "new best!" flash lasts


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_FAINT, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_MID, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_STRONG, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_BEST, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_FLASH, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_CITY, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def gen_cities(n, w, h, rng):
    """Random min-distance-separated cities as an (n, 2) array of
    (col, row) screen coordinates. Separation uses aspect-corrected
    distance so cities look spread out on screen."""
    w = max(8, w)
    h = max(4, h)
    # Target radius from equal-area packing in screen-corrected units.
    min_d = max(3.0, 0.55 * math.sqrt((w * h * ASPECT) / max(1, n)))
    cities = []
    attempts = 0
    while len(cities) < n and attempts < 6000:
        attempts += 1
        x = int(rng.integers(1, w - 1))
        y = int(rng.integers(1, h - 1))
        ok = True
        for cx, cy in cities:
            dx = x - cx
            dy = (y - cy) * ASPECT
            if dx * dx + dy * dy < min_d * min_d:
                ok = False
                break
        if ok:
            cities.append((x, y))
    while len(cities) < n:  # fallback if the screen is too cramped
        cities.append((int(rng.integers(1, w - 1)), int(rng.integers(1, h - 1))))
    return np.array(cities, dtype=float)


def dist_matrix(cities):
    """Pairwise distances in aspect-corrected (screen-true) coordinates."""
    pts = cities.copy()
    pts[:, 1] *= ASPECT
    diff = pts[:, None, :] - pts[None, :, :]
    d = np.sqrt((diff ** 2).sum(axis=-1))
    return d


def tour_length(tour, dist):
    return float(dist[tour, np.roll(tour, -1)].sum())


def build_tours(dist, tau, eta, num_ants, alpha, beta, rng):
    """Each ant builds a full tour via vectorized roulette selection
    with p ∝ τ^α · η^β over unvisited cities."""
    n = dist.shape[0]
    weight = (tau ** alpha) * (eta ** beta)
    np.fill_diagonal(weight, 0.0)

    tours = np.empty((num_ants, n), dtype=np.int64)
    current = rng.integers(0, n, size=num_ants)
    tours[:, 0] = current
    visited = np.zeros((num_ants, n), dtype=bool)
    visited[np.arange(num_ants), current] = True

    for step in range(1, n):
        w = weight[current] * ~visited
        totals = w.sum(axis=1)
        dead = totals <= 0.0
        if dead.any():  # numerical underflow: fall back to uniform
            w[dead] = ~visited[dead]
            totals = w.sum(axis=1)
        r = rng.random(num_ants) * totals
        nxt = (np.cumsum(w, axis=1) < r[:, None]).sum(axis=1)
        nxt = np.minimum(nxt, n - 1)
        # Float-edge safety: never pick an already-visited city.
        for k in np.nonzero(visited[np.arange(num_ants), nxt])[0]:
            nxt[k] = np.nonzero(~visited[k])[0][0]
        tours[:, step] = nxt
        visited[np.arange(num_ants), nxt] = True
        current = nxt
    return tours


def update_pheromone(tau, tours, lens, evaporation, q, best_tour, best_len):
    """Evaporate then deposit Δτ = Q/L on every ant's tour edges,
    with an elite double deposit on the best-so-far tour."""
    tau *= (1.0 - evaporation)
    for tour, length in zip(tours, lens):
        amt = q / max(length, 1e-9)
        a, b = tour, np.roll(tour, -1)
        tau[a, b] += amt
        tau[b, a] += amt
    if best_tour is not None:
        amt = 2.0 * q / max(best_len, 1e-9)
        a, b = best_tour, np.roll(best_tour, -1)
        tau[a, b] += amt
        tau[b, a] += amt
    np.clip(tau, 1e-8, None, out=tau)


def aco_iteration(dist, tau, eta, num_ants, alpha, beta, evaporation, q,
                  best_tour, best_len, rng):
    """One ACO iteration. Returns (best_tour, best_len, improved)."""
    tours = build_tours(dist, tau, eta, num_ants, alpha, beta, rng)
    lens = dist[tours, np.roll(tours, -1, axis=1)].sum(axis=1)
    i = int(np.argmin(lens))
    improved = False
    if best_tour is None or lens[i] < best_len - 1e-9:
        best_tour = tours[i].copy()
        best_len = float(lens[i])
        improved = True
    update_pheromone(tau, tours, lens, evaporation, q, best_tour, best_len)
    return best_tour, best_len, improved


def new_instance(num_cities, w, h, rng):
    """Fresh cities + ACO state for the current screen size."""
    cities = gen_cities(num_cities, w, h, rng)
    dist = dist_matrix(cities)
    with np.errstate(divide="ignore"):
        eta = 1.0 / np.where(dist > 0, dist, np.inf)
    off_diag = dist[~np.eye(len(cities), dtype=bool)]
    q = float(off_diag.mean()) * num_cities  # deposits scale ~O(1)
    tau = np.ones_like(dist)
    return cities, dist, eta, tau, q


def bresenham(x0, y0, x1, y1):
    """Integer line points from (x0, y0) to (x1, y1) inclusive."""
    points = []
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        points.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy
    return points


def draw_line(stdscr, x0, y0, x1, y1, ch, attr, max_x, max_y):
    for x, y in bresenham(x0, y0, x1, y1):
        if 0 <= x < max_x and 0 <= y < max_y - 1:
            try:
                stdscr.addstr(y, x, ch, attr)
            except curses.error:
                pass


def draw_pheromones(stdscr, cities, tau, max_x, max_y):
    n = len(cities)
    tmax = float(tau.max())
    if tmax <= 0:
        return
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            s = tau[i, j] / tmax
            if s > 0.06:
                edges.append((s, i, j))
    edges.sort()  # strongest drawn last, on top
    for s, i, j in edges:
        if s > 0.55:
            ch, attr = "#", curses.color_pair(COLOR_STRONG) | curses.A_BOLD
        elif s > 0.22:
            ch, attr = ":", curses.color_pair(COLOR_MID)
        else:
            ch, attr = "·", curses.color_pair(COLOR_FAINT) | curses.A_DIM
        x0, y0 = int(cities[i][0]), int(cities[i][1])
        x1, y1 = int(cities[j][0]), int(cities[j][1])
        draw_line(stdscr, x0, y0, x1, y1, ch, attr, max_x, max_y)


def draw_best_tour(stdscr, cities, tour, flash, max_x, max_y):
    if tour is None:
        return
    color = COLOR_FLASH if flash > 0 else COLOR_BEST
    attr = curses.color_pair(color) | curses.A_BOLD
    n = len(tour)
    for k in range(n):
        i, j = tour[k], tour[(k + 1) % n]
        x0, y0 = int(cities[i][0]), int(cities[i][1])
        x1, y1 = int(cities[j][0]), int(cities[j][1])
        draw_line(stdscr, x0, y0, x1, y1, "#", attr, max_x, max_y)


def draw_cities(stdscr, cities, max_x, max_y):
    attr = curses.color_pair(COLOR_CITY) | curses.A_BOLD
    for x, y in cities:
        xi, yi = int(x), int(y)
        if 0 <= xi < max_x and 0 <= yi < max_y - 1:
            try:
                stdscr.addstr(yi, xi, "O", attr)
            except curses.error:
                pass


def run(stdscr, duration, frame_delay, num_cities, num_ants,
        alpha, beta, evaporation):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    rng = np.random.default_rng()
    max_y, max_x = stdscr.getmaxyx()
    dims = (max_y, max_x)
    cities, dist, eta, tau, q = new_instance(num_cities, max_x, max_y - 1, rng)
    best_tour = None
    best_len = math.inf
    iteration = 0
    stale = 0
    flash = 0

    start = time.monotonic()
    while True:
        if time.monotonic() - start >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        if (max_y, max_x) != dims:  # resized: scatter a fresh instance
            dims = (max_y, max_x)
            cities, dist, eta, tau, q = new_instance(
                num_cities, max_x, max_y - 1, rng)
            best_tour, best_len = None, math.inf
            iteration, stale, flash = 0, 0, 0

        best_tour, best_len, improved = aco_iteration(
            dist, tau, eta, num_ants, alpha, beta, evaporation, q,
            best_tour, best_len, rng)
        iteration += 1
        if improved:
            stale = 0
            if iteration > 1:
                flash = FLASH_FRAMES
        else:
            stale += 1
        flash = max(0, flash - 1)

        if stale >= STALE_LIMIT:  # converged: scatter new cities, restart
            cities, dist, eta, tau, q = new_instance(
                num_cities, max_x, max_y - 1, rng)
            best_tour, best_len = None, math.inf
            iteration, stale, flash = 0, 0, 0

        stdscr.erase()
        draw_pheromones(stdscr, cities, tau, max_x, max_y)
        draw_best_tour(stdscr, cities, best_tour, flash, max_x, max_y)
        draw_cities(stdscr, cities, max_x, max_y)

        best_txt = f"{best_len:.1f}" if best_tour is not None else "-"
        info = (f"Ant Colony TSP  iter={iteration}  best={best_txt}  "
                f"cities={num_cities} ants={num_ants}  "
                f"a={alpha} b={beta} rho={evaporation}")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
            if flash > 0:
                col = 2 + len(info) + 2
                if col < max_x - 12:
                    stdscr.addstr(max_y - 1, col, "new best!",
                                  curses.color_pair(COLOR_FLASH)
                                  | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def main(duration=30, frame_delay=0.06, num_cities=18, num_ants=24,
         alpha=1.0, beta=3.0, evaporation=0.45):
    duration = float(duration)
    frame_delay = float(frame_delay)
    num_cities = max(4, int(num_cities))
    num_ants = max(2, int(num_ants))
    alpha = float(alpha)
    beta = float(beta)
    evaporation = min(0.99, max(0.0, float(evaporation)))
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        pass
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, num_cities, num_ants,
        alpha, beta, evaporation))


if __name__ == "__main__":
    main()
