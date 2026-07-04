import curses
import math
import time

import numpy as np


# Color pair ids
C_WATER = 1
C_GRASS = 2
C_HILL = 3
C_ROCK = 4
C_SNOW = 5
C_SKY = 6
C_LABEL = 7

# Terrain types (index into TYPE_CHARS / TYPE_PAIRS), by rising altitude
TYPE_CHARS = ["~", ".", ":", "*", "#", "@"]
TYPE_PAIRS = [C_WATER, C_GRASS, C_GRASS, C_HILL, C_ROCK, C_SNOW]
TYPE_BINS = [0.32, 0.45, 0.58, 0.72, 0.84]  # heightmap value thresholds

SEA_LEVEL = 0.32
N_BANDS = 3  # 0=near(bold) 1=mid(normal) 2=far(dim)

# code layout: 0 = sky/empty, 1..18 = type*3+band+1, 19 = star, 20 = glow
CODE_STAR = len(TYPE_CHARS) * N_BANDS + 1
CODE_GLOW = CODE_STAR + 1
N_CODES = CODE_GLOW + 1

Z_NEAR = 8.0
Z_FAR = 260.0
FOV = 0.85  # tan of half field-of-view


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(C_WATER, curses.COLOR_BLUE, -1)
    curses.init_pair(C_GRASS, curses.COLOR_GREEN, -1)
    curses.init_pair(C_HILL, curses.COLOR_YELLOW, -1)
    curses.init_pair(C_ROCK, curses.COLOR_WHITE, -1)
    curses.init_pair(C_SNOW, curses.COLOR_WHITE, -1)
    curses.init_pair(C_SKY, curses.COLOR_BLUE, -1)
    curses.init_pair(C_LABEL, curses.COLOR_CYAN, -1)


def build_code_tables():
    """Return (chars, attrs) lookup lists indexed by cell code."""
    band_attr = [curses.A_BOLD, curses.A_NORMAL, curses.A_DIM]
    chars = [" "] * N_CODES
    attrs = [curses.A_NORMAL] * N_CODES
    for t in range(len(TYPE_CHARS)):
        for b in range(N_BANDS):
            code = t * N_BANDS + b + 1
            chars[code] = TYPE_CHARS[t]
            a = band_attr[b]
            if t == len(TYPE_CHARS) - 1 and b < 2:  # snow pops
                a = curses.A_BOLD
            attrs[code] = curses.color_pair(TYPE_PAIRS[t]) | a
    chars[CODE_STAR] = "."
    attrs[CODE_STAR] = curses.color_pair(C_ROCK) | curses.A_DIM
    chars[CODE_GLOW] = "-"
    attrs[CODE_GLOW] = curses.color_pair(C_SKY) | curses.A_DIM
    return chars, attrs


def make_heightmap(size=512, octaves=4, seed=None):
    """Tileable fractal 2D value noise in [0, 1], fully vectorized."""
    rng = np.random.default_rng(seed)
    out = np.zeros((size, size), dtype=np.float64)
    amp = 1.0
    total = 0.0
    for o in range(octaves):
        freq = 4 * (2 ** o)  # lattice cells per side; modulo => tileable
        lattice = rng.random((freq, freq))
        c = np.arange(size) * (freq / size)
        i0 = np.floor(c).astype(np.int64)
        f = c - i0
        s = f * f * (3.0 - 2.0 * f)  # smoothstep
        i0 %= freq
        i1 = (i0 + 1) % freq
        sx = s[None, :]
        sy = s[:, None]
        v00 = lattice[np.ix_(i0, i0)]
        v01 = lattice[np.ix_(i0, i1)]
        v10 = lattice[np.ix_(i1, i0)]
        v11 = lattice[np.ix_(i1, i1)]
        top = v00 * (1.0 - sx) + v01 * sx
        bot = v10 * (1.0 - sx) + v11 * sx
        out += amp * (top * (1.0 - sy) + bot * sy)
        total += amp
        amp *= 0.5
    out /= total
    out -= out.min()
    out /= max(out.max(), 1e-9)
    return out ** 1.2  # flatten lowlands a bit, sharpen peaks


def sample_heightmap(hmap, x, y):
    """Bilinear, endlessly tiling sample of hmap at float coords (vectorized)."""
    n = hmap.shape[0]
    xi = np.floor(x).astype(np.int64)
    yi = np.floor(y).astype(np.int64)
    xf = x - xi
    yf = y - yi
    x0 = xi % n
    x1 = (xi + 1) % n
    y0 = yi % n
    y1 = (yi + 1) % n
    top = hmap[y0, x0] * (1.0 - xf) + hmap[y0, x1] * xf
    bot = hmap[y1, x0] * (1.0 - xf) + hmap[y1, x1] * xf
    return top * (1.0 - yf) + bot * yf


