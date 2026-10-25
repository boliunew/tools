#!/usr/bin/env python3
"""电影 / 音乐 Top 500 排行榜（按国家分类）→ 生成知识库文章 kb/top500-movies.md、kb/top500-music.md。

每周由 .github/workflows/rankings.yml 自动跑一次（家里主机：selfhost/run-job.sh rankings）。只用标准库。

电影：IMDb 官方公开数据集（datasets.imdbws.com，每天更新）里所有 ≥ 25,000 人评分的电影，
      按「加权评分」排名（和 IMDb Top 250 同一个公式：票少的片子会被拉向平均分），取前 500。
      国家（出品国）和中文片名来自 Wikidata（按 IMDb 编号精确匹配）。
音乐：Apple Music 在 25 个国家/地区的「最多播放」歌曲榜（每个前 100），
      按「上了几个国家的榜、排第几」合并成全球热度前 500。
      歌手所属国家来自 Wikidata（按 Apple Music 歌手编号精确匹配）；查不到的按它排名最高的那个地区的榜单归类，标「≈」。

  python rankings/build.py            两个都做
  python rankings/build.py movies     只做电影
  python rankings/build.py music      只做音乐
"""
import datetime as dt
import gzip
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
KB = os.path.join(ROOT, "kb")
DATA = os.path.join(HERE, "data")
UA = "boliunew-tools-rankings/1.0 (https://github.com/boliunew/tools)"
TOP = 500
MIN_GROUP = 3            # 少于这么多条的国家并进「其他国家和地区」

# ISO 3166-1 alpha-2 → (中文名, 旗帜)；没列到的用 Wikidata 的中文名
CC = {
    "US": "美国", "GB": "英国", "FR": "法国", "DE": "德国", "IT": "意大利", "ES": "西班牙", "JP": "日本",
    "KR": "韩国", "CN": "中国大陆", "HK": "中国香港", "TW": "中国台湾", "IN": "印度", "CA": "加拿大",
    "AU": "澳大利亚", "NZ": "新西兰", "IE": "爱尔兰", "SE": "瑞典", "DK": "丹麦", "NO": "挪威", "FI": "芬兰",
    "RU": "俄罗斯", "SU": "苏联", "PL": "波兰", "BR": "巴西", "MX": "墨西哥", "AR": "阿根廷", "IR": "伊朗",
    "TR": "土耳其", "BE": "比利时", "NL": "荷兰", "AT": "奥地利", "CH": "瑞士", "CZ": "捷克", "HU": "匈牙利",
    "PT": "葡萄牙", "GR": "希腊", "IL": "以色列", "LB": "黎巴嫩", "EG": "埃及", "ZA": "南非", "NG": "尼日利亚",
    "TH": "泰国", "ID": "印度尼西亚", "PH": "菲律宾", "SG": "新加坡", "MY": "马来西亚", "VN": "越南",
    "CO": "哥伦比亚", "CL": "智利", "PE": "秘鲁", "PR": "波多黎各", "JM": "牙买加", "UA": "乌克兰",
    "RO": "罗马尼亚", "RS": "塞尔维亚", "IS": "冰岛", "PK": "巴基斯坦", "BD": "孟加拉国", "AE": "阿联酋",
    "SA": "沙特阿拉伯", "MA": "摩洛哥", "TN": "突尼斯", "DZ": "阿尔及利亚", "CU": "古巴", "VE": "委内瑞拉",
    "PA": "巴拿马", "DO": "多米尼加", "YU": "南斯拉夫", "CS": "捷克斯洛伐克", "DD": "东德", "BG": "保加利亚",
    "HR": "克罗地亚", "BA": "波黑", "GE": "格鲁吉亚", "AM": "亚美尼亚", "KZ": "哈萨克斯坦", "EE": "爱沙尼亚",
    "LV": "拉脱维亚", "LT": "立陶宛", "SK": "斯洛伐克", "SI": "斯洛文尼亚", "LU": "卢森堡", "MN": "蒙古",
}
# Wikidata 里没有 ISO 代码的历史国家
QID_CC = {"Q15180": "SU", "Q83286": "YU", "Q33946": "CS", "Q16957": "DD", "Q713750": "DE"}  # Q713750 = 西德


