import curses
import random
import subprocess
import sys
import time


# Color pair indices
COLOR_STRONG = 1   # green
COLOR_MED = 2      # yellow
COLOR_WEAK = 3     # red
COLOR_LABEL = 4    # cyan (bottom label)
COLOR_DIM = 5      # dim gray-ish (BSSID)
COLOR_SECURE = 6   # green (WPA)
COLOR_INSECURE = 7  # red (Open)
COLOR_HEADER = 8   # magenta header

BAR_RAMP = "▁▂▃▄▅▆▇█"
ASCII_RAMP = ".:-=+*#@"
SPINNER = ["|", "/", "-", "\\"]

# 2.4 GHz channels + common 5 GHz channels
CHANNELS_24 = [1, 6, 11]
CHANNELS_5 = [36, 44, 149]
ALL_CHANNELS = CHANNELS_24 + CHANNELS_5

SSID_POOL = [
    "linksys", "NETGEAR", "xfinitywifi", "ATT-WiFi", "HOME-2G",
    "eero", "Google Nest", "TP-Link_5G", "Starbucks WiFi", "FBI Surveillance Van",
    "Pretty Fly for a WiFi", "The LAN Before Time", "Vault-Tec", "Skynet",
    "NSA_Honeypot", "Loading...", "It Hurts When IP",
]
SECURITY_POOL = ["WPA2", "WPA3", "WPA2", "WPA2", "Open"]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_STRONG, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_MED, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_WEAK, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_DIM, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_SECURE, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_INSECURE, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_HEADER, curses.COLOR_MAGENTA, -1)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def signal_to_rssi(signal):
    """nmcli SIGNAL is 0..100 quality; map to an approximate dBm (-100..-30)."""
    signal = max(0, min(100, int(signal)))
    return int(-100 + (signal / 100.0) * 70)


def rssi_to_quality(rssi):
    """Map dBm (-90..-30) to a 0..100 quality percentage."""
    q = (rssi + 90) / 60.0 * 100.0
    return max(0, min(100, int(q)))


def signal_color(quality):
    """Pick a color pair from a 0..100 quality value."""
    if quality >= 66:
        return COLOR_STRONG
    if quality >= 33:
        return COLOR_MED
    return COLOR_WEAK


def signal_bar(quality, width, ramp=BAR_RAMP):
    """Build a signal bar string of the given width from a 0..100 quality."""
    if width <= 0:
        return ""
    filled = int(round(quality / 100.0 * width))
    filled = max(0, min(width, filled))
    if filled == 0:
        return ramp[0] * width if False else " " * width
    # Use graded ramp characters so the bar has texture near its tip.
    n = len(ramp)
    bar = ramp[-1] * (filled - 1)
    # tip character reflects the fractional intensity
    tip_idx = min(n - 1, int(quality / 100.0 * n))
    bar += ramp[tip_idx]
    bar += " " * (width - filled)
    return bar


def _unescape_bssid(raw):
    """nmcli escapes the colons in a BSSID as '\\:' -> restore them."""
    return raw.replace("\\:", ":")


def parse_nmcli(output):
    """Parse `nmcli -t -f SSID,BSSID,CHAN,SIGNAL,SECURITY dev wifi list` output.

    Terse (-t) output is colon separated; nmcli escapes literal colons inside
    fields (notably the BSSID) as '\\:'. We split on unescaped colons.
    Returns a list of network dicts.
    """
    nets = []
    for line in output.splitlines():
        line = line.rstrip("\n")
        if not line.strip():
            continue
        # Split on colons that are not escaped by a backslash.
        fields = []
        cur = []
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "\\" and i + 1 < len(line):
                cur.append(line[i:i + 2])
                i += 2
                continue
            if ch == ":":
                fields.append("".join(cur))
                cur = []
                i += 1
                continue
            cur.append(ch)
            i += 1
        fields.append("".join(cur))

        if len(fields) < 5:
            continue
        ssid_raw = fields[0]
        bssid = _unescape_bssid(fields[1])
        chan = fields[2]
        signal = fields[3]
        security = ":".join(fields[4:]) if len(fields) > 5 else fields[4]

        ssid = ssid_raw.replace("\\:", ":")
        hidden = ssid == ""
        try:
            chan_i = int(chan)
        except ValueError:
            chan_i = 0
        try:
            sig_i = int(signal)
        except ValueError:
            sig_i = 0

        sec = security.strip()
        if sec == "" or sec == "--":
            sec = "Open"
        else:
            # nmcli may report e.g. "WPA2 802.1X"; keep first token-ish label.
            if "WPA3" in sec:
                sec = "WPA3"
            elif "WPA2" in sec:
                sec = "WPA2"
            elif "WPA1" in sec or "WPA" in sec:
                sec = "WPA"
            elif "WEP" in sec:
                sec = "WEP"

        nets.append({
            "ssid": "<hidden>" if hidden else ssid,
            "hidden": hidden,
            "bssid": bssid,
            "chan": chan_i,
            "rssi": signal_to_rssi(sig_i),
            "security": sec,
        })
    return nets


