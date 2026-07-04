import curses
import math
import random
import re
import subprocess
import time


# Color pair indices
COLOR_LABEL = 1
COLOR_ROUTER = 2
COLOR_NEW = 3
COLOR_FADE = 4
COLOR_DIM = 5
COLOR_LINE = 6
COLOR_APPLE = 7
COLOR_IOT = 8
COLOR_SAMSUNG = 9
COLOR_UNKNOWN = 10

SPINNER = ["|", "/", "-", "\\"]

# Small OUI prefix -> vendor table (first 3 MAC octets, lowercase, colon-joined)
OUI_TABLE = {
    "3c:22:fb": "Apple", "a4:83:e7": "Apple", "f0:18:98": "Apple",
    "ac:bc:32": "Apple", "1c:36:bb": "Apple", "dc:a9:04": "Apple",
    "24:0a:c4": "Espressif", "3c:71:bf": "Espressif", "84:0d:8e": "Espressif",
    "b4:e6:2d": "Espressif", "24:5a:4c": "Ubiquiti", "78:8a:20": "Ubiquiti",
    "68:d7:9a": "Ubiquiti", "fc:ec:da": "Ubiquiti", "b8:27:eb": "Raspberry Pi",
    "dc:a6:32": "Raspberry Pi", "e4:5f:01": "Raspberry Pi",
    "78:bd:bc": "Samsung", "5c:0a:5b": "Samsung", "8c:77:12": "Samsung",
    "f4:f5:d8": "Google", "1c:f2:9a": "Google", "3c:5a:b4": "Google",
    "44:65:0d": "Amazon", "fc:65:de": "Amazon", "68:37:e9": "Amazon",
    "b8:e9:37": "Sonos", "94:9f:3e": "Sonos", "00:1b:21": "Intel",
    "3c:fd:fe": "Intel", "a0:88:b4": "Intel", "00:0c:29": "VMware",
    "52:54:00": "QEMU", "d8:0d:17": "TP-Link", "50:c7:bf": "TP-Link",
    "b0:be:76": "TP-Link",
}

# vendor -> color pair
VENDOR_COLOR = {
    "Apple": COLOR_APPLE,
    "Espressif": COLOR_IOT,
    "Sonos": COLOR_IOT,
    "Amazon": COLOR_IOT,
    "Google": COLOR_IOT,
    "Raspberry Pi": COLOR_IOT,
    "Samsung": COLOR_SAMSUNG,
    "Ubiquiti": COLOR_ROUTER,
    "TP-Link": COLOR_ROUTER,
    "Intel": COLOR_APPLE,
}


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_ROUTER, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_NEW, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_FADE, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_DIM, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_LINE, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_APPLE, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_IOT, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_SAMSUNG, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_UNKNOWN, curses.COLOR_WHITE, -1)


def lookup_vendor(mac):
    """Return vendor name for a MAC address using the OUI table, else 'unknown'."""
    if not mac:
        return "unknown"
    parts = mac.lower().split(":")
    if len(parts) < 3:
        return "unknown"
    prefix = ":".join(parts[:3])
    return OUI_TABLE.get(prefix, "unknown")


def normalize_mac(mac):
    """Normalize a MAC to colon-joined, zero-padded 2-hex-digit octets."""
    parts = re.split(r"[:\-]", mac)
    out = []
    for p in parts:
        p = p.strip()
        if p == "":
            continue
        out.append(p.zfill(2).lower())
    return ":".join(out)


# macOS: hostname (192.168.1.1) at 1e:6a:1b:31:d0:2b on en10 ifscope [ethernet]
#        ? (192.168.1.5) at (incomplete) on en0 ...
ARP_RE = re.compile(
    r"^(?P<host>\S+)\s+\((?P<ip>[\d.]+)\)\s+at\s+(?P<mac>[0-9a-fA-F:]+|\(incomplete\))"
    r"(?:\s+on\s+(?P<iface>\S+))?"
)

