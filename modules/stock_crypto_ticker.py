"""Scrolling stock + crypto ticker tape with per-symbol sparkline panels.

By default (`simulate=True`) prices follow a geometric-random-walk so the
module is self-contained and works offline — the right choice on a headless
box or a Jetson/Pi screensaver. With `simulate=False` it fetches live prices
in a background thread (crypto from CoinGecko, stocks from Stooq — both
key-free) and falls back to simulation for any asset class whose fetch fails.

Layout: a scrolling marquee tape across the top, a grid of per-symbol panels
(symbol, price, 24h/session change, and a block-character sparkline) filling
the body, and a status label at the bottom.
"""

import curses
import json
import math
import os
import random
import threading
import time
import urllib.request
from collections import deque

import asciichartpy as acp


COLOR_UP = 1        # green   — price rising
COLOR_DOWN = 2      # red     — price falling
COLOR_SYMBOL = 3    # cyan    — symbol tickers
COLOR_LABEL = 4     # cyan    — bottom label
COLOR_NEUTRAL = 5   # white   — unchanged / chrome
COLOR_CRYPTO = 6    # magenta — crypto symbol accent

SPARK_CHARS = " ▁▂▃▄▅▆▇█"
UP_ARROW = "▲"
DOWN_ARROW = "▼"
HIST_LEN = 64
PORTFOLIO_HIST_LEN = 1024
# Each symbol is given this notional at start, so the synthetic portfolio is
# roughly equal-weight across holdings.
NOTIONAL_PER_SYMBOL = 10000.0
PANEL_W = 30
PANEL_H = 4
PANELS_TOP = 3

# Successful live pulls are cached here so a later rate-limited run can start
# from the most recent real prices instead of the hardcoded seeds.
_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CACHE_FILE = os.path.join(_DATA_DIR, "ticker_cache.json")

# Default universe: (symbol, display_name, kind, coingecko_id, seed_price)
DEFAULT_UNIVERSE = [
    ("AAPL", "Apple", "stock", None, 190.0),
    ("MSFT", "Microsoft", "stock", None, 420.0),
    ("GOOGL", "Alphabet", "stock", None, 175.0),
    ("AMZN", "Amazon", "stock", None, 185.0),
    ("NVDA", "Nvidia", "stock", None, 120.0),
    ("TSLA", "Tesla", "stock", None, 250.0),
    ("META", "Meta", "stock", None, 500.0),
    ("BTC", "Bitcoin", "crypto", "bitcoin", 65000.0),
    ("ETH", "Ethereum", "crypto", "ethereum", 3400.0),
    ("SOL", "Solana", "crypto", "solana", 150.0),
    ("DOGE", "Dogecoin", "crypto", "dogecoin", 0.12),
    ("XRP", "XRP", "crypto", "ripple", 0.5),
    ("ADA", "Cardano", "crypto", "cardano", 0.4),
]

# Per-kind random-walk volatility (std-dev of log-return per price tick).
VOL = {"stock": 0.004, "crypto": 0.010}


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_UP, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_DOWN, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_SYMBOL, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_NEUTRAL, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_CRYPTO, curses.COLOR_MAGENTA, -1)


# ---------------------------------------------------------------------------
# Formatting helpers (pure)
# ---------------------------------------------------------------------------

def fmt_price(p):
    """Format a price with a sensible number of decimals for its magnitude."""
    if p >= 1000:
        return "{:,.0f}".format(p)
    if p >= 1:
        return "{:,.2f}".format(p)
    return "{:.4f}".format(p)


def sparkline(values, width):
    """Render `values` as block-character sparkline of at most `width` chars."""
    if not values or width <= 0:
        return ""
    vals = list(values)[-width:]
    lo, hi = min(vals), max(vals)
    span = hi - lo
    out = []
    for v in vals:
        if span <= 0:
            idx = len(SPARK_CHARS) // 2
        else:
            idx = int((v - lo) / span * (len(SPARK_CHARS) - 1) + 0.5)
        out.append(SPARK_CHARS[max(0, min(len(SPARK_CHARS) - 1, idx))])
    return "".join(out)


# ---------------------------------------------------------------------------
# Live data fetching (best-effort; used only when simulate=False)
# ---------------------------------------------------------------------------

