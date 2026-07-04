import curses
import time

import numpy as np
from scipy.ndimage import uniform_filter


# Color pair ids: luminance bands dim blue -> cyan -> green -> yellow -> white
COLOR_BAND_1 = 1  # dim blue
COLOR_BAND_2 = 2  # cyan
COLOR_BAND_3 = 3  # green
COLOR_BAND_4 = 4  # yellow
COLOR_BAND_5 = 5  # white (hottest)
COLOR_LABEL = 6

ASCII_RAMP = " .:-=+*#%@"

# y motion scale: terminal cells are ~2:1 tall, so vertical motion is halved
Y_SCALE = 0.5


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_BAND_1, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_BAND_2, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_BAND_3, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_BAND_4, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_BAND_5, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def band_attrs():
    """Attributes for the 5 luminance bands, dimmest to hottest."""
    return [
        curses.color_pair(COLOR_BAND_1),
        curses.color_pair(COLOR_BAND_2),
        curses.color_pair(COLOR_BAND_3),
        curses.color_pair(COLOR_BAND_4) | curses.A_BOLD,
        curses.color_pair(COLOR_BAND_5) | curses.A_BOLD,
    ]


def spawn_agents(num_agents, w, h, rng):
    """Spawn agents in a ring around grid center, headings pointing inward-ish."""
    cx, cy = w / 2.0, h / 2.0
    radius = 0.35 * min(w, h)
    theta = rng.uniform(0.0, 2.0 * np.pi, num_agents)
    r = radius * (0.8 + 0.2 * rng.random(num_agents))
    x = cx + r * np.cos(theta)
    y = cy + r * np.sin(theta)
    heading = theta + np.pi + rng.uniform(-0.5, 0.5, num_agents)
    return x, y, heading


def sense(trail, x, y, heading, angle_offset, sensor_dist, w, h):
    """Sample trail at a sensor point offset from each agent's heading. Vectorized."""
    a = heading + angle_offset
    sx = (x + np.cos(a) * sensor_dist) % w
    sy = (y + np.sin(a) * sensor_dist * Y_SCALE) % h
    return trail[sy.astype(np.intp), sx.astype(np.intp)]


def step_agents(trail, x, y, heading, sensor_angle, sensor_dist,
                turn_speed, speed, deposit, w, h, rng):
    """One vectorized Physarum step: sense, turn, jitter, move, wrap, deposit."""
    f = sense(trail, x, y, heading, 0.0, sensor_dist, w, h)
    fl = sense(trail, x, y, heading, -sensor_angle, sensor_dist, w, h)
    fr = sense(trail, x, y, heading, sensor_angle, sensor_dist, w, h)

    # Turn toward strongest sensor; wobble randomly if front is weakest.
    turn = np.where(fl > fr, -turn_speed, turn_speed)
    random_turn = np.where(rng.random(x.shape[0]) < 0.5, -turn_speed, turn_speed)
    front_weakest = (f < fl) & (f < fr)
    front_strongest = (f >= fl) & (f >= fr)
    heading = heading + np.where(front_strongest, 0.0,
                                 np.where(front_weakest, random_turn, turn))
    # Small random jitter so trails stay organic.
    heading = heading + rng.uniform(-0.15, 0.15, x.shape[0])

    x = (x + np.cos(heading) * speed) % w
    y = (y + np.sin(heading) * speed * Y_SCALE) % h

    np.add.at(trail, (y.astype(np.intp), x.astype(np.intp)), deposit)
    return x, y, heading


def diffuse_decay(trail, decay):
    """Blur the trail with a 3x3 mean filter, then evaporate."""
    return uniform_filter(trail, size=3, mode="wrap") * decay


def run(stdscr, duration, frame_delay, num_agents, sensor_angle, sensor_dist,
        turn_speed, decay, deposit):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    rng = np.random.default_rng()
    bands = band_attrs()
    ramp = ASCII_RAMP
    n_ramp = len(ramp)
    speed = 1.0
    perturb_every = 10.0

    max_y, max_x = stdscr.getmaxyx()
    w = max(4, max_x)
    h = max(4, max_y - 1)  # bottom line reserved for label

    n = num_agents
    if w * h < 3000:  # small terminal: scale agent count down
        n = max(200, int(num_agents * (w * h) / 3000.0))

    trail = np.zeros((h, w), dtype=np.float64)
    x, y, heading = spawn_agents(n, w, h, rng)
    running_max = 1e-6

    start = time.monotonic()
    last_perturb = start
    while True:
        now = time.monotonic()
        if now - start >= duration:
            break

        # Handle resize: rebuild grid, remap agents into new bounds.
        max_y, max_x = stdscr.getmaxyx()
        new_w = max(4, max_x)
        new_h = max(4, max_y - 1)
        if new_w != w or new_h != h:
            x = x * (new_w / w)
            y = y * (new_h / h)
            w, h = new_w, new_h
            trail = np.zeros((h, w), dtype=np.float64)
            running_max = 1e-6

        # Periodic perturbation so the network re-forms.
        if now - last_perturb >= perturb_every:
            last_perturb = now
            if rng.random() < 0.5:
                heading = rng.uniform(0.0, 2.0 * np.pi, n)
            else:
                x, y, heading = spawn_agents(n, w, h, rng)

        x, y, heading = step_agents(trail, x, y, heading, sensor_angle,
                                    sensor_dist, turn_speed, speed, deposit,
                                    w, h, rng)
        trail = diffuse_decay(trail, decay)

        # Normalize by a slowly-adapting running max.
        frame_max = float(trail.max())
        running_max = max(frame_max, running_max * 0.995, 1e-6)
        norm = np.clip(trail / running_max, 0.0, 1.0)

        idx = np.minimum((norm * n_ramp).astype(np.intp), n_ramp - 1)
        band_idx = np.minimum((norm * len(bands)).astype(np.intp), len(bands) - 1)

        stdscr.erase()
        rows = min(h, max_y - 1)
        cols = min(w, max_x)
        for row in range(rows):
            ridx = idx[row, :cols]
            rband = band_idx[row, :cols]
            col = 0
            while col < cols:
                if ridx[col] == 0:
                    col += 1
                    continue
                # Emit a run of same-band cells as one addstr.
                b = rband[col]
                end = col + 1
                while end < cols and ridx[end] > 0 and rband[end] == b:
                    end += 1
                chunk = "".join(ramp[i] for i in ridx[col:end])
                try:
                    stdscr.addstr(row, col, chunk, bands[b])
                except curses.error:
                    pass
                col = end

        info = (f"Slime Mold  N={n}  sense={sensor_angle:.2f}rad@{sensor_dist:.1f}  "
                f"turn={turn_speed:.2f}  decay={decay:.2f}  dep={deposit:.2f}")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max(0, max_x - 4)],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def main(duration=30, frame_delay=0.04, num_agents=4000, sensor_angle=0.45,
         sensor_dist=6.0, turn_speed=0.35, decay=0.9, deposit=1.0):
    duration = float(duration)
    frame_delay = float(frame_delay)
    num_agents = max(50, int(num_agents))
    sensor_angle = float(sensor_angle)
    sensor_dist = float(sensor_dist)
    turn_speed = float(turn_speed)
    decay = float(decay)
    deposit = float(deposit)
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, num_agents, sensor_angle, sensor_dist,
        turn_speed, decay, deposit))


if __name__ == "__main__":
    main()
