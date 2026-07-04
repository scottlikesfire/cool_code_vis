import curses
import random
import re
import subprocess
import time


# Color pair indices
C_TCP = 1      # cyan
C_UDP = 2      # yellow
C_TLS = 3      # green
C_DNS = 4      # magenta
C_ERR = 5      # red / RST / errors
C_DIM = 6      # dim / hexdump / stats
COLOR_LABEL = 7

PROTO_COLOR = {
    "TCP": C_TCP,
    "UDP": C_UDP,
    "TLS": C_TLS,
    "DNS": C_DNS,
    "RST": C_ERR,
}

TCP_FLAGS = ["S", "S.", ".", "P.", "F.", "R"]
DECODES = [
    ("TLS", "TLSv1.3 Application Data"),
    ("TLS", "TLSv1.2 Client Hello"),
    ("HTTP", "GET / HTTP/1.1"),
    ("HTTP", "HTTP/1.1 200 OK"),
    ("HTTP", "POST /api/v1 HTTP/1.1"),
    ("DNS", "A? example.com"),
    ("DNS", "AAAA? cdn.example.net"),
]

FAKE_HOSTS = [
    "140.82.113.4", "151.101.1.140", "104.16.132.229", "142.250.72.14",
    "13.107.42.14", "17.253.144.10", "192.168.1.42", "10.0.0.5",
    "8.8.8.8", "1.1.1.1", "34.117.59.81", "162.159.61.3",
]
COMMON_DST_PORTS = [443, 443, 443, 80, 53, 22, 8080, 5228, 993]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(C_TCP, curses.COLOR_CYAN, -1)
    curses.init_pair(C_UDP, curses.COLOR_YELLOW, -1)
    curses.init_pair(C_TLS, curses.COLOR_GREEN, -1)
    curses.init_pair(C_DNS, curses.COLOR_MAGENTA, -1)
    curses.init_pair(C_ERR, curses.COLOR_RED, -1)
    curses.init_pair(C_DIM, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


# ---------------------------------------------------------------------------
# Parsers (pure) -- turn tool output into a set of connection tuples
# ---------------------------------------------------------------------------

_LSOF_ADDR = re.compile(r"^(.*):(\d+|\*)$")


def _split_addr(token):
    """Split 'host:port' (IPv4/IPv6/name) into (host, port)."""
    m = _LSOF_ADDR.match(token)
    if not m:
        return token, "0"
    host, port = m.group(1), m.group(2)
    # strip IPv6 brackets
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    if port == "*":
        port = "0"
    return host, port


def parse_lsof(text):
    """Parse `lsof -i -n -P` output into a set of connection dicts.

    Returns a set of (proto, laddr, lport, raddr, rport) tuples for
    established/active connections.
    """
    conns = set()
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 9:
            continue
        if parts[0] == "COMMAND":
            continue
        proto = "TCP" if "TCP" in parts else ("UDP" if "UDP" in parts else None)
        if proto is None:
            continue
        name = parts[8]
        # name looks like: laddr->raddr  or just laddr (listening)
        if "->" not in name:
            continue
        left, right = name.split("->", 1)
        laddr, lport = _split_addr(left)
        raddr, rport = _split_addr(right)
        conns.add((proto, laddr, lport, raddr, rport))
    return conns


def parse_netstat(text):
    """Parse `netstat -tn` output into a set of connection tuples.

    Handles common Linux/BSD layouts where Local and Foreign address
    columns are 'host:port' (or 'host.port' on BSD).
    """
    conns = set()
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        if not (parts[0].lower().startswith("tcp") or
                parts[0].lower().startswith("udp")):
            continue
        proto = "UDP" if parts[0].lower().startswith("udp") else "TCP"
        local = _netstat_addr(parts[3])
        foreign = _netstat_addr(parts[4])
        if local is None or foreign is None:
            continue
        laddr, lport = local
        raddr, rport = foreign
        if rport in ("0", "*"):
            continue
        conns.add((proto, laddr, lport, raddr, rport))
    return conns


def _netstat_addr(token):
    """Split netstat address 'host:port' or 'host.port' -> (host, port)."""
    if ":" in token and token.rsplit(":", 1)[1].isdigit():
        host, port = token.rsplit(":", 1)
        return host, port
    # BSD style host.port -- last dotted field is the port
    if "." in token:
        host, _, port = token.rpartition(".")
        if port.isdigit() or port == "*":
            return host, "0" if port == "*" else port
    return None


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

def poll_connections():
    """Poll the OS for real connections. Returns (conns_set, ok)."""
    for cmd, parser in (
        (["lsof", "-i", "-n", "-P"], parse_lsof),
        (["netstat", "-tn"], parse_netstat),
    ):
        try:
            out = subprocess.run(
                cmd, capture_output=True, text=True, timeout=3)
        except (OSError, subprocess.SubprocessError):
            continue
        conns = parser(out.stdout)
        if conns:
            return conns, True
    return set(), False


def synth_connection():
    """Fabricate one plausible connection tuple."""
    laddr = "192.168.1." + str(random.randint(2, 254))
    lport = str(random.randint(30000, 61000))
    raddr = random.choice(FAKE_HOSTS)
    rport = str(random.choice(COMMON_DST_PORTS))
    proto = "UDP" if rport == "53" else "TCP"
    return (proto, laddr, lport, raddr, rport)


# ---------------------------------------------------------------------------
# Packet line formatting (pure)
# ---------------------------------------------------------------------------

def fmt_time(t):
    lt = time.localtime(t)
    ms = int((t - int(t)) * 1000)
    return time.strftime("%H:%M:%S", lt) + ".%03d" % ms


def classify(conn, flag, decode):
    """Return the color-key protocol string for a packet."""
    if flag == "R":
        return "RST"
    if decode:
        proto = decode[0]
        if proto == "TLS":
            return "TLS"
        if proto == "DNS":
            return "DNS"
    if conn[0] == "UDP" or conn[4] == "53":
        return "DNS" if conn[4] == "53" else "UDP"
    if conn[4] in ("443", "993", "8443"):
        return "TLS"
    return "TCP"


def format_packet(conn, t, flag, seq, length, decode=None):
    """Build a tcpdump-ish line. Returns (text, proto_key)."""
    proto, laddr, lport, raddr, rport = conn
    ts = fmt_time(t)
    line = "%s IP %s.%s > %s.%s: %s" % (ts, laddr, lport, raddr, rport, flag)
    if flag.startswith("S") or "P" in flag or flag == ".":
        line += " seq %d, length %d" % (seq, length)
    else:
        line += " length %d" % length
    if decode:
        line += "  [%s] %s" % (decode[0], decode[1])
    return line, classify(conn, flag, decode)


def hexdump_snippet(nbytes=16, seed=None):
    """Generate a single-line compact hex + ascii dump of random bytes."""
    rng = random.Random(seed)
    data = bytes(rng.randint(0, 255) for _ in range(nbytes))
    hexpart = " ".join("%02x" % b for b in data)
    asc = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
    return "\t0x0000:  %s  %s" % (hexpart, asc)


def make_packet(conn, t):
    """Produce a synthesized packet (text, proto_key, is_new, hexline)."""
    flag = random.choice(TCP_FLAGS)
    if conn[0] == "UDP":
        flag = "."
    decode = None
    if random.random() < 0.28:
        decode = random.choice(DECODES)
    seq = random.randint(1, 4_000_000_000)
    length = random.choice([0, 0, 52, 128, 517, 1024, 1448, 60, 40])
    text, proto = format_packet(conn, t, flag, seq, length, decode)
    hexline = None
    if length > 0 and random.random() < 0.22:
        hexline = hexdump_snippet(16, seed=seq)
    return text, proto, False, hexline


# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------

def run(stdscr, duration, frame_delay, poll_interval, max_pps, simulate):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    feed = []          # list of (text, proto_key, is_new, is_hex)
    active = set()
    tools_ok = not simulate
    faked = simulate

    stats = {"pkts": 0, "bytes": 0, "proto": {}}
    pps_window = []    # timestamps of recent packets

    start = time.monotonic()
    last_frame = start
    last_poll = start - poll_interval  # force immediate first poll
    budget = 0.0       # fractional synthesized-packet budget

    def push(text, proto, is_new, hexline):
        feed.append((text, proto, is_new, False))
        if hexline:
            feed.append((hexline, proto, False, True))
        stats["pkts"] += 1
        m = re.search(r"length (\d+)", text)
        if m:
            stats["bytes"] += int(m.group(1))
        stats["proto"][proto] = stats["proto"].get(proto, 0) + 1
        pps_window.append(time.monotonic())
        if len(feed) > 4000:
            del feed[:2000]

    while True:
        now = time.monotonic()
        if now - start >= duration:
            break
        wall = time.time()

        # --- poll for real connection churn ---
        if now - last_poll >= poll_interval:
            last_poll = now
            if not simulate:
                conns, ok = poll_connections()
                if ok:
                    tools_ok = True
                    new = conns - active
                    closed = active - conns
                    for c in list(new)[:12]:
                        text, proto = format_packet(
                            c, wall, "S", random.randint(1, 4_000_000_000), 0)
                        push(text + "  [NEW]", proto, True, None)
                    for c in list(closed)[:12]:
                        text, proto = format_packet(
                            c, wall, "F.",
                            random.randint(1, 4_000_000_000), 0)
                        push(text + "  [FIN]", proto, True, None)
                    active = conns
                else:
                    tools_ok = False
                    faked = True
            if simulate or not tools_ok:
                faked = True
                # keep a pool of synthetic active connections
                while len(active) < 8:
                    active.add(synth_connection())
                if active and random.random() < 0.4:
                    active.pop()

        if not active:
            for _ in range(8):
                active.add(synth_connection())

        # --- emit synthesized packets up to max_pps ---
        dt = min(now - last_frame, 0.25)
        last_frame = now
        budget += max_pps * dt
        emit = int(budget)
        budget -= emit
        emit = min(emit, 12)  # throttle lines/frame for readability
        conn_list = list(active)
        for _ in range(emit):
            if not conn_list:
                break
            c = random.choice(conn_list)
            text, proto, is_new, hexline = make_packet(c, wall)
            push(text, proto, is_new, hexline)

        # --- prune pps window (1s) ---
        cutoff = now - 1.0
        while pps_window and pps_window[0] < cutoff:
            pps_window.pop(0)
        pps = len(pps_window)

        # --- render ---
        max_y, max_x = stdscr.getmaxyx()
        stdscr.erase()

        # top stats strip
        kb = stats["bytes"] / 1024.0
        pc = stats["proto"]
        strip = ("pps:%3d  bytes:%8.1fK  conns:%3d  "
                 "TCP:%d UDP:%d TLS:%d DNS:%d RST:%d") % (
            pps, kb, len(active),
            pc.get("TCP", 0), pc.get("UDP", 0), pc.get("TLS", 0),
            pc.get("DNS", 0), pc.get("RST", 0))
        try:
            stdscr.addstr(0, 0, strip[:max_x - 1],
                          curses.color_pair(C_DIM) | curses.A_REVERSE)
        except curses.error:
            pass

        # feed area: rows 1 .. max_y-2
        feed_rows = max(1, max_y - 2)
        visible = feed[-feed_rows:]
        for i, (text, proto, is_new, is_hex) in enumerate(visible):
            row = 1 + i
            if is_hex:
                attr = curses.color_pair(C_DIM) | curses.A_DIM
            else:
                attr = curses.color_pair(PROTO_COLOR.get(proto, C_TCP))
                if is_new:
                    attr |= curses.A_BOLD
            try:
                stdscr.addstr(row, 0, text[:max_x - 1], attr)
            except curses.error:
                pass

        # bottom label
        tag = "  [SIMULATED]" if (simulate or faked or not tools_ok) else ""
        label = "packet_sniffer  %d pkt/s  %d conns%s" % (
            pps, len(active), tag)
        try:
            stdscr.addstr(max_y - 1, 2, label[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def main(duration=30, frame_delay=0.06, poll_interval=1.0, max_pps=40,
         simulate=False):
    duration = float(duration)
    frame_delay = float(frame_delay)
    poll_interval = float(poll_interval)
    max_pps = float(max_pps)
    if isinstance(simulate, str):
        simulate = simulate.strip().lower() in ("1", "true", "yes", "y", "on")
    else:
        simulate = bool(simulate)
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, poll_interval, max_pps, simulate))


if __name__ == "__main__":
    main()
