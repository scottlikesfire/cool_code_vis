import curses
import math
import os
import random
import sys
import time

import numpy as np

# scottlib import
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SUBMODULES = os.path.join(_REPO_ROOT, "submodules")
if _SUBMODULES not in sys.path:
    sys.path.insert(0, _SUBMODULES)

from scottlib.utils.mesh import read_obj


# Color pairs 1..7 are mesh colors, 8 is the status-bar label color.
COLOR_PALETTE = [
    curses.COLOR_RED,
    curses.COLOR_YELLOW,
    curses.COLOR_GREEN,
    curses.COLOR_CYAN,
    curses.COLOR_BLUE,
    curses.COLOR_MAGENTA,
    curses.COLOR_WHITE,
]
COLOR_NAMES = ["red", "yellow", "green", "cyan", "blue", "magenta", "white"]
COLOR_LABEL = 8

# Dark → light. " " means "don't draw" (essentially in shadow).
SHADE_CHARS = " .:-=+*#%@"


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    for i, c in enumerate(COLOR_PALETTE):
        curses.init_pair(i + 1, c, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


# ----- Math -----

def normalize(v):
    n = float(np.linalg.norm(v))
    if n < 1e-9:
        return np.array([1.0, 0.0, 0.0])
    return v / n


def random_unit_vector():
    z = random.uniform(-1, 1)
    phi = random.uniform(0, math.tau)
    s = math.sqrt(max(0.0, 1 - z * z))
    return np.array([s * math.cos(phi), s * math.sin(phi), z])


def rotation_matrix(axis, angle):
    c = math.cos(angle)
    s = math.sin(angle)
    t = 1 - c
    x, y, z = axis
    return np.array([
        [t * x * x + c,     t * x * y - s * z, t * x * z + s * y],
        [t * x * y + s * z, t * y * y + c,     t * y * z - s * x],
        [t * x * z - s * y, t * y * z + s * x, t * z * z + c],
    ])


# ----- Mesh helpers -----

def fallback_cube():
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


def newell_normal(polygon_world_pts):
    """Robust polygon normal via Newell's method. Works for any planar
    polygon, including non-convex ones, where cross(v1-v0, v2-v0) using
    only the first three vertices can give the wrong sign on a concave
    corner.
    """
    n = np.zeros(3)
    num = len(polygon_world_pts)
    for i in range(num):
        v0 = polygon_world_pts[i]
        v1 = polygon_world_pts[(i + 1) % num]
        n[0] += (v0[1] - v1[1]) * (v0[2] + v1[2])
        n[1] += (v0[2] - v1[2]) * (v0[0] + v1[0])
        n[2] += (v0[0] - v1[0]) * (v0[1] + v1[1])
    length = float(np.linalg.norm(n))
    if length < 1e-9:
        return None
    return n / length


def _project_to_plane(polygon_world_pts, normal):
    """Project polygon vertices to a 2D coordinate system in the polygon's
    own plane."""
    ref = np.array([1.0, 0.0, 0.0])
    if abs(np.dot(ref, normal)) > 0.9:
        ref = np.array([0.0, 1.0, 0.0])
    u = np.cross(normal, ref)
    u = u / np.linalg.norm(u)
    v = np.cross(normal, u)
    return np.array([[np.dot(p, u), np.dot(p, v)] for p in polygon_world_pts])


def _ear_clip_2d(pts):
    """Ear-clip a 2D polygon. Returns triangle index tuples into pts.
    Polygon must be simple (no self-intersections); accepts any winding."""
    n = len(pts)
    if n < 3:
        return []
    if n == 3:
        return [(0, 1, 2)]

    # Compute signed area to determine winding
    area = 0.0
    for i in range(n):
        a = pts[i]
        b = pts[(i + 1) % n]
        area += a[0] * b[1] - b[0] * a[1]

    indices = list(range(n))
    if area < 0:
        indices.reverse()

    def cross2(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def inside_tri(p, a, b, c):
        d1 = cross2(a, b, p)
        d2 = cross2(b, c, p)
        d3 = cross2(c, a, p)
        has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
        has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
        return not (has_neg and has_pos)

    triangles = []
    safety = 0
    while len(indices) > 3 and safety < 4 * n:
        safety += 1
        ear_found = False
        for i in range(len(indices)):
            prev_i = indices[(i - 1) % len(indices)]
            cur_i = indices[i]
            next_i = indices[(i + 1) % len(indices)]
            a, b, c = pts[prev_i], pts[cur_i], pts[next_i]
            # Convex corner test (CCW since we normalized winding above)
            if cross2(a, b, c) <= 0:
                continue
            # Ensure no other vertex lies inside this candidate ear
            ear = True
            for j in indices:
                if j in (prev_i, cur_i, next_i):
                    continue
                if inside_tri(pts[j], a, b, c):
                    ear = False
                    break
            if ear:
                triangles.append((prev_i, cur_i, next_i))
                indices.pop(i)
                ear_found = True
                break
        if not ear_found:
            break  # degenerate / self-intersecting polygon

    if len(indices) == 3:
        triangles.append((indices[0], indices[1], indices[2]))
    return triangles


def triangulate(face, world_verts):
    """Triangulate a (possibly non-convex) polygon. Returns triangle index
    tuples into the original mesh vertex array. Falls back to fan
    triangulation if normal computation fails."""
    if len(face) < 3:
        return []
    if len(face) == 3:
        return [(face[0], face[1], face[2])]

    poly_pts = [world_verts[i] for i in face]
    normal = newell_normal(poly_pts)
    if normal is None:
        return [(face[0], face[i], face[i + 1])
                for i in range(1, len(face) - 1)]

    pts_2d = _project_to_plane(poly_pts, normal)
    local_tris = _ear_clip_2d(pts_2d)
    return [(face[i], face[j], face[k]) for (i, j, k) in local_tris]


# ----- Projection / rasterization -----

def project(point, focal, max_y, max_x, near=0.1):
    z = point[2]
    if z <= near:
        return None
    cx = max_x / 2
    cy = max_y / 2
    sx = cx + 2 * focal * point[0] / z
    sy = cy + focal * point[1] / z
    return (sx, sy, z)


def rasterize_triangle(stdscr, p0, p1, p2, ch, attr, max_y, max_x, zbuf):
    """Half-space triangle fill with per-pixel z-buffering, so interpenetrating
    geometry (e.g. the stellated octahedron's two tetrahedra) renders correctly."""
    xs = (p0[0], p1[0], p2[0])
    ys = (p0[1], p1[1], p2[1])
    z0, z1, z2 = p0[2], p1[2], p2[2]
    min_x = max(0, int(math.floor(min(xs))))
    end_x = min(max_x - 1, int(math.ceil(max(xs))))
    min_y = max(0, int(math.floor(min(ys))))
    end_y = min(max_y - 2, int(math.ceil(max(ys))))
    if end_x < min_x or end_y < min_y:
        return

    ax, ay = p0[0], p0[1]
    bx, by = p1[0], p1[1]
    cx, cy = p2[0], p2[1]

    # Edge functions; sign is consistent for points on a single side
    def edge(ux, uy, vx, vy, px, py):
        return (vx - ux) * (py - uy) - (vy - uy) * (px - ux)

    area = edge(ax, ay, bx, by, cx, cy)
    if abs(area) < 1e-9:
        return
    inv_area = 1.0 / area

    for y in range(min_y, end_y + 1):
        zbuf_row = zbuf[y]
        for x in range(min_x, end_x + 1):
            px = x + 0.5
            py = y + 0.5
            w0 = edge(bx, by, cx, cy, px, py)
            w1 = edge(cx, cy, ax, ay, px, py)
            w2 = edge(ax, ay, bx, by, px, py)
            inside = (w0 >= 0 and w1 >= 0 and w2 >= 0) or \
                     (w0 <= 0 and w1 <= 0 and w2 <= 0)
            if not inside:
                continue
            # Barycentric weights → interpolated depth at this pixel
            b0 = w0 * inv_area
            b1 = w1 * inv_area
            b2 = w2 * inv_area
            z = b0 * z0 + b1 * z1 + b2 * z2
            if z < zbuf_row[x]:
                zbuf_row[x] = z
                try:
                    stdscr.addstr(y, x, ch, attr)
                except curses.error:
                    pass


# ----- Shading -----

def shade_attr(intensity, color):
    intensity = max(0.0, min(1.0, intensity))
    idx = int(intensity * (len(SHADE_CHARS) - 1))
    ch = SHADE_CHARS[idx]
    if ch == " ":
        return None
    if intensity < 0.4:
        attr = curses.color_pair(color) | curses.A_DIM
    elif intensity > 0.7:
        attr = curses.color_pair(color) | curses.A_BOLD
    else:
        attr = curses.color_pair(color)
    return ch, attr


# ----- Main render loop -----

def run(stdscr, mesh_file, duration, frame_delay, mesh_scale, distance,
        focal_factor, angular_speed, ambient, light_offset):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    # Resolve mesh path: if a directory, pick a random .obj
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
            full_path = "<fallback>"
    except (OSError, FileNotFoundError, ValueError):
        verts, faces = fallback_cube()
        full_path = "<fallback>"

    display_name = os.path.basename(full_path) if full_path else "<fallback>"

    # Center on centroid, then normalize to a unit bounding sphere so the
    # same `distance` and `focal_factor` look right for any input mesh.
    centroid = verts.mean(axis=0)
    verts = verts - centroid
    radius = float(np.linalg.norm(verts, axis=1).max())
    if radius > 1e-9:
        verts = verts / radius
    verts = verts * float(mesh_scale)

    base_color = random.randint(1, len(COLOR_PALETTE))
    color_name = COLOR_NAMES[base_color - 1]

    angular_axis = random_unit_vector()
    orientation = np.eye(3)

    light_pos = np.array(light_offset, dtype=float)
    obj_pos = np.array([0.0, 0.0, distance])

    face_list = [list(f) for f in faces]

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

        # Continuous rotation
        delta_R = rotation_matrix(angular_axis, angular_speed * dt)
        orientation = delta_R @ orientation

        rotated = verts @ orientation.T
        world_verts = rotated + obj_pos

        # Project all vertices once
        projected = [project(v, focal, max_y, max_x) for v in world_verts]

        # For each face, cull and shade
        renderable = []  # (depth, ch, attr, [tri_index_tuples])
        for face in face_list:
            wp = [world_verts[i] for i in face]
            face_centroid = sum(wp) / len(wp)

            # Newell's normal handles non-convex faces correctly
            normal = newell_normal(wp)
            if normal is None:
                continue

            # Camera at origin: view_dir from face → camera = -centroid_world
            view_dir = -face_centroid
            view_len = float(np.linalg.norm(view_dir))
            if view_len < 1e-9:
                continue
            view_dir = view_dir / view_len

            # Backface culling: if normal points away from camera, skip
            if np.dot(normal, view_dir) <= 0:
                continue

            # Lambertian shading from a positional light
            light_dir = light_pos - face_centroid
            light_len = float(np.linalg.norm(light_dir))
            if light_len < 1e-9:
                continue
            light_dir = light_dir / light_len

            diffuse = max(0.0, float(np.dot(normal, light_dir)))
            intensity = ambient + (1 - ambient) * diffuse

            shade = shade_attr(intensity, base_color)
            if shade is None:
                continue
            ch, attr = shade

            renderable.append((float(face_centroid[2]), ch, attr,
                               triangulate(face, world_verts)))

        # Per-pixel z-buffer — required for interpenetrating geometry
        # (e.g. the stellated octahedron) where face-level painter's sort
        # can't pick the right surface for every pixel.
        zbuf = [[float("inf")] * max_x for _ in range(max_y)]

        stdscr.erase()
        for _depth, ch, attr, triangles in renderable:
            for a, b, c in triangles:
                p0, p1, p2 = projected[a], projected[b], projected[c]
                if p0 is None or p1 is None or p2 is None:
                    continue
                rasterize_triangle(stdscr, p0, p1, p2, ch, attr,
                                   max_y, max_x, zbuf)

        info = (f"Mesh: {display_name}  V={len(verts)} F={len(face_list)}  "
                f"Color: {color_name}  Faces drawn: {len(renderable)}")
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
    mesh_file="data/meshes",
    duration=20,
    frame_delay=0.05,
    mesh_scale=1.0,
    distance=4.0,
    focal_factor=0.7,
    angular_speed=0.6,
    ambient=0.15,
    light_offset=None,
):
    duration = float(duration)
    frame_delay = float(frame_delay)
    mesh_scale = float(mesh_scale)
    distance = float(distance)
    focal_factor = float(focal_factor)
    angular_speed = float(angular_speed)
    ambient = float(ambient)
    if light_offset is None:
        light_offset = [3.0, 2.0, 0.0]

    curses.wrapper(lambda stdscr: run(
        stdscr, mesh_file, duration, frame_delay, mesh_scale, distance,
        focal_factor, angular_speed, ambient, list(light_offset),
    ))


if __name__ == "__main__":
    main()
