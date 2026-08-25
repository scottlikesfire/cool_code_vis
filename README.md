# cool_code_vis

> **Heavily Vibe Coded, But All About the Vibes**

A growing collection of terminal visualizers — basically a screensaver app you
can run from a TTY. It currently ships **80 modules** spanning fractals,
backtracking algorithms, fluid effects, particle systems, ASCII 3D and 4D
rendering, scientific dynamics simulations (physics, biology, chemistry,
astronomy, math), cellular automata, text/data toys, network/security eye
candy, and a few weird ideas that just looked cool.

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
# Run the everything-enabled config (all 80 modules)
python main.py default.json

# Or one of the curated subsets
python main.py visual.json       # pure visual effects
python main.py algorithms.json   # backtracking / search / fractals
python main.py science.json      # physics / biology / dynamics / math
python main.py new.json          # the 20 newest CA / fractal / 3D modules
python main.py orph.json         # network / security-themed modules
python main.py mesh.json         # the two 3D mesh visualizers
python main.py shaded_mesh.json  # just the shaded 3D renderer
python main.py bouncing_mesh.json
python main.py hypercube.json    # rotating 4D tesseract
```

Press **`q`** or **`ESC`** at any time to skip to the next module.

---

## How the harness works

`main.py` reads a JSON config from `data/configs/`. Each top-level key (other
than `iterations` and `scheduler`) is a module name. Modules with
`"enabled": true` go into the random pool; the harness picks one each
iteration and passes the rest of the keys as keyword arguments to that
module's `main()` function.

Three per-module keys are consumed by the scheduler instead of being passed
to the module: `enabled`, `weight` (base selection weight, default 1.0), and
`after` (a map of predecessor-module → multiplier, making this module more —
or less — likely right after that predecessor runs).

```jsonc
{
    "iterations": 0,        // 0 = loop forever; positive = run that many times
    "scheduler": {          // optional; all keys have defaults
        "no_repeat_window": 3,   // never repeat any of the last N modules (default 1)
        "recency_boost": 0.25,   // >0 favors modules that haven't run in a while (default 0)
        "track_history": true,   // append every run to the history file (default true)
        "history_file": "data/run_history.json"
    },
    "fireworks": {
        "enabled": true,
        "weight": 2.0,           // twice as likely as a weight-1 module
        "duration": 25,
        "launch_rate": 1.5
        // ... module-specific params
    },
    "fire": {
        "enabled": true,
        "after": {"fireworks": 4.0},  // 4x more likely right after fireworks
        "duration": 15,
        "intensity": 2
    }
}
```

Every run is appended to `data/run_history.json` (git-ignored): total run
count, per-module counts, and the last 500 runs with timestamps. Recency
weighting itself is per-session; the file is there for stats and future
scheduling ideas.

Between modules the harness clears the terminal so leftover content from one
module never bleeds into the next.

### The window spawner

`window_spawner` is a meta-module that lives in the pool like any other.
When it comes up it opens `num_windows` new terminal windows, each running
`main.py` with a generated config of `subset_size` random modules from its
`pool` (each window does `runs_per_window` iterations of `child_duration`
seconds), shows a live status panel, and closes the windows when they finish.
The spawned windows are deliberately **small and scattered at large random
offsets** so they overlap but each stays visible — making it obvious that
several independent things are running at once. Backends, tried in order: tmux panes (when running inside tmux —
works on a bare TTY or over ssh), macOS Terminal.app, then a Linux GUI
terminal (gnome-terminal / konsole / xfce4-terminal / xterm). With no backend
available it politely skips its turn. In `default.json` it's given a low
`weight` so it comes up only occasionally.

---

## Running on other systems (Jetson, Raspberry Pi, headless)

The app is pure-Python curses and runs anywhere Python + a terminal do, but a
few things are worth knowing when moving off a desktop Mac/Linux box.

**Dependencies.** On ARM SBCs, prefer the distro packages for the compiled
libs so pip doesn't build them from source:

```bash
# Debian / Ubuntu / Jetson (L4T) / Raspberry Pi OS
sudo apt install python3-numpy python3-scipy
pip install asciimatics asciichartpy feedparser   # pure-Python, install anywhere
```

On Raspberry Pi OS, `piwheels` already ships prebuilt `numpy`/`scipy` wheels,
so a plain `pip install -r requirements.txt` also works — it's just slower.

**Performance.** Several modules recompute a full-screen NumPy/SciPy field
every frame and are the ones to watch on weaker hardware (Pi 3/4, Jetson
Nano): `slime_mold`, `terrain_flyover`, `raymarch_sdf`, `metaballs`,
`gray_scott`, `cyclic_ca`, `chladni`, `strange_attractors`. If they can't keep
up with their `frame_delay`, do any of:

- run in a **smaller terminal window** (cost scales with rows × cols),
- raise `frame_delay` (fewer frames/sec), and
- lower the per-module knob that drives the work: `num_agents` (slime_mold),
  `view_distance` (terrain_flyover), `march_steps` (raymarch_sdf),
  `batch` (strange_attractors), `points_per_frame` (chaos_game).

A Jetson (Nano/Orin) generally has plenty of headroom; the tighter squeeze is
a Pi Zero/3 on a large console. The pure-curses modules (algorithms, meshes,
particle systems) are cheap everywhere.

**The window spawner** needs a way to open windows. On a headless console or
over plain ssh there's no GUI terminal and it isn't macOS, so `window_spawner`
**self-skips** — unless you run the whole app inside **tmux**, where it uses
split panes and works on a bare TTY. If you want spawned windows on a Jetson/Pi,
launch inside `tmux` (`sudo apt install tmux`).

**Network / security modules and real data.** The `simulate: false` default
means these read live data using OS tools that differ by platform:

| Module | Linux (Jetson/Pi) uses | macOS uses |
|---|---|---|
| `connections`, `packet_sniffer` | `lsof`, `netstat` | same |
| `netmap` | `arp` / `ip neigh` | `arp` |
| `port_scanner` | raw socket + `netstat`/`route` | same |
| `wifi_scan` | `nmcli` (NetworkManager) | `system_profiler` |
| `bluetooth_scan` | `bluetoothctl` (BlueZ) | `system_profiler` |

Install what you're missing (`sudo apt install lsof net-tools iproute2
network-manager bluez`). Wi-Fi/Bluetooth scanning needs the actual radios and
sometimes root; if a tool is absent or a scan returns nothing, the module
falls back to (or you can force) its animated mode with `"simulate": true`.
On a headless server with no radios, set `simulate: true` for `wifi_scan` and
`bluetooth_scan`. These modules are Unix-oriented and are effectively
simulate-only on Windows.

**Locale / fonts.** A few modules (`space_filling`, `window_spawner` panel)
use box-drawing characters. The Linux framebuffer console font may render
these as blanks; over ssh in any modern UTF-8 terminal they're fine. Make sure
your locale is UTF-8 (`export LANG=C.UTF-8`) if you see stray characters.

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
- **`ant_colony`** — Ant Colony Optimization solving a travelling-salesman
  instance live. Each iteration a colony builds tours by pheromone-weighted
  probabilistic choice (`p ∝ τ^α·η^β`); pheromone evaporates and is
  re-deposited along good tours. Trail strength is drawn as line brightness,
  the best-so-far tour is overlaid, and it reseeds with new cities once it
  converges.
- **`snake_ai`** — Snake playing itself, competently. BFS shortest path to
  the food, but only taken when a tail-reachability simulation says the move
  is survivable; otherwise it chases its tail. Reliably fills most of the
  board, speeding up as it grows.
- **`turing_machine`** — Busy-beaver Turing machines running on a scrolling
  tape. Ships BB-2/3/4 (halting at their known step and one-count records)
  plus a non-halting "Christmas tree". The head stays centered, the active
  transition-table row is highlighted, and it flashes `HALTED` with the final
  counts before loading the next machine.
- **`space_filling`** — Hilbert and dragon curves drawn stroke by stroke at
  increasing order/iteration, colored as a rainbow gradient along traversal
  order so you see the curve's ordering, not just its shape.

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
- **`metaballs`** — lava-lamp blobs drifting on smooth sinusoidal paths. A
  vectorized scalar field is thresholded into interior / contour-edge / glow
  zones (marching-squares look) with a palette that slowly hue-shifts through
  the spectrum; blobs occasionally shrink away and respawn.
- **`spirograph`** — hypotrochoid / epitrochoid curves traced by a glowing
  pen with an age-faded trail. Integer gear ratios guarantee each curve
  closes; it holds the finished figure, clears, and picks new `R, r, d`.
- **`raymarch_sdf`** — donut-style ASCII raymarcher. Signed-distance sphere,
  torus, rounded box and octahedron are smooth-min blended and morph into one
  another, rotating on two axes, Lambertian-shaded via central-difference
  normals through a ` .,:;=+*#%@` luminance ramp. Fully NumPy-vectorized (all
  pixels marched at once).
