import curses
import math
import random
import time


COLOR_BACKBONE_A = 1
COLOR_BACKBONE_B = 2
COLOR_BASE_AT = 3   # adenine-thymine pairs
COLOR_BASE_GC = 4   # guanine-cytosine pairs
COLOR_LABEL = 5

# Watson–Crick pairs
PAIRS = {"A": "T", "T": "A", "G": "C", "C": "G"}
BASE_COLOR = {"A": COLOR_BASE_AT, "T": COLOR_BASE_AT,
              "G": COLOR_BASE_GC, "C": COLOR_BASE_GC}


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_BACKBONE_A, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_BACKBONE_B, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_BASE_AT, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_BASE_GC, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_WHITE, -1)


def run(stdscr, duration, frame_delay, num_pairs, twist_speed, radius,
        bp_per_turn, helix_height):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    # Random sequence
    sequence = [random.choice("ATGC") for _ in range(num_pairs)]

    backbone_attr_a = curses.color_pair(COLOR_BACKBONE_A) | curses.A_BOLD
    backbone_attr_b = curses.color_pair(COLOR_BACKBONE_B) | curses.A_BOLD

    start = time.monotonic()
    while True:
        now = time.monotonic()
        if now - start >= duration:
            break
        elapsed = now - start

        max_y, max_x = stdscr.getmaxyx()
        cy = max_y // 2

        # Horizontal axis: helix runs left → right, twists around the x axis.
        left_x = 2
        right_x = max_x - 2
        usable = right_x - left_x
        if usable < num_pairs:
            col_step = max(1, usable / num_pairs)
        else:
            col_step = usable / num_pairs

        rotation = elapsed * twist_speed

        stdscr.erase()

        # Each base pair lives at one column. The two strands sit above and
        # below the axis — y offset = ±radius·cos(phase). The depth (used
        # only for back/front ordering) is ±sin(phase).
        rungs = []
        for i, base in enumerate(sequence):
            x = left_x + int(round(i * col_step))
            phase = i * (2 * math.pi / bp_per_turn) + rotation
            ya = cy + radius * math.cos(phase)
            yb = cy + radius * math.cos(phase + math.pi)
            za = math.sin(phase)
            zb = math.sin(phase + math.pi)
            rungs.append((x, ya, yb, base, za, zb))

        # Draw rungs (vertical bar between strands at each base-pair column)
        for x, ya, yb, base, _, _ in rungs:
            if not (0 <= x < max_x):
                continue
            attr = curses.color_pair(BASE_COLOR[base]) | curses.A_BOLD
            ya_i = int(round(ya))
            yb_i = int(round(yb))
            y0, y1 = (ya_i, yb_i) if ya_i <= yb_i else (yb_i, ya_i)
            for y in range(y0 + 1, y1):
                if 0 <= y < max_y - 1:
                    try:
                        stdscr.addstr(y, x, "|", attr | curses.A_DIM)
                    except curses.error:
                        pass
            # Stamp the bases themselves at each strand position
            partner = PAIRS[base]
            if 0 <= ya_i < max_y - 1:
                try:
                    stdscr.addstr(ya_i, x, base, attr)
                except curses.error:
                    pass
            if 0 <= yb_i < max_y - 1:
                try:
                    stdscr.addstr(yb_i, x, partner, attr)
                except curses.error:
                    pass

        # Backbone strands: sample at sub-column resolution for a smooth
        # curve, drawing back-strand first so the front overdraws.
        n_samples = max(num_pairs * 2, usable)
        for k in range(n_samples + 1):
            t = k / n_samples
            x = left_x + int(round(t * usable))
            if not (0 <= x < max_x):
                continue
            phase = t * num_pairs * (2 * math.pi / bp_per_turn) + rotation
            ya = cy + radius * math.cos(phase)
            yb = cy + radius * math.cos(phase + math.pi)
            za = math.sin(phase)
            zb = math.sin(phase + math.pi)
            order = [(za, ya, backbone_attr_a),
                     (zb, yb, backbone_attr_b)]
            order.sort(key=lambda v: v[0])  # back first
            for _, y, attr in order:
                yi = int(round(y))
                if 0 <= yi < max_y - 1:
                    try:
                        stdscr.addstr(yi, x, "#", attr)
                    except curses.error:
                        pass

        info = (f"DNA helix  bp={num_pairs}  bp/turn={bp_per_turn}  "
                f"rotation rate={twist_speed:.2f} rad/s")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()

        key = stdscr.getch()
        if key == ord("q") or key == 27:
            return


def main(duration=25, frame_delay=0.05, num_pairs=20, twist_speed=0.6,
         radius=4.0, bp_per_turn=10, helix_height=20):
    duration = float(duration)
    frame_delay = float(frame_delay)
    num_pairs = max(2, int(num_pairs))
    twist_speed = float(twist_speed)
    radius = float(radius)
    bp_per_turn = max(1, int(bp_per_turn))
    helix_height = max(2, int(helix_height))
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, num_pairs, twist_speed, radius,
        bp_per_turn, helix_height))


if __name__ == "__main__":
    main()
