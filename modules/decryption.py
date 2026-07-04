import curses
import random
import string
import time


# Color pair indices
COLOR_LABEL = 1      # bottom cyan+bold label
COLOR_CHURN = 2      # amber/dim churning cells
COLOR_LOCKED = 3     # bold green locked cells
COLOR_HEADER = 4     # cyan headers
COLOR_ALERT = 5      # red alerts
COLOR_GRANTED = 6    # bright green banner
COLOR_DIM = 7        # dim gray stats

# Glyph pools for churning cells
HEX_GLYPHS = "0123456789abcdef"
ASCII_GLYPHS = string.ascii_letters + string.digits
SYMBOL_GLYPHS = "!@#$%^&*()_+-=[]{}|;:,.<>?/~`"
ALL_GLYPHS = HEX_GLYPHS + ASCII_GLYPHS + SYMBOL_GLYPHS

# Fun generic log lines
LOG_LINES = [
    "bypassing firewall...",
    "keyspace 2^128 enumerated",
    "collision found in bucket 0x3f",
    "dictionary exhausted, switching to mask attack",
    "rainbow table loaded (14.2 GB)",
    "seeding entropy from /dev/urandom",
    "spinning up 4096 worker threads",
    "GPU cluster online: 8x rigs",
    "rotating cipher block chain",
    "salt extracted, re-hashing",
    "handshake intercepted",
    "probing weak nonce reuse",
    "differential cryptanalysis pass 3",
    "reticulating splines",
    "quantum annealer warming up",
    "side-channel timing acquired",
    "birthday paradox exploited",
    "unrolling feistel network",
    "candidate space pruned 87%",
    "bruteforce vector aligned",
]

CANDIDATE_POOLS = [
    "hunter2", "correcthorse", "letmein", "s3cr3t", "passw0rd",
    "0xDEADBEEF", "trustno1", "qwerty123", "admin", "root",
    " swordfish", "hackthe planet", "zer0cool", "cerealkiller",
]

TARGET_NAMES = ["PASSPHRASE", "AES-256 KEY", "SHA-256 HASH", "PRIVATE KEY", "SESSION TOKEN"]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_CHURN, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_LOCKED, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_HEADER, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_ALERT, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_GRANTED, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_DIM, curses.COLOR_WHITE, -1)


def random_glyph(pool=ALL_GLYPHS):
    return random.choice(pool)


def random_hex(n):
    return "".join(random.choice(HEX_GLYPHS) for _ in range(n))


def make_target(name, length, glyph_pool):
    """Create a target with a hidden solution and per-cell lock state."""
    solution = "".join(random.choice(glyph_pool) for _ in range(length))
    # Random lock order for a satisfying non-uniform reveal.
    order = list(range(length))
    random.shuffle(order)
    return {
        "name": name,
        "solution": solution,
        "length": length,
        "locked": [False] * length,
        "display": [random.choice(glyph_pool) for _ in range(length)],
        "glyph_pool": glyph_pool,
        "order": order,
        "next_lock_idx": 0,
        # lock cadence: number of frames between locking cells
        "lock_every": max(1, random.randint(1, 4)),
        "frame": 0,
    }


def step_target(target):
    """Advance one frame: churn unlocked cells, occasionally lock the next one.

    Returns True when every cell is locked.
    """
    length = target["length"]
    # Churn unlocked cells with fresh random glyphs.
    for i in range(length):
        if not target["locked"][i]:
            target["display"][i] = random.choice(target["glyph_pool"])

    target["frame"] += 1
    if target["next_lock_idx"] < length:
        if target["frame"] % target["lock_every"] == 0:
            idx = target["order"][target["next_lock_idx"]]
            target["locked"][idx] = True
            target["display"][idx] = target["solution"][idx]
            target["next_lock_idx"] += 1

    return all(target["locked"])


def is_solved(target):
    return all(target["locked"])


