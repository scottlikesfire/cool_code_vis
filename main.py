import json
import os
import random
import sys

from modules.bouncing_balls import main as bouncing_balls
from modules.bouncing_mesh import main as bouncing_mesh
from modules.cellular_automaton import main as cellular_automaton
from modules.clock import main as clock
from modules.directory_structure_visualizer import main as directory_structure_visualizer
from modules.fire import main as fire
from modules.fireworks import main as fireworks
from modules.grapher import main as grapher
from modules.julia_set import main as julia_set
from modules.knights_tour import main as knights_tour
from modules.letter_frequency import main as letter_frequency
from modules.mandelbrot import main as mandelbrot
from modules.matrix_rain import main as matrix_rain
from modules.maze_generator import main as maze_generator
from modules.metaprogramming_imports import main as metaprogramming_imports
from modules.n_queens import main as n_queens
from modules.pathfinding import main as pathfinding
from modules.plasma import main as plasma
from modules.prime_sieve import main as prime_sieve
from modules.progress_bars import main as progress_bars
from modules.rainbow_code import main as rainbow_code
from modules.rss_feed_reader import main as rss_feed_reader
from modules.shaded_mesh import main as shaded_mesh
from modules.sorting_visualizer import main as sorting_visualizer
from modules.starfield import main as starfield
from modules.sudoku import main as sudoku
from modules.tower_of_hanoi import main as tower_of_hanoi
from modules.tunnel import main as tunnel
from modules.unredact import main as unredact
from modules.wave import main as wave

MODULES = {
    "bouncing_balls": bouncing_balls,
    "bouncing_mesh": bouncing_mesh,
    "cellular_automaton": cellular_automaton,
    "clock": clock,
    "directory_structure_visualizer": directory_structure_visualizer,
    "fire": fire,
    "fireworks": fireworks,
    "grapher": grapher,
    "julia_set": julia_set,
    "knights_tour": knights_tour,
    "letter_frequency": letter_frequency,
    "mandelbrot": mandelbrot,
    "matrix_rain": matrix_rain,
    "maze_generator": maze_generator,
    "metaprogramming_imports": metaprogramming_imports,
    "n_queens": n_queens,
    "pathfinding": pathfinding,
    "plasma": plasma,
    "prime_sieve": prime_sieve,
    "progress_bars": progress_bars,
    "rainbow_code": rainbow_code,
    "rss_feed_reader": rss_feed_reader,
    "shaded_mesh": shaded_mesh,
    "sorting_visualizer": sorting_visualizer,
    "starfield": starfield,
    "sudoku": sudoku,
    "tower_of_hanoi": tower_of_hanoi,
    "tunnel": tunnel,
    "unredact": unredact,
    "wave": wave,
}

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "data", "configs")


def print_usage():
    print("Usage: python main.py <config_file>")
    print()
    print("  config_file  Name of a JSON file in data/configs/ (e.g. test1.json)")


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
    enabled_modules = []
    for module_name, params in config.items():
        if module_name == "iterations":
            continue
        if module_name not in MODULES:
            print(f"Warning: unknown module '{module_name}', skipping.")
            continue
        if not params.get("enabled", False):
            continue
        module_params = {k: v for k, v in params.items() if k != "enabled"}
        enabled_modules.append((module_name, module_params))

    if not enabled_modules:
        print("No enabled modules found in config.")
        sys.exit(1)

    count = 0
    while True:
        clear_terminal()
        module_name, module_params = random.choice(enabled_modules)
        MODULES[module_name](**module_params)
        clear_terminal()
        count += 1
        if iterations > 0 and count >= iterations:
            break