def flag(cc):
    if not cc or len(cc) != 2 or not cc.isalpha() or cc in ("SU", "YU", "CS", "DD"):
        return "❓" if cc == "??" else "🏳️"
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in cc.upper())


def get(url, data=None, headers=None, tries=4, timeout=120):
    h = {"User-Agent": UA}
    h.update(headers or {})
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            if i == tries - 1:
                raise
            print("  retry %s (%s)" % (url[:80], e), flush=True)
            time.sleep(5 * (i + 1))


def sparql(query):
    body = urllib.parse.urlencode({"query": query}).encode()
    raw = get("https://query.wikidata.org/sparql", data=body,
              headers={"Accept": "application/sparql-results+json", "Content-Type": "application/x-www-form-urlencoded"})
    return json.loads(raw)["results"]["bindings"]


ZH_PREF = {"zh-cn": 0, "zh-hans": 1, "zh-sg": 2, "zh-my": 2, "zh": 3, "zh-tw": 4, "zh-hk": 5}


def wd_countries(rows_by_key, key_prop, key_values, country_props):
    """{key: {"zh": 中文名, "cs": [(cc, 中文国名), ...]}} via Wikidata. country_props: 依次尝试的属性。"""
    out = {}
    for i in range(0, len(key_values), 150):
        chunk = key_values[i:i + 150]
        vals = " ".join('"%s"' % v.replace('"', "") for v in chunk)
        cps = " UNION ".join("{ ?item wdt:%s ?c . BIND(%d AS ?pri) }" % (p, n) for n, p in enumerate(country_props))
        q = """SELECT ?k ?zh ?c ?iso ?cl ?pri WHERE {
  VALUES ?k { %s }
  ?item wdt:%s ?k .
  OPTIONAL { ?item rdfs:label ?zh . FILTER(LANG(?zh) IN ("zh-cn","zh-hans","zh-sg","zh-my","zh","zh-tw","zh-hk")) }
  OPTIONAL { %s
    OPTIONAL { ?c wdt:P297 ?iso }
    OPTIONAL { ?c rdfs:label ?cl . FILTER(LANG(?cl) IN ("zh-cn","zh-hans","zh")) } }
}""" % (vals, key_prop, cps)
        for b in sparql(q):
            k = b["k"]["value"]
            o = out.setdefault(k, {"zh": None, "zr": 9, "cs": {}})
            if b.get("zh"):
                r = ZH_PREF.get(b["zh"].get("xml:lang", "zh"), 5)
                if r < o["zr"]:
                    o["zh"], o["zr"] = b["zh"]["value"], r
            if b.get("c"):
                qid = b["c"]["value"].rsplit("/", 1)[-1]
                cc = (b.get("iso") or {}).get("value") or QID_CC.get(qid) or qid
                pri = int(b["pri"]["value"])
                name = CC.get(cc) or (b.get("cl") or {}).get("value") or cc
                if cc not in o["cs"] or o["cs"][cc][0] > pri:
                    o["cs"][cc] = (pri, name)
        time.sleep(1)
    for o in out.values():   # only the highest-priority property's countries
        if o["cs"]:
            best = min(p for p, _ in o["cs"].values())
            o["cs"] = [(cc, n) for cc, (p, n) in o["cs"].items() if p == best]
        else:
            o["cs"] = []
    return out


def cc_order(ccs):
    """co-productions: put the 'main' country first (a fixed preference order works better than Wikidata's random order)."""
    pref = ["US", "GB", "FR", "JP", "KR", "CN", "HK", "TW", "IN", "IT", "ES", "DE", "SU", "RU", "SE", "DK", "BR", "MX", "IR"]
    return sorted(ccs, key=lambda c: (pref.index(c[0]) if c[0] in pref else 99, c[0]))


