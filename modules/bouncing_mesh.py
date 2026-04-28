import curses
import math
import os
import random
import sys
import time

import numpy as np

# Make the scottlib submodule importable
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SUBMODULES = os.path.join(_REPO_ROOT, "submodules")
if _SUBMODULES not in sys.path:
    sys.path.insert(0, _SUBMODULES)

from scottlib.utils.mesh import read_obj


COLOR_VERT = 1
COLOR_EDGE = 2
COLOR_LABEL = 3


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_VERT, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_EDGE, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


# ----- Math -----

def normalize(v):
    n = float(np.linalg.norm(v))
    if n < 1e-9:
        return np.array([1.0, 0.0, 0.0])
    return v / n


def random_unit_vector():
    """Uniformly random unit vector on the sphere."""
    z = random.uniform(-1, 1)
    phi = random.uniform(0, math.tau)
    s = math.sqrt(max(0.0, 1 - z * z))
    return np.array([s * math.cos(phi), s * math.sin(phi), z])


def rotation_matrix(axis, angle):
    """Rodrigues' rotation. axis must be unit length."""
    c = math.cos(angle)
    s = math.sin(angle)
    t = 1 - c
    x, y, z = axis
    return np.array([
        [t * x * x + c,     t * x * y - s * z, t * x * z + s * y],
        [t * x * y + s * z, t * y * y + c,     t * y * z - s * x],
        [t * x * z - s * y, t * y * z + s * x, t * z * z + c],
    ])


# ----- Mesh -----

def get_edges(faces):
    """Extract unique undirected edges from a face list (any polygon size)."""
    edges = set()
    for face in faces:
        face_list = list(face) if not isinstance(face, list) else face
        n = len(face_list)
        for i in range(n):
            a, b = int(face_list[i]), int(face_list[(i + 1) % n])
            if a == b:
                continue
            edges.add((min(a, b), max(a, b)))
    return list(edges)


