import curses
import hashlib
import math
import random
import re
import subprocess
import time


# ---- color pair ids ----
COLOR_HOST = 1        # your host: green
COLOR_ARC = 2         # arcs: cyan/dim
COLOR_PULSE = 3       # active pulses: bright white/yellow
COLOR_LABEL = 4       # bottom info label: cyan bold
COLOR_MAP = 5         # world silhouette: dim white/blue
COLOR_FLASH = 6       # newly-seen connection flash
COLOR_FADE = 7        # closed connection fade
# remote node colors keyed by region bucket
COLOR_R0 = 8
COLOR_R1 = 9
COLOR_R2 = 10
COLOR_R3 = 11
COLOR_R4 = 12
COLOR_R5 = 13
REGION_COLORS = [COLOR_R0, COLOR_R1, COLOR_R2, COLOR_R3, COLOR_R4, COLOR_R5]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_HOST, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_ARC, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_PULSE, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_MAP, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_FLASH, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_FADE, curses.COLOR_BLACK, -1)
    curses.init_pair(COLOR_R0, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_R1, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_R2, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_R3, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_R4, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_R5, curses.COLOR_WHITE, -1)


# Compact ~60x20 world silhouette. '#' = land, ' ' = ocean.
WORLD_MAP = [
    "                                                            ",
    "        ..    ####      ############           ##           ",
    "      ##########      ##################      ####          ",
    "     ############    ####################    #######        ",
    "    ##############     ################     #########       ",
    "   ###############       ###########        ########        ",
    "    #############         #########        #######          ",
    "      #########            #######          #####           ",
    "       #######      ##      #####            ####           ",
    "        #####      ####      ###              ###           ",
    "         ####     #####       ##               ##  ##       ",
    "          ###    ######        #               #  ####      ",
    "           ##    ######        #                  #####     ",
    "           ##     #####        ##                  ###      ",
    "            #      ####         ###                          ",
    "                    ##          ####            ##          ",
    "                     #           ###           ####         ",
    "                                  ##            ##          ",
    "                                                            ",
    "                                                            ",
]
MAP_W = len(WORLD_MAP[0])
MAP_H = len(WORLD_MAP)


# Small embedded table of well-known provider IP prefixes -> (city, lon, lat).
# lon in [-180,180], lat in [-90,90].
PROVIDER_PREFIXES = [
    ("52.", ("AWS us-east", -77.5, 38.9)),
    ("54.", ("AWS us-east", -77.5, 38.9)),
    ("3.", ("AWS", -119.0, 45.8)),
    ("13.", ("AWS", -119.0, 45.8)),
    ("18.", ("AWS us-east", -77.5, 38.9)),
    ("34.", ("Google Cloud", -95.6, 41.3)),
    ("35.", ("Google Cloud", -95.6, 41.3)),
    ("142.250.", ("Google", -122.1, 37.4)),
    ("172.217.", ("Google", -122.1, 37.4)),
    ("104.16.", ("Cloudflare", -122.4, 37.8)),
    ("104.17.", ("Cloudflare", -122.4, 37.8)),
    ("162.159.", ("Cloudflare", -122.4, 37.8)),
    ("1.1.1.", ("Cloudflare DNS", -122.4, 37.8)),
    ("8.8.8.", ("Google DNS", -122.1, 37.4)),
    ("40.", ("Azure", -119.9, 47.2)),
    ("20.", ("Azure", -119.9, 47.2)),
    ("13.107.", ("Microsoft", -122.1, 47.6)),
    ("151.101.", ("Fastly", -122.4, 37.8)),
    ("199.232.", ("Fastly", -122.4, 37.8)),
    ("140.82.", ("GitHub", -122.4, 37.8)),
    ("185.199.", ("GitHub Pages", -0.1, 51.5)),
    ("31.13.", ("Meta", -122.0, 37.5)),
    ("157.240.", ("Meta", -122.0, 37.5)),
    ("17.", ("Apple", -122.0, 37.3)),
]

