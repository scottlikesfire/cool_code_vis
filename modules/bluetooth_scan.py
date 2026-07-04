import curses
import math
import random
import subprocess
import sys
import time


# Color pair indices
COLOR_STRONG = 1    # green (close / strong)
COLOR_MED = 2       # yellow (mid)
COLOR_WEAK = 3      # red (far / weak)
COLOR_LABEL = 4     # cyan (bottom label)
COLOR_DIM = 5       # dim (addresses)
COLOR_HEADER = 6    # magenta header / spinner
COLOR_RING = 7      # blue radar rings
COLOR_SWEEP = 8     # cyan sweep line
COLOR_FLASH = 9     # magenta new-device flash

BAR_RAMP = "▁▂▃▄▅▆▇█"
SPINNER = ["|", "/", "-", "\\"]

# RSSI bounds used for radius/quality mapping.
RSSI_NEAR = -40     # very close
RSSI_FAR = -95      # edge of range

# Device type -> single-char icon. Type keys are normalized lowercase.
TYPE_ICONS = {
    "headphones": "♪",
    "headset": "♪",
    "earbuds": "♪",
    "speaker": "♫",
    "keyboard": "⌨",
    "mouse": "◆",
    "trackpad": "▭",
    "phone": "☎",
    "watch": "⌚",
    "tablet": "▤",
    "computer": "▣",
    "health": "♥",
    "car": "⚙",
    "ble": "∙",
    "generic": "•",
}

# Names that hint at a device type when no explicit Minor Type is present.
_NAME_TYPE_HINTS = [
    ("airpods", "headphones"),
    ("buds", "earbuds"),
    ("headphone", "headphones"),
    ("headset", "headset"),
    ("beats", "headphones"),
    ("speaker", "speaker"),
    ("soundbar", "speaker"),
    ("mi band", "health"),
    ("band", "health"),
    ("watch", "watch"),
    ("keyboard", "keyboard"),
    ("mouse", "mouse"),
    ("trackpad", "trackpad"),
    ("iphone", "phone"),
    ("phone", "phone"),
    ("ipad", "tablet"),
    ("tablet", "tablet"),
    ("macbook", "computer"),
    ("mac ", "computer"),
    ("hft", "car"),
    ("honda", "car"),
    ("car", "car"),
]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_STRONG, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_MED, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_WEAK, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_DIM, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_HEADER, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_RING, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_SWEEP, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_FLASH, curses.COLOR_MAGENTA, -1)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def rssi_to_quality(rssi):
    """Map dBm (RSSI_FAR..RSSI_NEAR) to a 0..100 quality percentage."""
    span = float(RSSI_NEAR - RSSI_FAR)
    q = (rssi - RSSI_FAR) / span * 100.0
    return max(0, min(100, int(round(q))))


def rssi_to_radius(rssi):
    """Map RSSI to a normalized radar radius in [0.0, 1.0].

    Stronger signal (closer to RSSI_NEAR) -> smaller radius (nearer center).
    """
    q = rssi_to_quality(rssi)
    r = 1.0 - (q / 100.0)
    return max(0.0, min(1.0, r))


def address_to_angle(address):
    """Deterministically map an address string to an angle in [0, 2*pi)."""
    h = 0
    for ch in address:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return (h % 3600) / 3600.0 * 2.0 * math.pi


def signal_color(quality):
    """Pick a color pair from a 0..100 quality value."""
    if quality >= 66:
        return COLOR_STRONG
    if quality >= 33:
        return COLOR_MED
    return COLOR_WEAK


def signal_bar(quality, width, ramp=BAR_RAMP):
    """Build a signal bar of the given width from a 0..100 quality."""
    if width <= 0:
        return ""
    filled = int(round(quality / 100.0 * width))
    filled = max(0, min(width, filled))
    if filled == 0:
        return " " * width
    n = len(ramp)
    bar = ramp[-1] * (filled - 1)
    tip_idx = min(n - 1, int(quality / 100.0 * n))
    bar += ramp[tip_idx]
    bar += " " * (width - filled)
    return bar


def classify_type(name, minor_type=None):
    """Normalize a device to one of the TYPE_ICONS keys."""
    if minor_type:
        mt = minor_type.strip().lower()
        for key in TYPE_ICONS:
            if key in mt:
                return key
        if "head" in mt:
            return "headphones"
        if "pad" in mt:
            return "trackpad"
    n = (name or "").lower()
    for hint, key in _NAME_TYPE_HINTS:
        if hint in n:
            return key
    if n == "" or "ble device" in n:
        return "ble"
    return "generic"


def type_icon(dtype):
    return TYPE_ICONS.get(dtype, TYPE_ICONS["generic"])


# ---------------------------------------------------------------------------
# Parsers for real data sources
# ---------------------------------------------------------------------------

