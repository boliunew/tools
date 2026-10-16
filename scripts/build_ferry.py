#!/usr/bin/env python3
"""⛴️ 旧金山湾渡轮：航线 + 未来 14 天时刻表 → sf/ferry.json（sf.html 的交通图和渡轮时刻表用）

数据来源：各渡轮公司公开发布的 GTFS 时刻表数据（通过 Mobility Database 公开目录找到最新的下载地址）：
  · San Francisco Bay Ferry（WETA）：奥克兰、阿拉米达、列治文、瓦列霍、南旧金山……
  · Golden Gate Ferry：索萨利托、拉金斯珀、蒂伯龙……
每周由 .github/workflows/ferry.yml 重跑一次。只用标准库。

  python scripts/build_ferry.py
"""
import csv
import re
import datetime as dt
import io
import json
import os
import sys
import time
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "sf", "ferry.json")
UA = "boliunew-tools-ferry/1.0 (https://github.com/boliunew/tools)"
CATALOG = "https://share.mobilitydata.org/catalogs-csv"
DAYS = 14
DEBUG = []
WANT = [  # (keyword in provider/name, our label, default colour)
    ("bay ferry", "SF Bay Ferry", "#1F6FB2"),
    ("water emergency", "SF Bay Ferry", "#1F6FB2"),
    ("golden gate transit", "Golden Gate Ferry", "#C0362C"),
    ("golden gate ferry", "Golden Gate Ferry", "#C0362C"),
    ("alcatraz", "Alcatraz City Cruises", "#6B4F9E"),
]
ZH = [  # stop name keyword → 中文
    ("ferry building", "旧金山渡轮大厦"), ("san francisco-gate", "旧金山渡轮大厦"), ("pier 33", "旧金山 33 号码头（去恶魔岛）"), ("alcatraz", "恶魔岛"), ("pier 41", "旧金山 41 号码头（渔人码头）"), ("pier 39", "旧金山 39 号码头"), ("chase center", "大通中心（勇士队）"),
    ("oracle", "甲骨文球场（巨人队）"), ("jack london", "奥克兰 杰克伦敦广场"), ("oakland", "奥克兰"), ("main street", "阿拉米达 Main St"),
    ("seaplane", "阿拉米达 水上飞机湖"), ("harbor bay", "阿拉米达 港湾岛"), ("alameda", "阿拉米达"), ("richmond", "列治文"),
    ("mare island", "马雷岛"), ("vallejo", "瓦列霍"), ("south san francisco", "南旧金山（牡蛎角）"), ("oyster point", "南旧金山（牡蛎角）"),
    ("sausalito", "索萨利托"), ("larkspur", "拉金斯珀"), ("tiburon", "蒂伯龙"), ("angel island", "天使岛"), ("alcatraz", "恶魔岛"),
    ("treasure island", "金银岛"), ("redwood city", "红木城"), ("berkeley", "伯克利"),
]


def get(url, tries=3, timeout=120):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            if i == tries - 1:
                raise
            print("  retry", url[:90], e, flush=True)
            time.sleep(5 * (i + 1))


def zh_of(name):
    n = name.lower()
    for k, z in ZH:
        if k in n:
            return z
    return ""


def find_feeds():
    raw = get(CATALOG).decode("utf-8-sig", "replace")
    rows = list(csv.DictReader(io.StringIO(raw)))
    found = {}
    for r in rows:
        if (r.get("data_type") or "").lower() != "gtfs":
            continue
        if (r.get("location.country_code") or "").upper() not in ("US", ""):
            continue
        if (r.get("status") or "").lower() in ("deprecated", "inactive"):
            continue
        text = ((r.get("provider") or "") + " " + (r.get("name") or "")).lower()
        for kw, label, col in WANT:
            if kw in text:
                if (r.get("urls.authentication_type") or "0") not in ("0", ""):
                    continue
                lst = found.setdefault(label, [])
                # 先试运营方自己发布的地址（最新），再试 Mobility Database 的镜像
                for url in (r.get("urls.direct_download"), r.get("urls.latest")):
                    if url and all(u != url for u, *_ in lst):
                        item = (url, col, r.get("provider"), r.get("mdb_source_id"))
                        (lst.insert(0, item) if "ferry" in text else lst.append(item))
    return found