def build_targets(key_length):
    """Assemble the set of simultaneous cracking targets."""
    key_length = max(4, key_length)
    pass_len = max(6, min(16, key_length // 4))
    hash_len = key_length
    targets = [
        make_target(TARGET_NAMES[0], pass_len, ASCII_GLYPHS + SYMBOL_GLYPHS),
        make_target(TARGET_NAMES[1], key_length, HEX_GLYPHS),
        make_target(TARGET_NAMES[2], hash_len, HEX_GLYPHS),
    ]
    return targets


def format_attempts(n):
    """Human-friendly big-number formatting for the attempts counter."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f} B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f} M"
    if n >= 1_000:
        return f"{n / 1_000:.1f} K"
    return str(int(n))


def make_stats():
    return {
        "attempts": 0.0,
        "rate": random.uniform(1200, 5000),
        "start": time.monotonic(),
        "keyspace_pct": 0.0,
        "candidate": random.choice(CANDIDATE_POOLS),
        "logs": [],
        "log_cooldown": random.randint(4, 12),
    }


def step_stats(stats):
    # Rate spins up toward the millions.
    stats["rate"] *= random.uniform(1.02, 1.15)
    stats["rate"] = min(stats["rate"], 50_000_000)
    stats["attempts"] += stats["rate"]
    stats["keyspace_pct"] = min(99.9, stats["keyspace_pct"] + random.uniform(0.3, 2.2))
    if random.random() < 0.5:
        stats["candidate"] = "".join(
            random.choice(ALL_GLYPHS) for _ in range(random.randint(6, 14))
        )
    else:
        stats["candidate"] = random.choice(CANDIDATE_POOLS)

    stats["log_cooldown"] -= 1
    if stats["log_cooldown"] <= 0:
        stats["logs"].append(random.choice(LOG_LINES))
        stats["logs"] = stats["logs"][-6:]
        stats["log_cooldown"] = random.randint(4, 14)


def draw_target(stdscr, y, x, target, max_x):
    """Draw a target row: name header + churning/locked cells."""
    header = f"{target['name']:<14}"
    try:
        stdscr.addstr(y, x, header, curses.color_pair(COLOR_HEADER) | curses.A_BOLD)
    except curses.error:
        pass
    cx = x + len(header) + 1
    for i in range(target["length"]):
        if cx >= max_x - 1:
            break
        ch = target["display"][i]
        if target["locked"][i]:
            attr = curses.color_pair(COLOR_LOCKED) | curses.A_BOLD
        else:
            attr = curses.color_pair(COLOR_CHURN) | curses.A_DIM
        try:
            stdscr.addstr(y, cx, ch, attr)
        except curses.error:
            pass
        cx += 1


def draw_stats(stdscr, y, x, stats, max_y, max_x):
    """Draw the fake brute-force stats panel. Returns next free row."""
    elapsed = time.monotonic() - stats["start"]
    lines = [
        ("BRUTE FORCE ENGINE", COLOR_HEADER, curses.A_BOLD),
        (f"attempts    : {format_attempts(stats['attempts'])}", COLOR_DIM, 0),
        (f"rate        : {format_attempts(stats['rate'])}/sec", COLOR_DIM, 0),
        (f"elapsed     : {elapsed:6.1f}s", COLOR_DIM, 0),
        (f"candidate   : {stats['candidate']}", COLOR_CHURN, 0),
    ]
    row = y
    for text, color, extra in lines:
        if row >= max_y - 1:
            break
        try:
            stdscr.addstr(row, x, text[:max_x - x - 1],
                          curses.color_pair(color) | extra)
        except curses.error:
            pass
        row += 1

    # keyspace-explored progress bar
    if row < max_y - 1:
        bar_w = max(4, min(30, max_x - x - 20))
        filled = int(bar_w * stats["keyspace_pct"] / 100.0)
        bar = "[" + "#" * filled + "-" * (bar_w - filled) + "]"
        text = f"keyspace    : {bar} {stats['keyspace_pct']:4.1f}%"
        try:
            stdscr.addstr(row, x, text[:max_x - x - 1],
                          curses.color_pair(COLOR_LOCKED))
        except curses.error:
            pass
        row += 1

    # log lines
    row += 1
    for log in stats["logs"]:
        if row >= max_y - 1:
            break
        try:
            stdscr.addstr(row, x, ("> " + log)[:max_x - x - 1],
                          curses.color_pair(COLOR_DIM) | curses.A_DIM)
        except curses.error:
            pass
        row += 1
    return row


def draw_banner(stdscr, targets, max_y, max_x, retrying=False):
    """Big flashing banner when everything is solved (or a retry near-miss)."""
    if retrying:
        msg = "*** RETRYING... ***"
        attr = curses.color_pair(COLOR_ALERT) | curses.A_BOLD | curses.A_BLINK
    else:
        msg = "*** ACCESS GRANTED :: DECRYPTION COMPLETE ***"
        attr = curses.color_pair(COLOR_GRANTED) | curses.A_BOLD | curses.A_BLINK
    by = max_y // 2
    bx = max(0, (max_x - len(msg)) // 2)
    try:
        stdscr.addstr(by, bx, msg[:max_x - 1], attr)
    except curses.error:
        pass

    if not retrying:
        # reveal the plaintext solutions beneath the banner
        row = by + 2
        for t in targets:
            if row >= max_y - 1:
                break
            line = f"{t['name']:<14} {t['solution']}"
            lx = max(0, (max_x - len(line)) // 2)
            try:
                stdscr.addstr(row, lx, line[:max_x - 1],
                              curses.color_pair(COLOR_LOCKED) | curses.A_BOLD)
            except curses.error:
                pass
            row += 1


def run(stdscr, duration, frame_delay, key_length, completion_pause):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    start = time.monotonic()

    targets = build_targets(key_length)
    stats = make_stats()
    # state machine: "cracking" -> ("retry" ->) "granted" -> reset
    state = "cracking"
    state_until = 0.0
    retry_shown = False

    while True:
        now = time.monotonic()
        if now - start >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        stdscr.erase()

        if state == "cracking":
            step_stats(stats)
            all_solved = True
            for t in targets:
                if not step_target(t):
                    all_solved = False

            # draw targets across the top
            ty = 1
            for t in targets:
                draw_target(stdscr, ty, 2, t, max_x)
                ty += 2

            # stats panel below the targets
            draw_stats(stdscr, ty + 1, 2, stats, max_y, max_x)

            if all_solved:
                # Rare dramatic near-miss retry before granting.
                if not retry_shown and random.random() < 0.25:
                    state = "retry"
                    state_until = now + min(1.2, completion_pause * 0.5)
                    retry_shown = True
                else:
                    state = "granted"
                    state_until = now + completion_pause

        elif state == "retry":
            # keep churning targets a touch for tension, show red flash
            for t in targets:
                draw_target(stdscr, 1 + targets.index(t) * 2, 2, t, max_x)
            draw_banner(stdscr, targets, max_y, max_x, retrying=True)
            if now >= state_until:
                state = "granted"
                state_until = now + completion_pause

        elif state == "granted":
            draw_banner(stdscr, targets, max_y, max_x, retrying=False)
            if now >= state_until:
                # reset with fresh random targets and go again
                targets = build_targets(key_length)
                stats = make_stats()
                retry_shown = False
                state = "cracking"

        # bottom cyan+bold label
        label = (f"Decryption  key_length={key_length}  "
                 f"targets={len(targets)}  [q to quit]")
        try:
            stdscr.addstr(max_y - 1, 2, label[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key == ord("q") or key == ord("Q") or key == 27:
            return


def main(duration=25, frame_delay=0.04, key_length=64, completion_pause=2.5):
    duration = float(duration)
    frame_delay = float(frame_delay)
    key_length = max(4, int(key_length))
    completion_pause = float(completion_pause)
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, key_length, completion_pause))


if __name__ == "__main__":
    main()