def parse_system_profiler(output):
    """Parse `system_profiler SPBluetoothDataType` output.

    Returns a list of device dicts:
        {name, address, rssi, connected, dtype}
    The controller block is skipped; devices live under the "Connected:"
    and "Not Connected:" sections. RSSI is present for some devices; if a
    device is connected we treat it as very strong signal.
    """
    devices = []
    lines = output.splitlines()

    # Indentation level of a section header ("Connected:"), used to detect
    # device-name lines (one level deeper) vs. attribute lines (two deeper).
    section = None          # "connected" / "not_connected" / None
    section_indent = None
    cur = None
    name_indent = None

    def _indent(s):
        return len(s) - len(s.lstrip(" "))

    def _flush():
        nonlocal cur
        if cur is not None and cur.get("address"):
            devices.append(cur)
        cur = None

    for raw in lines:
        if not raw.strip():
            continue
        stripped = raw.strip()
        indent = _indent(raw)

        low = stripped.lower().rstrip(":")
        if low in ("connected", "not connected", "paired", "not paired"):
            _flush()
            section = "connected" if low == "connected" else "other"
            section_indent = indent
            name_indent = None
            continue
        if low in ("bluetooth controller", "bluetooth"):
            _flush()
            section = None
            continue

        if section is None:
            continue

        # A device-name line sits one indent level below the section header
        # and ends with a colon; an attribute line is deeper and has "key: val".
        is_name = (
            stripped.endswith(":")
            and (name_indent is None or indent <= name_indent)
            and section_indent is not None
            and indent > section_indent
        )
        if is_name:
            _flush()
            name_indent = indent
            cur = {
                "name": stripped[:-1].strip(),
                "address": "",
                "rssi": None,
                "connected": (section == "connected"),
                "minor_type": None,
            }
            continue

        if cur is None:
            continue

        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip().lower()
            val = val.strip()
            if key == "address":
                cur["address"] = val
            elif key == "rssi":
                try:
                    cur["rssi"] = int(val.split()[0])
                except (ValueError, IndexError):
                    pass
            elif key == "minor type":
                cur["minor_type"] = val
    _flush()

    result = []
    for d in devices:
        if d["connected"] and d["rssi"] is None:
            rssi = -45
        elif d["rssi"] is None:
            rssi = -80
        else:
            rssi = d["rssi"]
        result.append({
            "name": d["name"],
            "address": d["address"],
            "rssi": rssi,
            "connected": d["connected"],
            "dtype": classify_type(d["name"], d["minor_type"]),
        })
    return result


def parse_bluetoothctl(output):
    """Parse `bluetoothctl devices` output lines like:

        Device AA:BB:CC:DD:EE:FF Some Name
    Returns device dicts. RSSI is unknown here -> assigned a mid default.
    """
    devices = []
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("Device "):
            continue
        parts = line.split(" ", 2)
        if len(parts) < 2:
            continue
        address = parts[1].strip()
        name = parts[2].strip() if len(parts) >= 3 else ""
        # Some entries repeat the address as the "name" when unresolved.
        if name.replace("-", ":") == address:
            name = ""
        devices.append({
            "name": name,
            "address": address,
            "rssi": -70,
            "connected": False,
            "dtype": classify_type(name, None),
        })
    return devices


# ---------------------------------------------------------------------------
# Simulated data
# ---------------------------------------------------------------------------

_SIM_POOL = [
    ("AirPods Pro", "headphones", -55),
    ("Galaxy Buds", "earbuds", -62),
    ("Mi Band 7", "health", -70),
    ("Honda HFT", "car", -78),
    ("Sony WH-1000XM5", "headphones", -58),
    ("JBL Flip 6", "speaker", -66),
    ("MX Master 3", "mouse", -50),
    ("Magic Keyboard", "keyboard", -48),
    ("Apple Watch", "watch", -60),
    ("iPhone", "phone", -64),
    ("Tile Tracker", "generic", -85),
    ("BLE Device", "ble", -88),
    ("Fitbit Charge", "health", -74),
    ("Bose QC45", "headphones", -69),
]


def _rand_address():
    return ":".join("%02X" % random.randint(0, 255) for _ in range(6))


def make_simulated(n=None):
    """Generate ~6-14 believable devices, some name-less by address."""
    if n is None:
        n = random.randint(6, 14)
    pool = list(_SIM_POOL)
    random.shuffle(pool)
    devices = []
    for i in range(n):
        if i < len(pool):
            name, dtype, base = pool[i]
        else:
            name, dtype, base = "BLE Device", "ble", random.randint(-90, -78)
        addr = _rand_address()
        nameless = random.random() < 0.18
        rssi = base + random.randint(-6, 6)
        rssi = max(RSSI_FAR, min(RSSI_NEAR, rssi))
        devices.append({
            "name": "" if nameless else name,
            "address": addr,
            "rssi": rssi,
            "connected": random.random() < 0.15,
            "dtype": "ble" if nameless else dtype,
        })
    return devices


