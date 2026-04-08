import json
import os
import random
import sys

from modules.directory_structure_visualizer import main as directory_structure_visualizer
from modules.grapher import main as grapher
from modules.letter_frequency import main as letter_frequency
from modules.metaprogramming_imports import main as metaprogramming_imports
from modules.matrix_rain import main as matrix_rain
from modules.plasma import main as plasma
from modules.progress_bars import main as progress_bars
from modules.rss_feed_reader import main as rss_feed_reader
from modules.unredact import main as unredact

MODULES = {
    "directory_structure_visualizer": directory_structure_visualizer,
    "grapher": grapher,
    "letter_frequency": letter_frequency,
    "matrix_rain": matrix_rain,
    "metaprogramming_imports": metaprogramming_imports,
    "plasma": plasma,
    "progress_bars": progress_bars,
    "rss_feed_reader": rss_feed_reader,
    "unredact": unredact,
}

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "data", "configs")


def print_usage():
    print("Usage: python main.py <config_file>")
    print()
    print("  config_file  Name of a JSON file in data/configs/ (e.g. test1.json)")


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
        module_name, module_params = random.choice(enabled_modules)
        MODULES[module_name](**module_params)
        count += 1
        if iterations > 0 and count >= iterations:
            break
