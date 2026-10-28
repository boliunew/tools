#!/usr/bin/env python3
"""湾区高速公路路线图 → bay/roads.json（sf.html / sj.html 的「湾区路况」用）

从 OpenStreetMap（Overpass API）取湾区所有带编号的高速（motorway / trunk），按路线编号分组、简化坐标。
线路很少变，每月重跑一次。只用标准库。  python3 scripts/build_bay_roads.py
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "bay", "roads.json")
UA = "boliunew-tools-bayroads/1.0 (https://github.com/boliunew/tools)"
BBOX = (36.95, -122.85, 38.35, -121.55)  # 南, 西, 北, 东
EPS = 0.00025  # 简化容差（度，约 25 米）
SERVERS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
           "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
ZH = {  # 主要路线的中文说明
    "I-80": "旧金山 ⇄ 海湾大桥 ⇄ 伯克利 ⇄ 萨克拉门托", "I-280": "旧金山 ⇄ 半岛山边 ⇄ 圣何塞（号称最美高速）", "I-380": "SFO 机场旁的连接线",
    "I-580": "里士满大桥 ⇄ 奥克兰 ⇄ 都柏林 ⇄ I-5", "I-680": "圣何塞 ⇄ 弗里蒙特 ⇄ 核桃溪 ⇄ 本尼西亚", "I-880": "奥克兰港 ⇄ 东湾 ⇄ 圣何塞（货车最多）",
    "I-238": "I-580 和 I-880 之间的短连接", "I-780": "本尼西亚 ⇄ 瓦列霍", "I-505": "",
    "US-101": "旧金山 ⇄ 半岛 ⇄ 硅谷 ⇄ 圣何塞；北接金门大桥",
    "SR-1": "海岸公路", "SR-4": "康科德 ⇄ 安提阿", "SR-13": "奥克兰山边", "SR-17": "圣何塞 ⇄ 圣克鲁兹（山路急弯）", "SR-24": "奥克兰 ⇄ Caldecott 隧道 ⇄ 核桃溪",
    "SR-37": "北湾湿地", "SR-84": "邓巴顿大桥 ⇄ 弗里蒙特", "SR-85": "山景城 ⇄ 南圣何塞", "SR-87": "圣何塞市中心 ⇄ 机场", "SR-92": "圣马特奥大桥 ⇄ 半月湾",
    "SR-237": "山景城 ⇄ 米尔皮塔斯", "SR-262": "Mission Blvd 连接线", "SR-29": "纳帕", "SR-12": "", "SR-121": "", "SR-680": "",
}


def norm(ref):
    out = []
    for r in re.split(r"[;,/]", ref):
        r = r.strip().upper().replace("  ", " ")
        m = re.match(r"^(I|US|CA|SR)[\s-]*(\d+)\w?$", r)
        if not m:
            continue
        k = {"I": "I", "US": "US", "CA": "SR", "SR": "SR"}[m.group(1)]
        out.append("%s-%s" % (k, m.group(2)))
    return out


def simplify(pts, eps):
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]
        bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        L = (dx * dx + dy * dy) or 1e-18
        best, bi = -1, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
            d = (ax + t * dx - px) ** 2 + (ay + t * dy - py) ** 2
            if d > best:
                best, bi = d, i
        if best > eps * eps:
            keep[bi] = True
            stack += [(a, bi), (bi, b)]
    return [p for p, k in zip(pts, keep) if k]


def fetch():
    q = '[out:json][timeout:180];(way["highway"~"^(motorway|trunk)$"]["ref"](%s,%s,%s,%s););out geom tags;' % BBOX
    body = urllib.parse.urlencode({"data": q}).encode()
    for url in SERVERS:
        for i in range(2):
            try:
                req = urllib.request.Request(url, data=body, headers={"User-Agent": UA, "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=240) as r:
                    return json.loads(r.read())
            except Exception as e:
                print("  ✗", url, e, flush=True)
                time.sleep(10)
    raise SystemExit("Overpass 都连不上")


def main():
    d = fetch()
    by = {}
    for w in d.get("elements", []):
        g = w.get("geometry")
        refs = norm(w.get("tags", {}).get("ref", ""))
        if not g or not refs:
            continue
        pts = simplify([(p["lat"], p["lon"]) for p in g], EPS)
        line = [[round(a, 4), round(b, 4)] for a, b in pts]
        for k in refs:
            by.setdefault(k, {"hw": w["tags"].get("highway"), "seg": []})["seg"].append(line)
    # 合并首尾相接的小段，减少线条数
    for k, o in by.items():
        segs = o["seg"]
        merged = True
        while merged:
            merged = False
            ends = {}
            for i, s in enumerate(segs):
                ends.setdefault(tuple(s[0]), []).append(i)
            for i, s in enumerate(segs):
                if s is None:
                    continue
                nxt = [j for j in ends.get(tuple(s[-1]), []) if j != i and segs[j] is not None]
                if len(nxt) == 1:
                    j = nxt[0]
                    segs[i] = s + segs[j][1:]
                    segs[j] = None
                    merged = True
            segs = [s for s in segs if s]
        o["seg"] = segs
    routes = []
    for k, o in sorted(by.items(), key=lambda kv: ({"I": 0, "US": 1, "SR": 2}[kv[0].split("-")[0]], int(kv[0].split("-")[1]))):
        n = sum(len(s) for s in o["seg"])
        if k.startswith("SR") and n < 12 and k not in ZH:
            continue  # 很短的州道小段不画
        routes.append({"r": k, "zh": ZH.get(k, ""), "seg": o["seg"]})
    out = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "src": "© OpenStreetMap contributors (ODbL)", "routes": routes}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("bay/roads.json：%d 条路线 · %d 段 · %d KB" % (len(routes), sum(len(r["seg"]) for r in routes), os.path.getsize(OUT) // 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
