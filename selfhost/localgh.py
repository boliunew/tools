"""A tiny local stand-in for the GitHub issues the tools used for 股价提醒 and 网页监控.

On GitHub the alerts and page watches are issues and a bot comment is the phone notification.
At home the same scripts (stocks/alerts.py, monitor/check.py) talk to this store instead when
LOCAL_ISSUES=1, and every "comment" is pushed to the phone through ntfy.

Store: <data dir>/issues.json   {"next": n, "issues": {"7": {number, title, body, state, labels, comments, ...}}}
Env:   TOOLS_DATA (data dir), OWNER, NTFY_URL (e.g. http://127.0.0.1:8090/tools-xxxx), PUBLIC_URL (for click-through)
"""
import datetime as dt
import fcntl
import json
import os
import re
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get("TOOLS_DATA") or os.path.join(ROOT, ".local-data")
STORE = os.path.join(DATA, "issues.json")
LOCK = os.path.join(DATA, "issues.lock")
OWNER = os.environ.get("OWNER", "boliunew")


def now_iso():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class _Locked:
    """read-modify-write the store under an exclusive file lock (server and jobs share it)"""
    def __enter__(self):
        os.makedirs(DATA, exist_ok=True)
        self.f = open(LOCK, "a+")
        fcntl.flock(self.f, fcntl.LOCK_EX)
        try:
            with open(STORE, encoding="utf-8") as f:
                self.db = json.load(f)
        except (FileNotFoundError, ValueError):
            self.db = {"next": 1, "issues": {}}
        self.dirty = False
        return self

    def save(self):
        self.dirty = True

    def __exit__(self, *a):
        if self.dirty:
            tmp = STORE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.db, f, ensure_ascii=False, indent=1)
            os.replace(tmp, STORE)
        fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()


def _public(i):
    """the GitHub-API-shaped view the scripts and pages expect"""
    out = {k: v for k, v in i.items() if k != "comments"}
    out["user"] = {"login": OWNER}
    out["html_url"] = "issues.html#%d" % i["number"]
    out["comments"] = len(i.get("comments", []))
    return out


def list_issues(state="open"):
    with _Locked() as L:
        items = [i for i in L.db["issues"].values() if state == "all" or i.get("state") == state]
    items.sort(key=lambda i: -i["number"])
    return [_public(i) for i in items]


def get_issue(n, with_comments=False):
    with _Locked() as L:
        i = L.db["issues"].get(str(n))
    if not i:
        return None
    out = _public(i)
    if with_comments:
        out["comment_list"] = i.get("comments", [])
    return out


def create_issue(title, body="", labels=None):
    with _Locked() as L:
        n = L.db["next"]
        L.db["next"] = n + 1
        t = now_iso()
        L.db["issues"][str(n)] = {"number": n, "title": title.strip(), "body": body or "", "state": "open",
                                  "labels": [{"name": x} for x in (labels or [])], "created_at": t, "updated_at": t, "comments": []}
        L.save()
    return get_issue(n)


def update_issue(n, **fields):
    with _Locked() as L:
        i = L.db["issues"].get(str(n))
        if not i:
            return None
        for k in ("title", "body", "state"):
            if k in fields and fields[k] is not None:
                i[k] = fields[k]
        i["updated_at"] = now_iso()
        L.save()
    return get_issue(n)


def delete_issue(n):
    with _Locked() as L:
        if L.db["issues"].pop(str(n), None) is not None:
            L.save()
            return True
    return False


def add_comment(n, body):
    with _Locked() as L:
        i = L.db["issues"].get(str(n))
        if not i:
            raise KeyError(n)
        i.setdefault("comments", []).append({"body": body, "created_at": now_iso()})
        i["comments"] = i["comments"][-60:]
        i["updated_at"] = now_iso()
        L.save()
        title = i["title"]
    push(title, body, n)


def push(title, body, n=None):
    """send a notification to the phone through ntfy (silently skipped when not configured)"""
    url = os.environ.get("NTFY_URL", "").strip()
    if not url:
        return
    text = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)          # [label](link) → label
    text = text.replace("**", "").strip()
    headers = {"Title": _hdr(title), "Tags": "bell", "Markdown": "no"}
    base = os.environ.get("PUBLIC_URL", "").rstrip("/")
    if base:
        headers["Click"] = base + "/" + ("issues.html#%s" % n if n else "")
    try:
        req = urllib.request.Request(url, data=text.encode("utf-8"), method="POST", headers=headers)
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:  # noqa: BLE001
        print("ntfy push failed:", e)


def _hdr(s):
    # HTTP headers must be latin-1; ntfy accepts RFC 2047 encoded words for UTF-8 titles
    try:
        s.encode("latin-1")
        return s
    except UnicodeEncodeError:
        import base64
        return "=?UTF-8?B?" + base64.b64encode(s.encode("utf-8")).decode() + "?="


class LocalGH:
    """drop-in for the GH helper classes in stocks/alerts.py and monitor/check.py"""
    token = "local"
    repo = "local"
    owner = OWNER

    def alert_issues(self):
        return [i for i in list_issues("open") if (i.get("title") or "").strip().startswith("股价提醒")]

    def open_issues(self):
        return list_issues("open")

    def issue(self, n):
        return get_issue(n)

    def comments(self, n):
        i = get_issue(n, with_comments=True)
        return i["comment_list"] if i else []

    def comment(self, n, body):
        add_comment(n, body)

    def label(self, n):
        pass

    def ensure_label(self, n):
        pass
