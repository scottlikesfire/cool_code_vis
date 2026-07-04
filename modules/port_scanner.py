import curses
import ipaddress
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor


COLOR_OPEN = 1
COLOR_CLOSED = 2
COLOR_FILTERED = 3
COLOR_CURSOR = 4
COLOR_BANNER = 5
COLOR_LABEL = 6
COLOR_DIM = 7


# Well-known ports with service names (nmap-style).
PORT_SERVICES = [
    (21, "ftp"), (22, "ssh"), (23, "telnet"), (25, "smtp"),
    (53, "domain"), (67, "dhcps"), (68, "dhcpc"), (69, "tftp"),
    (80, "http"), (110, "pop3"), (111, "rpcbind"), (123, "ntp"),
    (135, "msrpc"), (137, "netbios-ns"), (139, "netbios-ssn"),
    (143, "imap"), (161, "snmp"), (179, "bgp"), (389, "ldap"),
    (443, "https"), (445, "microsoft-ds"), (465, "smtps"),
    (500, "isakmp"), (514, "syslog"), (515, "printer"), (587, "submission"),
    (631, "ipp"), (636, "ldaps"), (873, "rsync"), (990, "ftps"),
    (993, "imaps"), (995, "pop3s"), (1080, "socks"), (1194, "openvpn"),
    (1433, "ms-sql-s"), (1521, "oracle"), (1723, "pptp"), (2049, "nfs"),
    (2082, "cpanel"), (2181, "zookeeper"), (2375, "docker"),
    (3000, "ppp"), (3128, "squid-http"), (3306, "mysql"),
    (3389, "ms-wbt-server"), (4444, "krb524"), (5000, "upnp"),
    (5432, "postgresql"), (5601, "kibana"), (5672, "amqp"),
    (5900, "vnc"), (5984, "couchdb"), (6379, "redis"),
    (6443, "kube-apiserver"), (7000, "afs3-fileserver"), (7077, "spark"),
    (8000, "http-alt"), (8080, "http-proxy"), (8081, "blackice-icecap"),
    (8443, "https-alt"), (8888, "sun-answerbook"), (9000, "cslistener"),
    (9092, "kafka"), (9200, "elasticsearch"), (9300, "elastic-transport"),
    (11211, "memcache"), (15672, "rabbitmq-mgmt"), (27017, "mongodb"),
]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_OPEN, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_CLOSED, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_FILTERED, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_CURSOR, curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(COLOR_BANNER, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_DIM, curses.COLOR_WHITE, -1)


def service_name(port):
    for p, name in PORT_SERVICES:
        if p == port:
            return name
    return "unknown"


def build_port_list():
    """Ordered, de-duplicated list of ports to sweep."""
    seen = set()
    ports = []
    for p, _ in PORT_SERVICES:
        if p not in seen:
            seen.add(p)
            ports.append(p)
    return ports


def _is_private(ip):
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return addr.is_loopback or addr.is_private


def sanitize_target(target):
    """Clamp to safe, self/LAN targets only.

    Allow localhost/loopback and RFC1918 private addresses. Anything else
    (public IPs, external hostnames) falls back to 127.0.0.1.
    """
    if target is None:
        return "127.0.0.1"
    target = str(target).strip()
    if target.lower() in ("localhost", ""):
        return "127.0.0.1"
    if _is_private(target):
        return target
    return "127.0.0.1"


def detect_gateway():
    """Best-effort LAN gateway detection via netstat/route. Returns IP or None."""
    for cmd in (["netstat", "-rn"], ["route", "-n"]):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True,
                                 timeout=2.0).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        for line in out.splitlines():
            parts = line.split()
            if not parts:
                continue
            if parts[0] in ("default", "0.0.0.0"):
                for tok in parts[1:]:
                    if _is_private(tok):
                        return tok
    return None


