#!/usr/bin/env python3
"""Web UI for editing the JSON configs that drive main.py.

Stdlib-only (no new dependencies) so it runs anywhere the visualizer does,
including offline. Serves a single-page editor plus a small JSON API:

    GET  /                      the editor page
    GET  /api/state             {configs, modules, active}
    GET  /api/config?name=X     contents of data/configs/X
    POST /api/config?name=X     save body as data/configs/X (must parse as JSON)
    GET  /api/params?module=M   literal kwarg defaults of modules/M.py:main()
    POST /api/apply?name=X      restart the tmux "vis" session with config X
                                and remember it in data/active_config so it
                                survives reboots (start_vis.sh reads it)

Run:  python config_ui/server.py [--port 8765] [--bind 0.0.0.0]

There is no authentication — bind to 127.0.0.1 if the machine sits on a
network you don't trust.
"""
import argparse
import ast
import json
import re
import shutil
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "data" / "configs"
ACTIVE_FILE = ROOT / "data" / "active_config"
INDEX_FILE = Path(__file__).resolve().parent / "index.html"
DOCS_FILE = Path(__file__).resolve().parent / "param_docs.json"

CONFIG_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+\.json$")
MODULE_NAME_RE = re.compile(r"^[a-z0-9_]+$")
TMUX_SESSION = "vis"


def list_modules():
    """Module names from main.py's MODULES dict, without importing it."""
    tree = ast.parse((ROOT / "main.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            if any(getattr(t, "id", None) == "MODULES" for t in node.targets):
                return sorted(k.value for k in node.value.keys
                              if isinstance(k, ast.Constant))
    return []


def module_params(name):
    """Literal kwarg defaults of a module's main(), via ast (no import)."""
    if not MODULE_NAME_RE.fullmatch(name):
        raise ValueError("bad module name")
    tree = ast.parse((ROOT / "modules" / f"{name}.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            params = {}
            pos, defaults = node.args.args, node.args.defaults
            for arg, default in zip(pos[len(pos) - len(defaults):], defaults):
                try:
                    params[arg.arg] = ast.literal_eval(default)
                except (ValueError, SyntaxError):
                    params[arg.arg] = None
            for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
                try:
                    params[arg.arg] = ast.literal_eval(default) if default else None
                except (ValueError, SyntaxError):
                    params[arg.arg] = None
            return params
    return {}


def active_config():
    try:
        name = ACTIVE_FILE.read_text().strip()
        if CONFIG_NAME_RE.fullmatch(name) and (CONFIG_DIR / name).exists():
            return name
    except OSError:
        pass
    return "default.json"


def apply_config(name):
    """Point data/active_config at `name` and restart the display's tmux pane."""
    ACTIVE_FILE.write_text(name + "\n")
    if not shutil.which("tmux"):
        return False, "saved as boot config, but tmux is not installed here"
    has = subprocess.run(["tmux", "has-session", "-t", TMUX_SESSION],
                         capture_output=True)
    if has.returncode != 0:
        return False, ("saved as boot config, but the visualizer isn't running "
                       "— launch it from the desktop icon")
    py = ROOT / ".venv" / "bin" / "python"
    py = str(py) if py.exists() else "python3"
    inner = f'cd "{ROOT}" && exec {py} main.py {name}'
    subprocess.run(["tmux", "respawn-pane", "-k", "-t", TMUX_SESSION,
                    f"bash -c '{inner}'"], check=True)
    return True, f"display restarted with {name}"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quieter journal
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _error(self, code, msg):
        self._send(code, {"error": msg})

    def _config_path(self, query):
        name = parse_qs(query).get("name", [""])[0]
        if not CONFIG_NAME_RE.fullmatch(name):
            return None, None
        return name, CONFIG_DIR / name

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            self._send(200, INDEX_FILE.read_bytes(), "text/html; charset=utf-8")
        elif url.path == "/api/state":
            self._send(200, {
                "configs": sorted(p.name for p in CONFIG_DIR.glob("*.json")),
                "modules": list_modules(),
                "active": active_config(),
            })
        elif url.path == "/api/config":
            name, path = self._config_path(url.query)
            if not name or not path.exists():
                return self._error(404, "no such config")
            self._send(200, path.read_bytes())
        elif url.path == "/api/docs":
            body = DOCS_FILE.read_bytes() if DOCS_FILE.exists() else b"{}"
            self._send(200, body)
        elif url.path == "/api/params":
            name = parse_qs(url.query).get("module", [""])[0]
            try:
                self._send(200, module_params(name))
            except (ValueError, OSError):
                self._error(404, "no such module")
        else:
            self._error(404, "not found")

    def do_POST(self):
        url = urlparse(self.path)
        name, path = self._config_path(url.query)
        if not name:
            return self._error(400, "config name must look like name.json")
        if url.path == "/api/config":
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            try:
                cfg = json.loads(body)
                assert isinstance(cfg, dict)
            except (ValueError, AssertionError):
                return self._error(400, "body is not a JSON object")
            path.write_text(json.dumps(cfg, indent=4) + "\n")
            self._send(200, {"ok": True, "saved": name})
        elif url.path == "/api/apply":
            if not path.exists():
                return self._error(404, "no such config")
            try:
                ok, msg = apply_config(name)
            except subprocess.CalledProcessError as exc:
                return self._error(500, f"tmux respawn failed: {exc}")
            self._send(200, {"ok": ok, "message": msg})
        else:
            self._error(404, "not found")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--bind", default="0.0.0.0")
    args = ap.parse_args()
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    print(f"config UI on http://{args.bind}:{args.port}  (root: {ROOT})")
    server.serve_forever()


if __name__ == "__main__":
    main()
