import curses
import time


# Color pair ids
COLOR_STATE_A = 1
COLOR_STATE_B = 2
COLOR_STATE_C = 3
COLOR_STATE_D = 4
COLOR_STATE_E = 5
COLOR_ONE = 6
COLOR_LABEL = 7
COLOR_HALT = 8

STATE_PAIRS = {
    "A": COLOR_STATE_A,
    "B": COLOR_STATE_B,
    "C": COLOR_STATE_C,
    "D": COLOR_STATE_D,
    "E": COLOR_STATE_E,
    "H": COLOR_HALT,
}

HALT = "H"

# Transition tables: (state, symbol) -> (write, move 'L'/'R', next_state)
# BB-2: Rado's 2-state busy beaver. Halts in 6 steps with 4 ones.
BB2 = {
    ("A", 0): (1, "R", "B"), ("A", 1): (1, "L", "B"),
    ("B", 0): (1, "L", "A"), ("B", 1): (1, "R", HALT),
}

# BB-3: Lin & Rado 3-state sigma champion. Halts in 14 steps with 6 ones.
BB3 = {
    ("A", 0): (1, "R", "B"), ("A", 1): (1, "R", HALT),
    ("B", 0): (0, "R", "C"), ("B", 1): (1, "R", "B"),
    ("C", 0): (1, "L", "C"), ("C", 1): (1, "L", "A"),
}

# BB-4: Brady's 4-state busy beaver. Halts in 107 steps with 13 ones.
BB4 = {
    ("A", 0): (1, "R", "B"), ("A", 1): (1, "L", "B"),
    ("B", 0): (1, "L", "A"), ("B", 1): (0, "L", "C"),
    ("C", 0): (1, "R", HALT), ("C", 1): (1, "L", "D"),
    ("D", 0): (1, "R", "D"), ("D", 1): (0, "R", "A"),
}

# Christmas tree: a simple non-halting zig-zag machine that sweeps back
# and forth, extending its stripe of ones by one cell on each pass.
XMAS = {
    ("A", 0): (1, "R", "B"), ("A", 1): (1, "L", "A"),
    ("B", 0): (1, "L", "A"), ("B", 1): (1, "R", "B"),
}

MACHINES = [
    {"name": "BB-2 (Rado 1962)", "table": BB2,
     "halts": True, "steps": 6, "ones": 4, "max_steps": 6},
    {"name": "BB-3 (Lin-Rado 1965)", "table": BB3,
     "halts": True, "steps": 14, "ones": 6, "max_steps": 14},
    {"name": "BB-4 (Brady 1983)", "table": BB4,
     "halts": True, "steps": 107, "ones": 13, "max_steps": 107},
    {"name": "Christmas Tree (non-halting)", "table": XMAS,
     "halts": False, "steps": None, "ones": None, "max_steps": 400},
]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_STATE_A, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_STATE_B, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_STATE_C, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_STATE_D, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_STATE_E, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_ONE, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_HALT, curses.COLOR_GREEN, -1)


def machine_states(table):
    states = []
    for (state, _sym) in table:
        if state not in states:
            states.append(state)
    return sorted(states)


def tm_step(table, tape, pos, state):
    """Apply one transition. Returns (new_pos, new_state).
    Tape is a dict holding only cells that contain 1."""
    sym = tape.get(pos, 0)
    write, move, nxt = table[(state, sym)]
    if write:
        tape[pos] = 1
    else:
        tape.pop(pos, None)
    pos += 1 if move == "R" else -1
    return pos, nxt


def simulate(table, max_steps=1000000):
    """Headless run. Returns (steps, ones, halted)."""
    tape = {}
    pos = 0
    state = "A"
    steps = 0
    while state != HALT and steps < max_steps:
        pos, state = tm_step(table, tape, pos, state)
        steps += 1
    return steps, len(tape), state == HALT


def verify_machines():
    for m in MACHINES:
        if not m["halts"]:
            steps, _ones, halted = simulate(m["table"], max_steps=10000)
            assert not halted, f"{m['name']} unexpectedly halted at {steps}"
            continue
        steps, ones, halted = simulate(m["table"])
        assert halted, f"{m['name']} did not halt"
        assert steps == m["steps"], \
            f"{m['name']}: got {steps} steps, expected {m['steps']}"
        assert ones == m["ones"], \
            f"{m['name']}: got {ones} ones, expected {m['ones']}"


def state_attr(state, bold=True):
    pair = STATE_PAIRS.get(state, COLOR_STATE_E)
    attr = curses.color_pair(pair)
    return attr | curses.A_BOLD if bold else attr


def draw_table(stdscr, table, state, sym, max_x):
    try:
        stdscr.addstr(1, 2, "d(q,s) -> w,m,q'", curses.A_DIM)
    except curses.error:
        pass
    row = 2
    for st in machine_states(table):
        for s in (0, 1):
            write, move, nxt = table[(st, s)]
            line = f"{st}{s} -> {write}{move}{nxt}"
            attr = state_attr(st, bold=False)
            if st == state and s == sym:
                attr = state_attr(st) | curses.A_REVERSE
            try:
                stdscr.addstr(row, 2, line[:max_x - 3], attr)
            except curses.error:
                pass
            row += 1