_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120 Safari/537.36")


def _http_get(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def fetch_crypto(universe, timeout=4.0):
    """Return {symbol: price} for crypto via CoinGecko, or {} on failure."""
    ids = [cg for _s, _n, kind, cg, _p in universe if kind == "crypto" and cg]
    if not ids:
        return {}
    id_to_sym = {cg: s for s, _n, kind, cg, _p in universe
                 if kind == "crypto" and cg}
    url = ("https://api.coingecko.com/api/v3/simple/price?ids="
           + ",".join(ids) + "&vs_currencies=usd")
    try:
        data = json.loads(_http_get(url, timeout))
    except Exception:
        return {}
    out = {}
    for cg, sym in id_to_sym.items():
        node = data.get(cg)
        if isinstance(node, dict) and "usd" in node:
            try:
                out[sym] = float(node["usd"])
            except (TypeError, ValueError):
                pass
    return out


def _fetch_stocks_batch(syms, timeout):
    """One Yahoo v7 request for all symbols. Returns {symbol: price} (may be
    partial/empty). Cheapest and least rate-limited path when it's available."""
    url = ("https://query1.finance.yahoo.com/v7/finance/quote?symbols="
           + ",".join(syms))
    try:
        data = json.loads(_http_get(url, timeout))
        results = data["quoteResponse"]["result"]
    except Exception:
        return {}
    out = {}
    for item in results:
        sym = item.get("symbol")
        price = item.get("regularMarketPrice")
        if sym in syms and price and float(price) > 0:
            out[sym] = float(price)
    return out


def _fetch_stock_chart(sym, timeout):
    """One symbol via the Yahoo v8 chart endpoint (no auth/crumb needed)."""
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/%s"
           "?interval=1d&range=1d" % sym)
    try:
        data = json.loads(_http_get(url, timeout))
        meta = data["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice")
        if price is not None and float(price) > 0:
            return float(price)
    except Exception:
        pass
    return None


def fetch_stocks(universe, timeout=4.0):
    """Return {symbol: price} for stocks, best-effort. Tries the batch quote
    endpoint first (one gentle request), then fills any missing symbols with
    sequential per-symbol chart requests. Deliberately NOT parallel — a burst
    of simultaneous requests is what trips Yahoo's rate limiting."""
    syms = [s for s, _n, kind, _cg, _p in universe if kind == "stock"]
    if not syms:
        return {}
    out = _fetch_stocks_batch(syms, timeout)
    for sym in syms:
        if sym in out:
            continue
        price = _fetch_stock_chart(sym, timeout)
        if price is not None:
            out[sym] = price
    return out


# ---------------------------------------------------------------------------
# Price cache (survives between runs)
# ---------------------------------------------------------------------------

def load_price_cache(path=CACHE_FILE):
    """Return ({symbol: price}, timestamp) from the cache file, or ({}, 0)."""
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}, 0.0
    prices = {}
    for sym, v in (data.get("prices") or {}).items():
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if fv > 0:
            prices[sym] = fv
    try:
        ts = float(data.get("timestamp", 0))
    except (TypeError, ValueError):
        ts = 0.0
    return prices, ts


