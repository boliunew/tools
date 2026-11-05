"""📺 网络电视的台单：每天从 iptv-org 拿全部免费公开的电视直播，逐个连一遍，按国家分文件存好。

    python tv/build.py                 # 下载最新台单 + 检查每个地址
    python tv/build.py --src DIR       # 用本地的 iptv-org/api 数据（调试用）
    python tv/build.py --no-check      # 不检查，只整理

数据来源：https://github.com/iptv-org/iptv （只收公开免费播出的台）。这里再去掉成人台、停播的台和被要求下架的台。
输出：
    tv/data/index.json        国家列表、类别、总数、检查时间
    tv/data/c/<国家>.json      这个国家的台：名字、台标、类别、所有地址（能不能连、多快）
    tv/data/all.json          全球搜索用：台名 + 国家
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict

API = "https://iptv-org.github.io/api/"
FALLBACK = "https://raw.githubusercontent.com/iptv-org/api/gh-pages/"
FILES = ["channels", "streams", "logos", "categories", "blocklist"]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
ORIGIN = "https://boliunew.github.io"
NO_COUNTRY = "ZZ"   # 目录里没标国家的台
# 给家人用：除了 iptv-org 标出的成人台，台名带这些字眼的也不收（成人动画、裸露真人秀之类）
NOT_FAMILY = re.compile(r"\b(sexy|sex|naked|nude|nudity|xxx|porn\w*|erotic\w*|playboy|hustler|babes|nsfw|fetish|hentai|"
                        r"adult\s+(animation|swim|tv|channel|movies?|films?|xxx)|for\s+adults)\b|18\s*\+|成人|情色|色情", re.I)


def family_ok(*names):
    return not any(n and NOT_FAMILY.search(n) for n in names)


def load(src):
    out = {}
    for name in FILES:
        if src:
            with open(os.path.join(src, name + ".json"), encoding="utf-8") as f:
                out[name] = json.load(f)
            continue
        last = None
        for base in (API, FALLBACK):
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(urllib.request.Request(base + name + ".json", headers={"User-Agent": UA}), timeout=60) as r:
                        out[name] = json.loads(r.read().decode("utf-8"))
                    break
                except Exception as e:  # noqa: BLE001
                    last = e
                    time.sleep(3 * (attempt + 1))
            if name in out:
                break
        if name not in out:
            sys.exit(f"下载 {name}.json 失败：{last}")
    return out


CTX = ssl.create_default_context()


def check(url):
    """连一下：能不能拿到内容、多快（毫秒）、浏览器跨站能不能读（CORS）。"""
    t0 = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Origin": ORIGIN, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=8, context=CTX) as r:
            head = r.read(4096)
            ms = int((time.monotonic() - t0) * 1000)
            acao = r.headers.get("Access-Control-Allow-Origin") or ""
            ok = 200 <= r.status < 300
            if ok and (".m3u8" in url or b"#EXT" in head[:64]):
                ok = b"#EXTM3U" in head[:1024] or b"#EXT-X" in head
            if ok and ".mpd" in url:
                ok = b"<MPD" in head or b"<?xml" in head[:64]
            return {"ok": ok, "ms": ms if ok else -1, "cors": acao in ("*", ORIGIN)}
    except Exception:  # noqa: BLE001
        return {"ok": False, "ms": -1, "cors": False}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src")
    ap.add_argument("--no-check", action="store_true")
    ap.add_argument("--workers", type=int, default=96)
    ap.add_argument("--budget", type=int, default=25 * 60, help="检查最多花几秒")
    a = ap.parse_args()

    d = load(a.src)
    today = dt.date.today().isoformat()
    blocked = {b["channel"] for b in d["blocklist"]}
    chans = {}
    for c in d["channels"]:
        if c["id"] in blocked or c.get("is_nsfw") or "xxx" in (c.get("categories") or []):
            continue
        if not family_ok(c.get("name"), *(c.get("alt_names") or [])):
            continue
        if c.get("closed") and c["closed"] <= today:
            continue
        chans[c["id"]] = c

    logos = {}
    for lg in d["logos"]:   # 每个台挑一个台标：主台、在用、PNG/JPG、大一点的
        cid = lg.get("channel")
        if cid not in chans or not str(lg.get("url", "")).startswith("https://"):
            continue
        score = (lg.get("feed") is None, bool(lg.get("in_use", True)), lg.get("format") in ("PNG", "JPEG", "SVG", "WebP"),
                 min(lg.get("width") or 0, 512))
        if cid not in logos or score > logos[cid][0]:
            logos[cid] = (score, lg["url"])

    groups = defaultdict(list)   # 台 id（或没登记的台名）→ 地址
    meta = {}
    for s in d["streams"]:
        url = (s.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        cid = s.get("channel")
        if cid:
            if cid not in chans:
                continue   # 成人台、停播台、被下架的台
            key = cid
            if key not in meta:
                c = chans[cid]
                meta[key] = {"i": cid, "n": c["name"], "cc": (c.get("country") or NO_COUNTRY).upper(),
                             "c": [x for x in (c.get("categories") or []) if x != "xxx"], "l": logos.get(cid, (0, ""))[1],
                             "a": (c.get("alt_names") or [])[:3]}
        else:
            if not family_ok(s.get("title")):
                continue
            title = re.sub(r"\s*\((\d{3,4}p|\w+ \d+)\)\s*$", "", s.get("title") or "").strip() or url
            key = "t:" + title.lower()
            meta.setdefault(key, {"i": "", "n": title, "cc": NO_COUNTRY, "c": [], "l": "", "a": []})
        flags = ""
        if url.startswith("http://"):
            flags += "h"                       # 只有 http：网页里放不了，App 里可以
        labels = s.get("labels") or []
        if "Geo-blocked" in labels:
            flags += "g"                       # 只限本国
        if "Not 24/7" in labels:
            flags += "n"                       # 不是全天播
        if s.get("user_agent") or s.get("referrer"):
            flags += "r"                       # 要特殊请求头，浏览器给不了，多半放不了
        if ".mpd" in url.split("?")[0]:
            flags += "d"                       # DASH
        if any(x[0] == url for x in groups[key]):
            continue
        groups[key].append([url, s.get("quality") or "", flags, None])

    urls = sorted({x[0] for v in groups.values() for x in v})
    results, checked_at = {}, None
    if not a.no_check:
        t0 = time.monotonic()
        with cf.ThreadPoolExecutor(a.workers) as ex:
            futs = {ex.submit(check, u): u for u in urls}
            try:
                for n, f in enumerate(cf.as_completed(futs, timeout=a.budget), 1):
                    results[futs[f]] = f.result()
                    if n % 1000 == 0:
                        print(f"  检查了 {n}/{len(urls)}  {int(time.monotonic() - t0)}s", flush=True)
            except cf.TimeoutError:
                print(f"  ⏱ 时间到，检查了 {len(results)}/{len(urls)}", flush=True)
                for f in futs:
                    f.cancel()
        checked_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        for v in groups.values():
            for x in v:
                r = results.get(x[0])
                if r:
                    x[3] = r["ms"]
                    if r["ok"] and r["cors"]:
                        x[2] += "c"            # 网页里用 hls.js 也能放

    def stream_key(x):
        ms = x[3]
        q = int(re.sub(r"\D", "", x[1]) or 0)
        return (ms is None or ms < 0, "h" in x[2], "r" in x[2], "g" in x[2], -q if ms is not None and ms >= 0 else 0, ms if ms and ms > 0 else 99999)

    def chan_rank(ch):
        best = ch["s"][0]
        good = best[3] is not None and best[3] >= 0
        return (not good, "h" in best[2] or "r" in best[2], best[3] if good else 99999, ch["n"].lower())

    by_cc = defaultdict(list)
    for key, v in groups.items():
        m = meta[key]
        v.sort(key=stream_key)
        ch = {"n": m["n"], "s": v}
        for k in ("i", "l", "c", "a"):
            if m[k]:
                ch[k] = m[k]
        by_cc[m["cc"]].append(ch)

    os.makedirs(os.path.join(OUT, "c"), exist_ok=True)
    for f in os.listdir(os.path.join(OUT, "c")):
        os.remove(os.path.join(OUT, "c", f))
    countries, cats, everything = [], Counter(), []
    for cc, lst in sorted(by_cc.items()):
        lst.sort(key=chan_rank)
        ok = sum(1 for ch in lst if ch["s"][0][3] is not None and ch["s"][0][3] >= 0)
        countries.append([cc, len(lst), ok])
        for i, ch in enumerate(lst):
            cats.update(ch.get("c") or [])
            everything.append([ch["n"], cc, i] + ([" / ".join(ch["a"])] if ch.get("a") else []))
        with open(os.path.join(OUT, "c", cc + ".json"), "w", encoding="utf-8") as f:
            json.dump({"cc": cc, "ch": lst}, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(OUT, "all.json"), "w", encoding="utf-8") as f:
        json.dump(everything, f, ensure_ascii=False, separators=(",", ":"))
    total_ok = sum(c[2] for c in countries)
    index = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "checked": checked_at,
             "channels": len(everything), "streams": len(urls), "ok": total_ok,
             "countries": sorted(countries, key=lambda c: -c[1]), "cats": cats.most_common(),
             "source": "https://github.com/iptv-org/iptv"}
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))
    print(f"📺 {len(everything)} 个台，{len(urls)} 个地址，{len(countries)} 个国家；检查能连上的台 {total_ok} 个")


if __name__ == "__main__":
    main()