def fluctuate(devices, amount=2):
    """Gently jitter RSSI values frame to frame, clamped to range."""
    for d in devices:
        d["rssi"] += random.randint(-amount, amount)
        d["rssi"] = max(RSSI_FAR, min(RSSI_NEAR, d["rssi"]))
    return devices


# ---------------------------------------------------------------------------
# Real data acquisition (passive discovery only; no pairing/attacks/sudo)
# ---------------------------------------------------------------------------

def _run_cmd(args, timeout=8):
    try:
        out = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout)
        if out.returncode == 0:
            return out.stdout
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def scan_macos():
    """macOS: parse system_profiler for controller + known/nearby devices."""
    out = _run_cmd(["system_profiler", "SPBluetoothDataType"], timeout=12)
    if not out:
        return None
    devs = parse_system_profiler(out)
    return devs or None


def scan_bluetoothctl():
    """Linux: passive listing via bluetoothctl (needs bluetooth service).

    Prefer an active-but-passive short scan, falling back to the cached
    device list. No pairing/connecting is attempted.
    """
    out = _run_cmd(["bluetoothctl", "--timeout", "5", "scan", "on"],
                   timeout=8)
    devs = parse_bluetoothctl(out) if out else []
    if not devs:
        out = _run_cmd(["bluetoothctl", "devices"], timeout=6)
        devs = parse_bluetoothctl(out) if out else []
    return devs or None


def acquire_devices(simulate):
    """Return (devices, source_tag). source in {'macos','bluetoothctl','sim'}."""
    if not simulate:
        if sys.platform == "darwin":
            devs = scan_macos()
            if devs and len(devs) >= 1:
                return devs, "macos"
        elif sys.platform.startswith("linux"):
            devs = scan_bluetoothctl()
            if devs and len(devs) >= 1:
                return devs, "bluetoothctl"
    return make_simulated(), "sim"


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _merge_devices(old, new):
    """Merge a freshly-acquired list into the existing one, keyed by address.

    Preserves per-device animation state (flash counter). Newly seen
    addresses get a flash so they visibly pop on discovery.
    """
    by_addr = {d["address"]: d for d in old}
    merged = []
    for d in new:
        prev = by_addr.get(d["address"])
        if prev is not None:
            prev["name"] = d["name"] or prev["name"]
            prev["rssi"] = d["rssi"]
            prev["connected"] = d["connected"]
            prev["dtype"] = d["dtype"]
            merged.append(prev)
        else:
            d = dict(d)
            d["flash"] = 12
            merged.append(d)
    return merged


def _draw_radar(stdscr, devices, cx, cy, rx, ry, sweep_angle, max_y, max_x):
    """Draw concentric rings + sweep + device blips on the left panel."""
    # Concentric range rings (3 rings).
    steps = 120
    for ring in (0.34, 0.67, 1.0):
        for s in range(steps):
            a = s / steps * 2.0 * math.pi
            xi = int(round(cx + math.cos(a) * rx * ring))
            yi = int(round(cy + math.sin(a) * ry * ring))
            if 0 <= xi < max_x and 0 <= yi < max_y - 1:
                try:
                    stdscr.addstr(yi, xi, "·", curses.color_pair(COLOR_RING))
                except curses.error:
                    pass

    # Sweep line from center outward.
    for t in range(0, 100):
        f = t / 100.0
        xi = int(round(cx + math.cos(sweep_angle) * rx * f))
        yi = int(round(cy + math.sin(sweep_angle) * ry * f))
        if 0 <= xi < max_x and 0 <= yi < max_y - 1:
            try:
                stdscr.addstr(yi, xi, "/" if math.sin(sweep_angle) < 0 else "\\",
                              curses.color_pair(COLOR_SWEEP) | curses.A_BOLD)
            except curses.error:
                pass

    # Center marker.
    if 0 <= int(cx) < max_x and 0 <= int(cy) < max_y - 1:
        try:
            stdscr.addstr(int(cy), int(cx), "+",
                          curses.color_pair(COLOR_SWEEP) | curses.A_BOLD)
        except curses.error:
            pass

    # Device blips.
    for d in devices:
        ang = address_to_angle(d["address"])
        rad = rssi_to_radius(d["rssi"])
        xi = int(round(cx + math.cos(ang) * rx * rad))
        yi = int(round(cy + math.sin(ang) * ry * rad))
        if not (0 <= xi < max_x and 0 <= yi < max_y - 1):
            continue
        q = rssi_to_quality(d["rssi"])
        # Brighten when the sweep beam is near this device's angle.
        da = abs((ang - sweep_angle + math.pi) % (2 * math.pi) - math.pi)
        near_beam = da < 0.35
        attr = curses.color_pair(signal_color(q))
        if d.get("flash", 0) > 0:
            attr = curses.color_pair(COLOR_FLASH) | curses.A_BOLD | curses.A_REVERSE
        elif near_beam:
            attr |= curses.A_BOLD | curses.A_REVERSE
        else:
            attr |= curses.A_BOLD
        try:
            stdscr.addstr(yi, xi, type_icon(d["dtype"]), attr)
        except curses.error:
            pass


