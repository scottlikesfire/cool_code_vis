"""raymarch_sdf -- donut-style ASCII raymarching of morphing SDF shapes.

Sphere -> torus -> rounded box -> octahedron, morphed with a smoothstepped
mix, smooth-min blended with a small orbiting blob, lit by a slowly
orbiting key light. All rays are marched simultaneously with numpy.
"""

import curses
import math
import time

import numpy as np


COLOR_SHADOW = 1   # dim blue
COLOR_MID = 2      # cyan
COLOR_BRIGHT = 3   # white
COLOR_HOT = 4      # white + bold (applied at draw time)
COLOR_LABEL = 5

RAMP = " .,:;=+*#%@"
RAMP_ARR = np.array(list(RAMP))
BAND_THRESHOLDS = np.array([0.22, 0.48, 0.78])  # lum -> band 0..3

SHAPE_NAMES = ["sphere", "torus", "box", "octahedron"]

EPS_HIT = 0.004
T_MAX = 8.0
CAM_POS = np.array([0.0, 0.0, -3.4])
FOCAL = 2.2


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_SHADOW, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_MID, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_BRIGHT, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_HOT, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


# ---------------------------------------------------------------------------
# SDF primitives (all take (N, 3) arrays, return (N,) distances)
# ---------------------------------------------------------------------------

def sd_sphere(p, r=1.15):
    return np.sqrt(np.einsum("ij,ij->i", p, p)) - r


def sd_torus(p, big_r=0.95, small_r=0.42):
    qx = np.sqrt(p[:, 0] ** 2 + p[:, 2] ** 2) - big_r
    return np.sqrt(qx ** 2 + p[:, 1] ** 2) - small_r


def sd_round_box(p, b=0.75, r=0.2):
    q = np.abs(p) - b
    outside = np.sqrt(np.einsum("ij,ij->i", np.maximum(q, 0.0),
                                np.maximum(q, 0.0)))
    inside = np.minimum(np.max(q, axis=1), 0.0)
    return outside + inside - r


def sd_octahedron(p, s=1.35):
    # Lipschitz-safe bound form.
    return (np.abs(p[:, 0]) + np.abs(p[:, 1]) + np.abs(p[:, 2]) - s) * 0.57735


SHAPE_FUNCS = [sd_sphere, sd_torus, sd_round_box, sd_octahedron]


# ---------------------------------------------------------------------------
# Scene composition
# ---------------------------------------------------------------------------

def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def smin(a, b, k=0.5):
    """Polynomial smooth minimum."""
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1.0 - h) + a * h - k * h * (1.0 - h)


def rotation_matrix(t):
    """Combined two-axis rotation, time dependent."""
    ax, ay = 0.7 * t, 0.5 * t
    ca, sa = math.cos(ax), math.sin(ax)
    cb, sb = math.cos(ay), math.sin(ay)
    rx = np.array([[1, 0, 0], [0, ca, -sa], [0, sa, ca]])
    ry = np.array([[cb, 0, sb], [0, 1, 0], [-sb, 0, cb]])
    return rx @ ry


