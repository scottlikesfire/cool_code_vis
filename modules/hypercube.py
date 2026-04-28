import curses
import math
import random
import time

import numpy as np


COLOR_VERT = 1
COLOR_EDGE = 2
COLOR_LABEL = 3


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_VERT, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_EDGE, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


# Tesseract — 16 vertices at every (±1, ±1, ±1, ±1) combo
TESSERACT_VERTS = np.array([
    [x, y, z, w]
    for w in (-1, 1)
    for z in (-1, 1)
    for y in (-1, 1)
    for x in (-1, 1)
], dtype=float)


def _build_edges():
    """Edges connect vertex pairs that differ in exactly one coordinate."""
    edges = []
    for i in range(16):
        for j in range(i + 1, 16):
            diff = sum(1 for k in range(4)
                       if TESSERACT_VERTS[i][k] != TESSERACT_VERTS[j][k])
            if diff == 1:
                edges.append((i, j))
    return edges


TESSERACT_EDGES = _build_edges()  # 32 edges total


# (i, j) plane axes in (x, y, z, w) order; six rotation planes in 4D.
PLANES = [
    (0, 1, "xy"),
    (0, 2, "xz"),
    (0, 3, "xw"),
    (1, 2, "yz"),
    (1, 3, "yw"),
    (2, 3, "zw"),
]


def rotation_4d(i, j, angle):
    """4×4 rotation in the (i, j) coordinate plane."""
    M = np.eye(4)
    c = math.cos(angle)
    s = math.sin(angle)
    M[i, i] = c
    M[i, j] = -s
    M[j, i] = s
    M[j, j] = c
    return M


def run(stdscr, duration, frame_delay, distance_4d, distance,
        focal_factor, mesh_scale, angular_speeds):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    # Randomize starting angles so each run looks different
    angles = [random.uniform(0, math.tau) for _ in range(6)]

    start = time.monotonic()
    last_frame = start

    while True:
        now = time.monotonic()
        if now - start >= duration:
            break
        dt = min(now - last_frame, 0.1)
        last_frame = now

        for k in range(6):
            angles[k] += angular_speeds[k] * dt

        # Compose the six plane rotations into one 4×4 matrix
        R = np.eye(4)
        for k, (i, j, _) in enumerate(PLANES):
            if angular_speeds[k] != 0.0:
                R = R @ rotation_4d(i, j, angles[k])

        rotated = TESSERACT_VERTS @ R.T  # (16, 4)

        # 4D → 3D perspective projection. Camera at w = distance_4d looking
        # toward smaller w; vertices closer in 4D appear larger in 3D, which
        # is what produces the classic "cube inside a cube" tesseract look.
        denoms = distance_4d - rotated[:, 3]
        denoms = np.maximum(denoms, 1e-6)
        factors = distance_4d / denoms
        verts3d = rotated[:, :3] * factors[:, None] * mesh_scale

        # Translate so the object sits in front of the 3D camera
        verts3d[:, 2] += distance

        # 3D → 2D pinhole projection (x scaled 2× for terminal char aspect)
        max_y, max_x = stdscr.getmaxyx()
        focal = max_y * focal_factor
        cx = max_x / 2
        cy = max_y / 2
        projected = []
        for v in verts3d:
            z = v[2]
            if z <= 0.1:
                projected.append(None)
                continue
            sx = cx + 2 * focal * v[0] / z
            sy = cy + focal * v[1] / z
            projected.append((sx, sy))

        stdscr.erase()

        # Edges
        edge_attr = curses.color_pair(COLOR_EDGE) | curses.A_BOLD
        for a, b in TESSERACT_EDGES:
            pa = projected[a]
            pb = projected[b]
            if pa is None or pb is None:
                continue
            xa, ya = pa
            xb, yb = pb
            dx = xb - xa
            dy = yb - ya
            steps = max(abs(int(round(dx))), abs(int(round(dy))))
            if steps == 0:
                xi, yi = int(round(xa)), int(round(ya))
                if 0 <= xi < max_x and 0 <= yi < max_y - 1:
                    try:
                        stdscr.addstr(yi, xi, "*", edge_attr)
                    except curses.error:
                        pass
                continue
            for i in range(steps + 1):
                t = i / steps
                xi = int(round(xa + t * dx))
                yi = int(round(ya + t * dy))
                if 0 <= xi < max_x and 0 <= yi < max_y - 1:
                    try:
                        stdscr.addstr(yi, xi, "*", edge_attr)
                    except curses.error:
                        pass

        # Vertices on top
        vert_attr = curses.color_pair(COLOR_VERT) | curses.A_BOLD
        for p in projected:
            if p is None:
                continue
            xi, yi = int(round(p[0])), int(round(p[1]))
            if 0 <= xi < max_x and 0 <= yi < max_y - 1:
                try:
                    stdscr.addstr(yi, xi, "@", vert_attr)
                except curses.error:
                    pass

        # Status footer
        active = [n for k, (_, _, n) in enumerate(PLANES)
                  if angular_speeds[k] != 0.0]
        rotating = " ".join(active) if active else "static"
        info = (f"Tesseract  V=16  E={len(TESSERACT_EDGES)}  "
                f"4D rotation planes: {rotating}")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(
    duration=25,
    frame_delay=0.04,
    distance_4d=3.0,
    distance=5.0,
    focal_factor=0.7,
    mesh_scale=1.5,
    angular_speeds=None,
):
    duration = float(duration)
    frame_delay = float(frame_delay)
    distance_4d = float(distance_4d)
    distance = float(distance)
    focal_factor = float(focal_factor)
    mesh_scale = float(mesh_scale)
    if angular_speeds is None:
        # Defaults: rotate in some 3D planes (xy, yw) plus the unmistakably
        # 4D plane xw and zw, so the inner/outer cubes visibly swap places.
        angular_speeds = [0.3, 0.0, 0.5, 0.0, 0.4, 0.6]
    angular_speeds = [float(x) for x in list(angular_speeds)]
    angular_speeds = (angular_speeds + [0.0] * 6)[:6]

    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, distance_4d, distance,
        focal_factor, mesh_scale, angular_speeds))


if __name__ == "__main__":
    main()
