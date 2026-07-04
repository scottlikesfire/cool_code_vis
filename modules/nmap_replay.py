import curses
import random
import time


# Color pair indices
COLOR_OPEN = 1        # open ports -> green
COLOR_FILTERED = 2    # filtered -> amber/yellow
COLOR_CLOSED = 3      # closed -> dim
COLOR_VULN = 4        # VULNERABLE findings -> bold red
COLOR_HEADER = 5      # section headers -> cyan
COLOR_HOSTUP = 6      # host-up lines -> white
COLOR_LABEL = 7       # bottom label -> cyan bold

SPINNER = ["|", "/", "-", "\\"]

# Canned, clearly-synthetic service/version catalogs.
TCP_SERVICES = [
    (22, "ssh", ["OpenSSH 8.9 (protocol 2.0)", "OpenSSH 7.4 (protocol 2.0)",
                 "OpenSSH 9.2p1 Debian", "Dropbear sshd 2020.81"]),
    (21, "ftp", ["vsftpd 3.0.5", "ProFTPD 1.3.5", "Pure-FTPd"]),
    (23, "telnet", ["Linux telnetd", "BusyBox telnetd"]),
    (25, "smtp", ["Postfix smtpd", "Exim smtpd 4.94"]),
    (53, "domain", ["dnsmasq 2.85", "ISC BIND 9.16.1"]),
    (80, "http", ["Apache httpd 2.4.52 ((Ubuntu))", "nginx 1.18.0 (Ubuntu)",
                  "lighttpd 1.4.55", "Microsoft IIS httpd 10.0"]),
    (110, "pop3", ["Dovecot pop3d"]),
    (139, "netbios-ssn", ["Samba smbd 4.6.2"]),
    (143, "imap", ["Dovecot imapd"]),
    (443, "https", ["nginx 1.18.0", "Apache httpd 2.4.52 (OpenSSL/1.1.1)",
                    "Microsoft IIS httpd 10.0"]),
    (445, "microsoft-ds", ["Windows Server 2019 microsoft-ds",
                           "Samba smbd 4.6.2"]),
    (3306, "mysql", ["MySQL 8.0.32", "MariaDB 10.5.18", "MySQL 5.7.40"]),
    (3389, "ms-wbt-server", ["Microsoft Terminal Services (RDP)"]),
    (5432, "postgresql", ["PostgreSQL DB 14.6"]),
    (5900, "vnc", ["VNC (protocol 3.8)"]),
    (6379, "redis", ["Redis key-value store 6.2.6"]),
    (8080, "http-proxy", ["Apache Tomcat 9.0.65", "Jetty 9.4.43"]),
    (8443, "https-alt", ["nginx 1.20.1"]),
    (27017, "mongodb", ["MongoDB 5.0.14"]),
]

# Canned "findings" that look like nmap NSE script vuln hints. Keyed loosely
# by port so they only surface when a plausible service is present.
CANNED_FINDINGS = {
    443: [
        ("ssl-heartbleed", "VULNERABLE (CVE-2014-0160)", True),
        ("ssl-poodle", "VULNERABLE (CVE-2014-3566)", True),
        ("ssl-dh-params", "Anonymous Diffie-Hellman detected", False),
    ],
    80: [
        ("http-csrf", "Possible CSRF vulnerabilities found", False),
        ("http-slowloris-check", "likely VULNERABLE", True),
    ],
    445: [
        ("smb-vuln-ms17-010", "likely VULNERABLE (CVE-2017-0143)", True),
        ("smb-vuln-cve-2020-0796", "VULNERABLE (SMBGhost)", True),
        ("smb-security-mode", "message signing disabled", False),
    ],
    3389: [
        ("rdp-vuln-ms12-020", "likely VULNERABLE (CVE-2012-0002)", True),
    ],
    21: [
        ("ftp-anon", "Anonymous FTP login allowed", False),
    ],
    6379: [
        ("redis-info", "No authentication required", False),
    ],
    23: [
        ("telnet-encryption", "cleartext credentials in transit", False),
    ],
}

