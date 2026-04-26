# cool_code_vis

> **Heavily Vibe Coded, But All About the Vibes**

A growing collection of terminal visualizers — basically a screensaver app you
can run from a TTY. It currently ships **30 modules** spanning fractals,
backtracking algorithms, fluid effects, particle systems, ASCII 3D rendering,
text/data toys, and a few weird ideas that just looked cool.

The whole thing is driven by a single config file that picks which modules to
randomly cycle through.

---

## Quick start

```bash
# Run the everything-enabled config
python main.py test1.json

# Or one of the curated subsets
python main.py visual.json       # pure visual effects
python main.py algorithms.json   # backtracking / search / fractals
python main.py mesh.json         # the two 3D mesh visualizers
python main.py shaded_mesh.json  # just the shaded 3D renderer
python main.py bouncing_mesh.json
```

Press **`q`** or **`ESC`** at any time to skip to the next module.

---

## How the harness works

`main.py` reads a JSON config from `data/configs/`. Each top-level key (other
than `iterations`) is a module name. Modules with `"enabled": true` go into
the random pool; the harness picks one each iteration and passes the rest of
the keys as keyword arguments to that module's `main()` function.

```jsonc
{
    "iterations": 0,        // 0 = loop forever; positive = run that many times
    "fireworks": {
        "enabled": true,
        "duration": 25,
        "launch_rate": 1.5
        // ... module-specific params
    },
    "fire": {
        "enabled": true,
        "duration": 15,
        "intensity": 2
    }
}
```

Between modules the harness clears the terminal so leftover content from one
module never bleeds into the next.

---

## Modules

### Algorithmic & search

These visualize a classic algorithm running. Most expose a `step_delay` for
animation pacing and a `completion_pause` to hold the final frame.

- **`prime_sieve`** — Sieve of Eratosthenes. Numbers are laid out in a grid;
  primes flash green, composites are dimmed red as they get marked off.
- **`sorting_visualizer`** — picks bubble / insertion / selection / quick sort
  at random and animates the comparison/swap/sorted state on a vertical bar
  array.
- **`cellular_automaton`** — Conway's Game of Life. Yellow newborns, fading
  red deaths; auto-reseeds when the population dies out or stagnates.
- **`maze_generator`** — recursive backtracker carving a maze in real time.
- **`pathfinding`** — generates a maze, then runs A*. Frontier in yellow,
  visited in cyan, final path in magenta.
- **`n_queens`** — animates backtracking placement on a chessboard. Yellow
  trial queen, red flash on conflict, green confirmed placements. Cells scale
  to fill a `target_size`.
- **`knights_tour`** — Warnsdorff's heuristic on an N×N board. Each square is
  numbered as the knight visits it; previous step shown in green, current in
  yellow reverse.
- **`sudoku`** — pre-solves a randomly chosen puzzle as fast as possible
  (showing a progress bar), then replays the trace evenly across `duration`
  with a status panel showing `PLACING` / `BACKTRACKING`, percent complete,
  and a configurable activity log.
- **`tower_of_hanoi`** — classic recursive solver. Disks are color-coded
  blocks. A configurable-length history log and live peg-state panel sit
  above the puzzle, with disk numbers in the readout colored to match their
  on-screen color.
- **`mandelbrot`** — animated zoom into a randomly chosen high-precision
  target (Seahorse Valley, Misiurewicz Point, Triple Spiral, …). Iteration
  count grows logarithmically with zoom; auto-resets to a new target when it
  hits float64 precision (~1e13).
- **`julia_set`** — picks a random named Julia constant (Dendrite, Douady's
  Rabbit, Spiral, Siegel Disk, etc.) and morphs `c` along a small circular
  path so the fractal continuously evolves.

### Pure visual effects

- **`clock`** — big block-digit clock with a date label, surrounded by an
  oval ring of tick marks. A smooth sub-second hand sweeps the ring with a
  comet-style fading trail; spark particles fly off the second hand and a
  separate magenta minute marker creeps along its own arc.
- **`starfield`** — true 3D-perspective stars warping past with proper z
  projection; closer stars use denser characters and brighter colors.
- **`fire`** — Doom-style fire propagation algorithm. Heat source at the
  bottom, random horizontal spread + cooling upward, mapped to dim red →
  bright red → yellow → white. Sparks/embers occasionally launch from hot
  cells and float up with their own physics.
