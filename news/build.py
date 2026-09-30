#!/usr/bin/env python3
"""
每日英文新闻精选 (GitHub Actions)

Fetches public RSS feeds, reads each article server-side to measure its
difficulty (sentence length, syllables, word rarity via `wordfreq`), and writes
news/data/latest.json.  Only headline, the feed's own summary, link and our
computed stats are stored — the article text itself is NOT republished.

Offline test:  python news/build.py --fixtures <dir with feed_0.xml + article html>
"""
import argparse
import datetime as dt
import email.utils
import hashlib
import html
import json
import math
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "latest.json")
FEEDS_FILE = os.path.join(HERE, "feeds.json")
KEEP_HOURS = 72
MAX_PER_FEED = 12
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

DEFAULT_FEEDS = [
    {"source": "BBC", "topic": "国际", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"source": "BBC", "topic": "商业", "url": "https://feeds.bbci.co.uk/news/business/rss.xml"},
    {"source": "BBC", "topic": "科技", "url": "https://feeds.bbci.co.uk/news/technology/rss.xml"},
    {"source": "BBC", "topic": "科学", "url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"},
    {"source": "NPR", "topic": "综合", "url": "https://feeds.npr.org/1001/rss.xml"},
    {"source": "NPR", "topic": "科技", "url": "https://feeds.npr.org/1019/rss.xml"},
    {"source": "The Guardian", "topic": "国际", "url": "https://www.theguardian.com/world/rss"},
    {"source": "The Guardian", "topic": "科技", "url": "https://www.theguardian.com/technology/rss"},
    {"source": "The Guardian", "topic": "科学", "url": "https://www.theguardian.com/science/rss"},
    {"source": "Al Jazeera", "topic": "国际", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"source": "ScienceDaily", "topic": "科学", "url": "https://www.sciencedaily.com/rss/top/science.xml"},
]


# ----------------------------------------------------------------------------- text utils
def clean(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r"\s+([.,;:!?])", r"\1", s)


def syllables(w):
    w = re.sub(r"[^a-z]", "", w.lower())
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", w)))


SENT_RE = re.compile(r"(?<=[.!?])[\"'”’)]*\s+(?=[A-Z\"“‘(])")
WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


def level_of(fk, rr):
    # calibrated on real BBC / NPR / Guardian / Al Jazeera articles: news sits mostly in B2–C1
    adj = fk + rr * 8
    for cut, lv, zh in ((7, "A2", "入门"), (9.5, "B1", "初中级"), (12, "B2", "中级"), (14.5, "C1", "中高级"), (99, "C2", "高级")):
        if adj < cut:
            break
    return lv, zh, round(max(0, min(100, adj * 5.5)))


def grade(text):
    from wordfreq import zipf_frequency
    sents = [s for s in SENT_RE.split(text) if WORD_RE.search(s)]
    words, syl, content, rare, vocab = 0, 0, 0, 0, {}
    long_sent = 0
    for s in sents:
        ws = WORD_RE.findall(s)
        if len(ws) >= 25:
            long_sent += 1
        for i, w in enumerate(ws):
            words += 1
            syl += syllables(w)
            lw = w.lower().split("'")[0]
            if w[0].isupper() and i > 0:
                continue  # proper nouns don't count as vocabulary
            if len(lw) > 3:
                content += 1
                z = zipf_frequency(lw, "en")
                if z < 3.6:
                    rare += 1
                    if 1.8 <= z and lw not in vocab:
                        vocab[lw] = z
    if words < 80:
        return None
    S = max(len(sents), 1)
    asl, asw = words / S, syl / words
    fk = 0.39 * asl + 11.8 * asw - 15.59
    rr = rare / content if content else 0
    lv, zh, score = level_of(fk, rr)
    return {
        "words": words, "minutes": max(1, round(words / 130)), "asl": round(asl, 1), "fk": round(fk, 1),
        "rare": round(rr, 3), "level": lv, "levelZh": zh, "score": score,
        "long": long_sent,
        "vocab": [w for w, _ in sorted(vocab.items(), key=lambda kv: kv[1])[:8]],
    }


def extract(page_html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(page_html, "html.parser")
    for t in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "figure", "figcaption", "button"]):
        t.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup

    def paras(node):
        out = []
        for p in node.find_all("p"):
            t = clean(p.get_text(" "))
            if len(t) >= 40 and not re.match(r"(?i)(advertisement|sign up|subscribe|follow us|read more|copyright|©)", t):
                out.append(t)
        return out

    ps = paras(root)
    if len(ps) < 3 and soup.body:
        alt = paras(soup.body)
        if len(alt) > len(ps):
            ps = alt
    return "\n\n".join(ps)


