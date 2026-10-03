#!/usr/bin/env python3
"""打折关注 (GitHub Actions, runs right after deals/build.py)

Every open issue titled「打折关注: …」opened by the repo owner is one watch:
    打折关注: 键盘
    打折关注: 机械键盘 ≤ 80        （单价不超过 $80）
    打折关注: airpods 低于 120
Words are matched like the page's 🔔 关注 tab: Chinese words are expanded with deals/terms.json
(键盘 → keyboard …), every word must match, price cap optional.
New matching deals are posted as a comment (GitHub notifies the phone/e-mail; on the home server
LocalGH pushes via ntfy). Items already reported for an issue are remembered in deals/data/watch_seen.json.
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
SEEN = os.path.join(DATA, "watch_seen.json")
PREFIX = "打折关注"
LOCAL = bool(os.environ.get("LOCAL_ISSUES"))
PAGE = (os.environ.get("PUBLIC_URL", "").rstrip("/") + "/deals.html") if LOCAL and os.environ.get("PUBLIC_URL") else "https://boliunew.github.io/tools/deals.html"


def load(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


TERMS = load(os.path.join(HERE, "terms.json"), {})
CAP = re.compile(r"(?:≤|<=|<|低于|以下|不超过|under|below|max|\$)\s*\$?\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:刀|美元|块|以下|以内)", re.I)


def parse(title):
    t = re.sub(r"^\s*%s\s*[:：]?\s*" % PREFIX, "", title or "").strip()
    cap = None
    m = CAP.search(t)
    if m:
        cap = float(m.group(1) or m.group(2))
        t = (t[:m.start()] + " " + t[m.end():]).strip()
        t = re.sub(r"(以下|以内|的)", " ", t).strip()
    words = [w for w in re.split(r"[\s,，、/]+", t.lower()) if w]
    return words, cap


def word_re(opt):
    opt = opt.lower()
    if re.search(r"[一-鿿]", opt):
        return re.compile(re.escape(opt))
    return re.compile(r"\b" + r"\s+".join(re.escape(p) for p in opt.split()) + r"(?:s|es)?\b")


def matcher(words):
    groups = [[word_re(o) for o in [w] + TERMS.get(w, [])] for w in words]
    return lambda text: all(any(r.search(text) for r in g) for g in groups)


def each_price(x):
    m = re.match(r"^(\d+)/", x.get("pt") or "")
    p = x.get("p")
    return None if p is None else (p / int(m.group(1)) if m else p)


def items():
    meta, fly = load(os.path.join(DATA, "meta.json"), {}), load(os.path.join(DATA, "flyers.json"), {"flyers": {}})
    stores = meta.get("stores") or {}
    out = []
    for f in (fly.get("flyers") or {}).values():
        if f.get("up"):
            continue   # next week's ad — reported once it starts
        for it in f.get("items", []):
            x = dict(it, s=f["s"], to=f.get("to"))
            out.append(x)
    out += meta.get("online") or []
    for x in out:
        st = stores.get(x.get("s"), {})
        x["_store"] = st.get("name") or x.get("s")
        x["_q"] = " ".join(str(x.get(k) or "") for k in ("n", "b", "zh", "stz")).lower()
        x["_e"] = each_price(x)
        if not x.get("u"):
            q = st.get("q")
            x["u"] = q.replace("{q}", urllib.request.quote(x.get("n", ""))) if q else ""
    return out


class GH:
    def __init__(self):
        self.token = os.environ.get("GITHUB_TOKEN", "")
        self.repo = os.environ.get("GITHUB_REPOSITORY", "boliunew/tools")
        self.owner = os.environ.get("OWNER") or self.repo.split("/")[0]

    def req(self, method, path, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        h = {"Authorization": "Bearer " + self.token, "Accept": "application/vnd.github+json", "User-Agent": "boliunew-tools-deals"}
        if data:
            h["Content-Type"] = "application/json"
        rq = urllib.request.Request("https://api.github.com/repos/%s%s" % (self.repo, path), data=data, method=method, headers=h)
        with urllib.request.urlopen(rq, timeout=30) as r:
            txt = r.read().decode("utf-8")
            return json.loads(txt) if txt else None

    def open_issues(self):
        out, page = [], 1
        while page < 10:
            batch = self.req("GET", "/issues?state=open&per_page=100&page=%d" % page) or []
            out += [i for i in batch if "pull_request" not in i]
            if len(batch) < 100:
                break
            page += 1
        return out

    def comment(self, n, body):
        self.req("POST", "/issues/%s/comments" % n, {"body": body})


def line(x):
    price = x.get("pt") or ("$%s" % x["p"] if x.get("p") is not None else "见详情")
    was = " ~~$%s~~" % x["was"] if x.get("was") and x.get("p") is not None and x["was"] > x["p"] else ""
    off = " **-%d%%**" % x["off"] if x.get("off") and x["off"] >= 5 else ""
    to = "，到 %s" % x["to"][5:].replace("-", "/") if x.get("to") else ""
    name = x.get("n", "")[:90]
    link = "[%s](%s)" % (name, x["u"]) if x.get("u") else name
    return "- **%s**%s%s · %s · %s%s" % (price, was, off, x["_store"], link, to)


def main():
    if LOCAL:
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "selfhost"))
        from localgh import LocalGH
        gh = LocalGH()
    else:
        gh = GH()
    if not gh.token:
        print("no token; skip")
        return 0
    try:
        issues = [i for i in gh.open_issues() if (i.get("title") or "").strip().startswith(PREFIX) and (i.get("user") or {}).get("login") in (gh.owner, None)]
    except urllib.error.HTTPError as e:
        print("issues failed:", e)
        return 0
    if not issues:
        print("no watches")
        return 0
    seen = load(SEEN, {})
    pool = items()
    for iss in issues:
        n = str(iss["number"])
        words, cap = parse(iss["title"])
        if not words:
            continue
        ok = matcher(words)
        hits = [x for x in pool if ok(x["_q"]) and (cap is None or (x["_e"] is not None and x["_e"] <= cap))]
        first = n not in seen
        old = set(seen.get(n, []))
        new = [x for x in hits if x.get("id") not in old]
        seen[n] = sorted(set(x.get("id") for x in hits) | old)[-2000:]
        if not new:
            continue
        new.sort(key=lambda x: (x["_e"] if x["_e"] is not None else 1e9))
        what = " ".join(words) + (" ≤ $%g" % cap if cap is not None else "")
        head = ("🔔 已开始关注「%s」。现在就有 %d 件特价：" if first else "🔔「%s」有 %d 件新特价：") % (what, len(new))
        body = head + "\n\n" + "\n".join(line(x) for x in new[:15])
        if len(new) > 15:
            body += "\n\n……还有 %d 件，在页面的 🔔 关注 里看全部。" % (len(new) - 15)
        body += "\n\n[打开打折雷达](%s) · 不想再收到就关掉这个 issue。" % PAGE
        try:
            gh.comment(n, body)
            print("issue #%s: %d new" % (n, len(new)))
        except Exception as e:  # noqa: BLE001
            print("comment failed:", e)
    open_ids = set(str(i["number"]) for i in issues)
    seen = {k: v for k, v in seen.items() if k in open_ids}
    with open(SEEN, "w", encoding="utf-8") as f:
        json.dump(seen, f, separators=(",", ":"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
