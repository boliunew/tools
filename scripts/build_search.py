#!/usr/bin/env python3
"""全站搜索索引 → search/index.json

把技巧、知识库、菜谱、养生、解梦、心理、逻辑、人物专栏的内容汇成一个列表，search.html 在浏览器里搜。
每条：{"k": 类别, "t": 标题, "s": 一句话简介, "u": 链接, "x": 用来搜的全文（已转小写、截短）}
只用标准库；内容有变时在 GitHub Actions（kb.yml）或本地跑一下即可。
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "search", "index.json")


def load(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def flat(*parts, limit=1500):
    s = " ".join(" ".join(p) if isinstance(p, list) else str(p or "") for p in parts)
    return re.sub(r"\s+", " ", s).strip().lower()[:limit]


def short(s, n=60):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[:n] + "…"


def main():
    out = []

    tips = load("tips/tips.json")
    if tips:
        cats = {c["k"]: c["n"] for c in tips["cats"]}
        for it in tips["items"]:
            out.append({"k": "技巧·" + cats.get(it["c"], ""), "t": it["t"], "s": short(it["p"]), "u": "tips.html#" + it["id"],
                        "x": flat(it["t"], it["p"], it["s"], it["n"], it.get("r", ""), "忌讳 禁忌" if it.get("w") else "")})

    kb = load("kb/index.json")
    if kb:
        for a in kb["articles"]:
            out.append({"k": "知识库", "t": a["title"], "s": short(a["summary"]), "u": "kb.html#" + a["slug"],
                        "x": flat(a["title"], a["summary"], a["tags"], a.get("text", ""), limit=6000)})

    for f in ("recipes_cn", "recipes_cn2", "recipes_cn3", "recipes_west", "recipes_west2", "recipes_west3"):
        d = load("kitchen/%s.json" % f)
        for r in (d or {}).get("items", []):
            out.append({"k": "菜谱·" + r["cuisine"], "t": r["name"], "s": short("%s · %s · %d 分钟" % (r["en"], r["type"], r["time"])),
                        "u": "kitchen.html#r=" + r["id"],
                        "x": flat(r["name"], r["en"], r["type"], r["tags"], [i["n"] + " " + (i.get("buy") or "") for i in r["ing"]], r.get("tip", ""))})

    well = load("kitchen/wellness.json")
    if well:
        for t in well["tips"]:
            out.append({"k": "养生", "t": t["k"], "s": short(t["d"]), "u": "kitchen.html#well", "x": flat(t["k"], t["c"], t["d"], t["how"])})
        for j in well["jieqi"]:
            out.append({"k": "节气", "t": j["name"], "s": short(j["tcm"]), "u": "kitchen.html#well", "x": flat(j["name"], j["tcm"], j["eat"], j["life"], j["modern"])})

    dreams = load("dream/dreams.json")
    if dreams:
        for e in dreams["items"]:
            out.append({"k": "解梦", "t": "梦见" + e["k"], "s": short(e["t"]), "u": "dream.html#q=" + e["k"], "x": flat(e["k"], e["a"], e["t"], e["x"])})

    psy = load("mind/psy.json")
    if psy:
        for e in psy["items"]:
            out.append({"k": "心理学", "t": e["k"], "s": short(e["d"]), "u": "dream.html#psy", "x": flat(e["k"], e["en"], e["d"], e["e"], e["tip"], e.get("inv", ""))})
    logic = load("mind/logic.json")
    if logic:
        for e in logic["fallacies"]:
            out.append({"k": "逻辑", "t": e["k"], "s": short(e["d"]), "u": "dream.html#logic", "x": flat(e["k"], e["en"], e["d"], e["e"], e["fix"])})
        for e in logic["basics"]:
            out.append({"k": "逻辑", "t": e["k"], "s": short(e["d"]), "u": "dream.html#logic", "x": flat(e["k"], e["d"], e["e"])})

    for f in ("sushi_a", "sushi_b"):
        d = load("people/%s.json" % f)
        for w in (d or {}).get("items", []):
            out.append({"k": "苏轼", "t": w["title"], "s": short(w["why"]), "u": "people.html#sushi/" + w["id"],
                        "x": flat(w["title"], w["text"], w["trans"], w["bg"], w["tags"], w["place"])})
    gm = load("people/gm.json")
    if gm:
        for s in gm["songs"]:
            out.append({"k": "George Michael", "t": s["title"], "s": short("%s · %s" % (s["year"], s["album"])), "u": "people.html#gm/" + s["id"],
                        "x": flat(s["title"], s["album"], s["story"], s["about"], s.get("mood", []))})

    for f in ("en_work", "en_life", "en_spoken", "es_yard"):
        d = load("speak/%s.json" % f)
        for pk in (d or {}).get("packs", []):
            ls = pk.get("dialog", []) + pk.get("phrases", [])
            out.append({"k": "开口说·" + pk["group"], "t": pk["icon"] + " " + pk["name"], "s": short(pk["intro"]), "u": "speak.html#" + pk["id"],
                        "x": flat(pk["name"], pk["intro"], [l["t"] + " " + l["zh"] + " " + l.get("note", "") for l in ls], limit=4000)})

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"items": out}, f, ensure_ascii=False, separators=(",", ":"))
    print("%d 条 → %s (%d KB)" % (len(out), OUT, os.path.getsize(OUT) // 1024))


if __name__ == "__main__":
    main()
