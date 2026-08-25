import json
import os
import random
import sys
import time

from modules.ant_colony import main as ant_colony
from modules.bifurcation import main as bifurcation
from modules.bluetooth_scan import main as bluetooth_scan
from modules.boids import main as boids
from modules.bouncing_balls import main as bouncing_balls
from modules.bouncing_mesh import main as bouncing_mesh
from modules.cellular_automaton import main as cellular_automaton
from modules.chaos_game import main as chaos_game
from modules.chladni import main as chladni
from modules.clock import main as clock
from modules.connections import main as connections
from modules.cyclic_ca import main as cyclic_ca
from modules.directory_structure_visualizer import main as directory_structure_visualizer
from modules.dla import main as dla
from modules.dna_helix import main as dna_helix
from modules.double_pendulum import main as double_pendulum
from modules.decryption import main as decryption
from modules.falling_sand import main as falling_sand
from modules.fire import main as fire
from modules.fireworks import main as fireworks
from modules.fourier_epicycles import main as fourier_epicycles
from modules.galton_board import main as galton_board
from modules.grapher import main as grapher
from modules.gray_scott import main as gray_scott
from modules.hypercube import main as hypercube
from modules.ising_model import main as ising_model
from modules.julia_set import main as julia_set
from modules.knights_tour import main as knights_tour
from modules.langtons_ant import main as langtons_ant
from modules.letter_frequency import main as letter_frequency
from modules.lorenz_attractor import main as lorenz_attractor
from modules.lsystem import main as lsystem
from modules.mandelbrot import main as mandelbrot
from modules.matrix_breach import main as matrix_breach
from modules.matrix_rain import main as matrix_rain
from modules.maze_generator import main as maze_generator
from modules.metaballs import main as metaballs
from modules.metaprogramming_imports import main as metaprogramming_imports
from modules.n_body import main as n_body
from modules.n_queens import main as n_queens
from modules.netmap import main as netmap
from modules.nmap_replay import main as nmap_replay
from modules.packet_sniffer import main as packet_sniffer
from modules.pathfinding import main as pathfinding
from modules.pendulum_wave import main as pendulum_wave
from modules.percolation import main as percolation
from modules.predator_prey import main as predator_prey
from modules.plasma import main as plasma
from modules.port_scanner import main as port_scanner
from modules.prime_sieve import main as prime_sieve
from modules.progress_bars import main as progress_bars
from modules.rainbow_code import main as rainbow_code
from modules.raymarch_sdf import main as raymarch_sdf
from modules.rss_feed_reader import main as rss_feed_reader
from modules.sandpile import main as sandpile
from modules.shaded_mesh import main as shaded_mesh
from modules.sir_epidemic import main as sir_epidemic
from modules.slime_mold import main as slime_mold
from modules.snake_ai import main as snake_ai
from modules.solar_orrery import main as solar_orrery
from modules.sorting_visualizer import main as sorting_visualizer
from modules.space_filling import main as space_filling
from modules.spirograph import main as spirograph
from modules.starfield import main as starfield
from modules.stock_crypto_ticker import main as stock_crypto_ticker
from modules.strange_attractors import main as strange_attractors
from modules.sudoku import main as sudoku
from modules.terrain_flyover import main as terrain_flyover
from modules.tower_of_hanoi import main as tower_of_hanoi
from modules.tunnel import main as tunnel
from modules.turing_machine import main as turing_machine
from modules.ulam_spiral import main as ulam_spiral
from modules.unredact import main as unredact
from modules.wave import main as wave
from modules.wave_on_string import main as wave_on_string
from modules.wifi_scan import main as wifi_scan
from modules.window_spawner import main as window_spawner
from modules.wireworld import main as wireworld
from modules.wolfram_rule import main as wolfram_rule
from modules.worldmap_attack import main as worldmap_attack

