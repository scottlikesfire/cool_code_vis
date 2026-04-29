# cool_code_vis

> **Heavily Vibe Coded, But All About the Vibes**

A growing collection of terminal visualizers — basically a screensaver app you
can run from a TTY. It currently ships **48 modules** spanning fractals,
backtracking algorithms, fluid effects, particle systems, ASCII 3D and 4D
rendering, scientific dynamics simulations (physics, biology, chemistry,
astronomy, math), text/data toys, and a few weird ideas that just looked
cool.

The whole thing is driven by a single config file that picks which modules to
randomly cycle through.

---

## First-time setup

```bash
# 1. Clone with the scottlib submodule (or pull it after cloning)
git clone --recurse-submodules <repo-url> cool_code_vis
# already cloned without --recurse-submodules?
git submodule update --init --recursive

# 2. Install the Python dependencies (numpy, asciimatics, asciichartpy,
#    feedparser, scipy). Pick whichever flow matches your setup:

# pip / venv:
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# conda:
conda create -n cool_code python=3.11
conda activate cool_code
pip install -r requirements.txt

# 3. Generate the procedural mesh library. Everything in data/meshes/
#    except n64.obj is produced by these two scripts.
python generate_meshes.py           # platonic solids, sphere, torus, knot
python generate_advanced_meshes.py  # cones, cylinders, Möbius, Menger, etc.
```

After that, you're ready to run.

---

## Quick start