- **`terrain_flyover`** — voxel-space (Comanche-style) flight over endless
  procedural value-noise terrain. A per-column y-buffer gives correct
  occlusion; height/distance shading runs water → lowland → hills → rock →
  snow, and the camera banks and bobs as it flies. Vectorized per z-slice.

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

**Cellular automata & complexity**

- **`falling_sand`** — powder-game sandbox. Sand, water, stone and fire
  interact cell-by-cell (sand piles and slides, water spreads, fire
  flickers); drifting emitters near the top cycle which material they spawn,
  and the grid dissolves and restarts once it fills. Vectorized falls with
  numpy.
- **`sandpile`** — the Abelian sandpile. Grains dropped at the center; any
  cell with ≥4 grains topples to its four neighbors (vectorized), producing
  self-similar fractal avalanche patterns. Toppling cells flash as the
  cascade propagates.
- **`langtons_ant`** — multi-ant Langton's Ant with generalized turn rules
  (classic `LR`, longer strings like `LLRR`, or a random rule per run). Ants
  leave colored cell-state trails and self-organize into "highways".
- **`cyclic_ca`** — the cyclic (rock-paper-scissors) cellular automaton. A
  cell advances to the next state when enough neighbors already hold it,
  turning random noise into droplets and then rotating spirals across a
  color-wheel palette. Reseeds when it reaches a fixed point.