# Linux ip neigh: 192.168.1.1 dev eth0 lladdr 1e:6a:1b:31:d0:2b REACHABLE
NEIGH_RE = re.compile(
    r"^(?P<ip>[\d.]+)\s+dev\s+(?P<iface>\S+)(?:\s+lladdr\s+(?P<mac>[0-9a-fA-F:]+))?"
)


def parse_arp(text):
    """Parse `arp -a` (macOS/BSD) or `ip neigh` (Linux) output into device records."""
    devices = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = ARP_RE.match(line)
        if m:
            mac = m.group("mac")
            if not mac or mac == "(incomplete)":
                continue
            host = m.group("host")
            if host in ("?", ""):
                host = "?"
            devices.append({
                "hostname": host,
                "ip": m.group("ip"),
                "mac": normalize_mac(mac),
                "iface": m.group("iface") or "",
            })
            continue
        m = NEIGH_RE.match(line)
        if m:
            mac = m.group("mac")
            if not mac:
                continue
            devices.append({
                "hostname": "?",
                "ip": m.group("ip"),
                "mac": normalize_mac(mac),
                "iface": m.group("iface") or "",
            })
    return devices


def scan_arp():
    """Run the local arp/ip-neigh command. Returns device list or [] on failure."""
    for cmd in (["arp", "-a"], ["ip", "neigh"]):
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        except (OSError, subprocess.SubprocessError):
            continue
        if res.returncode == 0 and res.stdout.strip():
            devices = parse_arp(res.stdout)
            if devices:
                return devices
    return []


FAKE_NAMES = [
    ("router", "Ubiquiti"), ("gateway", "TP-Link"),
    ("Scotts-iPhone", "Apple"), ("Scotts-MacBook-Pro", "Apple"),
    ("iPad", "Apple"), ("Kitchen-Echo", "Amazon"),
    ("living-room-nest", "Google"), ("sonos-play", "Sonos"),
    ("esp32-sensor", "Espressif"), ("esp-lamp", "Espressif"),
    ("raspberrypi", "Raspberry Pi"), ("pi-hole", "Raspberry Pi"),
    ("Galaxy-S23", "Samsung"), ("smart-tv", "Samsung"),
    ("desktop-pc", "Intel"), ("thermostat", "Espressif"),
    ("doorbell", "Amazon"), ("chromecast", "Google"),
    ("printer", "unknown"), ("nas-server", "unknown"),
]