def fallback_cube():
    """Hard-coded cube mesh used if the OBJ file can't be read."""
    verts = np.array([
        [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
        [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1],
    ], dtype=float)
    faces = [
        [0, 1, 2, 3], [4, 5, 6, 7],
        [0, 1, 5, 4], [1, 2, 6, 5],
        [2, 3, 7, 6], [3, 0, 4, 7],
    ]
    return verts, faces


# ----- Camera projection -----

def project(point, focal, max_y, max_x, near=0.1):
    """Pinhole projection. Camera at origin looking down +z. Returns (sx, sy)
    or None if the point is at/behind the near plane.

    The x axis is scaled 2× to compensate for terminal characters being
    roughly twice as tall as wide, so a 3D circle renders as a screen circle.
    """
    z = point[2]
    if z <= near:
        return None
    cx = max_x / 2
    cy = max_y / 2
    sx = cx + 2 * focal * point[0] / z
    sy = cy + focal * point[1] / z
    return sx, sy


# ----- Run loop -----

def run(stdscr, mesh_file, duration, frame_delay, mesh_scale,
        box_x, box_y, box_z_min, box_z_max,
        linear_speed, angular_speed, focal_factor,
        bounce_jitter):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    # Resolve mesh path: if a directory, pick a random .obj from it
    full_path = (mesh_file if os.path.isabs(mesh_file)
                 else os.path.join(_REPO_ROOT, mesh_file))
    if os.path.isdir(full_path):
        candidates = sorted(
            os.path.join(full_path, f) for f in os.listdir(full_path)
            if f.lower().endswith(".obj")
        )
        if candidates:
            full_path = random.choice(candidates)
        else:
            full_path = ""

    try:
        verts, faces = read_obj(full_path)
        if len(verts) == 0:
            verts, faces = fallback_cube()
            full_path = "<fallback cube>"
    except (OSError, FileNotFoundError, ValueError):
        verts, faces = fallback_cube()
        full_path = "<fallback cube>"

    display_name = os.path.basename(full_path) if full_path else "<fallback>"

    # Center on centroid, normalize to a unit bounding sphere, then apply
    # mesh_scale. Matches shaded_mesh so the same mesh_scale, box, and speed
    # parameters look consistent across any input mesh.
    centroid = verts.mean(axis=0)
    verts = verts - centroid
    raw_radius = float(np.linalg.norm(verts, axis=1).max())
    if raw_radius > 1e-9:
        verts = verts / raw_radius
    verts = verts * float(mesh_scale)
    radius = float(np.linalg.norm(verts, axis=1).max())

    # Don't let bounding sphere exceed the box
    half_x = max(radius + 0.1, box_x)
    half_y = max(radius + 0.1, box_y)
    z_lo = min(box_z_min, box_z_max - 2 * radius - 0.2)
    z_hi = max(box_z_max, box_z_min + 2 * radius + 0.2)

    edges = get_edges(faces)

    # Initial state
    pos = np.array([
        random.uniform(-half_x + radius, half_x - radius),
        random.uniform(-half_y + radius, half_y - radius),
        random.uniform(z_lo + radius, z_hi - radius),
    ])
    linear_vel = random_unit_vector() * linear_speed
    orientation = np.eye(3)
    angular_axis = random_unit_vector()

    start = time.monotonic()
    last_frame = start

    while True:
        now = time.monotonic()
        if now - start >= duration:
            break
        dt = min(now - last_frame, 0.1)
        last_frame = now

        max_y, max_x = stdscr.getmaxyx()
        focal = max_y * focal_factor

        # Linear motion
        pos = pos + linear_vel * dt

        # Wall collisions: reflect velocity, snap inside box, jitter spin
        bounced = False
        if pos[0] - radius < -half_x and linear_vel[0] < 0:
            linear_vel[0] = -linear_vel[0]
            pos[0] = -half_x + radius
            bounced = True
        if pos[0] + radius > half_x and linear_vel[0] > 0:
            linear_vel[0] = -linear_vel[0]
            pos[0] = half_x - radius
            bounced = True
        if pos[1] - radius < -half_y and linear_vel[1] < 0:
            linear_vel[1] = -linear_vel[1]
            pos[1] = -half_y + radius
            bounced = True
        if pos[1] + radius > half_y and linear_vel[1] > 0:
            linear_vel[1] = -linear_vel[1]
            pos[1] = half_y - radius
            bounced = True
        if pos[2] - radius < z_lo and linear_vel[2] < 0:
            linear_vel[2] = -linear_vel[2]
            pos[2] = z_lo + radius
            bounced = True
        if pos[2] + radius > z_hi and linear_vel[2] > 0:
            linear_vel[2] = -linear_vel[2]
            pos[2] = z_hi - radius
            bounced = True

        if bounced and bounce_jitter > 0:
            # Perturb the spin axis a bit; keeps the tumbling lively.
            jitter = random_unit_vector() * bounce_jitter
            angular_axis = normalize(angular_axis + jitter)

        # Rotational motion
        delta_R = rotation_matrix(angular_axis, angular_speed * dt)
        orientation = delta_R @ orientation

        # Transform vertices to world space
        rotated = verts @ orientation.T
        world_verts = rotated + pos

        # Project all vertices
        projected = []
        for v in world_verts:
            projected.append(project(v, focal, max_y, max_x))

        stdscr.erase()

        # Edges first (green '*')
        edge_attr = curses.color_pair(COLOR_EDGE) | curses.A_BOLD
        for a, b in edges:
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

        # Vertices on top (white '@')
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
        info = (f"Mesh: {display_name}  "
                f"V={len(verts)} E={len(edges)} F={len(faces)}  "
                f"pos=({pos[0]:+.1f},{pos[1]:+.1f},{pos[2]:.1f})")
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
    mesh_file="data/meshes/cube.obj",
    duration=20,
    frame_delay=0.04,
    mesh_scale=1.0,
    box_x=4.0,
    box_y=2.5,
    box_z_min=4.0,
    box_z_max=10.0,
    linear_speed=2.5,
    angular_speed=1.5,
    focal_factor=0.5,
    bounce_jitter=0.3,
):
    duration = float(duration)
    frame_delay = float(frame_delay)
    mesh_scale = float(mesh_scale)
    box_x = float(box_x)
    box_y = float(box_y)
    box_z_min = float(box_z_min)
    box_z_max = float(box_z_max)
    linear_speed = float(linear_speed)
    angular_speed = float(angular_speed)
    focal_factor = float(focal_factor)
    bounce_jitter = float(bounce_jitter)

    curses.wrapper(lambda stdscr: run(
        stdscr, mesh_file, duration, frame_delay, mesh_scale,
        box_x, box_y, box_z_min, box_z_max,
        linear_speed, angular_speed, focal_factor, bounce_jitter,
    ))


if __name__ == "__main__":
    main()
