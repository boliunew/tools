#!/usr/bin/env python3
"""
股价提醒 (GitHub Actions) — every open issue titled「股价提醒…」opened by the repo owner is one alert.

  check : runs right after the daily scan. Compares the newest close in stocks/data/snap.json with
          every alert and comments on the issue when one fires; GitHub pushes that comment to the
          phone app / e-mail. What was already sent lives in stocks/data/alerts.json (the page reads it too).
  ack   : runs when an alert issue is opened / edited / reopened. Replies once with how far the price
          is from the alert, and adds tickers the scan doesn't cover to stocks/watchlist.txt.

Conditions — the title is enough (「股价提醒: VOO 跌到 650」); the issue form fills the same fields:
  跌到 P / 涨到 P     close ≤ P / close ≥ P              re-arms after moving 3% back
  回撤 X              ≥ X% below the 52-week high          re-arms 3 points shallower
  RSI X               RSI(14) ≤ X                          re-arms at X + 10
  200日线             close crosses the 200-day average (either way), every time
  单日涨跌 X           |daily move| ≥ X%, every time
  信号                any of the pool's buy signals (stocks only)
Standard library only, so the ack job needs no installs.

Env: GITHUB_TOKEN, GITHUB_REPOSITORY, OWNER, ISSUE_NUMBER (ack)
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, "data", "snap.json")
LATEST = os.path.join(HERE, "data", "latest.json")
STATE = os.path.join(HERE, "data", "alerts.json")
WATCHLIST = os.path.join(HERE, "watchlist.txt")
LOCAL = bool(os.environ.get("LOCAL_ISSUES"))          # running on the home server (selfhost/), not GitHub
PAGE = (os.environ.get("PUBLIC_URL", "").rstrip("/") + "/stocks.html") if LOCAL and os.environ.get("PUBLIC_URL") else "https://boliunew.github.io/tools/stocks.html"
PUSH_TXT = "手机上的 ntfy 会推送" if LOCAL else "GitHub App 会推送到手机，也会发邮件"
CLOSE_TXT = "在「通知中心」关掉它" if LOCAL else "关闭这个 issue"
PREFIX = "股价提醒"
SIGNAMES = {"squeeze": "挤压突破", "pit": "回踩金坑", "momentum": "强势新高", "rsi2": "RSI2 超跌反弹", "blood": "血筹码"}
LEVEL = ("below", "above", "dd", "rsi")          # fire once, re-arm after the condition clears by a margin
DEFAULT = {"dd": 10.0, "rsi": 30.0, "move": 3.0}
KINDS = [  # checked in this order — "跌破200日线" must be the 200-day kind, not "跌到"
    ("ma200", r"200\s*[日天]?\s*(?:均线|线)|(?:S?MA)\s*200"),
    ("sig", r"信号|买点|signal"),
    ("rsi", r"RSI"),
    ("dd", r"回撤|回调|drawdown|距.{0,4}高点"),
    ("move", r"单日|大涨大跌|涨跌幅|涨跌|异动|move"),
    ("above", r"涨到|涨破|涨过|高于|突破|above|>=?|≥"),
    ("below", r"跌到|跌破|跌至|低于|below|<=?|≤"),
]
TICKER = re.compile(r"\^?[A-Za-z][A-Za-z0-9]{0,5}(?:[.\-][A-Za-z]{1,2})?")


def fmt(v):
    return ("%.2f" % v).rstrip("0").rstrip(".")


def pct(x, d=1):
    return ("%+." + str(d) + "f%%") % (x * 100)


# ----------------------------------------------------------------------------- parsing
def form_fields(body):
    f, cur = {}, None
    for line in (body or "").splitlines():
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m:
            cur = m.group(1)
            f[cur] = []
        elif cur is not None:
            f[cur].append(line)
    out = {}
    for k, v in f.items():
        v = "\n".join(v).strip()
        out[k] = "" if v in ("_No response_", "None") else v
    return out


def pick(f, prefix):
    for k, v in f.items():
        if k.startswith(prefix):
            return v
    return ""


def parse(title, body=""):
    """→ {'t','kind','v','spec'} or None"""
    f = form_fields(body)
    t_txt, c_txt, v_txt = pick(f, "股票代码"), pick(f, "提醒条件"), pick(f, "数值")
    rest = re.sub(r"^\s*" + PREFIX + r"\s*[:：]?\s*", "", title or "")
    if not t_txt:  # everything from the title: 「股价提醒: VOO 跌到 650」
        m = TICKER.search(rest)
        if not m:
            return None
        t_txt, c_txt, v_txt = m.group(0), rest[m.end():], ""
    m = TICKER.search(t_txt)
    if not m:
        return None
    t = m.group(0).upper().replace(".", "-")
    kind = None
    for k, rx in KINDS:
        if re.search(rx, c_txt, re.I):
            kind = k
            break
    if kind is None:
        return None
    num_src = v_txt or re.sub(r"RSI\s*\(?\s*14\s*\)?|200\s*[日天]?\s*(?:均线|线)|S?MA\s*200", " ", c_txt, flags=re.I)
    n = re.search(r"\d+(?:\.\d+)?", num_src.replace(",", ""))
    v = float(n.group(0)) if n else DEFAULT.get(kind)
    if kind in ("below", "above") and not v:
        return None
    if kind in ("ma200", "sig"):
        v = None
    return {"t": t, "kind": kind, "v": v, "spec": "%s|%s|%s" % (t, kind, "" if v is None else fmt(v))}


def describe(a):
    v = a["v"]
    return {"below": "收盘跌到 %s 以下" % fmt(v or 0), "above": "收盘涨到 %s 以上" % fmt(v or 0),
            "dd": "距一年高点回撤 ≥ %s%%" % fmt(v or 0), "rsi": "RSI(14) ≤ %s" % fmt(v or 0),
            "ma200": "穿越 200 日线（跌破或站回）", "move": "单日涨跌 ≥ %s%%" % fmt(v or 0), "sig": "出现买点信号"}[a["kind"]]


def evaluate(a, r):
    """→ (condition met now, condition cleared enough to re-arm)"""
    k, v = a["kind"], a["v"]
    if k == "below":
        return r["c"] <= v, r["c"] >= v * 1.03
    if k == "above":
        return r["c"] >= v, r["c"] <= v * 0.97
    if k == "dd":
        dd = -(r.get("h") or 0) * 100
        return dd >= v, dd <= v - 3
    if k == "rsi":
        return r["rsi"] <= v, r["rsi"] >= v + 10
    if k == "move":
        return abs(r["d"]) * 100 >= v, True
    if k == "ma200":
        return bool(r.get("x2")), True
    return bool(r.get("sig")), True


def status_line(r, date):
    bits = ["今日 " + pct(r["d"], 2)]
    if r.get("h") is not None:
        bits.append("距一年高点 " + pct(r["h"]))
    bits.append("RSI %s" % r["rsi"])
    m2 = r.get("m2")
    bits.append("200 日线%s方%s" % ("上" if r.get("a200") else "下", "（%s）" % pct(m2) if m2 is not None else ""))
    return " · ".join(bits)


def mmdd(date):
    try:
        d = dt.date.fromisoformat(date)
    except (TypeError, ValueError):
        return date or ""
    return "%d/%d 周%s" % (d.month, d.day, "一二三四五六日"[d.weekday()])


# ----------------------------------------------------------------------------- GitHub
class GH:
    def __init__(self):
        self.token = os.environ.get("GITHUB_TOKEN", "")
        self.repo = os.environ.get("GITHUB_REPOSITORY", "boliunew/tools")
        self.owner = os.environ.get("OWNER") or self.repo.split("/")[0]

    def req(self, method, path, body=None):
        url = "https://api.github.com/repos/%s%s" % (self.repo, path)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        h = {"Authorization": "Bearer " + self.token, "Accept": "application/vnd.github+json",
             "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "boliunew-tools-alerts"}
        if data:
            h["Content-Type"] = "application/json"
        rq = urllib.request.Request(url, data=data, method=method, headers=h)
        with urllib.request.urlopen(rq, timeout=30) as r:
            txt = r.read().decode("utf-8")
            return json.loads(txt) if txt else None

    def alert_issues(self):
        out, page = [], 1
        while page < 10:
            batch = self.req("GET", "/issues?state=open&per_page=100&page=%d" % page) or []
            out += [i for i in batch if "pull_request" not in i and is_alert(i, self.owner)]
            if len(batch) < 100:
                break
            page += 1
        return out

    def issue(self, n):
        return self.req("GET", "/issues/%s" % n)

    def comments(self, n):
        return self.req("GET", "/issues/%s/comments?per_page=100" % n) or []

    def comment(self, n, body):
        self.req("POST", "/issues/%s/comments" % n, {"body": body})

    def label(self, n):
        try:
            self.req("POST", "/labels", {"name": "stock-alert", "color": "d23f31", "description": "股价提醒"})
        except urllib.error.HTTPError:
            pass  # already exists
        try:
            self.req("POST", "/issues/%s/labels" % n, {"labels": ["stock-alert"]})
        except urllib.error.HTTPError:
            pass


def is_alert(issue, owner):
    return (issue.get("title") or "").strip().startswith(PREFIX) and (issue.get("user") or {}).get("login") == owner


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return default


# ----------------------------------------------------------------------------- check (after the scan)
def fire_text(a, r, date, plan):
    k, v, t = a["kind"], a["v"], a["t"]
    head = "🔔 **%s** 收盘 %s（%s）" % (t, fmt(r["c"]), mmdd(date))
    if k == "below":
        why, after = "，已跌到你设的 %s。" % fmt(v), "价格回到 %s 以上后，这个提醒会自动重新开启。" % fmt(v * 1.03)
    elif k == "above":
        why, after = "，已涨到你设的 %s。" % fmt(v), "价格回落到 %s 以下后，这个提醒会自动重新开启。" % fmt(v * 0.97)
    elif k == "dd":
        why, after = "，距一年高点已回撤 %.1f%%（你设的是 %s%%）。" % (-r["h"] * 100, fmt(v)), "回撤收窄到 %s%% 以内后，这个提醒会自动重新开启。" % fmt(v - 3)
    elif k == "rsi":
        why, after = "，RSI(14) 降到 %s，低于你设的 %s（超卖区）。" % (r["rsi"], fmt(v)), "RSI 回到 %s 以上后，这个提醒会自动重新开启。" % fmt(v + 10)
    elif k == "ma200":
        why, after = ("，今天**站回** 200 日线。" if r.get("x2", 0) > 0 else "，今天**跌破** 200 日线。"), "每次穿越 200 日线都会提醒。"
    elif k == "move":
        why, after = "，今天%s %s。" % ("大涨" if r["d"] > 0 else "大跌", pct(r["d"], 2)), "每次单日涨跌超过 %s%% 都会提醒。" % fmt(v)
    else:
        why = "，今天出现买点信号：**%s**。" % "、".join(SIGNAMES.get(s, s) for s in r.get("sig", []))
        after = "出现新信号时会再提醒。"
        if plan:
            why += "\n\n股票池的参考计划：入场 %s · 止损 %s · 目标 %s · 盈亏比 %.1fR" % (fmt(plan["close"]), fmt(plan["stop"]), fmt(plan["target"]), plan["r"])
    return "%s%s\n\n%s\n\n%s不需要了就%s。 · [打开今日股票池](%s)" % (head, why, status_line(r, date), after, CLOSE_TXT, PAGE)


def age_hours(iso):
    try:
        t = dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except (TypeError, ValueError):
        return 999
    return (dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 3600


def recent(d0, d1, days):
    try:
        return (dt.date.fromisoformat(d1) - dt.date.fromisoformat(d0)).days <= days
    except (TypeError, ValueError):
        return False


def check(gh):
    snap = load(SNAP, None)
    if not snap or not snap.get("rows"):
        print("no snapshot; nothing to check")
        return
    date, rows = snap["date"], snap["rows"]
    plans = {c["t"]: c for c in (load(LATEST, {}) or {}).get("candidates", [])}
    old = load(STATE, {}).get("items", {})
    items, fired = {}, 0
    for iss in gh.alert_issues():
        key = str(iss["number"])
        a = parse(iss.get("title"), iss.get("body"))
        if not a:
            continue
        st = dict(old.get(key) or {})
        if st.get("spec") != a["spec"]:
            st = {"spec": a["spec"], "armed": True}
        st.update({"t": a["t"], "kind": a["kind"], "v": a["v"], "desc": describe(a), "url": iss.get("html_url")})
        r = rows.get(a["t"])
        if r is None:
            # a ticker the ack just added to watchlist.txt only shows up after the next full scan
            if not st.get("missing") and age_hours(iss.get("created_at")) > 30:
                try:
                    gh.comment(key, "⚠️ 今天（%s）的扫描里没有 **%s** 的数据：代码可能写错了，或者上市不到一年（扫描需要一年以上的日线）。改一下标题里的代码就行。" % (mmdd(date), a["t"]))
                    st["missing"] = date
                except Exception as e:  # noqa: BLE001
                    print("comment failed", key, e)
            items[key] = st
            continue
        st.pop("missing", None)
        met, rearm = evaluate(a, r)
        fire = False
        if a["kind"] in LEVEL:
            if st.get("armed", True) and met:
                fire = True
            elif not st.get("armed", True) and rearm:
                st["armed"] = True
        elif met and st.get("last") != date:
            sigs = sorted(r.get("sig") or [])
            fire = not (a["kind"] == "sig" and st.get("sigs") == sigs and recent(st.get("last"), date, 7))
        if fire:
            try:
                gh.comment(key, fire_text(a, r, date, plans.get(a["t"])))
                fired += 1
                st["last"] = date
                if a["kind"] in LEVEL:
                    st["armed"] = False
                if a["kind"] == "sig":
                    st["sigs"] = sorted(r.get("sig") or [])
            except Exception as e:  # noqa: BLE001
                print("comment failed", key, e)
        st["c"], st["met"] = r["c"], bool(met)
        items[key] = st
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump({"date": date, "items": items}, f, ensure_ascii=False, separators=(",", ":"))
    print("alerts: %d open, %d fired (data %s)" % (len(items), fired, date))


# ----------------------------------------------------------------------------- ack (issue opened / edited)
EXAMPLES = ("- 股价提醒: VOO 跌到 650\n- 股价提醒: VOO 回撤 10　（距一年高点跌 10%）\n- 股价提醒: QQQ RSI 30\n"
            "- 股价提醒: SPY 200日线　（跌破或站回都提醒）\n- 股价提醒: NVDA 单日涨跌 5\n- 股价提醒: AAPL 信号　（出现股票池买点）")


def add_to_watchlist(t):
    try:
        with open(WATCHLIST, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        text = ""
    have = {ln.split("#")[0].strip().upper() for ln in text.splitlines()}
    if t in have:
        return False
    with open(WATCHLIST, "a", encoding="utf-8") as f:
        f.write(("" if text.endswith("\n") or not text else "\n") + t + "\n")
    return True


def distance(a, r):
    k, v, c = a["kind"], a["v"], r["c"]
    met, _ = evaluate(a, r)
    if k in ("below", "above"):
        if met:
            return "现在已经满足，今天收盘后的检查会正式提醒一次。"
        return "还要%s %.1f%%。" % ("跌" if k == "below" else "涨", abs(v / c - 1) * 100)
    if k == "dd":
        dd = -(r.get("h") or 0) * 100
        return "现在距一年高点 −%.1f%%，%s" % (dd, "已经满足，今天收盘后的检查会正式提醒一次。" if met else "还差 %.1f 个百分点。" % (v - dd))
    if k == "rsi":
        return "现在 RSI(14) 是 %s%s" % (r["rsi"], "，已经满足，今天收盘后的检查会正式提醒一次。" if met else "。")
    if k == "ma200":
        m2 = r.get("m2")
        return "现在在 200 日线%s方%s。" % ("上" if r.get("a200") else "下", "（%s）" % pct(m2) if m2 is not None else "")
    if k == "move":
        return "最近一个交易日 %s。" % pct(r["d"], 2)
    if r.get("s") == "ETF":
        return "⚠️ ETF 不在买点信号的扫描范围里，这个条件不会触发。可以改成 回撤 / RSI / 200日线。"
    sig = r.get("sig") or []
    return ("最近一个交易日有信号：%s。" % "、".join(SIGNAMES.get(s, s) for s in sig)) if sig else "最近一个交易日没有信号。"


def ack(gh, number):
    iss = gh.issue(number)
    if not iss or not is_alert(iss, gh.owner) or iss.get("state") != "open":
        print("not an open alert issue")
        return
    a = parse(iss.get("title"), iss.get("body"))
    marker = "<!-- ack:%s -->" % (a["spec"] if a else "bad:" + (iss.get("title") or ""))
    if any(marker in (c.get("body") or "") for c in gh.comments(number)[-5:]):
        print("already acknowledged:", marker)
        return
    gh.label(number)
    if not a:
        gh.comment(number, "❓ 没看懂这个提醒。标题这样写就行（代码 + 条件 + 数值）：\n\n%s\n\n改好标题后会自动重新检查。%s" % (EXAMPLES, marker))
        return
    snap = load(SNAP, {}) or {}
    r = (snap.get("rows") or {}).get(a["t"])
    head = "✅ 提醒已登记：**%s** %s\n\n" % (a["t"], describe(a))
    tail = ("\n\n每个交易日收盘后检查一次（太平洋时间下午 3 点左右），触发时会在这里留言——%s。"
            "不需要了就%s；想改条件，直接改标题。\n%s" % (PUSH_TXT, CLOSE_TXT, marker))
    if r is None:
        added = add_to_watchlist(a["t"])
        mid = ("**%s** 还不在每日扫描范围，%s下一次收盘扫描后开始检查。如果代码写错了，到时会在这里告诉你。"
               % (a["t"], "已经把它加进扫描清单（stocks/watchlist.txt），" if added else "扫描清单里已经有它，"))
        gh.comment(number, head + mid + tail)
        return
    gh.comment(number, head + "最新收盘 %s（%s）· %s%s" % (fmt(r["c"]), mmdd(snap.get("date", "")), distance(a, r), tail))


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    if LOCAL:
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "selfhost"))
        from localgh import LocalGH
        gh = LocalGH()
    else:
        gh = GH()
    if not gh.token:
        print("GITHUB_TOKEN missing; skipping alerts")
        return 0
    if mode == "ack":
        ack(gh, os.environ.get("ISSUE_NUMBER"))
    else:
        check(gh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
