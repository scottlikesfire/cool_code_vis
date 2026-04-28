"""Generate the more involved meshes: fractals, ruled / oblique surfaces,
and the Möbius strip.

These are heavier than what generate_meshes.py builds, so they live here
as a separate, opt-in step. Run from the repo root:

    python generate_advanced_meshes.py
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
    print(f"  {name:<26}  V={len(verts):<5} F={len(faces):<5}  -> {path}")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"Writing advanced meshes to {OUT_DIR}/")

    # Cones / cylinders
    gen("cone", *meshes.generate_cone(
        radius=1.0, height=2.0, num_segments=12))
    gen("truncated_cone", *meshes.generate_truncated_cone(
        radius1=1.0, radius2=0.4, height=2.0, num_segments=12))
    gen("cylinder", *meshes.generate_cylinder(
        radius=1.0, height=2.0, num_segments=12))
    gen("oblique_cylinder", *meshes.generate_oblique_cylinder(
        radius=1.0, height=2.0, num_segments=12, top_offset=(0.8, 0.0)))

    # Möbius strip
    gen("mobius_strip", *meshes.generate_mobius_strip(
        major_radius=1.0, half_width=0.4, num_u=32, num_v=4))

    # Fractal solids
    gen("menger_sponge", *meshes.generate_menger_sponge(
        iterations=1, size=2.0))
    gen("sierpinski_tetrahedron", *meshes.generate_sierpinski_tetrahedron(
        iterations=2, size=1.0))


if __name__ == "__main__":
    main()
