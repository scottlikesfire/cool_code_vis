"""Spawns new terminal windows, each running a random subset of the other
modules via `python main.py <generated config>`, shows a live status panel
while they run, and closes the windows when they complete.

Backends, tried in order:
  - tmux panes, when running inside tmux (works on a bare TTY / over ssh)
  - macOS Terminal.app via osascript
  - a Linux GUI terminal (gnome-terminal / konsole / xfce4-terminal / xterm)

Child completion is detected with sentinel files: each child command removes
its sentinel when main.py exits, whatever the exit code. tmux panes and Linux
terminals close themselves when their command exits; Terminal.app windows are
closed explicitly once their sentinel disappears.
"""

import curses
import glob
import importlib
import inspect
import json
import os
import random
import shlex
import shutil
import subprocess
import sys
import tempfile
import time


COLOR_TITLE = 1
COLOR_RUNNING = 2
COLOR_DONE = 3
COLOR_LABEL = 4
COLOR_WARN = 5

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(REPO_ROOT, "data", "configs")
SPAWN_PREFIX = "_spawn_"
STALE_CONFIG_AGE = 3600

# Spawned windows are intentionally small, and scattered at large random
# offsets so they overlap but each one stays visible — making it obvious that
# several independent things are running at once.
WIN_COLS = 72
WIN_ROWS = 20
BASE_X = 60          # top-left of the scatter region (pixels)
BASE_Y = 60
SPREAD_X = 560       # each window is placed at a random offset within this
SPREAD_Y = 340       # box, so positions are large and random but on-screen


def _random_position():
    """A large random pixel offset for a spawned window."""
    return (BASE_X + random.randint(0, SPREAD_X),
            BASE_Y + random.randint(0, SPREAD_Y))

DEFAULT_POOL = [
    "metaballs", "cyclic_ca", "chaos_game", "strange_attractors",
    "spirograph", "chladni", "terrain_flyover", "raymarch_sdf",
    "slime_mold", "sandpile", "fire", "starfield", "matrix_rain",
    "tunnel", "plasma",
]

# Each builder takes (cmd, geom) where geom is an X11 geometry string like
# "72x20+128+124" (COLSxROWS+X+Y). Terminals that don't support geometry
# just ignore it.
LINUX_TERMINALS = [
    ("gnome-terminal", lambda cmd, geom: ["gnome-terminal",
                                          "--geometry=" + geom,
                                          "--", "bash", "-c", cmd]),
    ("xfce4-terminal", lambda cmd, geom: ["xfce4-terminal",
                                          "--geometry=" + geom,
                                          "-e", "bash -c " + shlex.quote(cmd)]),
    ("xterm", lambda cmd, geom: ["xterm", "-geometry", geom,
                                 "-e", "bash", "-c", cmd]),
    ("konsole", lambda cmd, geom: ["konsole", "-e", "bash", "-c", cmd]),
]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_TITLE, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_RUNNING, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_DONE, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_WARN, curses.COLOR_RED, -1)


def detect_backend():
    """Return 'tmux', 'terminal_app', a (name, builder) Linux terminal
    entry, or None."""
    if os.environ.get("TMUX") and shutil.which("tmux"):
        return "tmux"
    if sys.platform == "darwin" and shutil.which("osascript"):
        return "terminal_app"
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        preferred = os.environ.get("TERMINAL")
        for name, builder in LINUX_TERMINALS:
            if preferred and os.path.basename(preferred) != name:
                continue
            if shutil.which(name):
                return (name, builder)
        for name, builder in LINUX_TERMINALS:
            if shutil.which(name):
                return (name, builder)
    return None


def usable_pool(pool):
    """Keep only real modules whose main() accepts a duration kwarg."""
    valid = []
    for name in pool:
        if name == "window_spawner" or name in valid:
            continue
        try:
            mod = importlib.import_module(f"modules.{name}")
            if "duration" in inspect.signature(mod.main).parameters:
                valid.append(name)
        except (ImportError, AttributeError, ValueError):
            continue
    return valid