- **`fireworks`** — particle-system fireworks with five distinct burst
  patterns: simple sphere, falling-trail, tight ring, drooping willow, and
  a multi-burst that re-explodes its seeds in a unified secondary color
  (with a per-particle parent → child color fade). Almost everything is
  exposed to the config (per-burst counts, speed ranges, fade duration,
  launch rate, gravity).
- **`wave`** — randomly selects one of nine wave/curve types per run:
  traveling sines, Lissajous, standing wave, beats/interference, wave
  packet, polar rose curve, hypotrochoid (spirograph), damped wave, and
  EKG-style P-Q-R-S-T heartbeat. A bottom status bar shows the title,
  equation, and live parameters in color-coded segments.
- **`bouncing_balls`** — physics balls with gravity, wall bounces,
  configurable damping, and color-fading character trails.
- **`tunnel`** — radial depth-warping pulse that recedes outward with
  concentric color bands cycling through the palette.

### 3D mesh visualizers

Both load `.obj` files via `scottlib.utils.mesh.read_obj`. The `mesh_file`
parameter accepts either a single `.obj` path or a directory (in which case a
random `.obj` is chosen each run).

- **`bouncing_mesh`** — DVD-logo-style 3D bouncing. The mesh floats around
  inside a configurable 3D box, with linear and angular velocity. Wall hits
  reflect velocity, snap the object inside, and randomly perturb the spin
  axis. Vertices project to white `@`, rasterized edges to green `*`.
- **`shaded_mesh`** — solid 3D rendering. Object sits in front of a virtual
  camera, slowly rotating around a random axis. Each frame:
  - All meshes are auto-centered on their centroid and rescaled to a unit
    bounding sphere so the same `distance` and `focal_factor` work for every
    mesh.
  - **Backface culling** uses **Newell's method** for the polygon normal —
    robust on non-convex faces (where `cross(v1-v0, v2-v0)` would flip
    sign on a concave corner).
  - **Ear-clipping triangulation** correctly tessellates non-convex
    polygons without bleed-over into the missing notches.
  - **Per-pixel Z-buffer** so interpenetrating geometry like the stellated
    octahedron renders correctly (face-level painter's sort can't pick the
    right surface at every pixel).
  - **Lambertian shading** from a positional light, mapped through a
    density gradient `" .:-=+*#%@"` plus `A_DIM`/`A_BOLD` for an extended
    dynamic range.
  - Object color is randomly chosen from the 8-color palette per run.

### Code/repo-aware

These reach into the repo itself for content.

- **`directory_structure_visualizer`** — animates an indented `tree`-style
  view of a directory, expanding each subdirectory's contents one at a time
  with auto-scrolling. Supports a "reverse" mode where the root is at the
  bottom and branches grow upward (`┌──` instead of `└──`).
- **`metaprogramming_imports`** — walks every `.py` in the repo, parses with
  `ast`, and animates a ranked bar chart of `import` frequencies. A panel
  below shows live details of the file currently being scanned (line count,
  function count, file size).
- **`rainbow_code`** — picks a random Python file and prints it character by
  character, color-cycling through red/yellow/green/cyan/blue/magenta over a
  configurable `cycle_length`.

### Text & data

- **`grapher`** — animated multi-line ascii chart of four random walks. The
  curves draw in left-to-right with a moving title bar, axis labels
  ("baseline performance", "generation number"), and a sample legend.
- **`letter_frequency`** — reads a text file (default `data/text/words.txt`)
  word by word, animating a bar chart of letter frequencies that grows as
  words are processed.
- **`unredact`** — picks a random adjacent group of paragraphs from a text
  file (default `data/text/moby_dick.txt`), redacts each word with a
  configurable `redact_probability`, and slowly reveals them one at a time
  in random order. A green progress bar at the bottom tracks decryption
  progress.
- **`matrix_rain`** — classic Matrix code rain (green falling characters
  with bright white heads). Pre-seeds drops mid-screen so it doesn't start
  empty; preceded by a green "loading matrix code" progress bar.
- **`plasma`** — `asciimatics`-based plasma effect. Preceded by a centered
  "computing plasma simulation" progress bar.
- **`rss_feed_reader`** — fetches the configured RSS feeds, extracts words
  from titles/summaries (filtering stop words), and animates a ranked
  word-frequency chart. A loading screen pings every feed first; if all
  fail, shows a red **"FEEDS UNAVAILABLE — CHECK NETWORK"** screen instead.
- **`progress_bars`** — multiple green progress bars with random hex titles
  finish at random fractions of the total duration; a blue overall bar
  finishes at exactly `duration`.