def _rand_bssid():
    return ":".join("%02X" % random.randint(0, 255) for _ in range(6))


def make_simulated(n=None):
    """Generate ~8-15 believable networks."""
    if n is None:
        n = random.randint(8, 15)
    names = random.sample(SSID_POOL, min(n, len(SSID_POOL)))
    nets = []
    for i in range(n):
        if i < len(names):
            name = names[i]
        else:
            name = "AP_%04X" % random.randint(0, 0xFFFF)
        hidden = random.random() < 0.12
        chan = random.choice(ALL_CHANNELS)
        rssi = random.randint(-90, -30)
        sec = random.choice(SECURITY_POOL)
        nets.append({
            "ssid": "<hidden>" if hidden else name,
            "hidden": hidden,
            "bssid": _rand_bssid(),
            "chan": chan,
            "rssi": rssi,
            "security": sec,
        })
    return nets


def fluctuate(nets, amount=2):
    """Gently jitter RSSI values frame to frame, clamped to -95..-25."""
    for net in nets:
        net["rssi"] += random.randint(-amount, amount)
        net["rssi"] = max(-95, min(-25, net["rssi"]))
    return nets


def channel_histogram(nets):
    """Return {channel: count} for occupancy display."""
    hist = {}
    for net in nets:
        hist[net["chan"]] = hist.get(net["chan"], 0) + 1
    return hist


# ---------------------------------------------------------------------------
# Real data sources (passive scan only; no sudo, no association/attacks)
# ---------------------------------------------------------------------------

def _run_cmd(args, timeout=6):
    try:
        out = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout)
        if out.returncode == 0:
            return out.stdout
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def scan_nmcli():
    """Linux: passive listing via NetworkManager (no scan trigger privileges)."""
    out = _run_cmd(
        ["nmcli", "-t", "-f", "SSID,BSSID,CHAN,SIGNAL,SECURITY",
         "dev", "wifi", "list"])
    if not out:
        return None
    nets = parse_nmcli(out)
    return nets or None


def scan_macos_current():
    """macOS: best-effort read of the *current* network via system_profiler.

    Full nearby scanning needs sudo/wdutil on current macOS, so this only
    returns the associated network (if any) as a single-row hint.
    """
    out = _run_cmd(["system_profiler", "SPAirPortDataType"], timeout=12)
    if not out:
        return None
    lines = out.splitlines()
    current = None
    in_current = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("Current Network Information"):
            in_current = True
            continue
        if in_current:
            # First non-empty indented line naming the network ends with ':'
            if stripped.endswith(":") and not stripped.startswith("PHY"):
                ssid = stripped[:-1].strip()
                current = {
                    "ssid": ssid or "<current>",
                    "hidden": False,
                    "bssid": "--",
                    "chan": 0,
                    "rssi": -50,
                    "security": "WPA2",
                }
            elif current is not None:
                if "Signal / Noise" in stripped:
                    # e.g. "Signal / Noise: -55 dBm / -90 dBm"
                    try:
                        val = stripped.split(":", 1)[1].strip()
                        dbm = val.split("dBm")[0].strip()
                        current["rssi"] = int(dbm)
                    except (ValueError, IndexError):
                        pass
                elif stripped.startswith("Channel:"):
                    try:
                        chan_txt = stripped.split(":", 1)[1].strip()
                        current["chan"] = int(chan_txt.split()[0])
                    except (ValueError, IndexError):
                        pass
                elif stripped.startswith("Security:"):
                    sec = stripped.split(":", 1)[1].strip()
                    if "WPA3" in sec:
                        current["security"] = "WPA3"
                    elif "WPA2" in sec:
                        current["security"] = "WPA2"
                    elif "None" in sec or "Open" in sec:
                        current["security"] = "Open"
                    break
    if current is None:
        return None
    return [current]


