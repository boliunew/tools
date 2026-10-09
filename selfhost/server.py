#!/usr/bin/env python3
"""Home server for the tools site (standard library only).

  • serves the whole site (with Range support so the radio / audio can seek)
  • /api/kv       private sync of the browsers' saved progress (词库, 自选股, 购物清单 …) between phone and computer
  • /api/issues   the local stand-in for GitHub issues (股价提醒 / 网页监控); a new or edited one is checked right away
  • /api/ping     lets pages know they are running at home
  • /api/stream   relays an http-only internet radio stream, so the https page may play it (网络电台)
  • /api/audd     forwards a recorded radio clip to the AudD song-recognition API (网络电台 → 识别歌曲)

Listens on 127.0.0.1 only — reach it through `tailscale serve`, so only your own devices can open it.
Env: PORT (8080), TOOLS_DATA, OWNER, NTFY_URL, NTFY_SUB (public subscribe URL shown in the page), PUBLIC_URL, PYTHON
"""
import http.server
import ipaddress
import socket
import urllib.request
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import localgh  # noqa: E402

DATA = localgh.DATA
KV = os.path.join(DATA, "kv")
PORT = int(os.environ.get("PORT", "8080"))
PY = os.environ.get("PYTHON") or sys.executable
HIDDEN = re.compile(r"^/(\.git|\.venv|\.local-data|selfhost/config\.env)(/|$)")
KEY_OK = re.compile(r"^[\w:.\-]{1,120}$")
kv_lock = threading.Lock()


def kv_path(k):
    return os.path.join(KV, urllib.parse.quote(k, safe="") + ".json")


def run_bg(args, env_extra):
    """run one of the tools' scripts in the background (same environment the timers use)"""
    env = dict(os.environ, LOCAL_ISSUES="1", **env_extra)
    env.setdefault("OWNER", localgh.OWNER)
    log = open(os.path.join(DATA, "logs", "events.log"), "a")
    log.write("\n== %s %s %s\n" % (time.strftime("%F %T"), " ".join(args), env_extra))
    log.flush()
    subprocess.Popen([PY] + args, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)


def on_issue(issue, action):
    title = (issue.get("title") or "").strip()
    n = str(issue["number"])
    if title.startswith("股价提醒") and action in ("opened", "edited", "reopened"):
        run_bg(["stocks/alerts.py", "ack"], {"ISSUE_NUMBER": n})
    elif title.startswith("监控"):
        run_bg(["monitor/check.py"], {"EVENT_NAME": "issues", "ISSUE_NUMBER": n, "ISSUE_ACTION": action})


