import curses
import math
import random
import time


# ---- Color pair indices ----
COLOR_LABEL = 1     # HUD / bottom label (cyan)
COLOR_MAP = 2       # continents (dim green)
COLOR_OCEAN = 3     # subtle ocean speckle (blue)
COLOR_MALWARE = 4   # red
COLOR_DDOS = 5      # magenta
COLOR_PHISHING = 6  # yellow
COLOR_EXPLOIT = 7   # cyan
COLOR_BOTNET = 8    # green
COLOR_FLASH = 9     # bright white flash
COLOR_HIT = 10      # target pulse red
COLOR_CITY = 11     # source glow (white)
COLOR_DIM = 12      # dim log text


# Attack types: name -> color pair. Order is stable for the legend/leaderboards.
ATTACK_TYPES = [
    ("Malware", COLOR_MALWARE),
    ("DDoS", COLOR_DDOS),
    ("Phishing", COLOR_PHISHING),
    ("Exploit", COLOR_EXPLOIT),
    ("Botnet", COLOR_BOTNET),
]

COMMON_PORTS = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445,
                993, 1433, 3306, 3389, 5060, 8080, 8443]

# Path characters chosen by local slope of the arc.
ARC_CHARS = {"h": "-", "v": "|", "u": "/", "d": "\\"}


# Compact ASCII world map silhouette. Base resolution is fixed; we scale/crop
# to the terminal at draw time. Longitude spans -180..180 across the columns,
# latitude spans +83..-56 across the rows (Mercator-ish, cropped poles).
WORLD_MAP = [
    "        . _..::__:  ,-\"-\"._       |]       ,     _,.__             ",
    "  _.___ _ _<_>`!(._`.`-.    /        _._     `_ ,_/  '  '-._.---.-.__",
    ".{     \" \" `-==,',._\\{  \\  / {)     / _ \">_,-' `                mt-2_",
    " \\_.:--.       `._ )`^-. \"'      , [_/(                       __,/-'  ",
    "'\"'     \\         \"    _L        oD_,--'                )     /. (|    ",
    "         |           ,'         _)_.\\\\._<> 6              _,' /  '     ",
    "         `.         /          [_/_'` `\"(                <'}  )        ",
    "          \\\\    .-. )          /   `-'\"..' `:._          _)  '         ",
    "   `        \\  (  `(          /         `:\\  > \\  ,-^.  /' '           ",
    "    `.       \\  ` \\           /           _:  ..-  _/-  `-._,_ _       ",
    "      \\       `.   \\          /             . -_/    (   `.  `-'       ",
    "  ...\\.        `.   \\        /              . `-. ,'.    `-. \\         ",
    " {\\\"~..____ )   `. `.\\      /                 .    `._)  ,   `.\\       ",
    "  _....` )\\  )\\   `. \\`\\   /                    `-.   ,'  ,`.  `.      ",
    "        ,\\  \\.\\    `. \\`. |                        `._.'   ,   `-.    ",
    "       /  )  )  )    `.\\`\\|                            ,'      ,  \\    ",
    "      (  (  (  /       `\\`\\                            /       (   )   ",
    "       \\  \\  \\/          `\\|                         ,'   . _.'   /    ",
    "        \\  \\             ,'                        ,'   ,'      ,'     ",
    "         `. `._        ,'                       ,-'    /       /       ",
    "           `-._ `--..-'                        /      /      ,'        ",
    "               `-.._                          (      (     ,'          ",
    "                    `-.                         `.    `._,'            ",
    "                       `.                         `-._                 ",
    "                         `-.                          `.               ",
]

MAP_LON_MIN, MAP_LON_MAX = -180.0, 180.0
MAP_LAT_MAX, MAP_LAT_MIN = 83.0, -56.0