- **`wireworld`** — the Wireworld CA running hand-built circuits (a pair of
  clock loops feeding diodes, an electron raceway, a diode OR-merge).
  Electron heads/tails chase along conductor wires; circuits cycle every few
  seconds.
- **`percolation`** — site percolation with the occupation probability `p`
  sweeping up through the critical threshold `p_c ≈ 0.5927`. Clusters are
  labeled with `scipy.ndimage.label`; the cluster connected to the top is
  highlighted, and it flashes when one spans top-to-bottom (percolates), then
  resets with fresh random values.
- **`slime_mold`** — a Physarum simulation. Thousands of agents (numpy
  arrays) sense a pheromone trail map at three points, turn toward the
  strongest, move and deposit; the map is diffused and decayed each frame,
  self-organizing into branching vein networks. Fully vectorized.

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
- **`bifurcation`** — the logistic-map bifurcation diagram, drawn live. A
  scan line sweeps `r` left to right, histogramming the map's attractor into
  each column (period-doubling cascade into chaos), then zooms into windows
  like the period-3 island and redraws at the new scale.
- **`chaos_game`** — iterated-function-system fractals condensing out of
  random points: Sierpinski triangle, a pentagon flake, the Barnsley fern,
  and the Heighway dragon, each cycling in after a few seconds.
- **`strange_attractors`** — a gallery of 2D map attractors (de Jong,
  Clifford, Hopalong) rendered as a slowly-decaying density field with the
  parameters drifting so the shape morphs organically, auto-fitting the view.
- **`chladni`** — Chladni plate resonance figures. Brightness collects along
  the nodal lines of a vibrating square plate for mode pair `(m, n)`, morphing
  continuously between random mode pairs.
- **`galton_board`** — a bean machine. Balls bounce left/right through a peg
  pyramid into histogram bins, building a bell curve; once enough have landed
  it overlays the expected normal distribution.

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
- **`stock_crypto_ticker`** — a scrolling ticker tape across the top, a grid
  of per-symbol panels (price, session change ▲/▼, and a block-character
  sparkline), and an aggregate **portfolio line chart** across the bottom
  tracking the total value of an equal-weight synthetic portfolio over time
  (with its overall gain/loss). Green for up, red for down. Defaults to
  `simulate=true` —
  prices follow a geometric-random-walk so it runs offline. With
  `simulate=false` it fetches live prices in a background thread (crypto from
  CoinGecko, stocks from Yahoo Finance — both key-free) and falls back to the
  simulated walk for any asset class whose fetch fails; `refresh_interval`
  controls how often it refetches. Pass `symbols` (comma-separated) to limit
  the universe. Every successful live pull is cached to
  `data/ticker_cache.json` (git-ignored); the next run **seeds from that cache**
  so a rate-limited start opens on the most recent real prices rather than the
  hardcoded seeds. The cache is **cumulative** — each symbol's newest fetched
  price is merged in and stale ones are kept, so prices fill in across refreshes
  and runs even when an individual request is throttled. Stocks are fetched
  batch-first, then gently per-symbol (never a parallel burst, which is what
  trips rate limiting). The bottom label shows the data source — `[LIVE]`,
  `[CACHED 5m ago]`, or `[SIMULATED]`.

