#!/usr/bin/env python3
"""
今日大事 · 趣闻 · 历史上的今天  →  news/data/today.json

* 今日大事：几家中文新闻源（BBC 中文、德国之声、法广、纽约时报中文网、中新网……）的 RSS，
  把讲同一件事的标题聚成一组，被越多家报道的排越前。只存标题、摘要、链接。
* 趣闻：UPI Odd News 等英文奇闻源，标题顺手机翻成中文（MyMemory 免费接口，翻过的会缓存复用）。
* 历史上的今天：中文维基百科「10月3日」这类日期页的「大事记」和「节假日」，今天和明天（太平洋时间）各一份。

任何一个来源失败都只会跳过它，状态记在 today.json 的 "sources" 里。
"""
import datetime as dt
import html
import json
import math
import os
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "today.json")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
WIKI_UA = "boliunew-tools/1.0 (https://github.com/boliunew/tools; personal reader page)"
KEEP_HOURS = 30
TZ = dt.timezone(dt.timedelta(hours=-7))  # 太平洋夏令时；冬令时差一小时，对「今天是几号」影响很小

ZH_FEEDS = [
    ("BBC 中文", "https://feeds.bbci.co.uk/zhongwen/simp/rss.xml"),
    ("德国之声", "https://rss.dw.com/rdf/rss-chi-all"),
    ("法广", "https://www.rfi.fr/cn/rss"),
    ("纽约时报中文网", "https://cn.nytimes.com/rss/"),
    ("中新网", "https://www.chinanews.com.cn/rss/importnews.xml"),
    ("中新网", "https://www.chinanews.com.cn/rss/world.xml"),
]
ZH_ORDER = {name: i for i, (name, _) in enumerate(ZH_FEEDS)}
ODD_FEEDS = [
    ("UPI", "https://rss.upi.com/news/odd_news.rss"),
    ("Sky News", "https://feeds.skynews.com/feeds/rss/strange.xml"),
    ("Oddity Central", "https://www.odditycentral.com/feed"),
]


def http_get(url, timeout=20, headers=None, raw=False):
    import requests
    h = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
    h.update(headers or {})
    r = requests.get(url, timeout=timeout, headers=h)
    r.raise_for_status()
    return r.content if raw else r.text


