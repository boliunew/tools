#!/usr/bin/env python3
"""合并 part1–3 的周公解梦词条 → dream/dreams.json（重复关键词只留第一条，别名合并）。"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
CATS = ["人物", "动物", "身体", "自然", "物品", "场景", "行为", "鬼神"]
items, idx = [], {}
for mod in ("part1", "part2", "part3"):
    for e in __import__(mod).ENTRIES:
        k = e["k"].strip()
        if k in idx:
            old = items[idx[k]]
            old["a"] = list(dict.fromkeys(old["a"] + [x for x in e["a"] if x != k]))[:6]
            continue
        idx[k] = len(items)
        items.append({"k": k, "a": [x for x in e["a"] if x != k], "c": e["c"], "t": e["t"], "x": e["x"], "v": e["v"]})
EXTRA = {"去世的亲人": ["去世", "过世", "已故", "死去的"], "被追": ["追我", "追着", "蛇追", "狗追", "被追"]}
for e in items:
    for w in EXTRA.get(e["k"], []):
        if w not in e["a"] and w != e["k"]:
            e["a"].append(w)
items.sort(key=lambda e: CATS.index(e["c"]) if e["c"] in CATS else 99)
with open(os.path.join(HERE, "dreams.json"), "w", encoding="utf-8") as f:
    json.dump({"cats": CATS, "items": items}, f, ensure_ascii=False, separators=(",", ":"))
print(len(items), "条", {c: sum(1 for e in items if e["c"] == c) for c in CATS})