MODULES = {
    "ant_colony": ant_colony,
    "bifurcation": bifurcation,
    "bluetooth_scan": bluetooth_scan,
    "boids": boids,
    "bouncing_balls": bouncing_balls,
    "bouncing_mesh": bouncing_mesh,
    "cellular_automaton": cellular_automaton,
    "chaos_game": chaos_game,
    "chladni": chladni,
    "clock": clock,
    "connections": connections,
    "cyclic_ca": cyclic_ca,
    "directory_structure_visualizer": directory_structure_visualizer,
    "dla": dla,
    "dna_helix": dna_helix,
    "double_pendulum": double_pendulum,
    "decryption": decryption,
    "falling_sand": falling_sand,
    "fire": fire,
    "fireworks": fireworks,
    "fourier_epicycles": fourier_epicycles,
    "galton_board": galton_board,
    "grapher": grapher,
    "gray_scott": gray_scott,
    "hypercube": hypercube,
    "ising_model": ising_model,
    "julia_set": julia_set,
    "knights_tour": knights_tour,
    "langtons_ant": langtons_ant,
    "letter_frequency": letter_frequency,
    "lorenz_attractor": lorenz_attractor,
    "lsystem": lsystem,
    "mandelbrot": mandelbrot,
    "matrix_breach": matrix_breach,
    "matrix_rain": matrix_rain,
    "maze_generator": maze_generator,
    "metaballs": metaballs,
    "metaprogramming_imports": metaprogramming_imports,
    "n_body": n_body,
    "n_queens": n_queens,
    "netmap": netmap,
    "nmap_replay": nmap_replay,
    "packet_sniffer": packet_sniffer,
    "pathfinding": pathfinding,
    "pendulum_wave": pendulum_wave,
    "percolation": percolation,
    "plasma": plasma,
    "port_scanner": port_scanner,
    "predator_prey": predator_prey,
    "prime_sieve": prime_sieve,
    "progress_bars": progress_bars,
    "rainbow_code": rainbow_code,
    "raymarch_sdf": raymarch_sdf,
    "rss_feed_reader": rss_feed_reader,
    "sandpile": sandpile,
    "shaded_mesh": shaded_mesh,
    "sir_epidemic": sir_epidemic,
    "slime_mold": slime_mold,
    "snake_ai": snake_ai,
    "solar_orrery": solar_orrery,
    "sorting_visualizer": sorting_visualizer,
    "space_filling": space_filling,
    "spirograph": spirograph,
    "starfield": starfield,
    "stock_crypto_ticker": stock_crypto_ticker,
    "strange_attractors": strange_attractors,
    "sudoku": sudoku,
    "terrain_flyover": terrain_flyover,
    "tower_of_hanoi": tower_of_hanoi,
    "tunnel": tunnel,
    "turing_machine": turing_machine,
    "ulam_spiral": ulam_spiral,
    "unredact": unredact,
    "wave": wave,
    "wave_on_string": wave_on_string,
    "wifi_scan": wifi_scan,
    "window_spawner": window_spawner,
    "wireworld": wireworld,
    "wolfram_rule": wolfram_rule,
    "worldmap_attack": worldmap_attack,
}

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "data", "configs")
DEFAULT_HISTORY_FILE = os.path.join(os.path.dirname(__file__), "data", "run_history.json")

# Per-module config keys consumed by the scheduler, never passed to main().
RESERVED_KEYS = {"enabled", "weight", "after"}
# Top-level config keys that aren't module names.
TOP_LEVEL_KEYS = {"iterations", "scheduler"}
HISTORY_LIMIT = 500


def load_history(path):
    try:
        with open(path) as f:
            history = json.load(f)
        history.setdefault("total_runs", 0)
        history.setdefault("counts", {})
        history.setdefault("recent", [])
        return history
    except (OSError, ValueError):
        return {"total_runs": 0, "counts": {}, "recent": []}


def record_run(history, path, module_name, config_name):
    history["total_runs"] += 1
    history["counts"][module_name] = history["counts"].get(module_name, 0) + 1
    history["recent"].append({
        "module": module_name,
        "ts": time.time(),
        "config": config_name,
    })
    del history["recent"][:-HISTORY_LIMIT]
    try:
        with open(path, "w") as f:
            json.dump(history, f, indent=2)
    except OSError:
        pass