OS_GUESSES = [
    "Linux 4.15 - 5.8 (95%)",
    "Linux 3.2 - 4.9 (92%)",
    "Microsoft Windows Server 2019 (90%)",
    "Microsoft Windows 10 1809 - 21H2 (88%)",
    "FreeBSD 12.X (89%)",
    "Ubuntu Linux (kernel 5.4) (96%)",
]

HOST_PREFIXES = [
    "web", "db", "mail", "app", "gw", "dev", "vpn", "nas",
    "cache", "auth", "jump", "backup", "print", "dc", "proxy",
]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_OPEN, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_FILTERED, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_CLOSED, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_VULN, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_HEADER, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_HOSTUP, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


# ---------------------------------------------------------------------------
# Pure generators / formatters (no I/O, fully offline)
# ---------------------------------------------------------------------------

def gen_subnet():
    """Pick a synthetic RFC1918 /24 subnet base like '10.10.14'."""
    choices = [
        ("10", str(random.randint(0, 254)), str(random.randint(0, 254))),
        ("192", "168", str(random.randint(0, 254))),
        ("172", str(random.randint(16, 31)), str(random.randint(0, 254))),
    ]
    a, b, c = random.choice(choices)
    return f"{a}.{b}.{c}"


def gen_hosts(subnet, num_hosts):
    """Return a list of host dicts discovered on the subnet."""
    n = max(1, int(num_hosts))
    octets = random.sample(range(1, 255), min(n, 254))
    hosts = []
    used_names = set()
    for oct4 in octets:
        prefix = random.choice(HOST_PREFIXES)
        idx = random.randint(1, 9)
        name = f"{prefix}-{idx}"
        # avoid duplicate names
        while name in used_names:
            idx += 1
            name = f"{prefix}-{idx}"
        used_names.add(name)
        hosts.append({
            "ip": f"{subnet}.{oct4}",
            "name": name,
            "latency": round(random.uniform(0.0002, 0.0089), 4),
        })
    return hosts


def gen_ports(seed_rng=random):
    """Generate a realistic mix of open/filtered/closed ports for a host.

    Returns a list of dicts: {port, proto, state, service, version}.
    """
    catalog = list(TCP_SERVICES)
    seed_rng.shuffle(catalog)
    k = seed_rng.randint(2, 7)
    chosen = catalog[:k]
    chosen.sort(key=lambda s: s[0])
    ports = []
    for port, service, versions in chosen:
        roll = seed_rng.random()
        if roll < 0.62:
            state = "open"
            version = seed_rng.choice(versions)
        elif roll < 0.82:
            state = "filtered"
            version = ""
        else:
            state = "closed"
            version = ""
        ports.append({
            "port": port,
            "proto": "tcp",
            "state": state,
            "service": service,
            "version": version,
        })
    return ports


def gen_findings(ports, seed_rng=random):
    """Produce canned NSE-style findings for open ports. Returns list of
    dicts: {port, script, detail, vuln}."""
    findings = []
    for p in ports:
        if p["state"] != "open":
            continue
        candidates = CANNED_FINDINGS.get(p["port"])
        if not candidates:
            continue
        # roughly 40% chance a matching script fires for this port
        if seed_rng.random() < 0.40:
            script, detail, vuln = seed_rng.choice(candidates)
            findings.append({
                "port": p["port"],
                "script": script,
                "detail": detail,
                "vuln": vuln,
            })
    return findings


def count_open(ports):
    return sum(1 for p in ports if p["state"] == "open")


def format_port_row(port_rec):
    """Format one PORT/STATE/SERVICE/VERSION table row (no color)."""
    portstr = f"{port_rec['port']}/{port_rec['proto']}"
    return (f"{portstr:<9} {port_rec['state']:<8} "
            f"{port_rec['service']:<14} {port_rec['version']}").rstrip()