def morph_state(t, morph_time, hold_time):
    """Return (shape_a, shape_b, mix) for time t. mix is smoothstepped."""
    period = hold_time + morph_time
    n = len(SHAPE_FUNCS)
    cycle = t % (period * n)
    i = int(cycle // period)
    phase = cycle - i * period
    if phase < hold_time:
        s = 0.0
    else:
        s = float(smoothstep(np.array((phase - hold_time) / morph_time)))
    return i, (i + 1) % n, s


def scene_sdf(p, rot, sa, sb, mix, blob_c):
    """SDF of the full scene at world points p (N, 3)."""
    q = p @ rot  # rotate sample points into object space
    da = SHAPE_FUNCS[sa](q)
    if mix > 0.0:
        db = SHAPE_FUNCS[sb](q)
        d = da * (1.0 - mix) + db * mix
    else:
        d = da
    # small orbiting blob, smooth-min blended into the morphing shape
    d_blob = np.sqrt(np.einsum("ij,ij->i", p - blob_c, p - blob_c)) - 0.28
    return smin(d, d_blob, 0.5)


def estimate_normals(p, rot, sa, sb, mix, blob_c, h=2e-3):
    """Central-difference SDF gradient at points p (N, 3)."""
    n = np.empty_like(p)
    for axis in range(3):
        e = np.zeros(3)
        e[axis] = h
        n[:, axis] = (scene_sdf(p + e, rot, sa, sb, mix, blob_c)
                      - scene_sdf(p - e, rot, sa, sb, mix, blob_c))
    length = np.sqrt(np.einsum("ij,ij->i", n, n))
    length[length == 0] = 1.0
    return n / length[:, None]


# ---------------------------------------------------------------------------
# Frame rendering
# ---------------------------------------------------------------------------

def render_frame(w, h, t, morph_time, hold_time, march_steps):
    """Raymarch one frame.

    Returns (chars (h, w) unicode array, band (h, w) int array with -1 for
    background, normals (N_hit, 3), label string describing the blend).
    """
    sa, sb, mix = morph_state(t, morph_time, hold_time)
    rot = rotation_matrix(t)
    blob_c = np.array([1.5 * math.cos(0.9 * t),
                       0.55 * math.sin(1.3 * t),
                       1.5 * math.sin(0.9 * t)])

    # Film plane: terminal cells are ~2:1 tall, so rows advance twice as
    # fast as columns in film units.
    cols = (np.arange(w) - w / 2 + 0.5) / h
    rows = -(np.arange(h) - h / 2 + 0.5) * 2.0 / h
    px, py = np.meshgrid(cols, rows)
    rd = np.stack([px.ravel(), py.ravel(),
                   np.full(w * h, FOCAL)], axis=1)
    rd /= np.sqrt(np.einsum("ij,ij->i", rd, rd))[:, None]

    n_rays = w * h
    t_ray = np.zeros(n_rays)
    hit = np.zeros(n_rays, dtype=bool)
    alive = np.arange(n_rays)

    for _ in range(march_steps):
        p = CAM_POS + rd[alive] * t_ray[alive, None]
        d = scene_sdf(p, rot, sa, sb, mix, blob_c)
        hit_now = d < EPS_HIT
        hit[alive[hit_now]] = True
        t_ray[alive] += np.maximum(d, EPS_HIT * 0.5)
        keep = ~hit_now & (t_ray[alive] < T_MAX)
        alive = alive[keep]
        if alive.size == 0:
            break

    chars = np.full(n_rays, " ", dtype="<U1")
    band = np.full(n_rays, -1, dtype=np.int8)
    hit_idx = np.flatnonzero(hit)
    normals = np.zeros((0, 3))
    if hit_idx.size:
        hp = CAM_POS + rd[hit_idx] * t_ray[hit_idx, None]
        normals = estimate_normals(hp, rot, sa, sb, mix, blob_c)
        # slowly orbiting key light
        la = 0.4 * t
        light = np.array([0.8 * math.cos(la), 0.65,
                          0.8 * math.sin(la) - 0.5])
        light /= np.linalg.norm(light)
        diff = np.maximum(normals @ light, 0.0)
        lum = np.clip(0.12 + 0.92 * diff, 0.0, 1.0)
        ramp_idx = 1 + (lum * (len(RAMP) - 2)).astype(int)
        chars[hit_idx] = RAMP_ARR[ramp_idx]
        band[hit_idx] = np.searchsorted(BAND_THRESHOLDS, lum)

    if mix <= 0.0:
        label = SHAPE_NAMES[sa]
    else:
        label = f"{SHAPE_NAMES[sa]} -> {SHAPE_NAMES[sb]} {int(mix * 100)}%"
    return chars.reshape(h, w), band.reshape(h, w), normals, label


def draw_frame(stdscr, chars, band, max_x):
    """Draw the char grid as contiguous same-band runs per row."""
    attrs = [
        curses.color_pair(COLOR_SHADOW) | curses.A_DIM,
        curses.color_pair(COLOR_MID),
        curses.color_pair(COLOR_BRIGHT),
        curses.color_pair(COLOR_HOT) | curses.A_BOLD,
    ]
    h, w = band.shape
    for y in range(h):
        row_band = band[y]
        if not (row_band >= 0).any():
            continue
        row_chars = chars[y]
        edges = np.flatnonzero(np.diff(row_band)) + 1
        starts = np.concatenate(([0], edges))
        ends = np.concatenate((edges, [w]))
        for x0, x1 in zip(starts, ends):
            b = row_band[x0]
            if b < 0:
                continue
            try:
                stdscr.addstr(y, x0, "".join(row_chars[x0:x1]),
                              attrs[min(b, 3)])
            except curses.error:
                pass


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run(stdscr, duration, frame_delay, morph_time, hold_time, march_steps):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    start = time.monotonic()
    fps = 0.0
    last = start
    while True:
        now = time.monotonic()
        if now - start >= duration:
            break
        dt = now - last
        last = now
        if dt > 0:
            fps = 0.9 * fps + 0.1 * (1.0 / dt) if fps else 1.0 / dt

        max_y, max_x = stdscr.getmaxyx()
        w = max(2, max_x)
        h = max(2, max_y - 1)  # bottom line reserved for the label

        chars, band, _, blend_label = render_frame(
            w, h, now - start, morph_time, hold_time, march_steps)

        stdscr.erase()
        draw_frame(stdscr, chars, band, max_x)

        info = (f"raymarch_sdf  [{blend_label}]  steps={march_steps}  "
                f"morph={morph_time}s hold={hold_time}s  fps~{fps:4.1f}")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def main(duration=30, frame_delay=0.05, morph_time=4.0, hold_time=2.0,
         march_steps=56):
    duration = float(duration)
    frame_delay = float(frame_delay)
    morph_time = max(0.1, float(morph_time))
    hold_time = max(0.0, float(hold_time))
    march_steps = max(8, int(march_steps))
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, morph_time, hold_time, march_steps))


if __name__ == "__main__":
    main()
