"""Write card/today.json — today's 每日一句 and 今日单词 — for home-screen widget apps (KWGT etc.).

Same pick as card.html: item = days-since-1970 (Los Angeles date) mod pool size.
Runs with the news job (twice a day); stdlib only.
"""
import datetime as dt
import json
import os
import re
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    today = dt.datetime.now(ZoneInfo("America/Los_Angeles")).date()
    n = (today - dt.date(1970, 1, 1)).days
    pool = json.load(open(os.path.join(HERE, "daily.json"), encoding="utf-8"))["items"]
    it = pool[n % len(pool)]
    out = {"date": today.isoformat(), "kind": it["k"], "en": it["en"], "zh": it["zh"],
           "by": it.get("by") or it.get("note") or "", "line": "", "word": None,
           "page": "https://boliunew.github.io/tools/card.html"}
    out["line"] = "%s — %s" % (it["en"], it["by"]) if it.get("by") else it["en"]
    if it["k"] == "易错":
        out["line"] = "✗ %s → ✓ %s" % (it.get("bad", ""), it["en"])
    # 今日单词: a word from the 核心 band (3001–6000) with an example sentence, same for everyone
    words = open(os.path.join(HERE, "idx.txt"), encoding="utf-8").read().split("\n")
    for k in range(200):
        r = 3000 + (n * 7919 + k * 104729) % 3000
        rows = json.load(open(os.path.join(HERE, "c%02d.json" % (r // 500)), encoding="utf-8"))
        ph, tr, ex, exzh = rows[r % 500]
        if ex and not re.search(r"男子名|女子名|人名|姓氏|地名", tr):
            out["word"] = {"w": words[r], "ph": ph, "zh": tr, "ex": ex, "exzh": exzh}
            break
    with open(os.path.join(HERE, "today.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