def yt(q):
    """YouTube 搜索链接（不用 API，点开就是搜索结果，第一个一般就是官方 MV / 预告片）"""
    import re
    import urllib.parse
    return "[▶️](https://www.youtube.com/results?search_query=%s)" % urllib.parse.quote_plus(re.sub(r"\s+", " ", q).strip())


def cp(text):
    """📋 复制按钮（知识库页面把 copy: 链接显示成一点就复制的按钮）"""
    import urllib.parse
    return "[📋](copy:%s)" % urllib.parse.quote(str(text).strip(), safe="")


def esc(s):
    s = str(s or "").replace("|", "／").replace("\n", " ").replace("[", "(").replace("]", ")").replace("*", "＊").replace("`", "'")
    return s.replace("__", "_ _").strip()


def group_md(items, row, head, align):
    """Country sections. items need .cc / .cname; returns (summary table lines, section lines)."""
    groups = {}
    for it in items:
        groups.setdefault(it["cc"], []).append(it)
    big = sorted([g for g in groups.values() if len(g) >= MIN_GROUP], key=lambda g: (-len(g), g[0]["rank"]))
    small = sorted([it for g in groups.values() if len(g) < MIN_GROUP for it in g], key=lambda x: x["rank"])
    summ = ["| 国家/地区 | 数量 | 最高排名 |", "|---|---:|---|"]
    sec = []
    for g in big:
        cc, name = g[0]["cc"], g[0]["cname"]
        summ.append("| %s %s | %d | #%d %s |" % (flag(cc), name, len(g), g[0]["rank"], esc(g[0]["short"])))
        sec += ["", "## %s %s（%d）" % (flag(cc), name, len(g)), "", head, align] + [row(it) for it in g]
    if small:
        names = []
        for it in small:
            if it["cname"] not in names:
                names.append(it["cname"])
        summ.append("| 🌐 其他 %d 个国家和地区 | %d | #%d %s |" % (len(names), len(small), small[0]["rank"], esc(small[0]["short"])))
        sec += ["", "## 🌐 其他国家和地区（%d）" % len(small), "", "包括：" + "、".join(names) + "。", "", head, align] + [row(it) for it in small]
    return summ, sec


