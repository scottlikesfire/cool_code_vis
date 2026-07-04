import curses
import random
import time


# ---- color pairs ----
COLOR_RED = 1        # locked / alert
COLOR_GREEN = 2      # breached / success (bold)
COLOR_CYAN = 3       # info
COLOR_AMBER = 4      # warnings
COLOR_RAIN = 5       # dim green background rain
COLOR_LABEL = 6      # bottom label
COLOR_WHITE = 7      # bright accents


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_RED, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_GREEN, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_CYAN, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_AMBER, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_RAIN, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_WHITE, curses.COLOR_WHITE, -1)


PHASES = ["RECON", "EXPLOIT", "ACCESS", "EXFIL"]

RAIN_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789@#$%&*+=?/<>"

NODE_NAMES = ["firewall", "gateway", "db-node", "mainframe", "auth-svc"]

CVE_POOL = [
    "CVE-2024-3094", "CVE-2024-21762", "CVE-2023-4863", "CVE-2024-1086",
    "CVE-2023-38545", "CVE-2024-6387", "CVE-2022-0847", "CVE-2021-44228",
]

EXPLOIT_LINES = [
    "trying {cve} ...",
    "buffer overflow @ 0x7ffe{hex} ...",
    "injecting payload into {node} ...",
    "escalating privileges on {node} ...",
    "bypassing auth token check ...",
    "heap spray @ 0x{hex}{hex} ...",
    "ROP chain assembled, jumping ...",
]

SHELL_COMMANDS = [
    ("whoami", ["root"]),
    ("id", ["uid=0(root) gid=0(root) groups=0(root)"]),
    ("uname -a", ["Linux mainframe 6.5.0 #1 SMP x86_64 GNU/Linux"]),
    ("cat /etc/shadow", [
        "root:$6$xY9k...:19700:0:99999:7:::",
        "admin:$6$Qz2m...:19700:0:99999:7:::",
    ]),
    ("ls /opt/secrets", ["secrets.db  keys.pem  vault.bin"]),
    ("download secrets.db", ["queued secrets.db for exfiltration"]),
]

EXFIL_FILES = [
    "secrets.db", "keys.pem", "vault.bin", "users.sql",
    "creds.txt", "backup.tar.gz", "config.yaml", "shadow.bak",
]


# ---------------------------------------------------------------------------
# Pure helpers (headless-testable)
# ---------------------------------------------------------------------------