def cleanup_stale_configs():
    now = time.time()
    for path in glob.glob(os.path.join(CONFIG_DIR, SPAWN_PREFIX + "*.json")):
        try:
            if now - os.path.getmtime(path) > STALE_CONFIG_AGE:
                os.remove(path)
        except OSError:
            pass


def build_child_config(mods, runs_per_window, child_duration):
    config = {"iterations": runs_per_window,
              "scheduler": {"track_history": False}}
    for name in mods:
        config[name] = {"enabled": True, "duration": child_duration}
    return config


def child_command(config_name, sentinel):
    return (f"cd {shlex.quote(REPO_ROOT)}; "
            f"{shlex.quote(sys.executable)} main.py {shlex.quote(config_name)}; "
            f"rm -f {shlex.quote(sentinel)}")


def applescript_quote(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def spawn_window(backend, cmd, idx=0):
    """Launch cmd in a new small window/pane at a large random offset so the
    spawns overlap but stay individually visible. Returns an opaque handle for
    later cleanup (or None)."""
    left, top = _random_position()
    geom = "%dx%d+%d+%d" % (WIN_COLS, WIN_ROWS, left, top)
    if backend == "tmux":
        # Panes live inside the current terminal; a tiled layout already shows
        # them side by side, which is the tmux equivalent of cascaded windows.
        pane = subprocess.run(
            ["tmux", "split-window", "-d", "-P", "-F", "#{pane_id}", cmd],
            capture_output=True, text=True, timeout=10).stdout.strip()
        subprocess.run(["tmux", "select-layout", "tiled"],
                       capture_output=True, timeout=10)
        return ("tmux", pane) if pane else None
    if backend == "terminal_app":
        # Size (in character cells) and position (in pixels) are set after the
        # window opens so each spawn is small and cascaded down-right.
        script = ('tell application "Terminal"\n'
                  f'  do script "{applescript_quote(cmd)}"\n'
                  "  set theWin to front window\n"
                  f"  set number of columns of theWin to {WIN_COLS}\n"
                  f"  set number of rows of theWin to {WIN_ROWS}\n"
                  f"  set position of theWin to {{{left}, {top}}}\n"
                  "  return id of theWin\n"
                  "end tell")
        out = subprocess.run(["osascript", "-e", script],
                             capture_output=True, text=True, timeout=15)
        win_id = out.stdout.strip()
        return ("terminal_app", win_id) if win_id else None
    name, builder = backend
    proc = subprocess.Popen(builder(cmd, geom), stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    return ("proc", proc)


def close_window(handle):
    """Close a still-open window. tmux panes and Linux terminals normally
    close themselves when the child exits; this is for Terminal.app and
    for aborting early."""
    if handle is None:
        return
    kind, ref = handle
    try:
        if kind == "terminal_app":
            script = ('tell application "Terminal" to close '
                      f"(every window whose id is {ref}) saving no")
            subprocess.run(["osascript", "-e", script],
                           capture_output=True, timeout=10)
        elif kind == "tmux":
            subprocess.run(["tmux", "kill-pane", "-t", ref],
                           capture_output=True, timeout=10)
        elif kind == "proc":
            if ref.poll() is None:
                ref.terminate()
    except (OSError, subprocess.SubprocessError):
        pass


def draw_status(stdscr, windows, elapsed, max_wait, backend_name, message):
    stdscr.erase()
    max_y, max_x = stdscr.getmaxyx()

    def put(y, x, text, attr=0):
        if 0 <= y < max_y:
            try:
                stdscr.addstr(y, x, text[:max(0, max_x - x - 1)], attr)
            except curses.error:
                pass

    put(1, 2, "WINDOW SPAWNER", curses.color_pair(COLOR_TITLE) | curses.A_BOLD)
    put(2, 2, f"backend: {backend_name}   elapsed: {elapsed:5.1f}s / "
              f"{max_wait:.0f}s max", curses.color_pair(COLOR_LABEL))
    row = 4
    for w in windows:
        if w["failed"]:
            state, attr = "FAILED ", curses.color_pair(COLOR_WARN) | curses.A_BOLD
        elif w["done"]:
            state, attr = "DONE   ", curses.color_pair(COLOR_DONE) | curses.A_BOLD
        else:
            spinner = "|/-\\"[int(elapsed * 4) % 4]
            state = f"RUN {spinner}  "
            attr = curses.color_pair(COLOR_RUNNING) | curses.A_BOLD
        put(row, 4, state, attr)
        put(row, 12, f"window {w['idx'] + 1}: " + ", ".join(w["mods"]))
        row += 2
    if message:
        put(row, 4, message, curses.color_pair(COLOR_WARN) | curses.A_BOLD)
    put(max_y - 1, 2, "Window Spawner  q=abort",
        curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
    stdscr.refresh()


def run(stdscr, duration, frame_delay, num_windows, runs_per_window,
        child_duration, subset_size, pool, max_wait):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    backend = detect_backend()
    if backend is None:
        deadline = time.monotonic() + min(4.0, duration)
        while time.monotonic() < deadline:
            draw_status(stdscr, [], 0.0, 0.0, "none",
                        "No terminal backend found (need tmux, Terminal.app,"
                        " or a GUI terminal) — skipping.")
            if stdscr.getch() in (ord("q"), ord("Q"), 27):
                break
        return
    backend_name = backend if isinstance(backend, str) else backend[0]

    valid = usable_pool(pool)
    if len(valid) < 1:
        return
    cleanup_stale_configs()

    windows = []
    tag = f"{os.getpid()}_{int(time.time())}"
    for i in range(num_windows):
        mods = random.sample(valid, min(subset_size, len(valid)))
        config_name = f"{SPAWN_PREFIX}{tag}_{i}.json"
        config_path = os.path.join(CONFIG_DIR, config_name)
        with open(config_path, "w") as f:
            json.dump(build_child_config(mods, runs_per_window,
                                         child_duration), f)
        sentinel = os.path.join(tempfile.gettempdir(),
                                f"ccv_spawn_{tag}_{i}.lock")
        with open(sentinel, "w") as f:
            f.write(config_name)
        try:
            handle = spawn_window(backend,
                                  child_command(config_name, sentinel), i)
        except (OSError, subprocess.SubprocessError):
            handle = None
        if handle is None:
            try:
                os.remove(sentinel)
            except OSError:
                pass
        windows.append({"idx": i, "mods": mods, "config": config_path,
                        "sentinel": sentinel, "handle": handle,
                        "failed": handle is None, "done": handle is None})

    start = time.monotonic()
    aborted = False
    while True:
        elapsed = time.monotonic() - start
        for w in windows:
            if not w["done"] and not os.path.exists(w["sentinel"]):
                w["done"] = True
                close_window(w["handle"])
                w["handle"] = None
        all_done = all(w["done"] for w in windows)
        draw_status(stdscr, windows, elapsed, max_wait, backend_name,
                    "all windows completed" if all_done else "")
        if all_done:
            time.sleep(1.5)
            break
        if elapsed > max_wait:
            break
        if stdscr.getch() in (ord("q"), ord("Q"), 27):
            aborted = True
            break

    for w in windows:
        if not w["done"]:
            close_window(w["handle"])
            try:
                os.remove(w["sentinel"])
            except OSError:
                pass
        # On abort a child may not have read its config yet; leave it for
        # cleanup_stale_configs() next time.
        if not aborted:
            try:
                os.remove(w["config"])
            except OSError:
                pass


def main(duration=90, frame_delay=0.25, num_windows=2, runs_per_window=2,
         child_duration=15, subset_size=3, pool=None, max_wait=0):
    duration = float(duration)
    frame_delay = float(frame_delay)
    num_windows = max(1, int(num_windows))
    runs_per_window = max(1, int(runs_per_window))
    child_duration = float(child_duration)
    subset_size = max(1, int(subset_size))
    if pool is None:
        pool = DEFAULT_POOL
    elif isinstance(pool, str):
        pool = [p.strip() for p in pool.split(",") if p.strip()]
    max_wait = float(max_wait)
    if max_wait <= 0:
        max_wait = runs_per_window * (child_duration + 5) + 30
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, num_windows, runs_per_window,
        child_duration, subset_size, list(pool), max_wait))


if __name__ == "__main__":
    main()
