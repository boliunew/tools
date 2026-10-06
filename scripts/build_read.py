"""Graded reading for english.html: read/src/<level>/*.txt  ->  read/<level>.json

Source file format (one piece per file, file name sets the order):

    kind: story | article
    title: English title
    zh: 中文标题
    summary: 中文简介（一两句）
    grammar: 语法点名称 | 中文说明 | an exact sentence (or phrase) copied from the text
    grammar: ...
    vocab: word 中文; word 中文; ...
    ---
    First paragraph.

    Second paragraph.

The script checks every grammar example really appears in the text (so the page can highlight it)
and that stories have 1000+ words and articles 2000+ words.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "read", "src")
OUT = os.path.join(ROOT, "read")
LEVELS = ["elem", "mid", "high", "col"]
MIN_WORDS = {"story": 1000, "article": 2000}


def words(text):
    return len(re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)*", text))


def parse(path):
    raw = open(path, encoding="utf-8").read().replace("\r\n", "\n")
    head, body = raw.split("\n---\n", 1)
    doc = {"id": os.path.splitext(os.path.basename(path))[0], "grammar": [], "vocab": []}
    for line in head.strip().split("\n"):
        if not line.strip():
            continue
        k, v = line.split(":", 1)
        k, v = k.strip(), v.strip()
        if k == "grammar":
            name, zh, ex = [x.strip() for x in v.split("|")]
            doc["grammar"].append({"name": name, "zh": zh, "ex": ex})
        elif k == "vocab":
            for item in v.split(";"):
                item = item.strip()
                if item:
                    w, zh = item.split(" ", 1) if " " in item else (item, "")
                    # multi-word entries are written with _ : look_forward_to 期待
                    doc["vocab"].append([w.replace("_", " "), zh.strip()])
        else:
            doc[k] = v
    doc["paras"] = [re.sub(r"\s+", " ", p).strip() for p in body.strip().split("\n\n") if p.strip()]
    doc["words"] = words(" ".join(doc["paras"]))
    return doc


def main():
    bad = 0
    for lv in LEVELS:
        d = os.path.join(SRC, lv)
        if not os.path.isdir(d):
            continue
        items = [parse(os.path.join(d, f)) for f in sorted(os.listdir(d)) if f.endswith(".txt")]
        items.sort(key=lambda it: (it["kind"] != "story", it["id"]))   # stories first, then articles
        for it in items:
            full = " ".join(it["paras"])
            for g in it["grammar"]:
                if g["ex"] not in full:
                    print(f"[{lv}/{it['id']}] grammar example not found in text: {g['ex']!r}")
                    bad += 1
            low = full.lower()
            for w, _ in it["vocab"]:
                if w.lower() not in low:
                    print(f"[{lv}/{it['id']}] vocab word not in text: {w!r}")
                    bad += 1
            need = MIN_WORDS.get(it["kind"], 0)
            flag = "" if it["words"] >= need else f"   <-- needs {need}+"
            if flag:
                bad += 1
            print(f"{lv}/{it['id']:<4} {it['kind']:<8} {it['words']:>5} words  {it['title']}{flag}")
        with open(os.path.join(OUT, lv + ".json"), "w", encoding="utf-8") as f:
            json.dump({"level": lv, "items": items}, f, ensure_ascii=False, separators=(",", ":"))
    print("problems:", bad)
    return 1 if bad and "--strict" in sys.argv else 0


if __name__ == "__main__":
    sys.exit(main())