### Utility

- **`_quit_helper.py`** — `StdinPoller` context manager that puts stdin into
  cbreak mode and provides non-blocking `should_quit()` checks. Used by
  modules that don't have a curses window of their own (e.g. `grapher`,
  `plasma` loading screen, `matrix_rain` loading screen) so they can still
  honor `q`/`ESC`.

---
# NOTEON DATA
I have not include most of the data I am using here, this is because I do not know what I have the rights to etc. The meshes should generate, and eventually i will put together a full set of data that is public domain/appropriately licensed etc. 
---

## Configs

`data/configs/` holds the JSON configs:

| Config | Contents |
|---|---|
| `test1.json` | Master config — every module enabled |
| `visual.json` | Pure visual effects only |
| `algorithms.json` | Algorithmic / search modules |
| `mesh.json` | Both `bouncing_mesh` and `shaded_mesh` |
| `bouncing_mesh.json` | Just `bouncing_mesh` |
| `shaded_mesh.json` | Just `shaded_mesh` |

Make a new config by copying one of these and toggling `enabled` flags or
tweaking parameters. Every module's `main()` signature is the source of truth
for what params it accepts.

---

## Mesh library

`data/meshes/` ships with a low-poly mesh set, kept small enough for TUI
rendering:

| Mesh | V | F |
|---|---|---|
| `tetrahedron` | 4 | 4 |
| `cube` | 8 | 6 |
| `octahedron` | 6 | 8 |
| `icosahedron` | 12 | 20 |
| `dodecahedron` | 20 | 12 (pentagons) |
| `stellated_octahedron` | 8 | 8 |
| `uv_sphere` (6×8) | 50 | 56 |
| `torus` (12×6) | 72 | 72 |
| `trefoil_knot` (32×4) | 128 | 128 |

Regenerate the procedural meshes (everything except `cube` and `n64`) with:

```bash
python generate_meshes.py
```

This writes fresh `.obj` files to `data/meshes/`. Tweak the parameters at the
bottom of `generate_meshes.py` (or the generator defaults in
`submodules/scottlib/shape_gen/meshes.py`) to change resolution.

The OBJ I/O lives in `submodules/scottlib/utils/mesh.py` and supports
arbitrary polygon faces (triangles, quads, pentagons, mixed) — both reading
and writing.

---

## `scottlib` submodule

`submodules/scottlib/` is a small math/geometry library used by the mesh
generators and the 3D visualizers. The pieces touched by this repo:

- **`scottlib.utils.mesh`** — `read_obj` / `write_obj` / STL / PLY readers and
  writers. The OBJ functions handle any polygon size and the standard face
  formats (`v`, `v/vt`, `v//vn`, `v/vt/vn`).
- **`scottlib.shape_gen.meshes`** — procedural mesh generators:
  `generate_tetrahedron`, `generate_octahedron`, `generate_icosahedron`,
  `generate_dodecahedron` (built as the dual of the icosahedron with an
  outward-orientation pass on the resulting pentagons),
  `generate_uv_sphere`, `generate_torus`, `generate_trefoil_knot` (Frenet
  frames so the seam closes cleanly), `generate_stellated_octahedron`
  (compound of two interpenetrating tetrahedra with reversed-winding Tet B),
  plus the existing `generate_cylinder` and `generate_truncated_cone`.

---

## Repository layout

```
cool_code_vis/
├── main.py                  # harness: load config, randomly pick modules
├── generate_meshes.py       # rebuild data/meshes/ from scottlib generators
├── modules/                 # one file per visualizer
│   ├── _quit_helper.py      # shared cbreak-stdin polling utility
│   └── …                    # 30 visualization modules
├── data/
│   ├── configs/             # JSON configs
│   ├── meshes/              # .obj files used by the 3D visualizers
│   └── text/                # words.txt, moby_dick.txt for text-based modules
└── submodules/
    └── scottlib/            # mesh I/O, procedural geometry, coordinates
```

---

## Adding a new module

1. Create `modules/your_module.py`. Implement `def main(**kwargs)` —
   whatever kwargs you want will become config keys.
2. Use `curses.wrapper(...)` for terminal-graphics modules; honor `q`/`ESC`.
   For stdout-escape-based modules, use the `StdinPoller` from
   `_quit_helper.py` so quit still works.
3. Register it in `main.py`: import its `main`, add an entry to the
   `MODULES` dict.
4. Add a stanza to whichever config(s) should run it.
