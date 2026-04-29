import curses
import math
import random
import time


PALETTE = [
    curses.COLOR_RED, curses.COLOR_YELLOW, curses.COLOR_GREEN,
    curses.COLOR_CYAN, curses.COLOR_BLUE, curses.COLOR_MAGENTA,
]
COLOR_LABEL = 7

# Sectorized arrow chars indexed by direction angle. Index = floor(((angle/π)+1)*4) mod 8
DIR_CHARS = ["<", "\\", "^", "/", ">", "\\", "v", "/"]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    for i, c in enumerate(PALETTE):
        curses.init_pair(i + 1, c, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def boid_char(vx, vy):
    angle = math.atan2(vy, vx)
    sector = int(((angle / math.pi + 1) * 4)) % 8
    return DIR_CHARS[sector]


def step_boids(boids, w, h, sep_dist, neigh_dist, max_speed,
               sep_w, align_w, coh_w, dt):
    sep_d2 = sep_dist * sep_dist
    neigh_d2 = neigh_dist * neigh_dist
    n = len(boids)

    for i in range(n):
        bi = boids[i]
        sx = sy = 0.0
        ax = ay = 0.0
        cx = cy = 0.0
        sep_n = 0
        neigh_n = 0
        for j in range(n):
            if i == j:
                continue
            bj = boids[j]
            dx = bj["x"] - bi["x"]
            dy = bj["y"] - bi["y"]
            d2 = dx * dx + dy * dy
            if d2 == 0 or d2 > neigh_d2:
                continue
            neigh_n += 1
            ax += bj["vx"]
            ay += bj["vy"]
            cx += bj["x"]
            cy += bj["y"]
            if d2 < sep_d2:
                inv = 1.0 / math.sqrt(d2)
                sx -= dx * inv
                sy -= dy * inv
                sep_n += 1

        fx = fy = 0.0
        if sep_n > 0:
            fx += sep_w * sx
            fy += sep_w * sy
        if neigh_n > 0:
            ax /= neigh_n
            ay /= neigh_n
            cx = cx / neigh_n - bi["x"]
            cy = cy / neigh_n - bi["y"]
            fx += align_w * (ax - bi["vx"]) + coh_w * cx
            fy += align_w * (ay - bi["vy"]) + coh_w * cy

        bi["vx"] += fx * dt
        bi["vy"] += fy * dt
        speed = math.sqrt(bi["vx"] ** 2 + bi["vy"] ** 2)
        if speed > max_speed:
            bi["vx"] = bi["vx"] / speed * max_speed
            bi["vy"] = bi["vy"] / speed * max_speed

    for b in boids:
        b["x"] += b["vx"] * dt
        b["y"] += b["vy"] * dt
        if b["x"] < 0:
            b["x"] += w
        elif b["x"] >= w:
            b["x"] -= w
        if b["y"] < 0:
            b["y"] += h
        elif b["y"] >= h:
            b["y"] -= h


def run(stdscr, duration, frame_delay, num_boids, sep_dist, neigh_dist,
        max_speed, sep_w, align_w, coh_w):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    max_y, max_x = stdscr.getmaxyx()
    boids = []
    for _ in range(num_boids):
        boids.append({
            "x": random.uniform(0, max_x),
            "y": random.uniform(0, max(1, max_y - 1)),
            "vx": random.uniform(-max_speed, max_speed),
            "vy": random.uniform(-max_speed, max_speed) * 0.5,
            "color": random.randint(1, len(PALETTE)),
        })

    start = time.monotonic()
    last_frame = start
    while True:
        now = time.monotonic()
        if now - start >= duration:
            break
        dt = min(now - last_frame, 0.1)
        last_frame = now

        max_y, max_x = stdscr.getmaxyx()
        step_boids(boids, max_x, max(1, max_y - 1), sep_dist, neigh_dist,
                   max_speed, sep_w, align_w, coh_w, dt)

        stdscr.erase()
        for b in boids:
            xi = int(round(b["x"]))
            yi = int(round(b["y"]))
            if 0 <= xi < max_x and 0 <= yi < max_y - 1:
                ch = boid_char(b["vx"], b["vy"])
                attr = curses.color_pair(b["color"]) | curses.A_BOLD
                try:
                    stdscr.addstr(yi, xi, ch, attr)
                except curses.error:
                    pass

        info = (f"Boids  N={num_boids}  sep={sep_dist} neigh={neigh_dist}  "
                f"weights: sep={sep_w} align={align_w} coh={coh_w}")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=25, frame_delay=0.04, num_boids=40, sep_dist=2.5,
         neigh_dist=10.0, max_speed=15.0, sep_w=8.0, align_w=4.0, coh_w=2.0):
    duration = float(duration)
    frame_delay = float(frame_delay)
    num_boids = max(2, int(num_boids))
    sep_dist = float(sep_dist)
    neigh_dist = float(neigh_dist)
    max_speed = float(max_speed)
    sep_w = float(sep_w)
    align_w = float(align_w)
    coh_w = float(coh_w)
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, num_boids, sep_dist, neigh_dist,
        max_speed, sep_w, align_w, coh_w))


if __name__ == "__main__":
    main()