def phase_for_elapsed(elapsed, phase_time):
    """Return (phase_index, target_number, phase_local_elapsed) for a global
    elapsed time. Cycles RECON->EXPLOIT->ACCESS->EXFIL then resets to a new
    target and loops."""
    if phase_time <= 0:
        phase_time = 1.0
    total = int(elapsed // phase_time)
    idx = total % len(PHASES)
    target = total // len(PHASES) + 1
    local = elapsed - total * phase_time
    return idx, target, local


def make_nodes(rng):
    """Build the target network node-graph model. All start locked."""
    n = rng.randint(3, len(NODE_NAMES))
    names = rng.sample(NODE_NAMES, n)
    # ensure mainframe-like final target present for flavor
    nodes = []
    for i, name in enumerate(names):
        nodes.append({
            "name": name,
            "breached": False,
            "progress": 0.0,
        })
    return nodes


def crack_progress(nodes, phase_local, phase_time):
    """Advance the breach: nodes flip locked->breached one by one across the
    EXPLOIT phase based on how far through the phase we are. Returns the index
    of the node currently being cracked (or -1 if done)."""
    if not nodes:
        return -1
    if phase_time <= 0:
        phase_time = 1.0
    frac = max(0.0, min(1.0, phase_local / phase_time))
    n = len(nodes)
    # each node gets an equal slice of the phase
    per = 1.0 / n
    current = -1
    for i, node in enumerate(nodes):
        start = i * per
        end = (i + 1) * per
        if frac >= end:
            node["breached"] = True
            node["progress"] = 1.0
        elif frac >= start:
            node["breached"] = False
            node["progress"] = (frac - start) / per
            current = i
        else:
            node["breached"] = False
            node["progress"] = 0.0
    return current


def typewriter_reveal(text, elapsed, chars_per_sec):
    """Return the substring of `text` revealed so far given elapsed seconds."""
    if chars_per_sec <= 0:
        return text
    n = int(elapsed * chars_per_sec)
    if n < 0:
        n = 0
    if n > len(text):
        n = len(text)
    return text[:n]


def progress_bar(frac, width):
    """ASCII progress bar string of given inner width for frac in [0,1]."""
    if width < 1:
        width = 1
    frac = max(0.0, min(1.0, frac))
    filled = int(round(width * frac))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def rand_hex(rng, n=4):
    return "".join(rng.choice("0123456789abcdef") for _ in range(n))


def build_exploit_log(nodes, rng, count):
    """Generate a deterministic-ish list of exploit log lines for a target."""
    lines = []
    for i in range(count):
        tmpl = EXPLOIT_LINES[i % len(EXPLOIT_LINES)]
        node = rng.choice(nodes)["name"] if nodes else "host"
        lines.append(tmpl.format(
            cve=rng.choice(CVE_POOL),
            node=node,
            hex=rand_hex(rng, 4),
        ))
    return lines


# ---------------------------------------------------------------------------
# Rain (thin background atmosphere)
# ---------------------------------------------------------------------------

def step_rain(columns, max_x, max_y, density, rng):
    """Advance a thin column-drip of green glyphs. Persistent across phases."""
    for col in range(max_x):
        drop = columns.get(col)
        if drop is None or not drop["active"]:
            if rng.random() < density * 0.08:
                columns[col] = {
                    "head_y": 0,
                    "len": rng.randint(3, max(4, max_y // 3)),
                    "active": True,
                }
        else:
            drop["head_y"] += 1
            if drop["head_y"] - drop["len"] >= max_y:
                drop["active"] = False


def draw_rain(stdscr, columns, max_x, max_y, rng):
    for col, drop in columns.items():
        if not drop["active"] or col >= max_x:
            continue
        head = drop["head_y"]
        for i in range(drop["len"] + 1):
            y = head - i
            if y < 0 or y >= max_y - 1:
                continue
            ch = rng.choice(RAIN_CHARS)
            attr = curses.color_pair(COLOR_RAIN) | curses.A_DIM
            try:
                stdscr.addstr(y, col, ch, attr)
            except curses.error:
                pass


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _safe(stdscr, y, x, text, attr, max_y, max_x):
    if y < 0 or y >= max_y - 1 or x < 0 or x >= max_x:
        return
    try:
        stdscr.addstr(y, x, text[:max(0, max_x - x)], attr)
    except curses.error:
        pass


def draw_node_graph(stdscr, nodes, max_y, max_x, current, title):
    """Draw the target network as an ascii graph with node state colors."""
    top = 2
    _safe(stdscr, top, 2, title,
          curses.color_pair(COLOR_CYAN) | curses.A_BOLD, max_y, max_x)
    row = top + 2
    for i, node in enumerate(nodes):
        if node["breached"]:
            state = "[BREACHED]"
            attr = curses.color_pair(COLOR_GREEN) | curses.A_BOLD
            box = "(*)"
        elif i == current:
            state = "[CRACKING]"
            attr = curses.color_pair(COLOR_AMBER) | curses.A_BOLD
            box = "(~)"
        else:
            state = "[LOCKED]"
            attr = curses.color_pair(COLOR_RED) | curses.A_BOLD
            box = "(x)"
        connector = "  |" if i > 0 else "   "
        _safe(stdscr, row, 4, connector,
              curses.color_pair(COLOR_RAIN) | curses.A_DIM, max_y, max_x)
        line = f"{box}--[ {node['name']:<10} ] {state}"
        _safe(stdscr, row + 1, 4, line, attr, max_y, max_x)
        if not node["breached"] and i == current:
            bar = progress_bar(node["progress"], 20)
            _safe(stdscr, row + 1, 4 + len(line) + 1, bar,
                  curses.color_pair(COLOR_AMBER), max_y, max_x)
        row += 2


def draw_label(stdscr, max_y, max_x, phase_name, target):
    label = f"matrix_breach  phase: {phase_name}  target {target}"
    label += "   [q/ESC quit]"
    try:
        stdscr.addstr(max_y - 1, 2, label[:max_x - 4],
                      curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
    except curses.error:
        pass


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run(stdscr, duration, frame_delay, phase_time, rain_density):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    rng = random.Random()
    max_y, max_x = stdscr.getmaxyx()

    rain_cols = {}
    # per-target state, rebuilt when target changes
    cur_target = 0
    nodes = []
    exploit_log = []
    shell_seq = []

    start = time.monotonic()
    while True:
        now = time.monotonic()
        elapsed = now - start
        if elapsed >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        phase_idx, target, local = phase_for_elapsed(elapsed, phase_time)
        phase_name = PHASES[phase_idx]

        # (re)build per-target model on target change
        if target != cur_target or not nodes:
            cur_target = target
            nodes = make_nodes(rng)
            exploit_log = build_exploit_log(nodes, rng, 40)
            shell_seq = SHELL_COMMANDS[:]

        # advance rain
        step_rain(rain_cols, max_x, max_y, rain_density, rng)

        stdscr.erase()
        # rain is lighter during ACCESS (foreground shell), heavier in RECON
        if phase_name in ("RECON", "EXPLOIT", "EXFIL"):
            draw_rain(stdscr, rain_cols, max_x, max_y, rng)

        current = -1
        if phase_name == "EXPLOIT":
            current = crack_progress(nodes, local, phase_time)
        elif phase_name in ("ACCESS", "EXFIL"):
            for node in nodes:
                node["breached"] = True
                node["progress"] = 1.0

        if phase_name == "RECON":
            _render_recon(stdscr, nodes, local, phase_time, max_y, max_x, rng)
        elif phase_name == "EXPLOIT":
            _render_exploit(stdscr, nodes, exploit_log, local, phase_time,
                            current, max_y, max_x)
        elif phase_name == "ACCESS":
            _render_access(stdscr, shell_seq, local, max_y, max_x, target)
        elif phase_name == "EXFIL":
            _render_exfil(stdscr, local, phase_time, max_y, max_x, rng, target)

        draw_label(stdscr, max_y, max_x, phase_name, target)
        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def _render_recon(stdscr, nodes, local, phase_time, max_y, max_x, rng):
    title = "RECON // mapping target network"
    draw_node_graph(stdscr, nodes, max_y, max_x, -1, title)
    # scanning pulse probes nodes: a moving indicator
    frac = local / phase_time if phase_time > 0 else 0
    probe = int(frac * len(nodes)) % max(1, len(nodes))
    msg = f">> scanning node[{probe}] {nodes[probe]['name']} ...  ports open"
    _safe(stdscr, max_y - 4, 4, msg,
          curses.color_pair(COLOR_CYAN), max_y, max_x)
    dots = "." * (int(local * 4) % 4)
    _safe(stdscr, max_y - 3, 4, f"probing services{dots}",
          curses.color_pair(COLOR_AMBER), max_y, max_x)


def _render_exploit(stdscr, nodes, exploit_log, local, phase_time, current,
                    max_y, max_x):
    draw_node_graph(stdscr, nodes, max_y, max_x, current,
                    "EXPLOIT // cracking nodes")
    # scrolling log on the right / lower portion
    log_top = 2
    log_x = min(max_x - 44, max(40, max_x // 2))
    lines_visible = max(1, max_y - log_top - 2)
    shown = int(local * 6)
    start_line = max(0, shown - lines_visible)
    for i in range(lines_visible):
        li = start_line + i
        if li >= len(exploit_log) or li >= shown:
            break
        line = exploit_log[li]
        attr = curses.color_pair(COLOR_GREEN)
        if "overflow" in line or "spray" in line:
            attr = curses.color_pair(COLOR_AMBER)
        _safe(stdscr, log_top + i, log_x, line, attr, max_y, max_x)
    # active progress bar for current node
    if current >= 0:
        node = nodes[current]
        bar = progress_bar(node["progress"], 30)
        msg = f"cracking {node['name']}: {bar} {int(node['progress']*100)}%"
        _safe(stdscr, max_y - 3, 4, msg,
              curses.color_pair(COLOR_AMBER) | curses.A_BOLD, max_y, max_x)


BANNER = [
    "  ###   ###  ###  ####  ###  ###",
    "  # #  #    #    #     #    #   ",
    "  ###  #    #    ###   ###  ### ",
    "  # #  #    #    #        #    #",
    "  # #   ###  ###  ####  ###  ###",
]


def _render_access(stdscr, shell_seq, local, max_y, max_x, target):
    # banner appears immediately, then shell types
    for i, ln in enumerate(BANNER):
        _safe(stdscr, 2 + i, 4, ln,
              curses.color_pair(COLOR_GREEN) | curses.A_BOLD, max_y, max_x)
    _safe(stdscr, 2 + len(BANNER) + 1, 4, "ACCESS GRANTED -- ROOT SHELL",
          curses.color_pair(COLOR_GREEN) | curses.A_BOLD, max_y, max_x)

    # typewriter shell session
    top = 2 + len(BANNER) + 3
    cps = 22.0  # chars per second across whole session
    # Build full session as (prompt+cmd) and outputs with cumulative lengths
    y = top
    consumed = local * cps
    for cmd, outputs in shell_seq:
        prompt = "root@target:~# "
        full = prompt + cmd
        if consumed <= 0:
            break
        revealed = full[:int(min(len(full), consumed))]
        _safe(stdscr, y, 4, revealed,
              curses.color_pair(COLOR_WHITE) | curses.A_BOLD, max_y, max_x)
        y += 1
        consumed -= len(full)
        if consumed <= 0:
            break
        for out in outputs:
            rev = out[:int(min(len(out), consumed))]
            _safe(stdscr, y, 4, rev,
                  curses.color_pair(COLOR_CYAN), max_y, max_x)
            y += 1
            consumed -= len(out)
            if consumed <= 0:
                break
        if consumed <= 0:
            break
        if y >= max_y - 2:
            break


def _render_exfil(stdscr, local, phase_time, max_y, max_x, rng, target):
    _safe(stdscr, 2, 4, "EXFIL // streaming files to remote host",
          curses.color_pair(COLOR_CYAN) | curses.A_BOLD, max_y, max_x)
    frac_all = local / phase_time if phase_time > 0 else 0
    n = len(EXFIL_FILES)
    row = 4
    bar_w = min(30, max(10, max_x - 40))
    for i, fname in enumerate(EXFIL_FILES):
        if row >= max_y - 2:
            break
        # stagger each file's transfer across the phase
        start = i / (n + 1)
        f = max(0.0, min(1.0, (frac_all - start) * (n + 1)))
        if f <= 0:
            continue
        bar = progress_bar(f, bar_w)
        pct = int(f * 100)
        done = "OK" if f >= 1.0 else "  "
        attr = (curses.color_pair(COLOR_GREEN) | curses.A_BOLD if f >= 1.0
                else curses.color_pair(COLOR_AMBER))
        line = f"{fname:<14} {bar} {pct:3d}% {done}"
        _safe(stdscr, row, 4, line, attr, max_y, max_x)
        row += 1
    _safe(stdscr, max_y - 3, 4, ">> covering tracks / wiping logs ...",
          curses.color_pair(COLOR_RED), max_y, max_x)


def main(duration=30, frame_delay=0.05, phase_time=5.0, rain_density=0.15):
    duration = float(duration)
    frame_delay = float(frame_delay)
    phase_time = float(phase_time)
    rain_density = float(rain_density)
    if phase_time <= 0:
        phase_time = 1.0
    rain_density = max(0.0, min(1.0, rain_density))
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, phase_time, rain_density))


if __name__ == "__main__":
    main()
