"""Build news/data/articles.json: whole, coherent, freely licensed English articles for the 语境词库 reader.

Sources (both allow storing and showing the full text with attribution):
  * Simple English Wikipedia — "Very good" / "Good" articles (CC BY-SA 4.0): plain English, any topic
  * English Wikinews — recently published news stories (CC BY 2.5)
A rolling pool is kept: a few new articles per run, oldest dropped, so each run makes only a handful of requests.
The page itself works out which of the reader's words each article contains.
"""
import datetime as dt
import hashlib
import json
import os
import random
import re
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "news", "data", "articles.json")
UA = "boliunew-tools/1.0 (https://github.com/boliunew/tools; personal vocabulary reader)"
POOL_WIKI, POOL_NEWS = 90, 30      # articles kept per source
NEW_WIKI, NEW_NEWS = 8, 10         # fetched per run at most
MIN_WORDS, MAX_WORDS = 180, 650    # trim long articles at a paragraph boundary
DROP = re.compile(r"^(references?|notes?|sources?|other websites|related pages|related news|external links|further reading|see also|gallery|bibliography|footnotes|sister links|citations|works cited|filmography|discography)$", re.I)
notes = []


def api(host, **params):
    params.update({"format": "json", "formatversion": "2"})
    url = "https://%s/w/api.php?%s" % (host, urllib.parse.urlencode(params))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def split_sents(p):
    p = re.sub(r"\s+", " ", p).strip()
    parts = re.split(r"(?<=[.!?])[\"”’)]?\s+(?=[A-Z0-9\"“‘(])", p)
    out, hold = [], ""
    for s in parts:
        s = (hold + " " + s).strip() if hold else s.strip()
        hold = ""
        if not s:
            continue
        if re.search(r"\b(?:Mr|Mrs|Ms|Dr|St|Jr|Sr|Prof|Gen|Gov|Sen|Rep|No|vs|e\.g|i\.e)\.$", s):
            hold = s  # an abbreviation ends this piece: it belongs to the next sentence
            continue
        if out and len(s) < 12:
            out[-1] += " " + s
        else:
            out.append(s)
    if hold:
        out.append(hold)
    return out


def shape(text, title):
    """wiki-format extract → [{'h': heading}|{'s': [sentences]}], word count"""
    blocks, words, skip = [], 0, False
    for raw in re.split(r"\n+", text or ""):
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^(=+)\s*(.*?)\s*=+$", line)
        if m:
            skip = bool(DROP.match(m.group(2)))
            if not skip and len(m.group(1)) <= 3:
                blocks.append({"h": m.group(2)})
            continue
        if skip or len(line) < 40 or line.count(" ") < 6:
            continue
        sents = split_sents(line)
        if not sents:
            continue
        n = sum(len(s.split()) for s in sents)
        if words >= MIN_WORDS and words + n > MAX_WORDS:
            break
        blocks.append({"s": sents})
        words += n
    while blocks and "h" in blocks[-1]:
        blocks.pop()
    return blocks, words


def fetch_article(host, title, src, lic, lic_url):
    d = api(host, action="query", prop="extracts|info", explaintext=1, exsectionformat="wiki", inprop="url", titles=title, redirects=1)
    pages = d.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return None
    pg = pages[0]
    text = pg.get("extract") or ""
    date = ""
    if src == "wikinews":
        m = re.match(r"^\s*((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+\w+\s+\d{1,2},\s+\d{4})\s*", text)
        if m:
            date = m.group(1)
            text = text[m.end():]
    blocks, n = shape(text, pg.get("title"))
    if n < MIN_WORDS * 0.8:
        return None
    t = pg.get("title") or title
    return {"id": src[:2] + hashlib.md5(t.encode("utf-8")).hexdigest()[:8], "src": src, "title": t,
            "url": pg.get("fullurl") or "https://%s/wiki/%s" % (host, urllib.parse.quote(t.replace(" ", "_"))),
            "lic": lic, "licu": lic_url, "date": date, "n": n, "b": blocks,
            "added": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")}


def wiki_titles():
    titles = []
    for cat in ("Category:Very good articles", "Category:Good articles"):
        try:
            cont = {}
            for _ in range(4):
                d = api("simple.wikipedia.org", action="query", list="categorymembers", cmtitle=cat, cmlimit=500, **cont)
                for m in d.get("query", {}).get("categorymembers", []):
                    t = m.get("title", "")
                    t = re.sub(r"^Talk:", "", t)
                    if ":" not in t and t not in titles:
                        titles.append(t)
                if "continue" not in d:
                    break
                cont = d["continue"]
                time.sleep(0.5)
        except Exception as e:  # noqa: BLE001
            notes.append("simplewiki %s: %s" % (cat, str(e)[:80]))
    return titles


def news_titles():
    d = api("en.wikinews.org", action="query", list="categorymembers", cmtitle="Category:Published", cmsort="timestamp", cmdir="desc", cmlimit=40, cmnamespace=0)
    return [m["title"] for m in d.get("query", {}).get("categorymembers", [])]


def main():
    try:
        old = json.load(open(OUT, encoding="utf-8")).get("items", [])
    except Exception:  # noqa: BLE001
        old = []
    have = {a["title"]: a for a in old}
    wiki = [a for a in old if a["src"] == "simplewiki"]
    news = [a for a in old if a["src"] == "wikinews"]

    # Simple Wikipedia: a few new good articles per run, chosen at random so topics vary
    try:
        cand = [t for t in wiki_titles() if t not in have]
        random.seed(dt.date.today().toordinal())
        random.shuffle(cand)
        got = 0
        want = NEW_WIKI if len(wiki) >= 30 else 30   # fill the pool faster on the first runs
        for t in cand[:want * 3]:
            if got >= want:
                break
            try:
                a = fetch_article("simple.wikipedia.org", t, "simplewiki", "CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/")
            except Exception as e:  # noqa: BLE001
                notes.append("simplewiki %s: %s" % (t, str(e)[:60]))
                a = None
            if a:
                wiki.insert(0, a); got += 1
            time.sleep(0.6)
    except Exception as e:  # noqa: BLE001
        notes.append("simplewiki: %s" % str(e)[:100])

    # Wikinews: newest published stories
    try:
        got = 0
        for t in news_titles():
            if got >= NEW_NEWS or t in have:
                continue
            try:
                a = fetch_article("en.wikinews.org", t, "wikinews", "CC BY 2.5", "https://creativecommons.org/licenses/by/2.5/")
            except Exception as e:  # noqa: BLE001
                notes.append("wikinews %s: %s" % (t, str(e)[:60]))
                a = None
            if a:
                news.insert(0, a); got += 1
            time.sleep(0.6)
    except Exception as e:  # noqa: BLE001
        notes.append("wikinews: %s" % str(e)[:100])

    items = news[:POOL_NEWS] + wiki[:POOL_WIKI]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    doc = {"updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "items": items, "notes": notes}
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, OUT)
    print("articles: %d wikinews + %d simplewiki, %d KB, notes %s" % (len(news[:POOL_NEWS]), len(wiki[:POOL_WIKI]), os.path.getsize(OUT) // 1024, notes))
    for a in items[:6]:
        print("  ", a["src"], a["n"], "words ·", a["title"])


if __name__ == "__main__":
    main()