```bash
# Run the everything-enabled config
python main.py test1.json

# Or one of the curated subsets
python main.py visual.json       # pure visual effects
python main.py algorithms.json   # backtracking / search / fractals
python main.py science.json      # physics / biology / dynamics / math
python main.py mesh.json         # the two 3D mesh visualizers
python main.py shaded_mesh.json  # just the shaded 3D renderer
python main.py bouncing_mesh.json
python main.py hypercube.json    # rotating 4D tesseract
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

### 3D / 4D mesh visualizers

The two `.obj`-loading modules use `scottlib.utils.mesh.read_obj`. Their
`mesh_file` parameter accepts either a single `.obj` path or a directory (in
which case a random `.obj` is chosen each run). The `hypercube` module has
no input file — its geometry is hardcoded.

- **`bouncing_mesh`** — DVD-logo-style 3D bouncing. The mesh floats around
  inside a configurable 3D box, with linear and angular velocity. Wall hits
  reflect velocity, snap the object inside, and randomly perturb the spin
  axis. Vertices project to white `@`, rasterized edges to green `*`. Meshes
  are auto-centered and normalized to a unit bounding sphere so the same
  box / speed parameters work for any mesh.
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
- **`hypercube`** — wireframe rotating tesseract (4D cube). Hardcoded
  geometry: 16 vertices at every `(±1,±1,±1,±1)`, 32 edges. There's no
  single rotation axis in 4D, so each of the six coordinate planes
  (`xy / xz / xw / yz / yw / zw`) rotates at its own configurable angular
  speed. **4D → 3D** projection scales by `1/(distance_4d − w)`, so vertices
  closer to the 4D camera appear larger — that's what produces the classic
  "inner cube swaps with outer cube" tesseract look. Then standard 3D → 2D
  pinhole projection gives the screen output. Vertices as white `@`, edges
  as rasterized green `*`.

### Science & dynamics

Each of these is a small physical / mathematical / biological / chemical
simulation, animated continuously.

**Classical physics**

- **`double_pendulum`** — RK4-integrated chaotic two-link pendulum (full
  Lagrangian equations). Two arms swing from a top pivot; the end bob
  leaves a long fading cyan trail that exposes the chaotic orbit.
  Configurable masses, lengths, gravity, sub-step count.
- **`pendulum_wave`** — `num_pendulums` simple-harmonic pendulums hanging
  from a horizontal pivot bar with periods `T_i = T_beat/(period_offset+i)`.
  They start in phase, drift apart over the course of `T_beat` seconds,
  briefly form traveling-wave patterns, then snap back into sync. Each
  pendulum is one continuous color from pivot to bob.
- **`wave_on_string`** — Discrete 1D wave equation with fixed boundaries.
  Random Gaussian pulses are injected periodically and propagate, reflect
  off the ends, and superpose. `amplitude` is the **display scale** (u value
  that fills the chart); `pulse_strength` controls the size of injected
  pulses, decoupled from display.
- **`n_body`** — Sun-plus-planets gravitational simulation. Each planet is
  initialized with randomized velocity magnitude, tangent direction, and
  orbital radius, plus mass ~1/100 of the sun, so orbits are eccentric and
  planets perturb each other — occasionally producing decay, scattering,
  capture, or ejection events.
- **`lorenz_attractor`** — Standard `σ, ρ, β` parameters via RK4. The
  trail's color cycles through the full palette by age. Slow view rotation
  around the z-axis gives a 3D feel.

**Statistical / soft-matter physics**

- **`ising_model`** — 2D Metropolis Monte Carlo on the full terminal
  lattice with periodic boundary conditions. Temperature sinusoidally
  sweeps across the critical point so you watch the lattice condense into
  magnetic domains below `Tc≈2.269` and dissolve back into noise above.
  Live `M = ⟨s⟩` shown in the status bar.
- **`gray_scott`** — Reaction-diffusion (Turing patterns). Two species U/V
  evolve via `∂U/∂t = D_u∇²U − UV² + F(1−U)`,
  `∂V/∂t = D_v∇²V + UV² − (F+k)V`. Six named feed/kill presets — `spots`,
  `stripes`, `mazes`, `fingers`, `worms`, `ripples` — pick one per run.
  Vectorized with NumPy `np.roll` for the periodic-BC Laplacian.
- **`dla`** — Diffusion-limited aggregation. Random walkers stick on
  contact with the seed cluster, slowly growing dendritic / coral-like
  fractal structures. Uses smart spawning (walkers start on the cluster's
  bounding box expanded by `spawn_buffer`, killed if they wander past
  `kill_buffer`) so attachments happen in O(buffer²) steps instead of
  O(screen²). Particles colored by sequence number.

**Biology**

- **`dna_helix`** — Horizontally-running double helix with random A/T/G/C
  sequence and properly Watson–Crick-paired letters. Backbones use depth
  ordering so the front strand overdraws the back as the helix rotates.
- **`predator_prey`** — Lotka–Volterra dynamics. Split-screen: left panel
  is `prey/pred populations vs time`, right panel is the `phase portrait`
  showing the closed orbit.
- **`sir_epidemic`** — Spatial Moore-neighborhood SIR model. Top region is
  the agent grid (S=`.`, I=`@`, R=`#`); bottom region plots S/I/R
  populations over time. Auto-exits a couple seconds after the epidemic
  burns out.
- **`boids`** — Reynolds rules with separation, alignment, and cohesion
  weights. Each boid renders as a directional ASCII arrow chosen from
  velocity angle. Wrap-around boundaries.
- **`lsystem`** — Turtle-graphics L-system fractals. Seven presets
  (`fractal_tree`, `koch`, `koch_snowflake`, `sierpinski`, `dragon`,
  `plant`, `sierpinski_arrowhead`); picks one randomly per run and animates
  segments drawing in over time.

**Astronomy**

- **`solar_orrery`** — Inner + outer planets at correct relative orbital
  periods (Mercury 0.241 yr → Neptune 164.79 yr). Sun at the origin, faint
  dotted ellipses for orbits, color-coded markers with hovering name
  labels. `time_scale` controls how many simulated years pass per real
  second.

**Math**

- **`wolfram_rule`** — 1D elementary cellular automaton scrolling
  downward. `rule="random"` picks each run from a curated set
  `[30, 45, 73, 90, 105, 110, 150, 184]`. Newest generation is bold yellow.
- **`fourier_epicycles`** — Chain of rotating circles whose tip y-position
  draws the partial-sum waveform to the right. Picks among `square`,
  `sawtooth`, `triangle`, and `pulse` Fourier expansions per run by
  default. `Σ|a_n|` is normalized to `total_amplitude` so the on-screen
  size is identical regardless of which waveform was chosen — only the
  trail shape changes.