# ----------------------------------------------------------------------------- fetching
def http_get(url, timeout=20):
    import requests
    r = requests.get(url, timeout=timeout, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    r.raise_for_status()
    return r.text


def entry_time(e):
    for k in ("published_parsed", "updated_parsed"):
        v = e.get(k)
        if v:
            return dt.datetime(*v[:6], tzinfo=dt.timezone.utc)
    for k in ("published", "updated"):
        if e.get(k):
            try:
                return email.utils.parsedate_to_datetime(e[k]).astimezone(dt.timezone.utc)
            except Exception:  # noqa: BLE001
                pass
    return dt.datetime.now(dt.timezone.utc)


def load_feeds():
    if os.path.exists(FEEDS_FILE):
        with open(FEEDS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_FEEDS


def process(item, fixtures):
    try:
        if fixtures:
            fn = os.path.join(fixtures, hashlib.md5(item["link"].encode()).hexdigest()[:10] + ".html")
            page = open(fn, encoding="utf-8").read() if os.path.exists(fn) else ""
        else:
            page = http_get(item["link"])
        text = extract(page)
        g = grade(text)
        if not g:
            return None
        item.update(g)
        return item
    except Exception as e:  # noqa: BLE001
        print("  skip", item["link"][:80], type(e).__name__)
        return None


def main():
    import feedparser
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", help="directory with feed_*.xml and article html (offline test)")
    args = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc)

    old = {}
    if os.path.exists(OUT):
        try:
            with open(OUT, encoding="utf-8") as f:
                for a in json.load(f).get("articles", []):
                    old[a["id"]] = a
        except Exception:  # noqa: BLE001
            pass

    feeds = load_feeds()
    items, feed_status = [], []
    for i, fd in enumerate(feeds):
        try:
            if args.fixtures:
                raw = open(os.path.join(args.fixtures, f"feed_{i}.xml"), encoding="utf-8").read() \
                    if os.path.exists(os.path.join(args.fixtures, f"feed_{i}.xml")) else ""
            else:
                raw = http_get(fd["url"])
            parsed = feedparser.parse(raw)
            n = 0
            for e in parsed.entries[:MAX_PER_FEED * 2]:
                link = e.get("link", "")
                if not link or re.search(r"/(video|videos|live|av|sounds|podcasts?|gallery|pictures|audio)/", link):
                    continue
                t = entry_time(e)
                if (now - t).total_seconds() > KEEP_HOURS * 3600:
                    continue
                aid = hashlib.md5(link.split("?")[0].encode()).hexdigest()[:12]
                summ = clean(e.get("summary", ""))
                if len(summ) > 320:
                    summ = summ[:300].rsplit(" ", 1)[0] + "…"
                items.append({"id": aid, "title": clean(e.get("title", "")), "summary": summ, "link": link,
                              "source": fd["source"], "topic": fd["topic"], "time": t.strftime("%Y-%m-%dT%H:%M:%SZ")})
                n += 1
                if n >= MAX_PER_FEED:
                    break
            feed_status.append({"source": fd["source"], "topic": fd["topic"], "ok": True, "n": n})
        except Exception as e:  # noqa: BLE001
            print("feed failed", fd["url"], e)
            feed_status.append({"source": fd["source"], "topic": fd["topic"], "ok": False, "n": 0})

    # de-duplicate (same story in several feeds)
    seen, uniq = set(), []
    for it in items:
        if it["id"] in seen:
            continue
        seen.add(it["id"])
        uniq.append(it)

    todo = [it for it in uniq if it["id"] not in old]
    reuse = [dict(old[it["id"]], topic=it["topic"]) for it in uniq if it["id"] in old]
    print(f"{len(uniq)} items in window: {len(reuse)} cached, {len(todo)} to fetch")
    with ThreadPoolExecutor(max_workers=6) as ex:
        fresh = [r for r in ex.map(lambda it: process(it, args.fixtures), todo) if r]
    # keep old articles still inside the window even if the feed dropped them
    kept_ids = {a["id"] for a in reuse} | {a["id"] for a in fresh}
    carry = [a for a in old.values() if a["id"] not in kept_ids and
             (now - dt.datetime.strptime(a["time"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)).total_seconds() < KEEP_HOURS * 3600]
    arts = sorted(reuse + fresh + carry, key=lambda a: a["time"], reverse=True)
    for a in arts:  # re-grade cached items with the current calibration
        if "fk" in a and "rare" in a:
            a["level"], a["levelZh"], a["score"] = level_of(a["fk"], a["rare"])

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "feeds": feed_status, "articles": arts},
                  f, ensure_ascii=False, separators=(",", ":"))
    lv = {}
    for a in arts:
        lv[a["level"]] = lv.get(a["level"], 0) + 1
    print(f"wrote {len(arts)} articles; levels {lv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