def _draw_list(stdscr, devices, x0, top, max_y, max_x):
    """Draw the sorted device list on the right panel."""
    width = max_x - x0 - 1
    if width < 12:
        return
    hdr = "DEVICE            RSSI  SIGNAL"
    try:
        stdscr.addstr(top, x0, hdr[:width],
                      curses.color_pair(COLOR_DIM) | curses.A_DIM)
    except curses.error:
        pass
    row = top + 1
    bar_width = min(10, max(3, width - 24))
    for d in devices:
        if row >= max_y - 1:
            break
        q = rssi_to_quality(d["rssi"])
        scol = signal_color(q)
        name = d["name"] if d["name"] else "(%s)" % d["address"][:8]
        icon = type_icon(d["dtype"])
        label = f"{icon} {name}"
        name_attr = curses.A_BOLD
        if d.get("flash", 0) > 0:
            name_attr = curses.color_pair(COLOR_FLASH) | curses.A_BOLD
        try:
            stdscr.addstr(row, x0, label[:16].ljust(16), name_attr)
        except curses.error:
            pass
        try:
            stdscr.addstr(row, x0 + 17, f"{d['rssi']:>4}",
                          curses.color_pair(scol))
        except curses.error:
            pass
        bar = signal_bar(q, bar_width)
        try:
            stdscr.addstr(row, x0 + 22, bar,
                          curses.color_pair(scol) | curses.A_BOLD)
        except curses.error:
            pass
        # Address line (dim), if there is room.
        addr_x = x0 + 23 + bar_width
        if addr_x < max_x - 6:
            conn = " •LIVE" if d["connected"] else ""
            try:
                stdscr.addstr(row, addr_x,
                              (d["address"] + conn)[:max(0, max_x - addr_x - 1)],
                              curses.color_pair(COLOR_DIM) | curses.A_DIM)
            except curses.error:
                pass
        row += 1


def run(stdscr, duration, frame_delay, refresh_interval, simulate):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    devices, source = acquire_devices(simulate)
    devices = _merge_devices([], devices)
    simulated = source == "sim"

    start = time.monotonic()
    last_refresh = start
    frame = 0
    sweep_angle = 0.0

    while True:
        now = time.monotonic()
        if now - start >= duration:
            break

        if now - last_refresh >= refresh_interval:
            new_devs, source = acquire_devices(simulate)
            devices = _merge_devices(devices, new_devs)
            simulated = source == "sim"
            last_refresh = now

        # Animate signal + flash decay for a live feel.
        fluctuate(devices, amount=2 if simulated else 1)
        for d in devices:
            if d.get("flash", 0) > 0:
                d["flash"] -= 1

        devices_sorted = sorted(devices, key=lambda d: d["rssi"], reverse=True)

        max_y, max_x = stdscr.getmaxyx()
        stdscr.erase()

        spin = SPINNER[frame % len(SPINNER)]
        header = f"{spin} scanning BLE / Bluetooth  ({len(devices)} found)"
        try:
            stdscr.addstr(0, 2, header[:max(0, max_x - 4)],
                          curses.color_pair(COLOR_HEADER) | curses.A_BOLD)
        except curses.error:
            pass

        # Layout: radar on the left ~half, list on the right.
        radar_w = max(10, min(max_x // 2, max_x - 30))
        cx = radar_w / 2.0 + 1
        cy = (max_y - 1) / 2.0 + 1
        rx = max(3.0, radar_w / 2.0 - 2)
        ry = max(2.0, (max_y - 2) / 2.0 - 1)

        _draw_radar(stdscr, devices, cx, cy, rx, ry, sweep_angle,
                    max_y, max_x)
        _draw_list(stdscr, devices_sorted, radar_w + 2, 2, max_y, max_x)

        # Bottom label.
        tag = "  [SIMULATED]" if simulated else ""
        label = f"bluetooth_scan  {len(devices)} devices{tag}"
        try:
            stdscr.addstr(max_y - 1, 2, label[:max(0, max_x - 4)],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        frame += 1
        sweep_angle = (sweep_angle + 0.22) % (2.0 * math.pi)
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def main(duration=30, frame_delay=0.1, refresh_interval=5, simulate=False):
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