# City centers to sprinkle hashed IPs into populated regions.
POPULATED = [
    ("N.America", -100.0, 40.0),
    ("S.America", -58.0, -20.0),
    ("Europe", 10.0, 50.0),
    ("Africa", 20.0, 5.0),
    ("Asia", 100.0, 35.0),
    ("SE.Asia", 110.0, 5.0),
    ("Oceania", 145.0, -33.0),
    ("E.Asia", 130.0, 37.0),
]

SIM_PROCS = ["Chrome", "Slack", "python3", "Spotify", "Docker", "ssh",
             "curl", "node", "Firefox", "zoom.us", "Dropbox", "Mail",
             "Terminal", "Code", "Music"]
SIM_TARGETS = ["52.", "54.", "34.", "35.", "142.250.", "104.16.", "162.159.",
               "8.8.8.", "40.", "20.", "151.101.", "140.82.", "31.13.",
               "157.240.", "17."]


def geo_for_ip(ip):
    """Deterministically map an IP -> (region_label, lon, lat).

    Offline only. Uses the embedded provider table first, then hashes
    unknown IPs into a populated region. Coords stay in valid ranges.
    """
    for prefix, (label, lon, lat) in PROVIDER_PREFIXES:
        if ip.startswith(prefix):
            # tiny deterministic jitter so shared-prefix IPs don't overlap
            h = int(hashlib.md5(ip.encode()).hexdigest(), 16)
            jlon = ((h % 1000) / 1000.0 - 0.5) * 6.0
            jlat = (((h >> 10) % 1000) / 1000.0 - 0.5) * 4.0
            return label, _clamp(lon + jlon, -179.9, 179.9), _clamp(lat + jlat, -85.0, 85.0)
    h = int(hashlib.md5(ip.encode()).hexdigest(), 16)
    label, clon, clat = POPULATED[h % len(POPULATED)]
    jlon = ((h % 2000) / 2000.0 - 0.5) * 40.0
    jlat = (((h >> 11) % 2000) / 2000.0 - 0.5) * 24.0
    return label, _clamp(clon + jlon, -179.9, 179.9), _clamp(clat + jlat, -85.0, 85.0)


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def lonlat_to_map(lon, lat):
    """Project lon/lat onto the WORLD_MAP grid -> (col, row)."""
    col = int((lon + 180.0) / 360.0 * (MAP_W - 1))
    row = int((90.0 - lat) / 180.0 * (MAP_H - 1))
    return _clampi(col, 0, MAP_W - 1), _clampi(row, 0, MAP_H - 1)