def probe_port(target, port, connect_timeout):
    """Real non-blocking TCP connect. Returns 'open', 'closed', or 'filtered'."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(connect_timeout)
    try:
        result = sock.connect_ex((target, port))
    except (socket.timeout, OSError):
        return "filtered"
    finally:
        try:
            sock.close()
        except OSError:
            pass
    if result == 0:
        return "open"
    if result in (11, 10035, 115):  # EAGAIN/EWOULDBLOCK/EINPROGRESS
        return "filtered"
    return "closed"


def run(stdscr, duration, frame_delay, target, connect_timeout,
        completion_pause, workers):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    ports = build_port_list()
    gateway = detect_gateway()

    # Targets to rotate through: the requested one, then gateway if available.
    targets = [target]
    if gateway and gateway != target:
        targets.append(gateway)

    executor = ThreadPoolExecutor(max_workers=max(1, workers))
    start = time.monotonic()
    total_open = 0

    try:
        cycle = 0
        while time.monotonic() - start < duration:
            cur_target = sanitize_target(targets[cycle % len(targets)])
            cycle += 1
            total_open = _scan_cycle(stdscr, executor, cur_target, ports,
                                     connect_timeout, workers, start,
                                     duration, completion_pause)
            if total_open is None:  # user quit
                return
    finally:
        executor.shutdown(wait=False)


def _scan_cycle(stdscr, executor, target, ports, connect_timeout, workers,
                start, duration, completion_pause):
    """Run one full sweep with progressive per-frame batches. Returns open
    count, or None if the user quit."""
    n = len(ports)
    results = {}      # port -> classification
    inflight = {}     # future -> port
    idx = 0
    batch = max(1, workers)
    scan_start = time.monotonic()

    while True:
        if time.monotonic() - start >= duration:
            return sum(1 for v in results.values() if v == "open")

        # Launch a batch of probes this frame.
        launched = 0
        while idx < n and launched < batch:
            port = ports[idx]
            fut = executor.submit(probe_port, target, port, connect_timeout)
            inflight[fut] = port
            idx += 1
            launched += 1

        # Collect finished probes.
        done = [f for f in inflight if f.done()]
        for f in done:
            port = inflight.pop(f)
            try:
                results[port] = f.result()
            except Exception:
                results[port] = "filtered"

        open_n = sum(1 for v in results.values() if v == "open")
        closed_n = sum(1 for v in results.values() if v == "closed")
        filt_n = sum(1 for v in results.values() if v == "filtered")
        tested = len(results)
        elapsed = time.monotonic() - scan_start

        _draw(stdscr, target, ports, results, idx, tested, n,
              open_n, closed_n, filt_n, elapsed, phase="scan")

        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return None

        if idx >= n and not inflight:
            break

    # Summary / completion hold.
    open_n = sum(1 for v in results.values() if v == "open")
    closed_n = sum(1 for v in results.values() if v == "closed")
    filt_n = sum(1 for v in results.values() if v == "filtered")
    elapsed = time.monotonic() - scan_start
    hold_start = time.monotonic()
    while time.monotonic() - hold_start < completion_pause:
        if time.monotonic() - start >= duration:
            break
        _draw(stdscr, target, ports, results, n, len(results), n,
              open_n, closed_n, filt_n, elapsed, phase="summary")
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return None
    return open_n


def _classify_attr(cls):
    if cls == "open":
        return curses.color_pair(COLOR_OPEN) | curses.A_BOLD
    if cls == "closed":
        return curses.color_pair(COLOR_CLOSED) | curses.A_DIM
    if cls == "filtered":
        return curses.color_pair(COLOR_FILTERED)
    return curses.color_pair(COLOR_DIM) | curses.A_DIM


def _safe_addstr(stdscr, y, x, text, attr=0):
    try:
        stdscr.addstr(y, x, text, attr)
    except curses.error:
        pass


def _draw(stdscr, target, ports, results, cursor_idx, tested, total,
          open_n, closed_n, filt_n, elapsed, phase):
    max_y, max_x = stdscr.getmaxyx()
    stdscr.erase()

    # Header banner.
    banner = f"Starting scan ( https://nmap.org ) at {time.strftime('%H:%M:%S')}"
    _safe_addstr(stdscr, 0, 2, banner[:max_x - 4],
                 curses.color_pair(COLOR_BANNER) | curses.A_BOLD)
    _safe_addstr(stdscr, 1, 2, f"Scan report for {target}"[:max_x - 4],
                 curses.color_pair(COLOR_BANNER))

    # Port grid area.
    top = 3
    bottom = max_y - 4
    if bottom <= top:
        _draw_label(stdscr, max_y, max_x, target, open_n)
        stdscr.refresh()
        return

    cell_w = 12  # e.g. "  3306 mysql"
    cols = max(1, (max_x - 4) // cell_w)
    rows = bottom - top

    for i, port in enumerate(ports):
        col = i // rows
        row = i % rows
        if col >= cols:
            break
        y = top + row
        x = 2 + col * cell_w
        cls = results.get(port)
        svc = service_name(port)
        if cls is None:
            if i == cursor_idx or (i < cursor_idx + 1 and i >= tested):
                label = f"{port:>5} scan"
                attr = curses.color_pair(COLOR_CURSOR) | curses.A_BOLD
            else:
                label = f"{port:>5} ...."
                attr = curses.color_pair(COLOR_DIM) | curses.A_DIM
        elif cls == "open":
            label = f"{port:>5} {svc}"[:cell_w - 1]
            attr = _classify_attr(cls)
        else:
            tag = {"closed": "clsd", "filtered": "filt"}.get(cls, "????")
            label = f"{port:>5} {tag}"
            attr = _classify_attr(cls)
        _safe_addstr(stdscr, y, x, label[:cell_w - 1], attr)

    # Progress bar.
    bar_y = max_y - 3
    frac = tested / total if total else 0.0
    bar_w = max(4, max_x - 24)
    filled = int(bar_w * frac)
    bar = "#" * filled + "-" * (bar_w - filled)
    _safe_addstr(stdscr, bar_y, 2, f"[{bar}] {int(frac * 100):3d}%"[:max_x - 4],
                 curses.color_pair(COLOR_BANNER))

    # Counts line.
    counts_y = max_y - 2
    _safe_addstr(stdscr, counts_y, 2, "open ", curses.color_pair(COLOR_OPEN) | curses.A_BOLD)
    _safe_addstr(stdscr, counts_y, 7, f"{open_n:<4}",
                 curses.color_pair(COLOR_OPEN) | curses.A_BOLD)
    _safe_addstr(stdscr, counts_y, 12, "closed ", curses.color_pair(COLOR_CLOSED))
    _safe_addstr(stdscr, counts_y, 19, f"{closed_n:<4}", curses.color_pair(COLOR_CLOSED))
    _safe_addstr(stdscr, counts_y, 24, "filtered ", curses.color_pair(COLOR_FILTERED))
    _safe_addstr(stdscr, counts_y, 33, f"{filt_n:<4}", curses.color_pair(COLOR_FILTERED))
    _safe_addstr(stdscr, counts_y, 38, f"total {total}  {elapsed:4.1f}s",
                 curses.color_pair(COLOR_DIM))

    if phase == "summary":
        msg = (f"Nmap done: {open_n} open port{'s' if open_n != 1 else ''} "
               f"found on {target} in {elapsed:.2f}s")
        _safe_addstr(stdscr, counts_y, 0, "", 0)
        my = max_y // 2
        box = f"  {msg}  "
        bx = max(0, (max_x - len(box)) // 2)
        _safe_addstr(stdscr, my, bx, box[:max_x],
                     curses.color_pair(COLOR_OPEN) | curses.A_BOLD | curses.A_REVERSE)

    _draw_label(stdscr, max_y, max_x, target, open_n)
    stdscr.refresh()


def _draw_label(stdscr, max_y, max_x, target, open_n):
    label = f"port_scanner  target={target}  open={open_n}"
    _safe_addstr(stdscr, max_y - 1, 2, label[:max_x - 4],
                 curses.color_pair(COLOR_LABEL) | curses.A_BOLD)


def main(duration=30, frame_delay=0.03, target="127.0.0.1",
         connect_timeout=0.3, completion_pause=3, workers=50):
    duration = float(duration)
    frame_delay = float(frame_delay)
    target = sanitize_target(target)
    connect_timeout = float(connect_timeout)
    completion_pause = float(completion_pause)
    workers = max(1, int(workers))
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, target, connect_timeout,
        completion_pause, workers))


if __name__ == "__main__":
    main()