def build_host_lines(host, ports, findings, hostnum, total):
    """Build an ordered list of (text, color, bold) tuples for one host's
    scan report. Pure — used both live and in headless tests."""
    lines = []
    lines.append((f"Nmap scan report for {host['name']} ({host['ip']})",
                  COLOR_HOSTUP, False))
    lines.append((f"Host is up ({host['latency']:.4f}s latency).",
                  COLOR_HOSTUP, False))
    lines.append(("", COLOR_HOSTUP, False))
    lines.append(("PORT      STATE    SERVICE        VERSION",
                  COLOR_HEADER, True))
    find_by_port = {}
    for f in findings:
        find_by_port.setdefault(f["port"], []).append(f)
    for p in ports:
        if p["state"] == "open":
            color = COLOR_OPEN
        elif p["state"] == "filtered":
            color = COLOR_FILTERED
        else:
            color = COLOR_CLOSED
        bold = p["state"] == "open"
        lines.append((format_port_row(p), color, bold))
        for f in find_by_port.get(p["port"], []):
            text = f"| {f['script']}: {f['detail']}"
            if f["vuln"]:
                lines.append((text, COLOR_VULN, True))
            else:
                lines.append((text, COLOR_FILTERED, False))
    lines.append((f"OS details: {random.choice(OS_GUESSES)}",
                  COLOR_HOSTUP, False))
    lines.append(("", COLOR_HOSTUP, False))
    return lines


# ---------------------------------------------------------------------------
# Live rendering
# ---------------------------------------------------------------------------

