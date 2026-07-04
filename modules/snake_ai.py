import curses
import locale
import random
import time
from collections import deque


COLOR_HEAD = 1
COLOR_BODY = 2
COLOR_BODY_OLD = 3
COLOR_FOOD = 4
COLOR_WALL = 5
COLOR_LABEL = 6

DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))

CLEAR_FRACTION = 0.6   # board considered "cleared" at this fill ratio
FLASH_SECONDS = 1.5


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_HEAD, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_BODY, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_BODY_OLD, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_FOOD, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_WALL, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_LABEL, curses.COLOR_CYAN, -1)


def bfs_path(start, goal, blocked, w, h):
    """Shortest path from start to goal on a w*h grid, avoiding blocked cells.

    Returns a list of cells (excluding start, including goal), or None.
    The goal cell is always considered enterable, even if in blocked.
    """
    if start == goal:
        return []
    prev = {start: None}
    q = deque((start,))
    while q:
        cur = q.popleft()
        cx, cy = cur
        for dx, dy in DIRS:
            nxt = (cx + dx, cy + dy)
            if nxt in prev:
                continue
            if nxt == goal:
                path = [nxt]
                node = cur
                while node != start:
                    path.append(node)
                    node = prev[node]
                path.reverse()
                return path
            nx, ny = nxt
            if 0 <= nx < w and 0 <= ny < h and nxt not in blocked:
                prev[nxt] = cur
                q.append(nxt)
    return None


def simulate_path(snake, path, food):
    """Walk the snake (deque, head first) along path; grow on the food cell.

    Returns the resulting deque, or None if the path collides with the body.
    """
    s = deque(snake)
    occupied = set(s)
    for cell in path:
        grow = (cell == food)
        tail_cell = s[-1]
        if cell in occupied and not (cell == tail_cell and not grow):
            return None
        if not grow:
            occupied.discard(s.pop())
        s.appendleft(cell)
        occupied.add(cell)
    return s


def tail_reachable(snake, w, h):
    """Can the head still reach the tail cell? (Standard survival check.)"""
    head, tail = snake[0], snake[-1]
    if head == tail:
        return True
    blocked = set(snake)
    blocked.discard(head)
    blocked.discard(tail)
    return bfs_path(head, tail, blocked, w, h) is not None


class SnakeGame:
    """Headless self-playing snake on a w*h grid."""

    def __init__(self, w, h, rng=None):
        self.w = int(w)
        self.h = int(h)
        self.rng = rng if rng is not None else random.Random()
        self.reset()

    def reset(self):
        cx, cy = self.w // 2, self.h // 2
        self.snake = deque([(cx, cy), (cx - 1, cy), (cx - 2, cy)])
        self.score = 0
        self.dead = False
        self.strategy = "→ food"
        self.food = None
        self._place_food()

    def _place_food(self):
        occupied = set(self.snake)
        free = [(x, y) for x in range(self.w) for y in range(self.h)
                if (x, y) not in occupied]
        self.food = self.rng.choice(free) if free else None

    def _plan(self):
        """Pick the next head cell. Food path if provably survivable,
        otherwise chase the tail from as far away as possible."""
        head, tail = self.snake[0], self.snake[-1]
        body = set(self.snake)

        # 1) Shortest path to food, taken only if afterwards the head
        #    can still reach the tail.
        if self.food is not None:
            blocked = set(body)
            blocked.discard(tail)
            blocked.discard(head)
            path = bfs_path(head, self.food, blocked, self.w, self.h)
            if path:
                final = simulate_path(self.snake, path, self.food)
                if final is not None and tail_reachable(final, self.w, self.h):
                    self.strategy = "→ food"
                    return path[0]

        # 2) Tail chase: among safe one-step moves keep the tail reachable,
        #    preferring the move farthest from the tail (stalls gracefully)
        #    and avoiding accidental growth.
        best = None
        best_key = None
        fallback = None
        fallback_key = -1
        for dx, dy in DIRS:
            nxt = (head[0] + dx, head[1] + dy)
            nx, ny = nxt
            if not (0 <= nx < self.w and 0 <= ny < self.h):
                continue
            grow = (nxt == self.food)
            if nxt in body and not (nxt == tail and not grow):
                continue
            ns = deque(self.snake)
            ns.appendleft(nxt)
            if not grow:
                ns.pop()
            ntail = ns[-1]
            nblocked = set(ns)
            nblocked.discard(nxt)
            nblocked.discard(ntail)
            tpath = bfs_path(nxt, ntail, nblocked, self.w, self.h)
            if tpath is not None:
                key = (0 if grow else 1, len(tpath))
                if best_key is None or key > best_key:
                    best_key = key
                    best = nxt
            # last-resort fallback: most open neighbours
            free_deg = 0
            for ddx, ddy in DIRS:
                cell = (nx + ddx, ny + ddy)
                if (0 <= cell[0] < self.w and 0 <= cell[1] < self.h
                        and cell not in body):
                    free_deg += 1
            if free_deg > fallback_key:
                fallback_key = free_deg
                fallback = nxt
        if best is not None:
            self.strategy = "chasing tail"
            return best
        if fallback is not None:
            self.strategy = "cornered"
            return fallback
        return None

    def step(self):
        """Advance one tick. Returns 'ok', 'ate', 'dead' or 'cleared'."""
        if self.dead:
            return "dead"
        move = self._plan()
        if move is None:
            self.dead = True
            return "dead"
        grow = (move == self.food)
        mx, my = move
        if (not (0 <= mx < self.w and 0 <= my < self.h)
                or (move in set(self.snake)
                    and not (move == self.snake[-1] and not grow))):
            self.dead = True
            return "dead"
        self.snake.appendleft(move)
        if grow:
            self.score += 1
            if len(self.snake) >= int(CLEAR_FRACTION * self.w * self.h):
                return "cleared"
            self._place_food()
            if self.food is None:
                return "cleared"
            return "ate"
        self.snake.pop()
        return "ok"