def save_price_cache(prices, path=CACHE_FILE):
    """Write the latest known prices + a timestamp; best-effort."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"timestamp": time.time(), "prices": prices}, f, indent=2)
        os.replace(tmp, path)
    except OSError:
        pass


def _fmt_age(seconds):
    seconds = int(max(0, seconds))
    if seconds < 90:
        return "%ds ago" % seconds
    if seconds < 5400:
        return "%dm ago" % (seconds // 60)
    if seconds < 172800:
        return "%dh ago" % (seconds // 3600)
    return "%dd ago" % (seconds // 86400)


# ---------------------------------------------------------------------------
# Ticker state
# ---------------------------------------------------------------------------

class Ticker:
    def __init__(self, universe, simulate, refresh_interval):
        self.universe = universe
        self.simulate = simulate
        self.refresh_interval = refresh_interval
        self.lock = threading.Lock()
        self.live_prices = {}          # symbol -> latest fetched price
        self.live_kinds = set()        # kinds currently backed by live data
        self._stop = threading.Event()
        self._thread = None

        # Seed starting prices from the most recent cached pull when available,
        # so a rate-limited run still opens on real (if slightly stale) prices.
        cached, cache_ts = load_price_cache()
        self.cache_ts = cache_ts
        self.loaded_from_cache = bool(cached)
        # Pre-seed known prices from the cache so a later partial fetch (e.g.
        # crypto succeeds, stocks are rate-limited) merges into — rather than
        # overwrites — the previously cached symbols. live_kinds stays empty,
        # so the label reads CACHED until a real fetch lands this run.
        self.live_prices = dict(cached)

        self.state = {}
        for sym, name, kind, cg, seed in universe:
            start = cached.get(sym, float(seed))
            self.state[sym] = {
                "name": name, "kind": kind, "cg": cg,
                "price": start, "target": start,
                "open": start, "hist": deque([start], HIST_LEN),
                # Share count giving each symbol ~equal starting notional.
                "shares": NOTIONAL_PER_SYMBOL / start if start else 0.0,
            }
        self.port_open = self.portfolio_value()
        self.port_hist = deque([self.port_open], PORTFOLIO_HIST_LEN)

    # --- live fetching thread -------------------------------------------
    def start(self):
        if self.simulate:
            return
        self._thread = threading.Thread(target=self._fetch_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _apply_fetch(self, prices, kind):
        """Merge a fetched price set and persist the cache immediately."""
        if not prices:
            return
        with self.lock:
            self.live_prices.update(prices)
            self.live_kinds.add(kind)
            snapshot = dict(self.live_prices)
        # Persist as soon as anything arrives, so even a short run (or one
        # where the other asset class is slow/rate-limited) leaves a cache.
        save_price_cache(snapshot)

    def _fetch_loop(self):
        while not self._stop.is_set():
            # Crypto first and cached on its own — it's the fast, reliable
            # source, so we don't want a slow stock fetch to delay its write.
            self._apply_fetch(fetch_crypto(self.universe), "crypto")
            if self._stop.is_set():
                break
            self._apply_fetch(fetch_stocks(self.universe), "stock")
            # Fetch far less often than the UI ticks; APIs rate-limit.
            self._stop.wait(self.refresh_interval)

    # --- price evolution -------------------------------------------------
    def tick(self):
        """Advance targets (live snap or simulated walk) and ease prices."""
        with self.lock:
            live_prices = dict(self.live_prices)
            live_kinds = set(self.live_kinds)
        for sym, st in self.state.items():
            if not self.simulate and st["kind"] in live_kinds \
                    and sym in live_prices:
                st["target"] = live_prices[sym]
            else:
                vol = VOL.get(st["kind"], 0.005)
                drift = random.gauss(0.0, vol)
                st["target"] = max(1e-6, st["target"] * math.exp(drift))
            # Ease displayed price toward the target for smooth motion.
            st["price"] += (st["target"] - st["price"]) * 0.35
            st["hist"].append(st["price"])
        self.port_hist.append(self.portfolio_value())

    def portfolio_value(self):
        return sum(st["shares"] * st["price"] for st in self.state.values())

    def portfolio_change_pct(self):
        if self.port_open <= 0:
            return 0.0
        return (self.portfolio_value() - self.port_open) / self.port_open * 100.0

    def is_live(self):
        with self.lock:
            return (not self.simulate) and bool(self.live_kinds)

    def mode_label(self):
        """Status text: LIVE (fetched this run), CACHED (seeded from a prior
        pull but not yet refreshed), or SIMULATED."""
        if self.is_live():
            return "LIVE"
        if (not self.simulate) and self.loaded_from_cache:
            return "CACHED " + _fmt_age(time.time() - self.cache_ts
                                        if self.cache_ts else 0)
        return "SIMULATED"

    def change_pct(self, sym):
        st = self.state[sym]
        if st["open"] <= 0:
            return 0.0
        return (st["price"] - st["open"]) / st["open"] * 100.0


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def build_tape(ticker):
    """Build the scrolling marquee as parallel (chars, attrs) lists."""
    chars, attrs = [], []

    def push(text, attr):
        for ch in text:
            chars.append(ch)
            attrs.append(attr)

    sep_attr = curses.color_pair(COLOR_NEUTRAL) | curses.A_DIM
    for sym, _n, kind, _cg, _p in ticker.universe:
        st = ticker.state[sym]
        pct = ticker.change_pct(sym)
        up = pct >= 0
        sym_attr = curses.color_pair(
            COLOR_CRYPTO if kind == "crypto" else COLOR_SYMBOL) | curses.A_BOLD
        move_attr = curses.color_pair(
            COLOR_UP if up else COLOR_DOWN) | curses.A_BOLD
        arrow = UP_ARROW if up else DOWN_ARROW
        push(sym + " ", sym_attr)
        push(fmt_price(st["price"]) + " ", curses.color_pair(COLOR_NEUTRAL))
        push("%s%+.2f%% " % (arrow, pct), move_attr)
        push("   ", sep_attr)
    return chars, attrs


def draw_tape(stdscr, row, max_x, chars, attrs, offset):
    n = len(chars)
    if n == 0:
        return
    for x in range(max_x):
        i = (offset + x) % n
        try:
            stdscr.addstr(row, x, chars[i], attrs[i])
        except curses.error:
            pass


def _downsample(seq, n):
    """Evenly sample `seq` down to at most `n` points (keeps ends)."""
    seq = list(seq)
    if n <= 0 or len(seq) <= n:
        return seq
    step = (len(seq) - 1) / (n - 1)
    return [seq[int(round(i * step))] for i in range(n)]


def draw_portfolio(stdscr, top, height, max_x, ticker):
    """Header line + line chart of total portfolio value across the bottom."""
    value = ticker.portfolio_value()
    pct = ticker.portfolio_change_pct()
    up = pct >= 0
    trend_attr = curses.color_pair(
        COLOR_UP if up else COLOR_DOWN) | curses.A_BOLD
    arrow = UP_ARROW if up else DOWN_ARROW

    def put(yy, xx, text, attr):
        try:
            stdscr.addstr(yy, xx, text[:max(0, max_x - xx - 1)], attr)
        except curses.error:
            pass

    put(top, 2, "PORTFOLIO", curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
    put(top, 12, "$" + "{:,.0f}".format(value),
        curses.color_pair(COLOR_NEUTRAL) | curses.A_BOLD)
    put(top, 26, "%s%+.2f%%" % (arrow, pct), trend_attr)
    put(top, 40, "(%d holdings, since start)" % len(ticker.state),
        curses.color_pair(COLOR_NEUTRAL) | curses.A_DIM)

    chart_h = height - 1
    if chart_h < 2:
        return
    series = _downsample(ticker.port_hist, max(10, max_x - 12))
    series = [v for v in series if v == v and abs(v) != float("inf")]
    if len(series) < 2:
        return
    try:
        chart = acp.plot(series, {"height": chart_h})
    except Exception:
        return
    for i, line in enumerate(chart.split("\n")):
        put(top + 1 + i, 0, line, trend_attr)


def panel_rows_needed(n, max_x):
    """Rows of panels required to show `n` symbols at the current width."""
    cols = max(1, max_x // PANEL_W)
    return (n + cols - 1) // cols


def draw_panels(stdscr, top, bottom, max_x, ticker):
    panel_w = PANEL_W
    panel_h = PANEL_H
    cols = max(1, max_x // panel_w)
    gap_x = (max_x - cols * panel_w) // max(1, cols)
    items = list(ticker.universe)
    r = top
    idx = 0
    while r + panel_h <= bottom and idx < len(items):
        for c in range(cols):
            if idx >= len(items):
                break
            sym = items[idx][0]
            st = ticker.state[sym]
            kind = st["kind"]
            pct = ticker.change_pct(sym)
            up = pct >= 0
            x = c * (panel_w + gap_x) + 1
            sym_attr = curses.color_pair(
                COLOR_CRYPTO if kind == "crypto" else COLOR_SYMBOL) \
                | curses.A_BOLD
            move_attr = curses.color_pair(
                COLOR_UP if up else COLOR_DOWN) | curses.A_BOLD
            arrow = UP_ARROW if up else DOWN_ARROW

            def put(yy, xx, text, attr):
                try:
                    stdscr.addstr(yy, xx, text[:panel_w - 1], attr)
                except curses.error:
                    pass

            put(r, x, "%-6s" % sym, sym_attr)
            put(r, x + 7, st["name"][:panel_w - 9],
                curses.color_pair(COLOR_NEUTRAL) | curses.A_DIM)
            put(r + 1, x, "%12s" % fmt_price(st["price"]),
                curses.color_pair(COLOR_NEUTRAL) | curses.A_BOLD)
            put(r + 1, x + 13, "%s%+.2f%%" % (arrow, pct), move_attr)
            spark = sparkline(st["hist"], panel_w - 1)
            put(r + 2, x, spark, move_attr)
            idx += 1
        r += panel_h


def run(stdscr, duration, frame_delay, simulate, refresh_interval, symbols):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.timeout(int(frame_delay * 1000))

    universe = DEFAULT_UNIVERSE
    if symbols:
        wanted = {s.upper() for s in symbols}
        universe = [u for u in DEFAULT_UNIVERSE if u[0] in wanted] \
            or DEFAULT_UNIVERSE

    ticker = Ticker(universe, simulate, refresh_interval)
    ticker.start()

    start = time.monotonic()
    last_tick = start
    price_tick_interval = 0.5
    offset = 0
    chars, attrs = build_tape(ticker)

    try:
        while True:
            now = time.monotonic()
            if now - start >= duration:
                break

            if now - last_tick >= price_tick_interval:
                ticker.tick()
                chars, attrs = build_tape(ticker)
                last_tick = now

            max_y, max_x = stdscr.getmaxyx()
            stdscr.erase()

            draw_tape(stdscr, 0, max_x, chars, attrs, offset)
            try:
                stdscr.addstr(1, 0, "─" * max_x,
                              curses.color_pair(COLOR_NEUTRAL) | curses.A_DIM)
            except curses.error:
                pass

            # Panels take the rows they need at the top; the portfolio graph
            # then fills everything from just below them down to the label row,
            # so no middle band is left empty. On cramped screens the panel
            # area is capped so the graph always keeps at least MIN_GRAPH_H
            # rows (the ticker tape still scrolls every symbol).
            MIN_GRAPH_H = 6
            available = (max_y - 1) - PANELS_TOP
            prows = panel_rows_needed(len(ticker.universe), max_x)
            panels_h = prows * PANEL_H
            max_panel_h = max(PANEL_H, available - 1 - MIN_GRAPH_H)
            panels_h = min(panels_h, max_panel_h)
            panels_h = (panels_h // PANEL_H) * PANEL_H   # whole panel rows
            panels_bottom = PANELS_TOP + panels_h
            draw_panels(stdscr, PANELS_TOP, panels_bottom, max_x, ticker)

            graph_top = panels_bottom + 1        # leave a divider row
            graph_h = (max_y - 1) - graph_top    # label sits on max_y - 1
            if graph_h >= 4:
                try:
                    stdscr.addstr(panels_bottom, 0, "─" * max_x,
                                  curses.color_pair(COLOR_NEUTRAL)
                                  | curses.A_DIM)
                except curses.error:
                    pass
                draw_portfolio(stdscr, graph_top, graph_h, max_x, ticker)

            label = ("stock_crypto_ticker  %d symbols  [%s]"
                     % (len(universe), ticker.mode_label()))
            try:
                stdscr.addstr(max_y - 1, 2, label[:max_x - 4],
                              curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
            except curses.error:
                pass

            stdscr.refresh()
            offset = (offset + 1) % max(1, len(chars))
            key = stdscr.getch()
            if key in (ord("q"), ord("Q"), 27):
                break
    finally:
        ticker.stop()


def main(duration=30, frame_delay=0.12, simulate=True, refresh_interval=15.0,
         symbols=None):
    duration = float(duration)
    frame_delay = float(frame_delay)
    if isinstance(simulate, str):
        simulate = simulate.strip().lower() not in ("false", "0", "no", "off")
    else:
        simulate = bool(simulate)
    refresh_interval = max(5.0, float(refresh_interval))
    if isinstance(symbols, str):
        symbols = [s.strip() for s in symbols.split(",") if s.strip()]
    curses.wrapper(lambda stdscr: run(
        stdscr, duration, frame_delay, simulate, refresh_interval, symbols))


if __name__ == "__main__":
    main()