def render_frame(hmap, w, h, cam_x, cam_y, cam_alt, heading, horizon,
                 height_scale, view_distance, stars=None):
    """Voxel-space render: returns (h, w) uint8 array of cell codes."""
    buf = np.zeros((h, w), dtype=np.uint8)
    if w < 4 or h < 3:
        return buf
    ybuf = np.full(w, h, dtype=np.int64)  # per-column lowest undrawn row
    row_idx = np.arange(h, dtype=np.int64)[:, None]

    dx, dy = math.cos(heading), math.sin(heading)
    rx, ry = -dy, dx
    lat = np.linspace(-1.0, 1.0, w)
    zs = Z_NEAR * (Z_FAR / Z_NEAR) ** (np.arange(view_distance) /
                                       max(view_distance - 1, 1))
    pscale = h * 0.35
    n = len(zs)

    for i, z in enumerate(zs):  # front-to-back with y-buffer occlusion
        t = lat * (z * FOV)
        px = cam_x + dx * z + rx * t
        py = cam_y + dy * z + ry * t
        hv = sample_heightmap(hmap, px, py)
        terr = np.maximum(hv, SEA_LEVEL) * height_scale
        rows = (horizon + (cam_alt - terr) * pscale / z).astype(np.int64)
        np.clip(rows, 0, h, out=rows)

        band = 0 if i < n * 0.30 else (1 if i < n * 0.65 else 2)
        types = np.digitize(hv, TYPE_BINS)
        codes = (types * N_BANDS + band + 1).astype(np.uint8)

        mask = (row_idx >= rows[None, :]) & (row_idx < ybuf[None, :])
        buf = np.where(mask, codes[None, :], buf)
        np.minimum(ybuf, rows, out=ybuf)
        if not ybuf.any():  # whole screen filled by near terrain
            break

    # Sky decorations: stars drift opposite to heading, glow line at horizon
    if stars is not None and horizon > 1:
        fx, fy = stars
        cols = ((fx * w * 3.0 - heading * 60.0) % w).astype(np.int64)
        srows = (fy * (horizon - 1)).astype(np.int64)
        keep = buf[srows, cols] == 0
        buf[srows[keep], cols[keep]] = CODE_STAR
    if 0 <= horizon < h:
        line = buf[horizon]
        line[line == 0] = CODE_GLOW
    return buf


def draw_buffer(stdscr, buf, chars, attrs):
    """Blit code buffer as runs of identical cells (few addstr per row)."""
    h, w = buf.shape
    for y in range(h):
        arr = buf[y]
        if not arr.any():
            continue
        breaks = np.flatnonzero(np.diff(arr))
        starts = np.concatenate(([0], breaks + 1))
        ends = np.concatenate((breaks + 1, [w]))
        for s, e in zip(starts, ends):
            c = int(arr[s])
            if c == 0:
                continue
            try:
                stdscr.addstr(y, int(s), chars[c] * int(e - s), attrs[c])
            except curses.error:
                pass


def run(stdscr, duration, frame_delay, speed, camera_height, height_scale,
        view_distance):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))
    chars, attrs = build_code_tables()

    hmap = make_heightmap()
    rng = np.random.default_rng()
    stars = (rng.random(120), rng.random(120))

    cam_x, cam_y = 256.0, 256.0
    heading = 0.0
    cam_alt = camera_height
    start = time.monotonic()
    last = start
    while True:
        now = time.monotonic()
        t = now - start
        if t >= duration:
            break
        dt = min(now - last, 0.1)
        last = now

        # Gentle sinusoidal heading drift + forward flight
        heading = 0.45 * math.sin(t * 0.12) + 0.18 * math.sin(t * 0.047)
        cam_x += math.cos(heading) * speed * dt
        cam_y += math.sin(heading) * speed * dt

        max_y, max_x = stdscr.getmaxyx()
        h_draw = max_y - 1  # bottom line reserved for the label
        if h_draw >= 3 and max_x >= 4:
            horizon = int(h_draw * 0.35 + 1.5 * math.sin(t * 0.5))
            horizon = max(1, min(h_draw - 2, horizon))
            # Bobbing camera, kept safely above the terrain under it
            ground = float(sample_heightmap(
                hmap, np.array(cam_x), np.array(cam_y))) * height_scale
            cam_alt = max(camera_height + 2.5 * math.sin(t * 0.9),
                          ground + 5.0)

            buf = render_frame(hmap, max_x, h_draw, cam_x, cam_y, cam_alt,
                               heading, horizon, height_scale,
                               int(view_distance), stars=stars)
            stdscr.erase()
            draw_buffer(stdscr, buf, chars, attrs)

        info = (f"terrain_flyover  pos=({cam_x:.0f},{cam_y:.0f}) "
                f"alt={cam_alt:.1f}  speed={speed:g}  hdg={heading:+.2f}")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(C_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def main(duration=30, frame_delay=0.05, speed=18.0, camera_height=30.0,
         height_scale=38.0, view_distance=80):
    duration = float(duration)
    frame_delay = float(frame_delay)
    speed = float(speed)
    camera_height = float(camera_height)
    height_scale = float(height_scale)
    view_distance = max(8, int(view_distance))
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, speed, camera_height, height_scale,
        view_distance))


if __name__ == "__main__":
    main()
