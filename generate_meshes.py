"""Generate the low-poly mesh library used by the bouncing_mesh visualizer.

Writes a set of .obj files into data/meshes/. Run from the repo root:

    python generate_meshes.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "submodules"))

from scottlib.shape_gen import meshes
from scottlib.utils.mesh import write_obj


OUT_DIR = os.path.join(os.path.dirname(__file__), "data", "meshes")


def gen(name, verts, faces):
    path = os.path.join(OUT_DIR, f"{name}.obj")
    write_obj(verts, faces, path)
    print(f"  {name:<22}  V={len(verts):<4} F={len(faces):<4}  -> {path}")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"Writing meshes to {OUT_DIR}/")

    # Platonic solids
    gen("tetrahedron", *meshes.generate_tetrahedron())
    # Cube already exists in data/meshes/cube.obj — leave it alone.
    gen("octahedron", *meshes.generate_octahedron())
    gen("icosahedron", *meshes.generate_icosahedron())
    gen("dodecahedron", *meshes.generate_dodecahedron())

    # Solids of revolution
    gen("uv_sphere", *meshes.generate_uv_sphere(radius=1.0, num_lat=6, num_lon=8))
    gen("torus", *meshes.generate_torus(
        major_radius=1.0, minor_radius=0.35, num_major=12, num_minor=6))

    # Knot
    gen("trefoil_knot", *meshes.generate_trefoil_knot(
        major_radius=0.5, minor_radius=0.18, num_curve=32, num_ring=4))

    # Star polyhedron
    gen("stellated_octahedron", *meshes.generate_stellated_octahedron())


if __name__ == "__main__":
    main()
