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
    fun = load("people/sushi_fun.json")
    for w in (fun or {}).get("items", []):
        out.append({"k": "苏轼趣闻", "t": w["title"], "s": short(w["why"]), "u": "people.html#sushi/" + w["id"],
                    "x": flat(w["title"], w["story"], w["src"], w["tags"], w["place"])})
    gf = load("people/gf.json")
    if gf:
        for q in gf["quotes"]:
            out.append({"k": "怪诞小镇", "t": q["zh"][:40], "s": short("%s · %s %s" % (q["who"], q["ep"], q["en"])), "u": "people.html#gf/q-%d" % q["n"], "x": flat(q["en"], q["zh"], q.get("deep", ""), q["who"])})
        for pp in gf["people"]:
            out.append({"k": "怪诞小镇", "t": pp["zh"], "s": short(pp["tag"] + " · " + pp["bio"]), "u": "people.html#gf/p-" + pp["id"], "x": flat(pp["zh"], pp["en"], pp["bio"], pp["why"])})
        for i, v in enumerate(gf["essays"]):
            out.append({"k": "怪诞小镇", "t": v["t"], "s": short(v["lead"] + v["body"][0]), "u": "people.html#gf/v-%d" % i, "x": flat(v["t"], *v["body"])})
        for e in gf["episodes"]:
            out.append({"k": "怪诞小镇", "t": "%s %s" % (e["code"], e["zh"]), "s": short(e["title"] + " · " + e["note"]), "u": "people.html#gf/e-" + e["code"], "x": flat(e["title"], e["zh"], e["note"], *[c["dec"] for c in e["ci"]])})
    poi = load("people/poi.json")
    if poi:
        for q in poi["quotes"]:
            out.append({"k": "疑犯追踪", "t": q["zh"][:40], "s": short("%s · %s %s" % (q["who"], q["ep"], q["en"])), "u": "people.html#poi/q-%d" % q["n"],
                        "x": flat(q["en"], q["zh"], q["deep"], q["who"], q["title"])})
        for pp in poi["people"]:
            out.append({"k": "疑犯追踪", "t": pp["zh"], "s": short(pp["tag"] + " · " + pp["bio"]), "u": "people.html#poi/p-" + pp["id"], "x": flat(pp["zh"], pp["en"], pp["bio"], pp["why"], pp["actor"])})
        for i, v in enumerate(poi["values"]):
            out.append({"k": "疑犯追踪", "t": v["t"], "s": short(v["show"]), "u": "people.html#poi/v-%d" % i, "x": flat(v["t"], v["show"], v["us"], v["ask"])})
    gm = load("people/gm.json")
    if gm:
        for s in gm["songs"]:
            out.append({"k": "George Michael", "t": s["title"], "s": short("%s · %s" % (s["year"], s["album"])), "u": "people.html#gm/" + s["id"],
                        "x": flat(s["title"], s["album"], s["story"], s["about"], s.get("mood", []))})

    asi = load("people/asimov.json")
    if asi:
        for bk in asi["books"]:
            out.append({"k": "阿西莫夫", "t": bk["title"] + " " + bk["zh"], "s": short("%s · %s" % (bk["year"], bk["hook"])), "u": "people.html#asimov/" + bk["id"],
                        "x": flat(bk["title"], bk["zh"], bk["hook"], bk["about"], [v["w"] + " " + v["zh"] for v in bk["vocab"]])})
        for c in asi["concepts"]:
            out.append({"k": "阿西莫夫", "t": c["k"], "s": short(c["d"]), "u": "people.html#asimov", "x": flat(c["k"], c["en"], c["d"])})

    up = load("people/up.json")
    if up:
        for side, tag in (("uk", "人生七年 · 英国"), ("su", "人生七年 · 苏联")):
            for pp in up[side]["people"]:
                out.append({"k": tag, "t": pp["zh"] + " " + pp["name"], "s": short(pp["then"]), "u": "people.html#up/" + side + "-" + pp["id"],
                            "x": flat(pp["zh"], pp["name"], pp["from"], pp["seven"], pp["then"], [t[1] for t in pp["tl"]], pp["look"])})

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

    # 首页卡片上的数字（知识库几篇、技巧几条……）从这里读，不用手改
    def n(rel, *keys):
        d = load(rel)
        for k in keys:
            d = (d or {}).get(k)
        return len(d) if d else 0
    counts = {
        "kb": n("kb/index.json", "articles"), "tips": n("tips/tips.json", "items"),
        "recipes": sum(n("kitchen/%s.json" % f, "items") for f in ("recipes_cn", "recipes_cn2", "recipes_cn3", "recipes_west", "recipes_west2", "recipes_west3")),
        "dreams": n("dream/dreams.json", "items"), "psy": n("mind/psy.json", "items"),
        "sushi": n("people/sushi_a.json", "items") + n("people/sushi_b.json", "items"), "gm": n("people/gm.json", "songs"),
        "asimov": n("people/asimov.json", "books"), "cards": n("card/daily.json", "items"),
    }
    with open(os.path.join(ROOT, "search", "counts.json"), "w", encoding="utf-8") as f:
        json.dump(counts, f, separators=(",", ":"))
    print("counts", counts)


if __name__ == "__main__":
    main()