### Network & security (aesthetic)

Hacker-movie-style visualizers. Several can read **real** data from the local
machine — your own open connections, the LAN's ARP table, nearby Wi-Fi /
Bluetooth — but they never touch anything remote: the one real scanner
(`port_scanner`) is self-scoped to localhost and your own gateway, and the
rest are read-only observers or pure animation. Modules that read real data
take a **`simulate`** flag; set `"simulate": true` to force the animated
fake-data mode instead (the right choice on a headless box, when the
underlying CLI tools aren't installed, or when you just want the look without
touching the system). See the platform notes below for which CLI tools each
one uses on Linux vs. macOS.

- **`connections`** — arc diagram of your host's active network connections
  (read via `lsof` / `netstat`). Remote endpoints sit around a ring with arcs
  whose brightness fades as connections go idle. Honors `simulate`.
- **`packet_sniffer`** — `tcpdump`-style scrolling packet log. Observes your
  real local connection endpoints and animates plausible packet
  timing/flags/hexdumps around them — it does **not** capture payloads.
  Honors `simulate`.
- **`netmap`** — LAN host map built from the ARP table (`arp` / `ip neigh`).
  Discovered hosts arrange around the router with MAC/vendor guesses. Honors
  `simulate`.
- **`port_scanner`** — a **real** TCP-connect port scan, deliberately
  restricted to `127.0.0.1` and the detected LAN gateway (any public target
  falls back to localhost). Ports are colored open / closed / filtered as it
  sweeps. `target` must be localhost or a private-range address.
- **`nmap_replay`** — a simulated `nmap` run: hosts come up, ports resolve to
  open/filtered/closed, and service/version lines plus mock findings scroll
  by. Pure animation — no network access.
- **`wifi_scan`** — nearby Wi-Fi access points as a signal-strength view.
  Real scan via `nmcli` (Linux) or `system_profiler` (macOS) where available,
  otherwise simulated SSIDs; RSSI bars colored by strength. Honors `simulate`.
- **`bluetooth_scan`** — nearby Bluetooth devices on a radar-style sweep,
  distance mapped from RSSI. Real via `bluetoothctl` (Linux) or
  `system_profiler` (macOS) where available, else simulated. Honors
  `simulate`.
- **`decryption`** — a fake "brute-forcing the key" animation: a hex key
  locks in digit by digit with status chatter. Pure eye candy.
- **`matrix_breach`** — a multi-phase hacker montage (matrix rain → node scan
  → exploit chatter → privilege escalation → covering tracks). Pure
  animation.
- **`worldmap_attack`** — an ASCII world map with attack arcs launching
  between geographic points, in the style of a live "cyber threat map". Pure
  animation.

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
| `default.json` | Master config — all 80 modules enabled |
| `new.json` | The 20 newest modules (cellular automata, fractals, 3D) |
| `orph.json` | Network / security-themed modules |
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

### Config web UI

`config_ui/` is a stdlib-only web editor for the configs — no new
dependencies, works offline:

```bash
python config_ui/server.py            # http://<host>:8765
python config_ui/server.py --port 9000 --bind 127.0.0.1
```

It lists every config in `data/configs/`, renders each module as a card
(enable toggle, weight, typed param inputs), offers each module's `main()`
kwarg defaults as one-click addable params (discovered via `ast`, nothing is
imported), and has a raw-JSON mode for anything the form can't express.

**save** writes the JSON back; **save as…** copies to a new config; **new…**
creates a blank config; **set as boot config** makes the current config the
one `start_vis.sh` launches at boot without touching the running display;
**restore defaults** strips every module's param overrides so they run on
their `main()` defaults (kept only when you save); **save +
apply to display** additionally writes the chosen config's name to
`data/active_config` (git-ignored) and restarts the tmux session `vis` with
it. `start_vis.sh` — the boot/launcher script — reads `data/active_config`
too, so the applied config also becomes the boot config. On a machine that
isn't running the visualizer in tmux, apply degrades to just setting the
boot config.

There is no authentication: it binds `0.0.0.0` by default so you can
configure a display box from a phone on the same network. Bind `127.0.0.1`
if the machine sits on a network you don't trust.

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
│   └── …                            # 80 visualization modules
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