def acquire_networks(simulate):
    """Return (networks, source_tag). source_tag in {'nmcli','macos','sim'}."""
    if not simulate:
        if sys.platform.startswith("linux"):
            nets = scan_nmcli()
            if nets:
                return nets, "nmcli"
        elif sys.platform == "darwin":
            nets = scan_macos_current()
            if nets:
                return nets, "macos"
    return make_simulated(), "sim"


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def run(stdscr, duration, frame_delay, refresh_interval, simulate):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    nets, source = acquire_networks(simulate)
    simulated = source in ("sim",)

    start = time.monotonic()
    last_refresh = start
    frame = 0

    while True:
        now = time.monotonic()
        if now - start >= duration:
            break

        # Periodic re-acquire of the network list.
        if now - last_refresh >= refresh_interval:
            nets, source = acquire_networks(simulate)
            simulated = source in ("sim",)
            last_refresh = now

        # Gently animate signal each frame for a "live" feel.
        fluctuate(nets, amount=1 if not simulated else 2)
        nets_sorted = sorted(nets, key=lambda n: n["rssi"], reverse=True)

        max_y, max_x = stdscr.getmaxyx()
        stdscr.erase()

        spin = SPINNER[frame % len(SPINNER)]
        header = f"{spin} scanning 2.4/5 GHz..."
        try:
            stdscr.addstr(0, 2, header[:max(0, max_x - 4)],
                          curses.color_pair(COLOR_HEADER) | curses.A_BOLD)
        except curses.error:
            pass

        # Column layout
        col_hdr = "SSID              SIGNAL              RSSI  CH   SECURITY   BSSID"
        try:
            stdscr.addstr(2, 2, col_hdr[:max(0, max_x - 4)],
                          curses.color_pair(COLOR_DIM) | curses.A_DIM)
        except curses.error:
            pass

        bar_width = 14
        row = 3
        # leave room for histogram (about 4 lines) + label
        max_rows = max(0, max_y - row - 6)
        for net in nets_sorted[:max_rows]:
            if row >= max_y - 1:
                break
            quality = rssi_to_quality(net["rssi"])
            scol = signal_color(quality)
            bar = signal_bar(quality, bar_width)

            ssid = net["ssid"]
            ssid_disp = ssid[:16].ljust(16)
            x = 2
            # SSID
            ssid_attr = curses.A_BOLD
            if net["hidden"]:
                ssid_attr = curses.A_DIM | curses.A_ITALIC if hasattr(
                    curses, "A_ITALIC") else curses.A_DIM
            try:
                stdscr.addstr(row, x, ssid_disp, ssid_attr)
            except curses.error:
                pass
            x += 18
            # signal bar
            try:
                stdscr.addstr(row, x, "[", curses.color_pair(COLOR_DIM))
                stdscr.addstr(row, x + 1, bar,
                              curses.color_pair(scol) | curses.A_BOLD)
                stdscr.addstr(row, x + 1 + bar_width, "]",
                              curses.color_pair(COLOR_DIM))
            except curses.error:
                pass
            x += bar_width + 4
            # RSSI dBm
            try:
                stdscr.addstr(row, x, f"{net['rssi']:>4}dBm",
                              curses.color_pair(scol))
            except curses.error:
                pass
            x += 9
            # channel
            try:
                stdscr.addstr(row, x, f"{net['chan']:>3}",
                              curses.color_pair(COLOR_DIM))
            except curses.error:
                pass
            x += 5
            # security
            sec = net["security"]
            if sec == "Open":
                sec_attr = curses.color_pair(COLOR_INSECURE) | curses.A_BOLD
                sec_txt = "OPEN!"
            else:
                sec_attr = curses.color_pair(COLOR_SECURE)
                sec_txt = sec
            try:
                stdscr.addstr(row, x, sec_txt.ljust(10), sec_attr)
            except curses.error:
                pass
            x += 11
            # BSSID (dim)
            try:
                stdscr.addstr(row, x, net["bssid"][:max(0, max_x - x - 1)],
                              curses.color_pair(COLOR_DIM) | curses.A_DIM)
            except curses.error:
                pass
            row += 1

        # Channel occupancy histogram at the bottom
        hist = channel_histogram(nets)
        hist_y = max_y - 4
        if hist_y > row:
            try:
                stdscr.addstr(hist_y, 2, "channel occupancy:",
                              curses.color_pair(COLOR_DIM) | curses.A_DIM)
            except curses.error:
                pass
            hx = 2
            max_count = max(hist.values()) if hist else 1
            for chan in ALL_CHANNELS:
                count = hist.get(chan, 0)
                blocks = int(round(count / max(1, max_count) * 6))
                cell = f"ch{chan:>3}:{'#' * blocks}({count}) "
                if hx + len(cell) < max_x - 1:
                    ccol = COLOR_STRONG if count <= 1 else (
                        COLOR_MED if count <= 2 else COLOR_WEAK)
                    try:
                        stdscr.addstr(hist_y + 1, hx, cell,
                                      curses.color_pair(ccol))
                    except curses.error:
                        pass
                    hx += len(cell)

        # Bottom label
        tag = "  [SIMULATED]" if simulated else ""
        note = ""
        if source == "macos":
            note = "  (current net only; full scan needs sudo)"
        label = f"wifi_scan  {len(nets)} networks{tag}{note}"
        try:
            stdscr.addstr(max_y - 1, 2, label[:max(0, max_x - 4)],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        frame += 1
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def main(duration=30, frame_delay=0.1, refresh_interval=4, simulate=False):
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