def _fake_mac(vendor):
    prefixes = [p for p, v in OUI_TABLE.items() if v == vendor]
    if prefixes:
        prefix = random.choice(prefixes)
    else:
        prefix = "%02x:%02x:%02x" % (
            random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    tail = "%02x:%02x:%02x" % (
        random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    return prefix + ":" + tail


def simulate_devices(subnet="192.168.1"):
    """Generate ~12-20 believable fake LAN devices."""
    n = random.randint(12, 20)
    chosen = FAKE_NAMES[:2] + random.sample(FAKE_NAMES[2:], min(n - 2, len(FAKE_NAMES) - 2))
    used_ips = set()
    devices = []
    # router at .1
    for i, (name, vendor) in enumerate(chosen):
        if i == 0:
            last = 1
        else:
            last = random.randint(2, 254)
            while last in used_ips:
                last = random.randint(2, 254)
        used_ips.add(last)
        devices.append({
            "hostname": name,
            "ip": "%s.%d" % (subnet, last),
            "mac": _fake_mac(vendor),
            "iface": "en0",
        })
    return devices


def ip_key(ip):
    """Sortable numeric key for an IPv4 string; huge value if unparseable."""
    try:
        return tuple(int(p) for p in ip.split("."))
    except (ValueError, AttributeError):
        return (999, 999, 999, 999)


def subnet_of(devices):
    """Derive a /24-ish subnet label from the device IPs."""
    for d in devices:
        parts = d["ip"].split(".")
        if len(parts) == 4:
            return ".".join(parts[:3]) + ".0/24"
    return "unknown"


def pick_router(devices):
    """Choose the gateway node: named like a router, else the lowest IP."""
    if not devices:
        return None
    for d in devices:
        h = d["hostname"].lower()
        if "router" in h or "gateway" in h or h.endswith(".1"):
            return d
    for d in devices:
        if d["ip"].endswith(".1"):
            return d
    return min(devices, key=lambda d: ip_key(d["ip"]))


def draw_line(stdscr, y0, x0, y1, x1, attr, max_y, max_x, phase):
    """Draw a pulsing ascii line from (y0,x0) to (y1,x1)."""
    dy = y1 - y0
    dx = x1 - x0
    steps = int(max(abs(dy), abs(dx)))
    if steps == 0:
        return
    if abs(dx) > abs(dy) * 2:
        ch = "-"
    elif abs(dy) > abs(dx) * 2:
        ch = "|"
    elif (dx > 0) == (dy > 0):
        ch = "\\"
    else:
        ch = "/"
    for i in range(1, steps):
        t = i / steps
        yy = int(round(y0 + dy * t))
        xx = int(round(x0 + dx * t))
        if not (0 <= yy < max_y - 1 and 0 <= xx < max_x):
            continue
        # pulse: a bright dot travels along the line
        pulse = (i + phase) % max(4, steps // 2)
        a = attr
        if pulse == 0:
            a = curses.color_pair(COLOR_NEW) | curses.A_BOLD
        try:
            stdscr.addstr(yy, xx, ch, a)
        except curses.error:
            pass


def run(stdscr, duration, frame_delay, refresh_interval, simulate):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    def do_scan():
        if simulate:
            return simulate_devices()
        devs = scan_arp()
        if not devs:
            return simulate_devices()
        return devs

    using_sim = simulate
    devices = do_scan()
    if not simulate and not scan_arp():
        using_sim = True
    known = {d["mac"]: d for d in devices}
    # per-mac animation state: appear time / departure time
    anim = {mac: {"born": time.monotonic(), "gone": None} for mac in known}
    event_log = []  # (timestamp_str, text)

    def log_event(text):
        ts = time.strftime("%H:%M:%S")
        event_log.append((ts, text))
        if len(event_log) > 200:
            del event_log[:100]

    log_event("scan started")

    start = time.monotonic()
    last_scan = start
    frame = 0
    while True:
        now = time.monotonic()
        if now - start >= duration:
            break

        # periodic rescan + diff
        if now - last_scan >= refresh_interval:
            last_scan = now
            new_devices = do_scan()
            new_macs = {d["mac"] for d in new_devices}
            old_macs = set(known.keys())
            for d in new_devices:
                if d["mac"] not in known:
                    anim[d["mac"]] = {"born": now, "gone": None}
                    log_event("JOIN  %s (%s)" % (d["ip"], d["hostname"]))
                known[d["mac"]] = d
            for mac in old_macs - new_macs:
                if anim.get(mac, {}).get("gone") is None:
                    anim.setdefault(mac, {"born": now})["gone"] = now
                    d = known.get(mac, {})
                    log_event("LEAVE %s (%s)" % (d.get("ip", "?"), d.get("hostname", "?")))

        # prune devices whose fade-out finished
        for mac in list(known.keys()):
            st = anim.get(mac, {})
            if st.get("gone") is not None and now - st["gone"] > 2.0:
                del known[mac]

        devices = list(known.values())
        devices.sort(key=lambda d: ip_key(d["ip"]))
        router = pick_router(devices)
        subnet = subnet_of(devices)

        max_y, max_x = stdscr.getmaxyx()
        stdscr.erase()

        # right-hand recon panel width
        panel_w = min(34, max(20, max_x // 3))
        map_w = max_x - panel_w - 1
        cy = (max_y - 1) // 2
        cx = map_w // 2

        others = [d for d in devices if d is not router]
        ring = max(4, min(cy - 2, map_w // 4))
        # place router center; others on an ellipse
        positions = {}
        if router:
            positions[router["mac"]] = (cy, cx)
        na = max(1, len(others))
        for i, d in enumerate(others):
            ang = 2 * math.pi * i / na
            ry = ring
            rx = int(ring * 1.9)
            py = int(round(cy + ry * math.sin(ang)))
            px = int(round(cx + rx * math.cos(ang)))
            py = max(1, min(max_y - 3, py))
            px = max(1, min(map_w - 2, px))
            positions[d["mac"]] = (py, px)

        # draw connection lines router -> each device
        if router:
            ry, rx = positions[router["mac"]]
            for d in others:
                py, px = positions[d["mac"]]
                draw_line(stdscr, ry, rx, py, px,
                          curses.color_pair(COLOR_LINE), max_y, map_w, frame)

        # draw nodes
        for d in devices:
            if d["mac"] not in positions:
                continue
            py, px = positions[d["mac"]]
            vendor = lookup_vendor(d["mac"])
            st = anim.get(d["mac"], {})
            is_router = d is router
            if st.get("gone") is not None:
                attr = curses.color_pair(COLOR_FADE)
            elif now - st.get("born", 0) < 1.5:
                # flash bright green when new
                attr = curses.color_pair(COLOR_NEW) | (
                    curses.A_BOLD if frame % 2 == 0 else 0)
            elif is_router:
                attr = curses.color_pair(COLOR_ROUTER) | curses.A_BOLD
            else:
                attr = curses.color_pair(VENDOR_COLOR.get(vendor, COLOR_UNKNOWN))

            host = d["hostname"][:16]
            if is_router:
                label = "[*%s %s]" % (host, d["ip"])
            else:
                label = "[%s %s]" % (host, d["ip"])
            x0 = max(0, px - len(label) // 2)
            try:
                stdscr.addstr(py, x0, label[:map_w - x0], attr)
            except curses.error:
                pass
            # mac dim + vendor colored on line below
            mac_short = d["mac"]
            vattr = curses.color_pair(VENDOR_COLOR.get(vendor, COLOR_UNKNOWN))
            sub = "%s %s" % (mac_short, vendor)
            try:
                stdscr.addstr(py + 1, x0, mac_short[:map_w - x0],
                              curses.color_pair(COLOR_DIM))
                vx = x0 + len(mac_short) + 1
                if vx < map_w:
                    stdscr.addstr(py + 1, vx, vendor[:map_w - vx], vattr)
            except curses.error:
                pass

        # ---- recon side panel ----
        px0 = max_x - panel_w
        spin = SPINNER[frame % len(SPINNER)]
        active = sum(1 for m in known if anim.get(m, {}).get("gone") is None)
        panel_lines = [
            "%s scanning..." % spin,
            "hosts:  %d" % active,
            "subnet: %s" % subnet,
            "iface:  %s" % (devices[0]["iface"] if devices else "-"),
            "-" * (panel_w - 1),
            "EVENTS:",
        ]
        for ts, text in event_log[-(max_y - len(panel_lines) - 2):]:
            panel_lines.append("%s %s" % (ts, text))

        for i, line in enumerate(panel_lines):
            if i >= max_y - 1:
                break
            a = curses.color_pair(COLOR_LABEL)
            if line.startswith(SPINNER[frame % len(SPINNER)]) or line == "EVENTS:":
                a |= curses.A_BOLD
            if " JOIN " in line or line[9:].startswith("JOIN"):
                a = curses.color_pair(COLOR_NEW)
            elif " LEAVE " in line or line[9:].startswith("LEAVE"):
                a = curses.color_pair(COLOR_FADE)
            try:
                stdscr.addstr(i, px0, line[:panel_w - 1], a)
            except curses.error:
                pass

        # ---- bottom label ----
        sim_tag = "  [SIMULATED]" if using_sim else ""
        info = "netmap  %d hosts  subnet %s%s  [q]uit" % (
            active, subnet, sim_tag)
        try:
            stdscr.addstr(max_y - 1, 2, info[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        frame += 1
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def _truthy(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "y", "on")
    return bool(v)


def main(duration=30, frame_delay=0.1, refresh_interval=4.0, simulate=False):
    duration = float(duration)
    frame_delay = float(frame_delay)
    refresh_interval = float(refresh_interval)
    simulate = _truthy(simulate)
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, refresh_interval, simulate))


if __name__ == "__main__":
    main()
