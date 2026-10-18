#!/usr/bin/env python3
"""🚆 Amtrak 时刻表 + 线路走向 → amtrak/data.json（amtrak.html 用）

数据来源：Amtrak 官方公开的 GTFS 时刻表（content.amtrak.com/content/gtfs/GTFS.zip），每周由 .github/workflows/amtrak.yml 重跑。
只取和加州 / 西部有关、最值得坐的几条线。GTFS 里的时间按 agency_timezone（美东）给出，这里换算成每个车站的当地时间。
只用标准库。  python3 scripts/build_amtrak.py
"""
import csv
import datetime as dt
import io
import json
import os
import sys
import time
import urllib.request
import zipfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "amtrak", "data.json")
URL = "https://content.amtrak.com/content/gtfs/GTFS.zip"
UA = "boliunew-tools-amtrak/1.0 (https://github.com/boliunew/tools)"
WANT = [  # GTFS route_long_name, 中文, 颜色
    ("Pacific Surfliner", "太平洋冲浪者号", "#1B75BB"),
    ("Coast Starlight", "海岸星光号", "#2A893D"),
    ("California Zephyr", "加州和风号", "#B5121B"),
    ("Southwest Chief", "西南酋长号", "#C8102E"),
    ("Sunset Limited", "日落特快", "#E87722"),
    ("Texas Eagle", "德州之鹰号", "#00558C"),
    ("Capitol Corridor", "首府走廊（湾区 ⇄ 萨克拉门托）", "#6A3D9A"),
]
EPS = {"Pacific Surfliner": 0.0006, "Capitol Corridor": 0.0006}


def get(url):
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.read()
        except Exception as e:
            if i == 2:
                raise
            print("retry", e, flush=True)
            time.sleep(10)


def rows(z, name):
    with z.open(name) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, "utf-8-sig"))


def simplify(pts, eps):
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    st = [(0, len(pts) - 1)]
    while st:
        a, b = st.pop()
        ax, ay = pts[a]
        bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy or 1e-18
        best, bi = -1, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
            d = (ax + t * dx - px) ** 2 + (ay + t * dy - py) ** 2
            if d > best:
                best, bi = d, i
        if best > eps * eps:
            keep[bi] = True
            st += [(a, bi), (bi, b)]
    return [p for p, k in zip(pts, keep) if k]


def main():
    z = zipfile.ZipFile(io.BytesIO(get(URL)))
    agency_tz = {}
    for a in rows(z, "agency.txt"):
        agency_tz[a["agency_id"]] = a["agency_timezone"]
    routes, want_names = {}, {w[0]: w for w in WANT}
    for r in rows(z, "routes.txt"):
        if r["route_long_name"] in want_names and r.get("route_type") == "2":
            routes[r["route_id"]] = r
    print("routes:", {r["route_long_name"]: k for k, r in routes.items()})
    trips = {t["trip_id"]: t for t in rows(z, "trips.txt") if t["route_id"] in routes}
    cal = {c["service_id"]: c for c in rows(z, "calendar.txt")}
    st = {}
    for r in rows(z, "stop_times.txt"):
        if r["trip_id"] in trips:
            st.setdefault(r["trip_id"], []).append(r)
    stops = {s["stop_id"]: s for s in rows(z, "stops.txt")}
    need_shapes = {t.get("shape_id") for t in trips.values() if t.get("shape_id")}
    shp = {}
    for r in rows(z, "shapes.txt"):
        if r["shape_id"] in need_shapes:
            shp.setdefault(r["shape_id"], []).append((int(r["shape_pt_sequence"]), float(r["shape_pt_lat"]), float(r["shape_pt_lon"])))

    today = (dt.datetime.utcnow() - dt.timedelta(hours=8)).date()
    used, out_trips, out_routes = set(), [], []
    for idx, (name, zh, col) in enumerate(WANT):
        rids = [k for k, r in routes.items() if r["route_long_name"] == name]
        rtrips = [t for t in trips.values() if t["route_id"] in rids and t["trip_id"] in st]
        if not rtrips:
            print("  no trips for", name)
            continue
        atz = ZoneInfo(agency_tz.get(routes[rids[0]]["agency_id"], "America/New_York"))
        longest = None
        for t in rtrips:
            c = cal.get(t["service_id"])
            if not c or c["end_date"] < today.strftime("%Y%m%d"):
                continue
            seq = sorted(st[t["trip_id"]], key=lambda x: int(x["stop_sequence"]))
            # 参考日：服务期内（不早于今天）的第一个开行日，用来把美东时间换算成当地时间（夏令时也就对了）
            ref = max(today, dt.datetime.strptime(c["start_date"], "%Y%m%d").date())
            days = [c[k] for k in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")]
            for _ in range(7):
                if days[ref.weekday()] == "1":
                    break
                ref += dt.timedelta(days=1)
            pts, first_local = [], None
            for x in seq:
                s = stops.get(x["stop_id"])
                if not s:
                    continue
                stz = ZoneInfo(s.get("stop_timezone") or "America/Los_Angeles")

                def loc(hms):
                    if not hms:
                        return None
                    h, m, sec = (int(v) for v in hms.split(":"))
                    base = dt.datetime(ref.year, ref.month, ref.day, tzinfo=atz) + dt.timedelta(hours=h, minutes=m, seconds=sec)
                    return base.astimezone(stz)
                a, d = loc(x["arrival_time"]), loc(x["departure_time"])
                if first_local is None:
                    first_local = (d or a).date()
                ref_dt = d or a
                pts.append([x["stop_id"], a.strftime("%H:%M") if a else "", d.strftime("%H:%M") if d else "", (ref_dt.date() - first_local).days])
                used.add(x["stop_id"])
            if len(pts) < 2:
                continue
            out_trips.append({"r": idx, "no": t.get("trip_short_name") or "", "h": t.get("trip_headsign") or "", "dir": t.get("direction_id") or "",
                              "days": "".join(days), "from": c["start_date"], "to": c["end_date"], "st": pts})
            if not longest or len(seq) > len(longest[1]):
                longest = (t, seq)
        if not longest:
            continue
        t0 = longest[0]
        pts = sorted(shp.get(t0.get("shape_id"), []))
        shape = [[round(a, 4), round(b, 4)] for a, b in simplify([(a, b) for _, a, b in pts], EPS.get(name, 0.002))] if pts else []
        out_routes.append({"i": idx, "n": name, "zh": zh, "c": col, "shape": shape,
                           "stops": [x["stop_id"] for x in sorted(longest[1], key=lambda x: int(x["stop_sequence"]))]})
        print("  %-18s %3d 班 · %d 站 · 走向 %d 点" % (name, sum(1 for x in out_trips if x["r"] == idx), len(out_routes[-1]["stops"]), len(shape)), flush=True)
    stations = {}
    for sid in used:
        s = stops[sid]
        stations[sid] = {"n": s["stop_name"], "ll": [round(float(s["stop_lat"]), 5), round(float(s["stop_lon"]), 5)], "tz": s.get("stop_timezone") or ""}
    out = {"generated": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "src": URL, "routes": out_routes, "stations": stations, "trips": out_trips}
    # 自检：海岸星光号 11 次西雅图应该是早上开（当地时间）
    for t in out_trips:
        if t["no"] == "11" and t["st"]:
            print("check 11:", t["st"][0], t["st"][-1])
            break
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("amtrak/data.json：%d 条线 · %d 班次 · %d 站 · %d KB" % (len(out_routes), len(out_trips), len(stations), os.path.getsize(OUT) // 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