- **`ulam_spiral`** — Sieve up to `max_n`, then walk a square spiral
  plotting one integer per step. Primes are bold yellow `#`, composites
  are dim blue `.`. Diagonals show the unexpected prime patterns.

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
# NOTE ON DATA
I have not include most of the data I am using here, this is because I do not know what I have the rights to etc. The meshes should generate, and eventually i will put together a full set of data that is public domain/appropriately licensed etc. 
---

## Configs

`data/configs/` holds the JSON configs:

| Config | Contents |
|---|---|
| `test1.json` | Master config — every module enabled |
| `visual.json` | Pure visual effects only |
| `algorithms.json` | Algorithmic / search / fractal modules |
| `science.json` | Physics, biology, dynamics, math |
| `mesh.json` | Both `bouncing_mesh` and `shaded_mesh` |
| `bouncing_mesh.json` | Just `bouncing_mesh` |
| `shaded_mesh.json` | Just `shaded_mesh` |
| `hypercube.json` | Just the 4D tesseract |

Make a new config by copying one of these and toggling `enabled` flags or
tweaking parameters. Every module's `main()` signature is the source of truth
for what params it accepts.

---

## Mesh library

`data/meshes/` ships with a low-poly mesh set, kept small enough for TUI
rendering:

**Generated by `generate_meshes.py`:**

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

**Generated by `generate_advanced_meshes.py`:**

| Mesh | V | F |
|---|---|---|
| `cone` | 14 | 24 |
| `truncated_cone` | 26 | 48 |
| `cylinder` | 26 | 48 |
| `oblique_cylinder` | 26 | 36 |
| `mobius_strip` (32×4) | 128 | 192 (doubled) |
| `menger_sponge` (1 iter) | 160 | 120 |
| `sierpinski_tetrahedron` (2 iter) | 64 | 64 |

The Möbius strip emits each face *twice* with reversed winding — it's a
non-orientable surface, so doubling lets backface culling pick the visible
side regardless of rotation angle.

**Checked in (not regenerated):** `n64.obj`.

Regenerate the procedural meshes any time with:

```bash
python generate_meshes.py
python generate_advanced_meshes.py
```

Both write `.obj` files to `data/meshes/`. Tweak the parameters at the bottom
of either script (or the generator defaults in
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
  - **Platonic & related:** `generate_tetrahedron`, `generate_cube`,
    `generate_octahedron`, `generate_icosahedron`, `generate_dodecahedron`
    (built as the dual of the icosahedron with an outward-orientation pass
    on the resulting pentagons), `generate_stellated_octahedron`
    (interpenetrating tetrahedra with reversed-winding Tet B).
  - **Smooth surfaces:** `generate_uv_sphere`, `generate_torus`,
    `generate_trefoil_knot` (Frenet frames so the seam closes cleanly).
  - **Cones & cylinders:** `generate_cone`, `generate_cylinder`,
    `generate_truncated_cone`, `generate_oblique_cylinder`.
  - **Fractals:** `generate_menger_sponge` (3³ minus 7 sub-cubes per
    iteration), `generate_sierpinski_tetrahedron` (4 corner sub-tets per
    iteration with per-face outward-orientation correction).
  - **Non-orientable:** `generate_mobius_strip` with the seam vertex flip
    plus doubled-winding faces so both sides render.

---

## Repository layout

```
cool_code_vis/
├── main.py                          # harness: load config, randomly pick modules
├── generate_meshes.py               # platonic solids, sphere, torus, knot
├── generate_advanced_meshes.py      # cones, cylinders, Möbius, fractals
├── requirements.txt
├── modules/                         # one file per visualizer
│   ├── _quit_helper.py              # shared cbreak-stdin polling utility
│   └── …                            # 48 visualization modules
├── data/
│   ├── configs/                     # JSON configs
│   ├── meshes/                      # .obj files used by the 3D visualizers
│   └── text/                        # words.txt, moby_dick.txt
└── submodules/
    └── scottlib/                    # mesh I/O, procedural geometry, coordinates
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