def read(z, name):
    try:
        with z.open(name) as f:
            return list(csv.DictReader(io.TextIOWrapper(f, "utf-8-sig")))
    except KeyError:
        return []


def hhmm(t):
    h, m = t.split(":")[:2]
    return "%02d:%s" % (int(h), m)   # 可能超过 24:00（跨午夜的班次），保留原样


def parse(label, url, col, today):
    print("%s ← %s" % (label, url), flush=True)
    z = zipfile.ZipFile(io.BytesIO(get(url, timeout=300)))
    routes = {r["route_id"]: r for r in read(z, "routes.txt") if r.get("route_type", "").strip() in ("4", "1200")}
    if not routes:
        print("  没有渡轮线路（route_type 4）", flush=True)
        return None
    trips = [t for t in read(z, "trips.txt") if t["route_id"] in routes]
    tids = {t["trip_id"] for t in trips}
    st = {}
    for r in read(z, "stop_times.txt"):
        if r["trip_id"] in tids:
            st.setdefault(r["trip_id"], []).append(r)
    stops = {s["stop_id"]: s for s in read(z, "stops.txt")}
    # services active on each of the next DAYS days
    cal = read(z, "calendar.txt")
    cd = read(z, "calendar_dates.txt")
    wd = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    days = {}
    for i in range(DAYS):
        d = today + dt.timedelta(days=i)
        ds = d.strftime("%Y%m%d")
        act = set()
        for c in cal:
            if c["start_date"] <= ds <= c["end_date"] and c.get(wd[d.weekday()]) == "1":
                act.add(c["service_id"])
        for c in cd:
            if c["date"] == ds:
                (act.add if c["exception_type"] == "1" else act.discard)(c["service_id"])
        days[d.isoformat()] = act
    used_services = set().union(*days.values()) if days else set()
    DEBUG.append({"feed": label, "url": url[:80], "routes4": [(r.get("route_short_name"), r.get("route_long_name")) for r in routes.values()][:20],
                  "trips": len(trips), "with_times": sum(1 for t in trips if t["trip_id"] in st),
                  "svc_trips": sorted({t["service_id"] for t in trips})[:15], "cal": [(c["service_id"], c["start_date"], c["end_date"]) for c in cal][:15],
                  "cd": len(cd), "cd_range": [min((c["date"] for c in cd), default=""), max((c["date"] for c in cd), default="")], "active": sorted(used_services)[:15]})
    # shapes
    shp = {}
    for r in read(z, "shapes.txt"):
        shp.setdefault(r["shape_id"], []).append((int(r["shape_pt_sequence"]), float(r["shape_pt_lat"]), float(r["shape_pt_lon"])))
    out_routes, out_trips, used_stops = [], [], set()
    stale_mode = not used_services
    for rid, r in routes.items():
        rtrips = [t for t in trips if t["route_id"] == rid and t["service_id"] in used_services and t["trip_id"] in st]
        if stale_mode:
            rtrips = [t for t in trips if t["route_id"] == rid and t["trip_id"] in st]
        if not rtrips:
            continue
        shape = None
        for t in rtrips:
            if t.get("shape_id") in shp:
                pts = sorted(shp[t["shape_id"]])
                step = max(1, len(pts) // 120)
                shape = [[round(a, 5), round(b, 5)] for _, a, b in pts[::step]] + [[round(pts[-1][1], 5), round(pts[-1][2], 5)]]
                break
        seqs = []
        for t in rtrips:
            rows = sorted(st[t["trip_id"]], key=lambda x: int(x["stop_sequence"]))
            times = [[x["stop_id"], hhmm(x.get("departure_time") or x.get("arrival_time"))] for x in rows if (x.get("departure_time") or x.get("arrival_time"))]
            if len(times) < 2:
                continue
            for s, _ in times:
                used_stops.add(s)
            seqs.append(tuple(s for s, _ in times))
            if stale_mode:
                continue
            out_trips.append({"r": label + ":" + rid, "h": t.get("trip_headsign") or "", "d": t.get("direction_id") or "", "s": label + ":" + t["service_id"], "t": times})
        longest = max(seqs, key=len) if seqs else ()
        name = (r.get("route_long_name") or r.get("route_short_name") or rid).strip()
        out_routes.append({"id": label + ":" + rid, "op": label, "n": name, "short": (r.get("route_short_name") or "").strip(),
                           "c": "#" + r["route_color"] if r.get("route_color") and len(r["route_color"]) == 6 and r["route_color"].upper() not in ("FFFFFF", "000000") else col,
                           "shape": shape, "stops": list(longest)})
    out_stops = {}
    for sid in used_stops:
        s = stops.get(sid)
        if not s:
            continue
        nm = re.sub(r"\s*-\s*No Service to .*$", "", s.get("stop_name", sid)).replace("San Francisco-Gate", "SF Ferry Building Gate")
        out_stops[label + ":" + sid] = {"n": nm, "zh": zh_of(nm), "ll": [round(float(s["stop_lat"]), 5), round(float(s["stop_lon"]), 5)]}
    for t in out_trips:
        t["t"] = [[label + ":" + a, b] for a, b in t["t"]]
    for r in out_routes:
        r["stops"] = [label + ":" + x for x in r["stops"]]
    days = {k: sorted(label + ":" + x for x in v) for k, v in days.items()}
    print("  %d 条航线 · %d 个码头 · %d 班次（服务组）" % (len(out_routes), len(out_stops), len(out_trips)), flush=True)
    if stale_mode:
        return [], out_stops, [], {"__stale_routes": out_routes}
    return out_routes, out_stops, out_trips, days


def main():
    today = (dt.datetime.utcnow() - dt.timedelta(hours=8)).date()
    feeds = find_feeds()
    print("找到的数据源：", {k: [x[2] for x in v] for k, v in feeds.items()}, flush=True)
    R, S, T, D, src = [], {}, [], {}, []
    stale = {}
    for label, cands in feeds.items():
        res = None
        for url, col, prov, mid in cands[:6]:
            try:
                res = parse(label, url, col, today)
            except Exception as e:
                print("  ✗", label, prov, e, flush=True)
                res = None
            if res and res[0]:
                break
            if res and res[3].get("__stale_routes") and not stale.get(label):
                stale[label] = res
            res = None
        if not res and stale.get(label):
            # 只有过期的数据：航线和码头照样画在地图上，时刻表不用（随季节变化，旧表会误导）
            s0, d0 = stale[label][1], stale[label][3]
            r0 = d0.get("__stale_routes", [])
            for r in r0:
                r["stale"] = 1
            res = (r0, s0, [], {})
        if not res:
            continue
        r, s, t, d = res
        R += r
        S.update(s)
        T += t
        for k, v in d.items():
            D.setdefault(k, []).extend(v)
        src.append({"op": label, "provider": prov, "mdb": mid})
    if not R:
        print("没有拿到任何渡轮数据，保留旧文件。")
        return 1
    # 只保留会用到的服务组
    used = set(x for v in D.values() for x in v)
    T = [t for t in T if t["s"] in used]
    out = {"generated": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "from": today.isoformat(), "src": src,
           "routes": R, "stops": S, "trips": T, "days": D}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("sf/ferry.json：%d 条航线 · %d 个码头 · %d 班次 · %d KB" % (len(R), len(S), len(T), os.path.getsize(OUT) // 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