def body_style(i, length):
    """Char + attr for body segment i (0 = head) of a snake of given length."""
    frac = i / max(1, length - 1)
    if frac < 0.4:
        return "o", curses.color_pair(COLOR_BODY) | curses.A_BOLD
    if frac < 0.75:
        return "o", curses.color_pair(COLOR_BODY)
    return "·", curses.color_pair(COLOR_BODY_OLD) | curses.A_DIM


def run(stdscr, duration, frame_delay, min_delay):
    init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass

    rng = random.Random()
    game = None
    board_w = board_h = 0
    flash_msg = ""
    flash_until = 0.0

    start = time.monotonic()
    while True:
        now = time.monotonic()
        if now - start >= duration:
            break

        max_y, max_x = stdscr.getmaxyx()
        # Board: 2 screen columns per cell, 1-char border, bottom label line.
        bw = max(8, min(50, (max_x - 3) // 2))
        bh = max(6, min(30, max_y - 4))
        if game is None or bw != board_w or bh != board_h:
            board_w, board_h = bw, bh
            game = SnakeGame(bw, bh, rng)
            flash_msg = ""

        length = len(game.snake)
        eff_delay = max(min_delay, frame_delay - (frame_delay - min_delay)
                        * min(1.0, max(0, length - 3) / 50.0))
        stdscr.timeout(max(1, int(eff_delay * 1000)))

        if now >= flash_until:
            if flash_msg:
                flash_msg = ""
                game.reset()
            status = game.step()
            if status == "dead":
                flash_msg = f"GAME OVER — score {game.score}"
                flash_until = now + FLASH_SECONDS
            elif status == "cleared":
                flash_msg = f"BOARD CLEARED — score {game.score}"
                flash_until = now + FLASH_SECONDS

        stdscr.erase()
        ox = max(0, (max_x - (2 * bw + 2)) // 2)
        oy = max(0, (max_y - 1 - (bh + 2)) // 2)
        wall_attr = curses.color_pair(COLOR_WALL) | curses.A_DIM
        hline = "#" * (2 * bw + 2)
        for row, text in ((oy, hline), (oy + bh + 1, hline)):
            try:
                stdscr.addstr(row, ox, text[:max(0, max_x - ox - 1)], wall_attr)
            except curses.error:
                pass
        for y in range(bh):
            for col in (ox, ox + 2 * bw + 1):
                try:
                    stdscr.addstr(oy + 1 + y, col, "#", wall_attr)
                except curses.error:
                    pass

        if game.food is not None:
            fx, fy = game.food
            food_attr = curses.color_pair(COLOR_FOOD)
            if int(now * 2.5) % 2 == 0:
                food_attr |= curses.A_BOLD
            try:
                stdscr.addstr(oy + 1 + fy, ox + 1 + 2 * fx, "*", food_attr)
            except curses.error:
                pass

        n = len(game.snake)
        for i, (sx, sy) in enumerate(game.snake):
            if i == 0:
                ch = "@"
                attr = curses.color_pair(COLOR_HEAD) | curses.A_BOLD
            else:
                ch, attr = body_style(i, n)
            try:
                stdscr.addstr(oy + 1 + sy, ox + 1 + 2 * sx, ch, attr)
            except curses.error:
                pass

        if flash_msg:
            msg = f"  {flash_msg}  "
            try:
                stdscr.addstr(oy + 1 + bh // 2,
                              max(0, ox + 1 + bw - len(msg) // 2),
                              msg[:max(0, max_x - 1)],
                              curses.color_pair(COLOR_LABEL)
                              | curses.A_BOLD | curses.A_REVERSE)
            except curses.error:
                pass

        info = (f"Snake AI  score={game.score}  len={len(game.snake)}  "
                f"{game.strategy}  delay={eff_delay * 1000:.0f}ms")
        try:
            stdscr.addstr(max_y - 1, 2, info[:max(0, max_x - 4)],
                          curses.color_pair(COLOR_LABEL) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return


def main(duration=30, frame_delay=0.05, min_delay=0.02):
    duration = float(duration)
    frame_delay = max(0.005, float(frame_delay))
    min_delay = max(0.005, min(float(min_delay), frame_delay))
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        pass
    curses.wrapper(lambda stdscr: run(stdscr, duration, frame_delay, min_delay))


if __name__ == "__main__":
    main()