# ~34 major cities across all continents: (name, lon, lat)
CITIES = [
    ("New York", -74.0, 40.7),
    ("Los Angeles", -118.2, 34.0),
    ("Chicago", -87.6, 41.9),
    ("Toronto", -79.4, 43.7),
    ("Mexico City", -99.1, 19.4),
    ("Bogota", -74.1, 4.6),
    ("Lima", -77.0, -12.0),
    ("Sao Paulo", -46.6, -23.5),
    ("Buenos Aires", -58.4, -34.6),
    ("Rio", -43.2, -22.9),
    ("London", -0.1, 51.5),
    ("Paris", 2.3, 48.9),
    ("Madrid", -3.7, 40.4),
    ("Berlin", 13.4, 52.5),
    ("Rome", 12.5, 41.9),
    ("Moscow", 37.6, 55.8),
    ("Istanbul", 29.0, 41.0),
    ("Kyiv", 30.5, 50.5),
    ("Cairo", 31.2, 30.0),
    ("Lagos", 3.4, 6.5),
    ("Nairobi", 36.8, -1.3),
    ("Johannesburg", 28.0, -26.2),
    ("Dubai", 55.3, 25.2),
    ("Tehran", 51.4, 35.7),
    ("Mumbai", 72.9, 19.1),
    ("Delhi", 77.2, 28.6),
    ("Bangkok", 100.5, 13.8),
    ("Singapore", 103.8, 1.4),
    ("Jakarta", 106.8, -6.2),
    ("Beijing", 116.4, 39.9),
    ("Shanghai", 121.5, 31.2),
    ("Hong Kong", 114.2, 22.3),
    ("Seoul", 127.0, 37.6),
    ("Tokyo", 139.7, 35.7),
    ("Sydney", 151.2, -33.9),
]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_MAP, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_OCEAN, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_MALWARE, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_DDOS, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_PHISHING, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_EXPLOIT, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_BOTNET, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_FLASH, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_HIT, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_CITY, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_DIM, curses.COLOR_BLUE, -1)


def map_dims():
    """Return (base_cols, base_rows) of the embedded ascii map."""
    return (len(WORLD_MAP[0]), len(WORLD_MAP))


def project(lon, lat, cols, rows):
    """Project (lon, lat) onto integer (col, row) within a cols x rows grid.

    Always returns coordinates clamped to [0, cols-1] x [0, rows-1].
    """
    fx = (lon - MAP_LON_MIN) / (MAP_LON_MAX - MAP_LON_MIN)
    fy = (MAP_LAT_MAX - lat) / (MAP_LAT_MAX - MAP_LAT_MIN)
    col = int(round(fx * (cols - 1)))
    row = int(round(fy * (rows - 1)))
    col = max(0, min(cols - 1, col))
    row = max(0, min(rows - 1, row))
    return col, row


def arc_points(x0, y0, x1, y1, bow=0.35):
    """Generate a curved (bowed) path of integer (x, y) points from src to dst.

    The path arcs "upward" (toward smaller y / north) like a great-circle
    projection, giving the classic attack-map look. Always includes the
    endpoints and returns points in source->target order with no duplicates.
    """
    dx = x1 - x0
    dy = y1 - y0
    dist = math.hypot(dx, dy)
    steps = max(2, int(dist))
    # Perpendicular offset magnitude scales with distance.
    lift = -bow * dist
    pts = []
    last = None
    for i in range(steps + 1):
        t = i / steps
        # Quadratic bezier with a control point lifted perpendicular to the chord.
        mx = (x0 + x1) / 2.0
        my = (y0 + y1) / 2.0
        # perpendicular unit (normal) of the chord
        if dist > 0:
            nx = -dy / dist
            ny = dx / dist
        else:
            nx, ny = 0.0, -1.0
        # bias the control point upward regardless of chord orientation
        if ny > 0:
            nx, ny = -nx, -ny
        cx = mx + nx * lift
        cy = my + ny * lift
        omt = 1.0 - t
        px = omt * omt * x0 + 2 * omt * t * cx + t * t * x1
        py = omt * omt * y0 + 2 * omt * t * cy + t * t * y1
        p = (int(round(px)), int(round(py)))
        if p != last:
            pts.append(p)
            last = p
    if pts[0] != (int(round(x0)), int(round(y0))):
        pts.insert(0, (int(round(x0)), int(round(y0))))
    if pts[-1] != (int(round(x1)), int(round(y1))):
        pts.append((int(round(x1)), int(round(y1))))
    return pts


