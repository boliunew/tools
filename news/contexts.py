"""Build news/data/contexts.json: real, fresh example sentences for the words in 语境词库 (vocab.html).

Runs after news/build.py. Keeps a rolling 14-day pool of sentences taken from the
headline + summary of each article (the only text we store), and indexes which
vocab words (any inflected form) appear in them.
"""
import datetime as dt
import html
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "news", "data", "contexts.json")
KEEP_DAYS, MAX_SENTS, PER_WORD, SKIP_TOP = 14, 1600, 3, 400
JUNK = re.compile(r"follow (our|the)|continue reading|sign up|newsletter|photograph:|getty images|click here|live blog|listen to|subscribe|\bpodcast\b|©", re.I)


def vocab_forms():
    s = open(os.path.join(ROOT, "vocab.html"), encoding="utf-8").read()
    a = s.index('<script type="application/json" id="data">') + len('<script type="application/json" id="data">')
    data = json.loads(s[a:s.index("</script>", a)])
    fm = {}
    for i, e in enumerate(data["w"]):
        if i < SKIP_TOP:
            continue
        for f in [e[0]] + list(e[4]):
            fm.setdefault(f.lower(), e[0])
    return fm


def sentences(text):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"'‘“])", text):
        s = s.strip()
        if 40 <= len(s) <= 240 and len(s.split()) >= 7 and not JUNK.search(s) and re.search(r"[a-z]", s):
            yield s


def main():
    news = json.load(open(os.path.join(ROOT, "news", "data", "latest.json"), encoding="utf-8"))
    old = {"sents": []}
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    pool, seen = [], set()
    for a in news.get("articles", []):
        iso = (a.get("time") or dt.datetime.now(dt.timezone.utc).isoformat())[:10]
        d = dt.date.fromisoformat(iso)
        for s in list(sentences(a.get("title", "") + ".")) + list(sentences(a.get("summary", ""))):
            if s not in seen:
                seen.add(s)
                pool.append([s, a.get("source", ""), f"{d.month}/{d.day}", iso])
    for e in old.get("sents", []):
        if len(e) >= 4 and e[3] >= cutoff and e[0] not in seen:
            seen.add(e[0])
            pool.append(e)
    pool.sort(key=lambda e: e[3], reverse=True)
    pool = pool[:MAX_SENTS]

    fm = vocab_forms()
    idx = {}
    for i, e in enumerate(pool):
        for tok in set(re.findall(r"[A-Za-z][a-z'\-]+", e[0])):
            base = fm.get(tok.lower())
            if base and (tok[0].islower() or tok.lower() == tok):  # skip capitalised names
                lst = idx.setdefault(base, [])
                if len(lst) < PER_WORD:
                    lst.append(i)
    doc = {"updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "sents": pool, "idx": idx}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"contexts: {len(pool)} sentences, {len(idx)} words indexed, {os.path.getsize(OUT) // 1024} KB")


if __name__ == "__main__":
    main()
