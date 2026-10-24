#!/usr/bin/env python3
"""☀️ 每日简报：每天早上用网站已有的数据自动拼出一期简报，写进 brief/data/（brief.html 读）。

不需要 AI，也不需要任何授权：
  🤖 AI 与科技   ← news/data/latest.json 里 BBC / NPR / 卫报的科技新闻（机翻成中文）
  📈 美股市场   ← stocks/data/latest.json（大盘状态）+ stocks/data/snap.json（涨跌最大的个股）+ 财报日历
  🏦 宏观经济   ← earnings/data/latest.json 的经济数据日历（最近公布的结果 + 接下来几天）
  🌍 世界大事   ← news/data/today.json「今日大事」（多家媒体同时报道的排前面）
  📌 今日一件事 ← 近 3 天有「高」重要性的经济数据就选它，否则选报道媒体最多的那条新闻
  🗓️ 本周关注   ← 只在周一：本周的重要经济数据 + 市值最大的财报

  python brief/build.py          正常运行
  python brief/build.py --dry    只打印，不写文件
只用标准库。"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "data")
SITE = (os.environ.get("PUBLIC_URL", "").rstrip("/") or "https://boliunew.github.io/tools")
UA = "Mozilla/5.0 (boliunew-tools brief)"
WK = "一二三四五六日"
KEEP_DAYS = 30

AI_WORDS = re.compile(r"\b(AI|A\.I\.|artificial intelligence|OpenAI|ChatGPT|Anthropic|Claude|Gemini|DeepMind|Nvidia|chip|chips|semiconductor|"
                      r"robot|robotics|model|LLM|data cent(?:er|re)s?|Microsoft|Google|Apple|Meta|Amazon|Tesla|xAI|Grok|quantum|cyber|hack)", re.I)
SKIP_TECH = re.compile(r"\b(podcast|quiz|newsletter|live:|in pictures|review:|the week in)\b", re.I)


def la_now():
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("America/Los_Angeles"))
    except Exception:
        return dt.datetime.utcnow() - dt.timedelta(hours=7)


def load(rel):
    try:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("⚠️ 读不到 %s：%s" % (rel, e))
        return {}


def parse_t(s):
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def pct(x, digits=2):
    return ("%+." + str(digits) + "f%%") % (x * 100)


def md(d):
    """'2026-10-27' → '10/27 周二'"""
    t = dt.date.fromisoformat(d)
    return "%d/%d 周%s" % (t.month, t.day, WK[t.weekday()])


def clip(s, n):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[:n - 1].rstrip("，,。. ") + "…"


# ----------------------------------------------------------------------------- 机翻（谷歌免费接口 → MyMemory），带缓存
TCACHE_PATH = os.path.join(OUT, "tcache.json")


def http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def translate(text, cache):
    text = (text or "").strip()
    if not text:
        return ""
    if text in cache:
        return cache[text]
    try:
        q = urllib.parse.urlencode({"client": "gtx", "sl": "en", "tl": "zh-CN", "dt": "t", "q": text[:1800]})
        d = json.loads(http_get("https://translate.googleapis.com/translate_a/single?" + q))
        zh = "".join(seg[0] for seg in (d[0] or []) if seg and seg[0]).strip()
        if zh and zh != text:
            cache[text] = zh
            return zh
    except Exception:
        pass
    try:
        q = urllib.parse.urlencode({"q": text[:450], "langpair": "en|zh-CN"})
        d = json.loads(http_get("https://api.mymemory.translated.net/get?" + q))
        zh = (d.get("responseData") or {}).get("translatedText") or ""
        if d.get("responseStatus") in (200, "200") and zh and not re.search(r"MYMEMORY WARNING|QUOTA", zh, re.I):
            cache[text] = html.unescape(zh)
            return cache[text]
    except Exception:
        pass
    return ""


# ----------------------------------------------------------------------------- 各板块
def sec_ai(now_utc, cache):
    L = load("news/data/latest.json")
    arts = [a for a in L.get("articles", []) if a.get("topic") == "科技" and not SKIP_TECH.search(a.get("title", ""))]
    fresh = []
    for a in arts:
        t = parse_t(a.get("time"))
        age = (now_utc - t).total_seconds() / 3600 if t else 99
        if age > 48:
            continue
        score = (3 if AI_WORDS.search(a.get("title", "") + " " + a.get("summary", "")) else 0) - age / 12
        fresh.append((score, a))
    fresh.sort(key=lambda x: -x[0])
    items, seen = [], set()
    for _, a in fresh:
        key = re.sub(r"\W+", "", a["title"].lower())[:40]
        if key in seen:
            continue
        seen.add(key)
        zt = translate(a["title"], cache) or a["title"]
        zs = translate(a.get("summary", ""), cache) or a.get("summary", "")
        items.append({"t": clip(zt, 60), "d": clip(zs, 140), "src": [{"n": a.get("source", "来源"), "u": a.get("link", "")}]})
        if len(items) >= 3:
            break
    return items


def sec_market(today):
    S = load("stocks/data/latest.json")
    snap = load("stocks/data/snap.json")
    E = load("earnings/data/latest.json")
    items = []
    rg = S.get("regime") or {}
    spy, qqq = rg.get("spy") or {}, rg.get("qqq") or {}
    day = S.get("date") or snap.get("date")
    if spy.get("close"):
        t = "%s 收盘：标普500 ETF（SPY）%s，纳指100 ETF（QQQ）%s" % (md(day) if day else "上个交易日", pct(spy.get("chg", 0)), pct(qqq.get("chg", 0)))
        bits = []
        if rg.get("label"):
            bits.append("大盘状态「%s」：%s" % (rg["label"], rg.get("desc", "").rstrip("。")))
        if rg.get("vix") is not None:
            bits.append("VIX 恐慌指数 %.1f" % rg["vix"])
        if rg.get("breadth50") is not None:
            bits.append("%d%% 的股票站在 50 日均线上方" % round(rg["breadth50"] * 100))
        items.append({"t": t, "d": "；".join(bits) + "。", "src": [{"n": "今日股票池", "u": SITE + "/stocks.html"}]})
    rows = [(k, v) for k, v in (snap.get("rows") or {}).items() if isinstance(v.get("d"), (int, float))]
    if rows:
        rows.sort(key=lambda kv: kv[1]["d"])
        up = rows[::-1][:3]
        dn = rows[:3]

        def fmt(kv):
            return "%s %s" % (kv[0], pct(kv[1]["d"], 1))
        why = []
        secs = {}
        for k, v in up + dn:
            secs.setdefault(v.get("s", ""), []).append(k)
        crowd = [s for s, ks in secs.items() if s and len(ks) >= 2]
        if crowd:
            why.append("%s板块集中出现在榜上" % "、".join(crowd))
        items.append({"t": "涨幅最大：%s；跌幅最大：%s" % ("、".join(fmt(x) for x in up), "、".join(fmt(x) for x in dn)),
                      "d": ("扫描范围约 %d 只股票（标普 500 为主）。" % len(rows)) + ("".join(w + "。" for w in why)),
                      "src": [{"n": "今日股票池", "u": SITE + "/stocks.html"}]})
    nxt = next((d for d in E.get("days", []) if d.get("date", "") >= today and d.get("earnings")), None)
    if nxt:
        er = sorted(nxt["earnings"], key=lambda e: -(e.get("cap") or 0))[:5]
        when = {"pre": "盘前", "post": "盘后"}
        names = "、".join("%s（%s）" % (e["t"], when.get(e.get("when"), "时间未定")) for e in er)
        label = "今天" if nxt["date"] == today else md(nxt["date"])
        items.append({"t": "%s的重要财报：%s" % (label, names),
                      "d": "按市值挑出最大的几家，共 %d 家公司发布财报。财报日个股波动通常比平时大得多。" % len(nxt["earnings"]),
                      "src": [{"n": "财报与经济日历", "u": SITE + "/earnings.html"}]})
    return items


def macro_events(E):
    out = []
    for d in E.get("past", []) + E.get("days", []):
        for m in d.get("macro", []):
            out.append(dict(m, date=m.get("date") or d.get("date")))
    seen, uniq = set(), []
    for m in out:
        k = (m["date"], m.get("key"), m.get("title"))
        if k not in seen:
            seen.add(k)
            uniq.append(m)
    return uniq


def sec_macro(today):
    E = load("earnings/data/latest.json")
    ev = macro_events(E)
    items = []
    done = [m for m in ev if m["date"] <= today and any(l.get("actual") for l in m.get("lines", []))]
    if done:
        m = max(done, key=lambda m: (m["date"], m.get("time") or ""))
        ln = [l for l in m.get("lines", []) if l.get("actual")][:2]
        res = "；".join("%s 实际 %s（预期 %s，前值 %s）" % (l.get("name", ""), l.get("actual"), l.get("consensus") or "—", l.get("previous") or "—") for l in ln)
        items.append({"t": "最近公布：%s（%s）" % (m.get("title", ""), md(m["date"])), "d": clip(res + "。" + (m.get("note") or ""), 160),
                      "src": [{"n": "财报与经济日历", "u": SITE + "/earnings.html"}]})
    end = (dt.date.fromisoformat(today) + dt.timedelta(days=5)).isoformat()
    up = [m for m in ev if today <= m["date"] <= end and not any(l.get("actual") for l in m.get("lines", []))]
    order = {"高": 0, "中": 1, "低": 2}
    up.sort(key=lambda m: (order.get(m.get("imp"), 3), m["date"], m.get("time") or ""))
    for m in sorted(up[:3], key=lambda m: (m["date"], m.get("time") or "")):
        items.append({"t": "%s %s：%s（重要性：%s）" % (md(m["date"]), m.get("time") or "", m.get("title", ""), m.get("imp", "—")),
                      "d": m.get("note") or "", "src": [{"n": "财报与经济日历", "u": SITE + "/earnings.html"}]})
    return items, up


def sec_world():
    T = load("news/data/today.json")
    items = []
    for g in (T.get("big") or [])[:4]:
        src = [{"n": g.get("source", "来源"), "u": g.get("link", "")}]
        for o in (g.get("others") or [])[:1]:
            src.append({"n": o.get("source", "来源"), "u": o.get("link", "")})
        n = g.get("n") or 1
        d = clip(g.get("summary", ""), 130)
        if n > 1:
            d += "（%d 家媒体同时报道）" % n
        items.append({"t": clip(g.get("title", ""), 60), "d": d, "src": src, "_n": n})
    return items


def build(dry=False):
    now_utc = dt.datetime.now(dt.timezone.utc)
    today = la_now().date().isoformat()
    try:
        cache = json.load(open(TCACHE_PATH, encoding="utf-8"))
    except Exception:
        cache = {}
    ai = sec_ai(now_utc, cache)
    market = sec_market(today)
    macro, upcoming = sec_macro(today)
    world = sec_world()

    hi = [m for m in upcoming if m.get("imp") == "高" and m["date"] <= (dt.date.fromisoformat(today) + dt.timedelta(days=3)).isoformat()]
    if hi:
        m = hi[0]
        pick = {"t": "%s：%s" % (md(m["date"]), m.get("title", "")), "d": (m.get("note") or "") + " 这是近几天最可能让整个市场大幅波动的事件，公布前后留意仓位。"}
    elif world:
        w = max(world, key=lambda x: x["_n"])
        pick = {"t": w["t"], "d": "今天报道媒体最多的一件事。" + w["d"]}
    else:
        pick = {}
    for w in world:
        w.pop("_n", None)

    week = []
    if dt.date.fromisoformat(today).weekday() == 0:
        E = load("earnings/data/latest.json")
        fri = (dt.date.fromisoformat(today) + dt.timedelta(days=4)).isoformat()
        for m in sorted([m for m in macro_events(E) if today <= m["date"] <= fri and m.get("imp") in ("高", "中")], key=lambda m: (m["date"], m.get("time") or "")):
            week.append({"t": "%s %s" % (md(m["date"]), m.get("title", "")), "d": m.get("note") or ""})
        for d in E.get("days", []):
            if today <= d.get("date", "") <= fri and d.get("earnings"):
                big = sorted(d["earnings"], key=lambda e: -(e.get("cap") or 0))[:4]
                week.append({"t": "%s 财报：%s" % (md(d["date"]), "、".join(e["t"] for e in big)), "d": "当天共 %d 家公司发布财报，这里列市值最大的几家。" % len(d["earnings"])})

    secs = [("ai", "🤖 AI 与科技", ai), ("market", "📈 美股市场", market), ("macro", "🏦 宏观经济", macro), ("world", "🌍 世界大事", world)]
    D = {"date": today, "generated": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"), "auto": True,
         "sections": [{"key": k, "title": t, "items": it} for k, t, it in secs], "pick": pick, "week": week}
    n = sum(len(s["items"]) for s in D["sections"])
    print("%s：%s，共 %d 条%s" % (today, " / ".join("%s %d" % (t, len(it)) for _, t, it in secs), n, "，含本周关注 %d 条" % len(week) if week else ""))
    if n < 4:
        print("❌ 内容太少（上游数据可能没更新），这次不写入")
        return 1
    if dry:
        print(json.dumps(D, ensure_ascii=False, indent=1)[:4000])
        return 0

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, today + ".json"), "w", encoding="utf-8") as f:
        json.dump(D, f, ensure_ascii=False, indent=1)
    # index.json：只放日期列表（最新在前，最多 30 天），清理旧文件
    dates = sorted({fn[:-5] for fn in os.listdir(OUT) if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", fn)}, reverse=True)
    keep, drop = dates[:KEEP_DAYS], dates[KEEP_DAYS:]
    for d in drop:
        os.remove(os.path.join(OUT, d + ".json"))
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"generated": D["generated"], "dates": keep}, f, ensure_ascii=False)
    # 翻译缓存只留最近 300 条，避免越存越大
    keep_cache = dict(list(cache.items())[-300:])
    with open(TCACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(keep_cache, f, ensure_ascii=False)
    print("✅ 已写入 brief/data/%s.json（共保留 %d 期）" % (today, len(keep)))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    sys.exit(build(ap.parse_args().dry))