def arc_char(prev, cur):
    """Choose a line character based on the local slope between two points."""
    dx = cur[0] - prev[0]
    dy = cur[1] - prev[1]
    if abs(dx) > abs(dy) * 2:
        return ARC_CHARS["h"]
    if abs(dy) > abs(dx) * 2:
        return ARC_CHARS["v"]
    if (dx > 0) == (dy > 0):
        return ARC_CHARS["d"]
    return ARC_CHARS["u"]


def spawn_attack(now, cols, rows, city_positions):
    """Create a new attack record between two distinct random cities."""
    src_i, dst_i = random.sample(range(len(CITIES)), 2)
    name, color = random.choice(ATTACK_TYPES)
    (sx, sy) = city_positions[src_i]
    (dx, dy) = city_positions[dst_i]
    pts = arc_points(sx, sy, dx, dy, bow=random.uniform(0.25, 0.45))
    travel = random.uniform(1.4, 2.6)  # seconds src->dst
    return {
        "src": src_i,
        "dst": dst_i,
        "type": name,
        "color": color,
        "points": pts,
        "born": now,
        "travel": travel,
        "impact": None,     # set to time when pulse reaches target
        "done_at": None,    # set when the impact flash finishes
        "port": random.choice(COMMON_PORTS),
    }


def update_attacks(attacks, now):
    """Advance the attack model: mark impacts, expire finished attacks.

    Returns a list of attacks that just impacted this call (newly arrived).
    """
    just_hit = []
    alive = []
    for a in attacks:
        age = now - a["born"]
        if a["impact"] is None and age >= a["travel"]:
            a["impact"] = now
            a["done_at"] = now + 0.9  # flash duration
            just_hit.append(a)
        if a["done_at"] is not None and now >= a["done_at"]:
            continue  # expired
        alive.append(a)
    return just_hit, alive


def format_log_entry(a, cities):
    """Build a human-readable log line for an attack."""
    ts = time.strftime("%H:%M:%S")
    src = cities[a["src"]][0]
    dst = cities[a["dst"]][0]
    return "%s  %-8s %s -> %s  port %d" % (ts, a["type"], src, dst, a["port"])


def color_for_type(name):
    for n, c in ATTACK_TYPES:
        if n == name:
            return c
    return COLOR_LABEL


def draw_map(stdscr, ox, oy, cols, rows, max_y, max_x):
    """Render the ascii world map cropped/scaled into the given screen area."""
    base_cols, base_rows = map_dims()
    for sr in range(rows):
        by = int(sr * base_rows / rows)
        if by >= base_rows:
            by = base_rows - 1
        line = WORLD_MAP[by]
        sy = oy + sr
        if not (0 <= sy < max_y - 1):
            continue
        for sc in range(cols):
            bx = int(sc * base_cols / cols)
            if bx >= len(line):
                continue
            ch = line[bx]
            if ch == " ":
                continue
            sx = ox + sc
            if not (0 <= sx < max_x):
                continue
            try:
                stdscr.addstr(sy, sx, ch, curses.color_pair(COLOR_MAP))
            except curses.error:
                pass