def draw_tape(stdscr, tape, pos, state, max_y, max_x):
    tape_row = max(3, max_y // 2)
    center_col = max_x // 2
    cell_w = 2
    half = max(1, (max_x - 4) // (2 * cell_w))
    for i in range(-half, half + 1):
        col = center_col + i * cell_w
        if col < 0 or col >= max_x - 1:
            continue
        sym = tape.get(pos + i, 0)
        if sym:
            ch, attr = "1", curses.color_pair(COLOR_ONE) | curses.A_BOLD
        else:
            ch, attr = "·", curses.A_DIM
        if i == 0:
            attr = state_attr(state) | curses.A_REVERSE
            ch = str(sym)
        try:
            stdscr.addstr(tape_row, col, ch, attr)
        except curses.error:
            pass
    try:
        stdscr.addstr(tape_row - 1, center_col, "▼", state_attr(state))
    except curses.error:
        pass
    return tape_row


def draw_status(stdscr, machine, state, steps, tape, max_y, max_x):
    tape_row = max(3, max_y // 2)
    name_line = machine["name"]
    try:
        stdscr.addstr(max(0, tape_row - 4), max(0, (max_x - len(name_line)) // 2),
                      name_line[:max_x - 1], curses.A_BOLD)
    except curses.error:
        pass
    ones = len(tape)
    try:
        stdscr.addstr(max(0, tape_row - 3),
                      max(0, (max_x - 30) // 2), "state ")
        stdscr.addstr(state, state_attr(state))
        stdscr.addstr(f"   step {steps}   ones {ones}")
    except curses.error:
        pass


def run(stdscr, duration, step_delay, completion_pause):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(step_delay * 1000))

    delay_floor = 0.01
    decay = 0.95
    start = time.monotonic()
    machine_idx = 0

    while time.monotonic() - start < duration:
        machine = MACHINES[machine_idx % len(MACHINES)]
        table = machine["table"]
        tape = {}
        pos = 0
        state = "A"
        steps = 0
        finished = False

        # ---- run one machine ----
        while not finished:
            if time.monotonic() - start >= duration:
                return
            max_y, max_x = stdscr.getmaxyx()

            # Speed ramp: exponentially shrink the per-step delay; once it
            # hits the floor, take multiple steps per frame instead.
            cur_delay = max(delay_floor, step_delay * (decay ** steps))
            per_frame = max(1, min(30, int(round(step_delay / cur_delay))))
            for _ in range(per_frame):
                if state == HALT or steps >= machine["max_steps"]:
                    finished = True
                    break
                pos, state = tm_step(table, tape, pos, state)
                steps += 1
            if state == HALT or steps >= machine["max_steps"]:
                finished = True

            stdscr.erase()
            sym = tape.get(pos, 0)
            draw_table(stdscr, table, state if state != HALT else "", sym, max_x)
            draw_tape(stdscr, tape, pos, state, max_y, max_x)
            draw_status(stdscr, machine, state, steps, tape, max_y, max_x)
            info = (f"Turing Machines  [{machine_idx % len(MACHINES) + 1}"
                    f"/{len(MACHINES)}]  {machine['name']}  |  q to quit")
            try:
                stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                              curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
            except curses.error:
                pass
            stdscr.refresh()
            key = stdscr.getch()
            if key in (ord("q"), ord("Q"), 27):
                return

        # ---- halt / max-steps flash, then next machine ----
        ones = len(tape)
        if state == HALT:
            msg = f" HALTED — steps: {steps}, ones: {ones} "
        else:
            msg = f" MAX STEPS — steps: {steps}, ones: {ones} "
        pause_start = time.monotonic()
        while time.monotonic() - pause_start < completion_pause:
            if time.monotonic() - start >= duration:
                return
            max_y, max_x = stdscr.getmaxyx()
            stdscr.erase()
            draw_table(stdscr, table, "", tape.get(pos, 0), max_x)
            tape_row = draw_tape(stdscr, tape, pos, state, max_y, max_x)
            draw_status(stdscr, machine, state, steps, tape, max_y, max_x)
            attr = curses.color_pair(COLOR_HALT) | curses.A_BOLD
            if int((time.monotonic() - pause_start) * 4) % 2 == 0:
                attr |= curses.A_REVERSE
            try:
                stdscr.addstr(min(max_y - 2, tape_row + 2),
                              max(0, (max_x - len(msg)) // 2),
                              msg[:max_x - 1], attr)
            except curses.error:
                pass
            info = "Turing Machines  |  loading next machine..."
            try:
                stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                              curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
            except curses.error:
                pass
            stdscr.refresh()
            key = stdscr.getch()
            if key in (ord("q"), ord("Q"), 27):
                return
        machine_idx += 1


def main(duration=30, step_delay=0.05, completion_pause=2.5):
    duration = float(duration)
    step_delay = float(step_delay)
    completion_pause = float(completion_pause)
    verify_machines()
    curses.wrapper(lambda stdscr: run(stdscr, duration, step_delay,
                                      completion_pause))


if __name__ == "__main__":
    main()