def run(stdscr, duration, frame_delay, num_hosts, scan_speed):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    start = time.monotonic()

    # Feed of already-emitted lines (scrolling buffer).
    feed = []          # list of (text, color, bold)
    pending = []       # list of (text, color, bold) not yet emitted
    spin_idx = 0

    # Engagement state
    def new_engagement():
        subnet = gen_subnet()
        hosts = gen_hosts(subnet, num_hosts)
        return {
            "subnet": subnet,
            "hosts": hosts,
            "hi": 0,           # current host index
            "total_open": 0,
            "total_findings": 0,
            "hosts_up": len(hosts),
        }

    eng = new_engagement()

    def emit(text, color, bold):
        feed.append((text, color, bold))

    def queue_intro():
        subnet = eng["subnet"]
        pending.append((f"Starting Nmap 7.94 ( https://nmap.org ) scan",
                        COLOR_HEADER, True))
        pending.append((f"Scanning {subnet}.0/24 [host discovery]",
                        COLOR_HEADER, False))
        for h in eng["hosts"]:
            pending.append((f"  Discovered host {h['ip']} ({h['name']})",
                            COLOR_HOSTUP, False))
        pending.append((f"Nmap done host discovery: "
                        f"{len(eng['hosts'])} hosts up.", COLOR_HEADER, False))
        pending.append(("", COLOR_HOSTUP, False))

    def queue_host(h, hostnum, total):
        ports = gen_ports()
        findings = gen_findings(ports)
        eng["total_open"] += count_open(ports)
        eng["total_findings"] += len(findings)
        lines = build_host_lines(h, ports, findings, hostnum, total)
        pending.extend(lines)

    def queue_summary():
        pending.append(("=" * 46, COLOR_HEADER, True))
        pending.append((f"Engagement complete for {eng['subnet']}.0/24",
                        COLOR_HEADER, True))
        pending.append((f"{eng['hosts_up']} hosts up, "
                        f"{eng['total_open']} open ports, "
                        f"{eng['total_findings']} potential findings",
                        COLOR_OPEN, True))
        pending.append(("=" * 46, COLOR_HEADER, True))
        pending.append(("", COLOR_HOSTUP, False))

    # phases: "intro", "hosts", "summary", "pause"
    phase = "intro"
    queue_intro()
    pause_until = 0.0
    scanning = False       # show spinner while a host is "scanning"
    next_emit = start
    scan_speed = max(0.1, scan_speed)
    # base lines-per-second; scan_speed multiplies it
    base_lps = 12.0

    last_frame = start
    while True:
        now = time.monotonic()
        if now - start >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        body_rows = max(1, max_y - 1)

        # Advance the feed: emit pending lines according to pacing.
        if phase != "pause":
            interval = 1.0 / (base_lps * scan_speed)
            # occasional burst/pause jitter
            emitted_this_frame = 0
            while pending and now >= next_emit and emitted_this_frame < 6:
                emit(*pending.pop(0))
                emitted_this_frame += 1
                jitter = interval
                if random.random() < 0.12:
                    jitter += random.uniform(0.15, 0.55)  # brief pause
                next_emit = now + jitter
            if not pending:
                scanning = False

        # Phase transitions once pending is drained.
        if not pending and phase != "pause":
            if phase == "intro":
                phase = "hosts"
                eng["hi"] = 0
                if eng["hosts"]:
                    scanning = True
                    h = eng["hosts"][0]
                    emit((f"Nmap scan report for {h['name']} "
                          f"({h['ip']}) [scanning...]"),
                         COLOR_HEADER, False)
                    queue_host(h, 1, len(eng["hosts"]))
            elif phase == "hosts":
                eng["hi"] += 1
                if eng["hi"] < len(eng["hosts"]):
                    scanning = True
                    h = eng["hosts"][eng["hi"]]
                    emit((f"Nmap scan report for {h['name']} "
                          f"({h['ip']}) [scanning...]"),
                         COLOR_HEADER, False)
                    queue_host(h, eng["hi"] + 1, len(eng["hosts"]))
                else:
                    phase = "summary"
                    queue_summary()
            elif phase == "summary":
                phase = "pause"
                pause_until = now + 2.5

        if phase == "pause" and now >= pause_until:
            # restart with a fresh randomized engagement
            eng = new_engagement()
            feed.clear()
            pending.clear()
            phase = "intro"
            scanning = False
            next_emit = now
            queue_intro()

        # Trim feed to what fits on screen.
        if len(feed) > body_rows:
            del feed[:len(feed) - body_rows]

        # Render
        stdscr.erase()
        visible = feed[-body_rows:]
        row = 0
        for text, color, bold in visible:
            if row >= body_rows:
                break
            attr = curses.color_pair(color)
            if bold:
                attr |= curses.A_BOLD
            elif color == COLOR_CLOSED:
                attr |= curses.A_DIM
            try:
                stdscr.addstr(row, 0, text[:max_x - 1], attr)
            except curses.error:
                pass
            row += 1

        # Spinner overlay on the last visible line while scanning.
        if scanning and pending:
            spin_idx = (spin_idx + 1) % len(SPINNER)
            sp = SPINNER[spin_idx]
            try:
                stdscr.addstr(max(0, min(row, body_rows - 1)), 0,
                              f"  {sp} scanning ports...",
                              curses.color_pair(COLOR_FILTERED))
            except curses.error:
                pass

        # Bottom label
        hostnum = min(eng["hi"] + 1, len(eng["hosts"])) if eng["hosts"] else 0
        label = (f"nmap_replay  <host {hostnum}/of {len(eng['hosts'])}>  "
                 f"open={eng['total_open']}")
        try:
            stdscr.addstr(max_y - 1, 2, label[:max_x - 4],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return
        last_frame = now


def main(duration=30, frame_delay=0.04, num_hosts=8, scan_speed=1.0):
    duration = float(duration)
    frame_delay = float(frame_delay)
    num_hosts = max(1, int(num_hosts))
    scan_speed = float(scan_speed)
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, num_hosts, scan_speed))


if __name__ == "__main__":
    main()