def _clampi(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def _ip_is_local(ip):
    return (ip.startswith("127.") or ip.startswith("::1") or ip == "0.0.0.0"
            or ip.startswith("10.") or ip.startswith("192.168.")
            or ip.startswith("169.254.") or ip.startswith("fe80")
            or _is_private_172(ip))


def _is_private_172(ip):
    if not ip.startswith("172."):
        return False
    try:
        second = int(ip.split(".")[1])
        return 16 <= second <= 31
    except (ValueError, IndexError):
        return False


def _split_hostport(token):
    """Split 'ip.port' or 'ip:port' or IPv6 into (ip, port)."""
    token = token.strip()
    if not token:
        return None, None
    # IPv6 like [::1]:443
    m = re.match(r"^\[([^\]]+)\]:(\d+|\*)$", token)
    if m:
        return m.group(1), m.group(2)
    # netstat macOS/linux style ip.port (last dot separates port)
    if "." in token and token.rsplit(".", 1)[-1].isdigit():
        ip, port = token.rsplit(".", 1)
        return ip, port
    if ":" in token and token.count(":") == 1:
        ip, port = token.rsplit(":", 1)
        return ip, port
    return token, None


def parse_netstat(text):
    """Parse `netstat -tn` output into ESTABLISHED connection dicts."""
    conns = []
    for line in text.splitlines():
        line = line.strip()
        if "ESTABLISHED" not in line:
            continue
        parts = line.split()
        if not parts or parts[0].lower() not in ("tcp", "tcp4", "tcp6"):
            continue
        # Find the two address tokens: usually parts[-4] local, parts[-3] remote
        # macOS: Proto Recv-Q Send-Q Local Foreign (state) ...
        # linux: Proto Recv-Q Send-Q Local Foreign State
        try:
            state_idx = next(i for i, p in enumerate(parts)
                             if p.upper() == "ESTABLISHED")
        except StopIteration:
            continue
        local_tok = parts[state_idx - 2]
        remote_tok = parts[state_idx - 1]
        lip, lport = _split_hostport(local_tok)
        rip, rport = _split_hostport(remote_tok)
        if not rip:
            continue
        conns.append({
            "local_ip": lip, "local_port": lport,
            "remote_ip": rip, "remote_port": rport,
            "state": "ESTABLISHED", "proc": None,
        })
    return conns


def parse_lsof(text):
    """Parse `lsof -i -n -P` output into connection dicts (with proc names)."""
    conns = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 9:
            continue
        if parts[0] == "COMMAND":
            continue
        proto = parts[7].upper() if len(parts) > 7 else ""
        if "TCP" not in proto:
            continue
        proc = parts[0]
        name = " ".join(parts[8:])
        # name like 192.168.1.5:52344->52.1.2.3:443 (ESTABLISHED)
        state = None
        sm = re.search(r"\(([A-Z]+)\)", name)
        if sm:
            state = sm.group(1)
        if state != "ESTABLISHED":
            continue
        arrow = re.search(r"(\S+)->(\S+)", name)
        if not arrow:
            continue
        lip, lport = _split_hostport(arrow.group(1))
        rip, rport = _split_hostport(arrow.group(2))
        if not rip:
            continue
        conns.append({
            "local_ip": lip, "local_port": lport,
            "remote_ip": rip, "remote_port": rport,
            "state": "ESTABLISHED", "proc": proc,
        })
    return conns


def _run_cmd(args, timeout=3):
    try:
        out = subprocess.run(args, capture_output=True, text=True,
                             timeout=timeout)
        return out.stdout or ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def gather_connections():
    """Gather real ESTABLISHED outbound connections from this host only.

    Prefers lsof (gives process names); merges in netstat. Returns list of
    connection dicts filtered to non-local remotes. Empty on failure.
    """
    lsof_conns = parse_lsof(_run_cmd(["lsof", "-i", "-n", "-P"]))
    net_conns = parse_netstat(_run_cmd(["netstat", "-tn"]))

    merged = {}
    for c in lsof_conns:
        key = (c["remote_ip"], c["remote_port"], c["local_port"])
        merged[key] = c
    for c in net_conns:
        key = (c["remote_ip"], c["remote_port"], c["local_port"])
        if key in merged:
            if not merged[key].get("proc"):
                merged[key]["proc"] = c.get("proc")
        else:
            merged[key] = c

    conns = [c for c in merged.values()
             if c["remote_ip"] and not _ip_is_local(c["remote_ip"])]
    return conns


def simulate_connections(n=None):
    """Synthesize believable outbound connections to cloud IPs."""
    if n is None:
        n = random.randint(15, 30)
    conns = []
    for _ in range(n):
        prefix = random.choice(SIM_TARGETS)
        octets = prefix.count(".")
        parts = prefix.rstrip(".").split(".")
        while len(parts) < 4:
            parts.append(str(random.randint(1, 254)))
        rip = ".".join(parts[:4])
        conns.append({
            "local_ip": "192.168.1." + str(random.randint(2, 254)),
            "local_port": str(random.randint(49152, 65535)),
            "remote_ip": rip,
            "remote_port": random.choice(["443", "443", "443", "80", "22", "5223"]),
            "state": "ESTABLISHED",
            "proc": random.choice(SIM_PROCS),
        })
    return conns


def conn_key(c):
    return (c.get("proc") or "?", c["remote_ip"], c["remote_port"])


def draw_line(stdscr, y0, x0, y1, x1, ch, attr, max_y, max_x, skip_ends=True):
    """Bresenham-ish line; returns list of (y,x) cells drawn (for pulses)."""
    cells = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    cx, cy = x0, y0
    guard = 0
    while guard < 4 * (max_y + max_x):
        guard += 1
        cells.append((cy, cx))
        if cx == x1 and cy == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            cx += sx
        if e2 < dx:
            err += dx
            cy += sy
    for i, (yy, xx) in enumerate(cells):
        if skip_ends and (i == 0 or i == len(cells) - 1):
            continue
        if 0 <= yy < max_y - 1 and 0 <= xx < max_x:
            try:
                stdscr.addstr(yy, xx, ch, attr)
            except curses.error:
                pass
    return cells


def run(stdscr, duration, frame_delay, refresh_interval, simulate):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    tracked = {}      # key -> connection state {..., first_seen, last_seen, seen}
    last_refresh = 0.0
    frame = 0

    def refresh_conns(now):
        if simulate:
            conns = simulate_connections()
            simd = True
        else:
            conns = gather_connections()
            simd = False
            if not conns:
                conns = simulate_connections()
                simd = True
        seen_keys = set()
        for c in conns:
            k = conn_key(c)
            seen_keys.add(k)
            if k in tracked:
                tracked[k].update({
                    "remote_port": c["remote_port"], "state": c["state"],
                    "last_seen": now, "alive": True,
                })
            else:
                label, lon, lat = geo_for_ip(c["remote_ip"])
                tracked[k] = {
                    "proc": c.get("proc") or "?",
                    "remote_ip": c["remote_ip"],
                    "remote_port": c["remote_port"],
                    "state": c["state"], "region": label,
                    "lon": lon, "lat": lat,
                    "first_seen": now, "last_seen": now,
                    "flash_until": now + 2.0, "alive": True,
                    "fade_until": None,
                }
        # mark connections no longer present as closing (fade)
        for k, t in list(tracked.items()):
            if k not in seen_keys and t.get("alive", True):
                t["alive"] = False
                t["fade_until"] = now + 2.5
        # drop fully faded
        for k in [k for k, t in tracked.items()
                  if not t.get("alive", True) and t.get("fade_until", 0) < now]:
            del tracked[k]
        return simd

    simd = refresh_conns(time.monotonic())
    last_refresh = time.monotonic()

    start = time.monotonic()
    while True:
        now = time.monotonic()
        if now - start >= duration:
            break
        frame += 1

        if now - last_refresh >= refresh_interval:
            simd = refresh_conns(now)
            last_refresh = now

        max_y, max_x = stdscr.getmaxyx()
        stdscr.erase()

        # Layout: map area top-left, table panel on the right.
        table_w = min(46, max(24, max_x // 3))
        map_area_w = max_x - table_w - 1
        # scale map into available area
        draw_w = min(MAP_W, max(10, map_area_w))
        draw_h = min(MAP_H, max(6, max_y - 2))

        def map_cell(col, row):
            """WORLD_MAP grid -> screen (y,x)."""
            x = int(col / (MAP_W - 1) * (draw_w - 1)) if MAP_W > 1 else 0
            y = int(row / (MAP_H - 1) * (draw_h - 1)) if MAP_H > 1 else 0
            return y, x

        # draw world silhouette
        for row in range(MAP_H):
            for col in range(MAP_W):
                ch = WORLD_MAP[row][col]
                if ch == "#":
                    y, x = map_cell(col, row)
                    if 0 <= y < max_y - 1 and 0 <= x < map_area_w:
                        try:
                            stdscr.addstr(y, x, ".",
                                          curses.color_pair(COLOR_MAP) | curses.A_DIM)
                        except curses.error:
                            pass

        # host location: center-ish (San Francisco-ish)
        hcol, hrow = lonlat_to_map(-100.0, 40.0)
        hy, hx = map_cell(hcol, hrow)

        active = [t for t in tracked.values() if t.get("alive", True)]

        # draw arcs + pulses to each remote endpoint
        for t in tracked.values():
            rcol, rrow = lonlat_to_map(t["lon"], t["lat"])
            ry, rx = map_cell(rcol, rrow)
            fading = not t.get("alive", True)
            arc_attr = curses.color_pair(COLOR_ARC) | curses.A_DIM
            if fading:
                arc_attr = curses.color_pair(COLOR_ARC) | curses.A_DIM
            cells = draw_line(stdscr, hy, hx, ry, rx, ":", arc_attr,
                              max_y, min(max_x, map_area_w + 1))
            # animated pulse traveling along the arc
            if not fading and len(cells) > 2:
                phase = (frame + hash(t["remote_ip"]) % 20) % max(1, len(cells))
                pos = phase
                if 0 < pos < len(cells) - 1:
                    py, px = cells[pos]
                    if 0 <= py < max_y - 1 and 0 <= px < map_area_w:
                        try:
                            stdscr.addstr(py, px, "*",
                                          curses.color_pair(COLOR_PULSE) | curses.A_BOLD)
                        except curses.error:
                            pass

        # draw remote nodes
        for t in tracked.values():
            rcol, rrow = lonlat_to_map(t["lon"], t["lat"])
            ry, rx = map_cell(rcol, rrow)
            fading = not t.get("alive", True)
            flashing = t.get("flash_until", 0) > now
            region_color = REGION_COLORS[abs(hash(t["region"])) % len(REGION_COLORS)]
            if fading:
                node_attr = curses.color_pair(COLOR_FADE) | curses.A_DIM
                nch = "x"
            elif flashing and frame % 2 == 0:
                node_attr = curses.color_pair(COLOR_FLASH) | curses.A_BOLD
                nch = "@"
            else:
                node_attr = curses.color_pair(region_color) | curses.A_BOLD
                nch = "o"
            if 0 <= ry < max_y - 1 and 0 <= rx < map_area_w:
                try:
                    stdscr.addstr(ry, rx, nch, node_attr)
                except curses.error:
                    pass

        # draw host marker on top
        if 0 <= hy < max_y - 1 and 0 <= hx < map_area_w:
            try:
                stdscr.addstr(hy, hx, "H",
                              curses.color_pair(COLOR_HOST) | curses.A_BOLD)
            except curses.error:
                pass

        # ---- table panel ----
        tx = map_area_w + 1
        try:
            stdscr.addstr(0, tx, "PROC        REMOTE            REGION"[:table_w],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass
        # sort by activity: alive first, then most recently seen
        rows = sorted(tracked.values(),
                      key=lambda t: (t.get("alive", True), t.get("last_seen", 0)),
                      reverse=True)
        line = 1
        for t in rows:
            if line >= max_y - 1:
                break
            fading = not t.get("alive", True)
            flashing = t.get("flash_until", 0) > now
            proc = (t["proc"] or "?")[:10].ljust(10)
            endpoint = f"{t['remote_ip']}:{t['remote_port']}"[:16].ljust(16)
            region = (t["region"] or "?")[:14]
            txt = f"{proc}  {endpoint}  {region}"[:table_w]
            if fading:
                attr = curses.color_pair(COLOR_FADE) | curses.A_DIM
            elif flashing:
                attr = curses.color_pair(COLOR_FLASH) | curses.A_BOLD
            else:
                region_color = REGION_COLORS[abs(hash(t["region"])) % len(REGION_COLORS)]
                attr = curses.color_pair(region_color)
            try:
                stdscr.addstr(line, tx, txt, attr)
            except curses.error:
                pass
            line += 1

        # ---- bottom info label ----
        n_live = len(active)
        tag = "  [SIMULATED]" if simd else ""
        info = f"connections  {n_live} live{tag}"
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key == ord("q") or key == ord("Q") or key == 27:
            return


def main(duration=30, frame_delay=0.15, refresh_interval=3.0, simulate=False):
    duration = float(duration)
    frame_delay = float(frame_delay)
    refresh_interval = float(refresh_interval)
    if isinstance(simulate, str):
        simulate = simulate.strip().lower() in ("1", "true", "yes", "y", "on")
    else:
        simulate = bool(simulate)
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, refresh_interval, simulate))


if __name__ == "__main__":
    main()