# ------------------------------------------------------------------ movies
def movies():
    print("电影：下载 IMDb 评分数据…", flush=True)
    ratings = {}
    with gzip.open(io.BytesIO(get("https://datasets.imdbws.com/title.ratings.tsv.gz")), "rt", encoding="utf-8") as f:
        next(f)
        for ln in f:
            t, r, v = ln.rstrip("\n").split("\t")
            v = int(v)
            if v >= 25000:
                ratings[t] = (float(r), v)
    print("  %d 部作品 ≥ 25000 票；下载片名数据（约 200MB，流式读取）…" % len(ratings), flush=True)
    films = {}
    req = urllib.request.Request("https://datasets.imdbws.com/title.basics.tsv.gz", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=600) as resp, gzip.open(resp, "rt", encoding="utf-8") as f:
        next(f)
        for ln in f:
            t = ln[:ln.index("\t")]
            if t not in ratings:
                continue
            p = ln.rstrip("\n").split("\t")
            # tconst titleType primaryTitle originalTitle isAdult startYear endYear runtimeMinutes genres
            if p[1] != "movie" or p[4] == "1":
                continue
            films[t] = {"id": t, "title": p[2], "orig": p[3], "year": p[5] if p[5] != "\\N" else "",
                        "genres": p[8] if p[8] != "\\N" else "", "rating": ratings[t][0], "votes": ratings[t][1]}
    if len(films) < 1000:
        raise SystemExit("IMDb 数据异常：只有 %d 部电影" % len(films))
    m = 25000
    C = sum(x["rating"] for x in films.values()) / len(films)
    for x in films.values():
        v, R = x["votes"], x["rating"]
        x["wr"] = v / (v + m) * R + m / (v + m) * C
    top = sorted(films.values(), key=lambda x: (-x["wr"], -x["votes"]))[:TOP]
    for i, x in enumerate(top):
        x["rank"] = i + 1
    print("  %d 部电影入池，平均分 %.2f；查 Wikidata 出品国 + 中文名…" % (len(films), C), flush=True)

    wd = wd_countries(None, "P345", [x["id"] for x in top], ["P495"])
    miss = 0
    for x in top:
        w = wd.get(x["id"]) or {"zh": None, "cs": []}
        cs = cc_order(w["cs"])
        x["zh"] = w["zh"] if w["zh"] and w["zh"] not in (x["title"], x["orig"]) else ""
        x["countries"] = cs
        if cs:
            x["cc"], x["cname"] = cs[0]
        else:
            x["cc"], x["cname"], miss = "??", "未知", miss + 1
        x["short"] = x["zh"] or x["title"]

    def row(x):
        co = "、".join(n for _, n in x["countries"][1:4])
        sub = " · ".join(p for p in (esc(x["title"]) if x["zh"] else "", ("合拍：" + co) if co else "") if p)
        return "| %d | [**%s**](https://www.imdb.com/title/%s/)%s | %s | %.1f | %s | %s |" % (
            x["rank"], esc(x["zh"] or x["title"]), x["id"], (" · " + sub) if sub else "", x["year"], x["rating"], wan(x["votes"]),
            yt("%s %s trailer" % (x["title"], x["year"])) + " " + cp(x["zh"] or x["title"]))

    summ, sec = group_md(top, row, "| # | 片名 | 年份 | 评分 | 人数 | 预告片 · 复制 |", "|---:|---|---|---:|---:|:---:|")
    today = dt.date.today().isoformat()
    top10 = ["| # | 片名 | 国家 | 年份 | 评分 | 预告片 · 复制 |", "|---:|---|---|---|---:|:---:|"] + [
        "| %d | [%s](https://www.imdb.com/title/%s/) | %s %s | %s | %.1f | %s |" % (x["rank"], esc(x["short"]), x["id"], flag(x["cc"]), x["cname"], x["year"], x["rating"],
                                                                          yt("%s %s trailer" % (x["title"], x["year"])) + " " + cp(x["zh"] or x["title"])) for x in top[:20]]
    L = ["---", "title: 电影 Top 500（按国家分类）", "tags: [电影, 排行榜]",
         "summary: IMDb 评分人数 ≥ 2.5 万的电影按加权评分取前 500，按出品国分组；每周自动更新。", "---", "",
         "# 🎬 电影 Top 500（按国家分类）", "",
         "> 自动生成，最近更新：**%s**。每周一自动重算一次，评分和名次会随 IMDb 数据变化。" % today, "",
         "**怎么排的**：从 IMDb 官方公开数据里，挑出评分人数 ≥ 25,000 的全部电影（%s 部），按和 IMDb Top 250 相同的**加权评分**排序："
         "评分人数越少，分数越会被拉向平均分（%.1f），避免小众片靠少量高分冲榜。国家是 Wikidata 里的**出品国**，"
         "多国合拍的放在主要出品国下，备注里写合拍国。中文片名来自 Wikidata，没有的显示英文名。" % ("{:,}".format(len(films)), C), "",
         "## 各国数量", ""] + summ + ["", "## 总榜前 20", ""] + top10 + sec + [
         "", "---", "", "数据：[IMDb Non-Commercial Datasets](https://developer.imdb.com/non-commercial-datasets/)（个人非商业使用）、"
         "[Wikidata](https://www.wikidata.org/)（CC0）。生成脚本：`rankings/build.py`。" + (" 有 %d 部没查到出品国，归在「未知」。" % miss if miss else ""), ""]
    with open(os.path.join(KB, "top500-movies.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    save("movies", top)
    print("  ✓ kb/top500-movies.md（%d 部，%d 部没查到国家）" % (len(top), miss), flush=True)


# ------------------------------------------------------------------ music
STORES = ["us", "gb", "ca", "au", "de", "fr", "es", "it", "nl", "se", "br", "mx", "ar", "co",
          "jp", "kr", "tw", "hk", "cn", "in", "id", "th", "ph", "tr", "za"]


def norm(name, artist):
    import re
    n = re.sub(r"\s*[\(\[（【].*?(feat|ft\.|with|remix).*?[\)\]）】]", "", name, flags=re.I)
    return re.sub(r"\W+", "", n.lower()) + "|" + re.sub(r"\W+", "", artist.lower().split(",")[0].split("&")[0])


def music():
    print("音乐：拉 Apple Music %d 个地区的最多播放榜…" % len(STORES), flush=True)
    songs, got, alias = {}, [], {}
    for cc in STORES:
        try:
            d = json.loads(get("https://rss.applemarketingtools.com/api/v2/%s/music/most-played/100/songs.json" % cc, tries=3))
            res = d["feed"]["results"]
        except Exception as e:
            print("  %s 失败：%s" % (cc, e), flush=True)
            continue
        got.append(cc)
        for i, r in enumerate(res):
            key = alias.setdefault(norm(r.get("name", ""), r.get("artistName", "")), r["id"])
            s = songs.setdefault(key, {"id": r["id"], "name": r.get("name", ""), "artist": r.get("artistName", ""),
                                           "aid": r.get("artistId", ""), "url": r.get("url", ""),
                                           "date": (r.get("releaseDate") or "")[:4], "charts": {}})
            if cc.upper() not in s["charts"]:
                s["charts"][cc.upper()] = i + 1
        time.sleep(0.5)
    if len(got) < 10:
        raise SystemExit("Apple Music 榜单只拿到 %d 个地区，放弃本次更新" % len(got))
    for s in songs.values():   # 每上一个榜得 (101-名次)/100 分，最多 1 分
        s["score"] = sum((101 - r) / 100 for r in s["charts"].values())
        s["best"] = min(s["charts"].items(), key=lambda kv: kv[1])
    top = sorted(songs.values(), key=lambda s: (-s["score"], s["best"][1]))[:TOP]
    for i, s in enumerate(top):
        s["rank"] = i + 1
    print("  %d 首不同的歌，取前 %d；查 Wikidata 歌手国家…" % (len(songs), len(top)), flush=True)

    aids = sorted({s["aid"] for s in top if s["aid"]})
    # 个人：国籍 P27；乐队：成立地所在国 P495 / P17 不常有，先 P27，再 P495，再 P17
    wd = wd_countries(None, "P2850", aids, ["P27", "P495", "P17"])
    guess = 0
    for s in top:
        w = wd.get(s["aid"]) or {"cs": []}
        cs = cc_order(w["cs"])
        if cs:
            s["cc"], s["cname"], s["approx"] = cs[0][0], cs[0][1], False
        else:
            cc = s["best"][0]
            s["cc"], s["cname"], s["approx"] = cc, CC.get(cc, cc), True
            guess += 1
        s["short"] = "%s — %s" % (s["name"], s["artist"])

    def row(s):
        ch = sorted(s["charts"].items(), key=lambda kv: kv[1])
        where = " ".join("%s%d" % (flag(c), r) for c, r in ch[:3])
        return "| %d | [**%s**](%s) · %s%s | %d | %s | %s |" % (
            s["rank"], esc(s["name"]), s["url"], esc(s["artist"]), " ≈" if s["approx"] else "", len(ch), where, yt("%s %s" % (s["name"], s["artist"])) + " " + cp("%s %s" % (s["name"], s["artist"])))

    summ, sec = group_md(top, row, "| # | 歌曲 · 歌手 | 上榜 | 最好名次 | YouTube · 复制 |", "|---:|---|---:|---|:---:|")
    today = dt.date.today().isoformat()
    top20 = ["| # | 歌曲 · 歌手 | 国家 | 上榜 | YouTube · 复制 |", "|---:|---|---|---:|:---:|"] + [
        "| %d | [**%s**](%s) · %s | %s %s%s | %d | %s |" % (s["rank"], esc(s["name"]), s["url"], esc(s["artist"]), flag(s["cc"]), s["cname"], "≈" if s["approx"] else "",
                                                       len(s["charts"]), yt("%s %s" % (s["name"], s["artist"])) + " " + cp("%s %s" % (s["name"], s["artist"]))) for s in top[:20]]
    region_names = "、".join(flag(c.upper()) + CC.get(c.upper(), c) for c in got)
    L = ["---", "title: 音乐 Top 500（按国家分类）", "tags: [音乐, 排行榜]",
         "summary: Apple Music 25 个国家和地区的最多播放榜合并成全球热歌前 500，按歌手国家分组；每周自动更新。", "---", "",
         "# 🎵 音乐 Top 500（按国家分类）", "",
         "> 自动生成，最近更新：**%s**。这是**当下的热歌榜**，每周一自动更新，名单会随流行变化。" % today, "",
         "**怎么排的**：取 Apple Music 在 %d 个国家和地区的「最多播放」歌曲榜（每个前 100 名，共 %s 首不同的歌），"
         "每上一个地区的榜得 0.01–1 分（第 1 名 1 分，第 100 名 0.01 分），加起来排出全球前 500。"
         "国家是**歌手**所属国（来自 Wikidata；乐队用所属国）。查不到的按它排名最高的那个地区归类，标「≈」。" % (len(got), "{:,}".format(len(songs))), "",
         "「上榜」= 上了几个地区的榜；「最好名次」列出排得最高的 3 个地区，🇯🇵3 = 在日本榜排第 3。", "",
         "统计的地区：" + region_names + "。", "",
         "## 各国数量", ""] + summ + ["", "## 总榜前 20", ""] + top20 + sec + [
         "", "---", "", "数据：[Apple Music RSS 榜单](https://rss.marketingtools.apple.com/)、[Wikidata](https://www.wikidata.org/)（CC0）。"
         "生成脚本：`rankings/build.py`。本次有 %d 首按榜单地区推断国家（≈）。" % guess, ""]
    with open(os.path.join(KB, "top500-music.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    save("music", top)
    print("  ✓ kb/top500-music.md（%d 首，%d 首按榜单推断国家）" % (len(top), guess), flush=True)


def wan(v):
    return "%.0f万" % (v / 1e4) if v >= 1e5 else "%.1f万" % (v / 1e4)


def save(kind, items):
    """JSON copy (for other tools / history). Keeps one file per week."""
    os.makedirs(DATA, exist_ok=True)
    keep = ("rank", "id", "zh", "title", "year", "rating", "votes", "name", "artist", "cc", "cname", "score", "charts", "approx")
    rows = [{k: it[k] for k in keep if k in it} for it in items]
    with open(os.path.join(DATA, "%s.json" % kind), "w", encoding="utf-8") as f:
        json.dump({"updated": dt.date.today().isoformat(), "items": rows}, f, ensure_ascii=False, separators=(",", ":"))


def main():
    what = sys.argv[1:] or ["movies", "music"]
    err = 0
    for w in what:
        try:
            {"movies": movies, "music": music}[w]()
        except SystemExit as e:
            print("✗ %s：%s" % (w, e), flush=True)
            err = 1
        except Exception:
            import traceback
            traceback.print_exc()
            err = 1
    return err


if __name__ == "__main__":
    sys.exit(main())