class H(http.server.SimpleHTTPRequestHandler):
    server_version = "tools-home/1.0"

    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def log_message(self, fmt, *args):
        first = str(args[0]) if args else ""
        if "/api/" in first or fmt.startswith("code") or os.environ.get("VERBOSE"):
            sys.stderr.write("%s %s\n" % (time.strftime("%T"), fmt % args))

    # ------------------------------------------------------------------ helpers
    def send_json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def body_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 20 * 1024 * 1024:
            raise ValueError("too large")
        raw = self.rfile.read(n) if n else b""
        return json.loads(raw.decode("utf-8") or "null")

    def end_headers(self):
        p = self.path.split("?")[0]
        if not p.startswith("/api/") and (p.endswith((".json", ".html", ".txt", ".js", ".m3u")) or p.endswith("/")):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    # ------------------------------------------------------------------ static (+ Range)
    def send_head(self):
        p = urllib.parse.urlsplit(self.path).path
        if HIDDEN.match(p):
            self.send_error(404)
            return None
        path = self.translate_path(self.path)
        rng = self.headers.get("Range")
        if not rng or os.path.isdir(path) or not os.path.exists(path):
            return super().send_head()
        size = os.path.getsize(path)
        m = re.match(r"bytes=(\d*)-(\d*)", rng)
        if not m:
            return super().send_head()
        a = int(m.group(1)) if m.group(1) else max(0, size - int(m.group(2) or 0))
        b = int(m.group(2)) if m.group(1) and m.group(2) else size - 1
        b = min(b, size - 1)
        if a > b:
            self.send_response(416)
            self.send_header("Content-Range", "bytes */%d" % size)
            self.end_headers()
            return None
        f = open(path, "rb")
        f.seek(a)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", "bytes %d-%d/%d" % (a, b, size))
        self.send_header("Content-Length", str(b - a + 1))
        self.end_headers()
        self._left = b - a + 1
        return f

    def copyfile(self, src, dst):
        left = getattr(self, "_left", None)
        if left is None:
            return super().copyfile(src, dst)
        while left > 0:
            chunk = src.read(min(65536, left))
            if not chunk:
                break
            dst.write(chunk)
            left -= len(chunk)

    # ------------------------------------------------------------------ API
    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        if not u.path.startswith("/api/"):
            return super().do_GET()
        q = urllib.parse.parse_qs(u.query)
        try:
            if u.path == "/api/stream":
                return self.stream(urllib.parse.parse_qs(u.query).get("u", [""])[0])
            if u.path == "/api/ping":
                return self.send_json({"ok": 1, "local": 1, "ntfy": os.environ.get("NTFY_SUB", ""), "time": int(time.time())})
            if u.path == "/api/kv":
                keys = q.get("keys", [""])[0]
                out = {}
                with kv_lock:
                    names = os.listdir(KV) if os.path.isdir(KV) else []
                    for fn in names:
                        if not fn.endswith(".json"):
                            continue
                        k = urllib.parse.unquote(fn[:-5])
                        if keys and k not in keys.split(","):
                            continue
                        try:
                            with open(os.path.join(KV, fn), encoding="utf-8") as f:
                                d = json.load(f)
                        except ValueError:
                            continue
                        out[k] = d if keys else d.get("mt", 0)
                return self.send_json(out)
            if u.path == "/api/issues":
                return self.send_json(localgh.list_issues(q.get("state", ["open"])[0]))
            m = re.match(r"^/api/issues/(\d+)$", u.path)
            if m:
                i = localgh.get_issue(m.group(1), with_comments=True)
                return self.send_json(i) if i else self.send_json({"error": "not found"}, 404)
        except Exception as e:  # noqa: BLE001
            return self.send_json({"error": str(e)}, 500)
        self.send_json({"error": "not found"}, 404)

    def stream(self, url):
        """Pipe an http:// radio stream through (browsers block http audio on an https page)."""
        sp = urllib.parse.urlsplit(url)
        if sp.scheme != "http" or not sp.hostname:
            return self.send_json({"error": "only http:// stream urls"}, 400)
        try:   # never let it reach this machine or the home network
            for info in socket.getaddrinfo(sp.hostname, sp.port or 80):
                ip = ipaddress.ip_address(info[4][0])
                if not ip.is_global:
                    return self.send_json({"error": "address not allowed"}, 403)
        except (OSError, ValueError):
            return self.send_json({"error": "cannot resolve host"}, 502)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (tools radio relay)", "Icy-MetaData": "0"})
        try:
            up = urllib.request.urlopen(req, timeout=15)
        except Exception as e:  # noqa: BLE001
            return self.send_json({"error": str(e)[:200]}, 502)
        with up:
            self.send_response(200)
            self.send_header("Content-Type", up.headers.get("Content-Type") or "audio/mpeg")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                while True:
                    chunk = up.read(16384)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, socket.timeout, OSError):
                pass   # the phone stopped listening or the station dropped
        return None

    def do_POST(self):
        u = urllib.parse.urlsplit(self.path)
        if u.path == "/api/audd":   # 网络电台「识别歌曲」：浏览器直连 AudD 被拦时，从家里转一手（原样转发 multipart）
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > 11 * 1024 * 1024:
                    return self.send_json({"status": "error", "error": {"error_message": "录音太大或为空"}}, 400)
                raw = self.rfile.read(n)
                req = urllib.request.Request("https://api.audd.io/", data=raw, method="POST",
                                             headers={"Content-Type": self.headers.get("Content-Type", ""), "User-Agent": "tools-home/1.0"})
                with urllib.request.urlopen(req, timeout=40) as r:
                    return self.send_json(json.loads(r.read().decode("utf-8", "replace")))
            except Exception as e:  # noqa: BLE001
                return self.send_json({"status": "error", "error": {"error_message": str(e)[:200]}}, 502)
        try:
            body = self.body_json()
            if u.path == "/api/kv":   # {key: {v: string|null, mt: ms}} — the newest write wins, per key
                res = {}
                os.makedirs(KV, exist_ok=True)
                with kv_lock:
                    for k, it in (body or {}).items():
                        if not KEY_OK.match(k) or not isinstance(it, dict):
                            continue
                        mt = int(it.get("mt") or 0)
                        p = kv_path(k)
                        try:
                            with open(p, encoding="utf-8") as f:
                                cur = json.load(f).get("mt", 0)
                        except (FileNotFoundError, ValueError):
                            cur = -1
                        if mt < cur:
                            res[k] = "older"
                            continue
                        tmp = p + ".tmp"
                        with open(tmp, "w", encoding="utf-8") as f:
                            json.dump({"v": it.get("v"), "mt": mt}, f, ensure_ascii=False)
                        os.replace(tmp, p)
                        res[k] = "ok"
                return self.send_json(res)
            if u.path == "/api/watchlist":   # add a ticker to the daily scan
                t = str((body or {}).get("t") or "").strip().upper().replace(".", "-")
                if not re.match(r"^\^?[A-Z][A-Z0-9]{0,5}(-[A-Z]{1,2})?$", t):
                    return self.send_json({"error": "bad ticker"}, 400)
                p = os.path.join(ROOT, "stocks", "watchlist.txt")
                try:
                    text = open(p, encoding="utf-8").read()
                except FileNotFoundError:
                    text = ""
                if t not in {ln.split("#")[0].strip().upper() for ln in text.splitlines()}:
                    with open(p, "a", encoding="utf-8") as f:
                        f.write(("" if not text or text.endswith("\n") else "\n") + t + "\n")
                return self.send_json({"ok": 1, "t": t})
            if u.path == "/api/issues":
                title = str((body or {}).get("title") or "").strip()
                if not title:
                    return self.send_json({"error": "title required"}, 400)
                i = localgh.create_issue(title, str(body.get("body") or ""), body.get("labels") or [])
                on_issue(i, "opened")
                return self.send_json(i, 201)
        except Exception as e:  # noqa: BLE001
            return self.send_json({"error": str(e)}, 500)
        self.send_json({"error": "not found"}, 404)

    def do_PATCH(self):
        u = urllib.parse.urlsplit(self.path)
        m = re.match(r"^/api/issues/(\d+)$", u.path)
        if not m:
            return self.send_json({"error": "not found"}, 404)
        try:
            body = self.body_json() or {}
            before = localgh.get_issue(m.group(1))
            if not before:
                return self.send_json({"error": "not found"}, 404)
            i = localgh.update_issue(m.group(1), title=body.get("title"), body=body.get("body"), state=body.get("state"))
            if body.get("state") == "closed" and before["state"] != "closed":
                on_issue(i, "closed")
            elif body.get("state") == "open" and before["state"] != "open":
                on_issue(i, "reopened")
            elif body.get("title") is not None or body.get("body") is not None:
                on_issue(i, "edited")
            return self.send_json(i)
        except Exception as e:  # noqa: BLE001
            return self.send_json({"error": str(e)}, 500)

    def do_DELETE(self):
        m = re.match(r"^/api/issues/(\d+)$", urllib.parse.urlsplit(self.path).path)
        if not m:
            return self.send_json({"error": "not found"}, 404)
        i = localgh.get_issue(m.group(1))
        ok = localgh.delete_issue(m.group(1))
        if ok and i and i["title"].startswith("监控"):
            on_issue(i, "closed")
        self.send_json({"ok": ok})


def main():
    os.makedirs(os.path.join(DATA, "logs"), exist_ok=True)
    os.makedirs(KV, exist_ok=True)
    host = os.environ.get("BIND", "127.0.0.1")
    srv = http.server.ThreadingHTTPServer((host, PORT), H)
    print("tools home server on http://%s:%d  (site: %s, data: %s)" % (host, PORT, ROOT, DATA), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