def run(stdscr, duration, frame_delay, spawn_rate, max_active):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    attacks = []
    log = []           # list of (color_pair, text)
    totals = {n: 0 for n, _ in ATTACK_TYPES}
    total_all = 0
    attacker_counts = {}
    target_counts = {}
    hit_times = []     # recent impact timestamps for attacks/sec

    def add_log(a):
        log.append((a["color"], format_log_entry(a, CITIES)))
        if len(log) > 300:
            del log[:150]

    start = time.monotonic()
    last_frame = start
    spawn_accum = 0.0
    frame = 0

    while True:
        now = time.monotonic()
        if now - start >= duration:
            break
        dt = min(now - last_frame, 0.2)
        last_frame = now

        max_y, max_x = stdscr.getmaxyx()

        # ---- layout ----
        # HUD panel on the right; map fills the rest.
        panel_w = min(38, max(24, max_x // 3))
        map_area_w = max(10, max_x - panel_w - 1)
        map_area_h = max(6, max_y - 1)
        # Keep the map roughly at base aspect but clip to area.
        map_cols = map_area_w
        map_rows = map_area_h
        ox, oy = 0, 0

        city_positions = [
            (ox + c, oy + r)
            for (c, r) in (
                project(lon, lat, map_cols, map_rows)
                for (_n, lon, lat) in CITIES
            )
        ]

        # ---- spawn attacks by rate ----
        spawn_accum += spawn_rate * dt
        while spawn_accum >= 1.0:
            spawn_accum -= 1.0
            if len(attacks) < max_active:
                a = spawn_attack(now, map_cols, map_rows, city_positions)
                attacks.append(a)

        # ---- advance model ----
        just_hit, attacks = update_attacks(attacks, now)
        for a in just_hit:
            totals[a["type"]] += 1
            total_all += 1
            sname = CITIES[a["src"]][0]
            tname = CITIES[a["dst"]][0]
            attacker_counts[sname] = attacker_counts.get(sname, 0) + 1
            target_counts[tname] = target_counts.get(tname, 0) + 1
            hit_times.append(now)
            add_log(a)
        # trim rate window to last 5s
        cutoff = now - 5.0
        hit_times = [t for t in hit_times if t >= cutoff]

        stdscr.erase()
        draw_map(stdscr, ox, oy, map_cols, map_rows, max_y, max_x)

        # ---- draw attacks ----
        for a in attacks:
            pts = a["points"]
            npts = len(pts)
            color = a["color"]
            if a["impact"] is None:
                # traveling: fraction complete along the path
                frac = min(1.0, (now - a["born"]) / a["travel"])
                head = int(frac * (npts - 1))
                # draw a fading trail behind the head
                trail = max(3, npts // 6)
                for i in range(max(0, head - trail), head + 1):
                    px, py = pts[i]
                    if not (0 <= px < map_area_w and 0 <= py < max_y - 1):
                        continue
                    prev = pts[i - 1] if i > 0 else pts[i]
                    ch = arc_char(prev, (px, py))
                    if i == head:
                        attr = curses.color_pair(COLOR_FLASH) | curses.A_BOLD
                        ch = "*"
                    else:
                        attr = curses.color_pair(color)
                        if (head - i) <= 1:
                            attr |= curses.A_BOLD
                    try:
                        stdscr.addstr(py, px, ch, attr)
                    except curses.error:
                        pass
            else:
                # impacted: draw faint full arc + expanding ring at target
                for i in range(1, npts):
                    px, py = pts[i]
                    if not (0 <= px < map_area_w and 0 <= py < max_y - 1):
                        continue
                    ch = arc_char(pts[i - 1], pts[i])
                    try:
                        stdscr.addstr(py, px, ch, curses.color_pair(color))
                    except curses.error:
                        pass
                # expanding ring / flash
                tx, ty = pts[-1]
                age = now - a["impact"]
                radius = int(age / 0.9 * 4) + 1
                ring_attr = (curses.color_pair(COLOR_FLASH) | curses.A_BOLD
                             if age < 0.3
                             else curses.color_pair(COLOR_HIT) | curses.A_BOLD)
                for ang in range(0, 360, 30):
                    rad = math.radians(ang)
                    rx = tx + int(round(math.cos(rad) * radius))
                    ry = ty + int(round(math.sin(rad) * radius * 0.5))
                    if 0 <= rx < map_area_w and 0 <= ry < max_y - 1:
                        try:
                            stdscr.addstr(ry, rx, "o", ring_attr)
                        except curses.error:
                            pass

        # ---- draw cities ----
        active_targets = {a["dst"]: a["impact"] for a in attacks
                          if a["impact"] is not None}
        for i, (cx, cy) in enumerate(city_positions):
            if not (0 <= cx < map_area_w and 0 <= cy < max_y - 1):
                continue
            if i in active_targets:
                attr = curses.color_pair(COLOR_HIT) | curses.A_BOLD
                ch = "@"
            else:
                attr = curses.color_pair(COLOR_CITY) | (
                    curses.A_BOLD if frame % 6 < 3 else 0)
                ch = "+"
            try:
                stdscr.addstr(cy, cx, ch, attr)
            except curses.error:
                pass

        # ---- HUD panel ----
        px0 = max_x - panel_w
        aps = len(hit_times) / 5.0
        active_ct = len(attacks)
        hud = []
        hud.append(("t", "== THREAT MAP =="))
        hud.append(("t", "attacks/sec: %.1f" % aps))
        hud.append(("t", "active arcs: %d/%d" % (active_ct, max_active)))
        hud.append(("t", "total:       %d" % total_all))
        hud.append(("t", "-" * (panel_w - 1)))
        hud.append(("t", "BY TYPE:"))
        for n, c in ATTACK_TYPES:
            hud.append(("c%d" % c, "  %-9s %d" % (n, totals[n])))
        hud.append(("t", "-" * (panel_w - 1)))
        hud.append(("t", "TOP ATTACKERS:"))
        top_a = sorted(attacker_counts.items(), key=lambda kv: -kv[1])[:4]
        for name, cnt in top_a:
            hud.append(("d", "  %-14s %d" % (name[:14], cnt)))
        hud.append(("t", "TOP TARGETS:"))
        top_t = sorted(target_counts.items(), key=lambda kv: -kv[1])[:4]
        for name, cnt in top_t:
            hud.append(("d", "  %-14s %d" % (name[:14], cnt)))
        hud.append(("t", "-" * (panel_w - 1)))
        hud.append(("t", "LIVE FEED:"))
        # fill remaining rows with the scrolling log
        used = len(hud)
        feed_rows = max(0, (max_y - 1) - used)
        for color, text in log[-feed_rows:]:
            hud.append(("f%d" % color, text))

        for i, (kind, text) in enumerate(hud):
            if i >= max_y - 1:
                break
            if kind == "t":
                attr = curses.color_pair(COLOR_LABEL) | curses.A_BOLD
            elif kind == "d":
                attr = curses.color_pair(COLOR_DIM)
            elif kind.startswith("c"):
                attr = curses.color_pair(int(kind[1:])) | curses.A_BOLD
            elif kind.startswith("f"):
                attr = curses.color_pair(int(kind[1:]))
            else:
                attr = curses.color_pair(COLOR_LABEL)
            try:
                stdscr.addstr(i, px0, text[:panel_w - 1], attr)
            except curses.error:
                pass

        # ---- bottom legend + label ----
        # colored legend of attack types along the bottom-left
        lx = 2
        try:
            stdscr.addstr(max_y - 1, 0, " ", curses.color_pair(COLOR_LABEL))
        except curses.error:
            pass
        for n, c in ATTACK_TYPES:
            seg = "%s " % n
            if lx + len(seg) >= max_x - 12:
                break
            try:
                stdscr.addstr(max_y - 1, lx, seg,
                              curses.color_pair(c) | curses.A_BOLD)
            except curses.error:
                pass
            lx += len(seg)
        label = "worldmap_attack  [q]uit"
        try:
            stdscr.addstr(max_y - 1, max(lx + 1, max_x - len(label) - 2),
                          label[:max(0, max_x - lx - 2)],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        frame += 1
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def main(duration=30, frame_delay=0.05, spawn_rate=4.0, max_active=25):
    duration = float(duration)
    frame_delay = float(frame_delay)
    spawn_rate = float(spawn_rate)
    max_active = max(1, int(max_active))
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, spawn_rate, max_active))


if __name__ == "__main__":
    main()