def clean(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def to_simplified(s):
    try:
        import zhconv
        return zhconv.convert(s, "zh-cn")
    except Exception:
        return s


def entry_time(e):
    for k in ("published_parsed", "updated_parsed"):
        t = e.get(k)
        if t:
            return dt.datetime(*t[:6], tzinfo=dt.timezone.utc)
    return None


def fetch_feed(name, url):
    import feedparser
    try:
        parsed = feedparser.parse(http_get(url, raw=True))
        out = []
        for e in parsed.entries[:40]:
            title = clean(e.get("title"))
            link = e.get("link") or ""
            if not title or not link.startswith("http"):
                continue
            summ = clean(e.get("summary") or e.get("description") or "")
            if summ.startswith(title):
                summ = summ[len(title):].strip(" ：:-—")
            out.append({"source": name, "title": title, "summary": summ[:220], "link": link, "time": entry_time(e)})
        return name, url, out, None
    except Exception as ex:  # noqa: BLE001
        return name, url, [], "%s: %s" % (type(ex).__name__, str(ex)[:120])


# ----------------------------------------------------------------------------- 聚类：讲同一件事的放一组
CJK = re.compile(r"[一-鿿]+")
LAT = re.compile(r"[A-Za-z][A-Za-z0-9\-]{2,}")
STOP_BIGRAMS = {"表示", "认为", "指出", "报道", "消息", "最新", "今天", "昨天", "一个", "这个", "我们", "他们", "没有", "已经",
                "可能", "进行", "发生", "问题", "情况", "相关", "目前", "继续", "周一", "周二", "周三", "周四", "周五", "周六",
                "周日", "星期", "日电", "记者", "中新", "新网", "什么", "为何", "如何", "是否", "不是", "成为", "之后", "以来"}


def tokens(s):
    toks = []
    for run in CJK.findall(s):
        toks += [run[i:i + 2] for i in range(len(run) - 1)]
    toks += [w.lower() for w in LAT.findall(s)]
    return [t for t in toks if t not in STOP_BIGRAMS]


def cluster(items):
    docs = [tokens(it["title"] + " " + it["title"] + " " + it["summary"][:80]) for it in items]   # 标题算两遍，权重更高
    df = {}
    for d in docs:
        for t in set(d):
            df[t] = df.get(t, 0) + 1
    n = len(docs)
    vecs = []
    for d in docs:
        tf = {}
        for t in d:
            tf[t] = tf.get(t, 0) + 1
        v = {t: c * math.log((n + 1) / (df[t] + 0.5)) for t, c in tf.items() if df[t] <= max(6, n * 0.25)}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1
        vecs.append({t: x / norm for t, x in v.items()})

    def cos(a, b):
        if len(a) > len(b):
            a, b = b, a
        return sum(x * b.get(t, 0) for t, x in a.items())

    groups = []   # [ {members:[idx], vec:{}} ]
    for i in sorted(range(n), key=lambda k: items[k]["time"] or dt.datetime.min.replace(tzinfo=dt.timezone.utc), reverse=True):
        best, bs = None, 0.0
        for g in groups:
            s = max(cos(vecs[i], vecs[j]) for j in g["members"])
            if s > bs:
                best, bs = g, s
        if best is not None and bs >= 0.2:
            best["members"].append(i)
        else:
            groups.append({"members": [i]})
    out = []
    for g in groups:
        mem = [items[i] for i in g["members"]]
        srcs = []
        for m in mem:
            if m["source"] not in srcs:
                srcs.append(m["source"])
        # 代表条目：摘要最完整的那条
        rep = max(mem, key=lambda m: (len(m["summary"]) > 20, -ZH_ORDER.get(m["source"], 9), len(m["summary"])))
        latest = max((m["time"] for m in mem if m["time"]), default=None)
        others = [{"source": m["source"], "title": m["title"], "link": m["link"]} for m in mem if m is not rep][:4]
        out.append({"title": rep["title"], "summary": rep["summary"], "link": rep["link"], "source": rep["source"],
                    "time": latest.strftime("%Y-%m-%dT%H:%M:%SZ") if latest else None, "n": len(srcs), "sources": srcs, "others": others})
    out.sort(key=lambda c: (c["n"], c["time"] or ""), reverse=True)
    return out



# ----------------------------------------------------------------------------- 趣闻：标题机翻（带缓存）
def translate(text, cache):
    if text in cache:
        return cache[text]
    try:
        q = urllib.parse.urlencode({"q": text[:450], "langpair": "en|zh-CN"})
        d = json.loads(http_get("https://api.mymemory.translated.net/get?" + q, timeout=15))
        zh = (d.get("responseData") or {}).get("translatedText") or ""
        if d.get("responseStatus") in (200, "200") and zh and not re.search(r"MYMEMORY WARNING|QUOTA", zh, re.I):
            cache[text] = html.unescape(zh)
            return cache[text]
    except Exception:
        pass
    return ""


# ----------------------------------------------------------------------------- 历史上的今天（中文维基日期页）
def onthisday(month, day):
    from bs4 import BeautifulSoup
    page = "%d月%d日" % (month, day)
    url = "https://zh.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "parse", "page": page, "prop": "text", "format": "json", "variant": "zh-cn", "redirects": 1, "disableeditsection": 1})
    d = json.loads(http_get(url, headers={"User-Agent": WIKI_UA}))
    soup = BeautifulSoup(d["parse"]["text"]["*"], "html.parser")
    for s in soup.select("sup, .mw-editsection, style, .noprint"):
        s.decompose()

    def section(pred):
        h2 = next((h for h in soup.find_all("h2") if pred(h.get_text(strip=True))), None)
        if not h2:
            return []
        lis = []
        for el in h2.find_all_next(["h2", "li"]):
            if el.name == "h2":
                break
            lis.append(el)
        return lis

    events = []
    for li in section(lambda t: t.startswith("大事")):
        if li.find_parent("li") is not None:
            continue   # 嵌套的子条目在父条目里处理
        sub = li.find("ul")
        own = li.get_text("", strip=True) if not sub else "".join(
            x if isinstance(x, str) else x.get_text("", strip=True) for x in li.contents if getattr(x, "name", None) != "ul").strip()
        m = re.match(r"^(前)?\s*(\d{1,4})\s*年\s*[：:]?\s*(.*)$", own)
        if not m:
            continue
        year = int(m.group(2)) * (-1 if m.group(1) else 1)
        texts = [m.group(3)] if m.group(3) else []
        if sub:
            texts += [x.get_text("", strip=True) for x in sub.find_all("li", recursive=False)]
        for t in texts:
            t = re.sub(r"\s+", " ", re.sub(r"\s+([，。、；：！？）」』])", r"\1", re.sub(r"([（「『])\s+", r"\1", t))).strip()
            if 4 <= len(t) <= 160:
                events.append({"year": year, "text": to_simplified(t)})
    hol = []
    for li in section(lambda t: ("节" in t and ("日" in t or "俗" in t)) or "节假" in t):
        t = re.sub(r"\s+", " ", li.get_text("", strip=True))
        t = re.sub(r"\s+([，。、；：）])", r"\1", t)
        if 2 <= len(t) <= 80:
            hol.append(to_simplified(t))
    # 挑一部分：近代多挑一些，古代挑几条，按年份排
    modern = [e for e in events if e["year"] >= 1900]
    old = [e for e in events if e["year"] < 1900]

    def spread(lst, k):
        if len(lst) <= k:
            return lst
        return [lst[round(i * (len(lst) - 1) / (k - 1))] for i in range(k)]

    pick = spread(old, 3) + spread(modern, 7)
    return {"page": page, "url": "https://zh.wikipedia.org/wiki/" + urllib.parse.quote(page), "events": pick, "holidays": hol[:6], "total": len(events)}


# ----------------------------------------------------------------------------- main
def main():
    now = dt.datetime.now(dt.timezone.utc)
    prev = {}
    if os.path.exists(OUT):
        try:
            with open(OUT, encoding="utf-8") as f:
                prev = json.load(f)
        except Exception:
            prev = {}
    tcache = prev.get("tcache", {})
    status = []

    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda f: fetch_feed(*f), ZH_FEEDS + ODD_FEEDS))
    zh_items, odd_items, seen = [], [], set()
    for (name, url, items, err) in res:
        kind = "zh" if (name, url) in ZH_FEEDS else "odd"
        status.append({"kind": kind, "source": name, "url": url, "ok": err is None and bool(items), "n": len(items), "err": err})
        for it in items:
            key = it["link"].split("?")[0]
            if key in seen:
                continue
            seen.add(key)
            if it["time"] and now - it["time"] > dt.timedelta(hours=KEEP_HOURS if kind == "zh" else 24 * 5):
                continue
            if kind == "zh":
                it["title"], it["summary"] = to_simplified(it["title"]), to_simplified(it["summary"])
                zh_items.append(it)
            else:
                odd_items.append(it)

    big = cluster(zh_items)[:12] if zh_items else []

    odd_items.sort(key=lambda it: it["time"] or now, reverse=True)
    odd, per_src = [], {}
    for it in odd_items:
        if per_src.get(it["source"], 0) >= 6:
            continue
        per_src[it["source"]] = per_src.get(it["source"], 0) + 1
        title = re.sub(r"^(Watch|Look|Video|Photos?)\s*:\s*", "", it["title"])
        odd.append({"title": title, "video": bool(re.match(r"^(Watch|Video)\s*:", it["title"])), "zh": translate(title, tcache),
                    "summary": it["summary"][:200], "link": it["link"], "source": it["source"],
                    "time": it["time"].strftime("%Y-%m-%dT%H:%M:%SZ") if it["time"] else None})
        if len(odd) >= 10:
            break
    keep = set(o["title"] for o in odd)
    tcache = {k: v for k, v in tcache.items() if k in keep}

    otd = {}
    local = now.astimezone(TZ).date()
    for d in (local, local + dt.timedelta(days=1)):
        key = "%02d-%02d" % (d.month, d.day)
        try:
            otd[key] = onthisday(d.month, d.day)
            status.append({"kind": "otd", "source": "维基百科", "url": otd[key]["url"], "ok": bool(otd[key]["events"]), "n": len(otd[key]["events"]), "err": None})
        except Exception as ex:  # noqa: BLE001
            status.append({"kind": "otd", "source": "维基百科", "url": key, "ok": False, "n": 0, "err": "%s: %s" % (type(ex).__name__, str(ex)[:120])})
            if key in (prev.get("onthisday") or {}):
                otd[key] = prev["onthisday"][key]
        time.sleep(0.5)

    out = {"generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "big": big, "odd": odd, "onthisday": otd, "sources": status, "tcache": tcache}
    if not big and prev.get("big"):
        out["big"], out["stale_big"] = prev["big"], True   # 这次全失败就保留上次的
    if not odd and prev.get("odd"):
        out["odd"] = prev["odd"]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    ok = [s["source"] for s in status if s["ok"]]
    bad = ["%s(%s)" % (s["source"], s["err"] or "空") for s in status if not s["ok"]]
    print("今日大事 %d 组（%d 条）· 趣闻 %d 条 · 历史上的今天 %s" % (len(out["big"]), len(zh_items), len(out["odd"]), {k: len(v["events"]) for k, v in otd.items()}))
    print("OK:", ", ".join(ok))
    if bad:
        print("FAILED:", "; ".join(bad))


if __name__ == "__main__":
    main()