def pick_module(enabled_modules, session_recent, scheduler_cfg):
    """Weighted pick from (name, params, weight, after) entries.

    - weight: a module's base selection weight (config key "weight").
    - after: {predecessor: multiplier} boosts applied when the previous run
      was that predecessor (config key "after").
    - no_repeat_window: the last N modules get weight 0 (if the pool is big
      enough to allow it).
    - recency_boost: modules that haven't run in a while (or ever) this
      session get proportionally more weight.
    """
    no_repeat = int(scheduler_cfg.get("no_repeat_window", 1))
    recency_boost = float(scheduler_cfg.get("recency_boost", 0.0))
    last = session_recent[-1] if session_recent else None
    blocked = set(session_recent[-no_repeat:]) if no_repeat > 0 else set()
    if len(blocked) >= len(enabled_modules):
        blocked = set()

    names = []
    weights = []
    for name, _params, weight, after in enabled_modules:
        w = weight
        if last is not None and last in after:
            w *= after[last]
        if recency_boost > 0:
            if name in session_recent:
                last_idx = max(i for i, m in enumerate(session_recent) if m == name)
                staleness = len(session_recent) - 1 - last_idx
            else:
                staleness = len(session_recent) + len(enabled_modules)
            w *= 1.0 + recency_boost * min(staleness, 3 * len(enabled_modules))
        if name in blocked:
            w = 0.0
        names.append(name)
        weights.append(max(0.0, w))

    if not any(w > 0 for w in weights):
        weights = [1.0] * len(names)
    return random.choices(names, weights=weights, k=1)[0]


def print_usage():
    print("Usage: python main.py <config_file>")
    print()
    print("  config_file  Name of a JSON file in data/configs/ (e.g. default.json)")


def clear_terminal():
    """Wipe the terminal so leftover content from one module doesn't bleed
    into the next."""
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print_usage()
        sys.exit(0 if sys.argv[1:] in (["--help"], ["-h"]) else 1)

    config_path = os.path.join(CONFIG_DIR, sys.argv[1])
    if not os.path.isfile(config_path):
        print(f"Error: config file not found: {config_path}")
        sys.exit(1)

    with open(config_path) as f:
        config = json.load(f)

    iterations = config.get("iterations", 0)
    scheduler_cfg = config.get("scheduler", {})
    enabled_modules = []
    for module_name, params in config.items():
        if module_name in TOP_LEVEL_KEYS:
            continue
        if module_name not in MODULES:
            print(f"Warning: unknown module '{module_name}', skipping.")
            continue
        if not params.get("enabled", False):
            continue
        weight = float(params.get("weight", 1.0))
        after = {k: float(v) for k, v in params.get("after", {}).items()}
        for predecessor in after:
            if predecessor not in MODULES:
                print(f"Warning: '{module_name}' has an 'after' entry for "
                      f"unknown module '{predecessor}'.")
        module_params = {k: v for k, v in params.items()
                         if k not in RESERVED_KEYS}
        enabled_modules.append((module_name, module_params, weight, after))

    if not enabled_modules:
        print("No enabled modules found in config.")
        sys.exit(1)

    track_history = scheduler_cfg.get("track_history", True)
    history_path = scheduler_cfg.get("history_file", DEFAULT_HISTORY_FILE)
    if not os.path.isabs(history_path):
        history_path = os.path.join(os.path.dirname(__file__), history_path)
    history = load_history(history_path)

    params_by_name = {name: params for name, params, _w, _a in enabled_modules}
    session_recent = []
    count = 0
    while True:
        clear_terminal()
        module_name = pick_module(enabled_modules, session_recent, scheduler_cfg)
        MODULES[module_name](**params_by_name[module_name])
        clear_terminal()
        session_recent.append(module_name)
        if track_history:
            record_run(history, history_path, module_name, sys.argv[1])
        count += 1
        if iterations > 0 and count >= iterations:
            break
