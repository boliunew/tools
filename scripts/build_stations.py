#!/usr/bin/env python3
"""📍 附近车站：把各家的车站合成一份 → stations/near.json（nearby.js 用）

· Amtrak：amtrak/data.json（车站 + 每站接下来的发车，按星期）
· BART / Muni 轻轨：sf/transit.json
· VTA 轻轨 / Caltrain：sj/transit.json
· Metrolink（南加州通勤火车，Upland 有站）：官方公开 GTFS（通过 Mobility Database 目录找下载地址）
只用标准库。  python3 scripts/build_stations.py
"""
import csv
import io
import json
import os
import re
import sys
import time
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "stations", "near.json")
UA = "boliunew-tools-stations/1.0 (https://github.com/boliunew/tools)"
CATALOG = "https://share.mobilitydata.org/catalogs-csv"
ML_FALLBACK = ["https://metrolinktrains.com/globalassets/about/gtfs/gtfs.zip"]
ML_ZH = {"Upland": "Upland（家门口）", "L.A. Union": "洛杉矶联合车站", "Pomona - North": "波莫纳北站", "Pomona - Downtown": "波莫纳市中心", "Ontario - East": "安大略东站", "Riverside - Downtown": "河滨市中心", "San Bernardino - Downtown": "圣贝纳迪诺市中心", "Anaheim - ARTIC": "阿纳海姆", "Burbank Airport - South (VC Line)": "伯班克机场南", "Burbank Airport - North (AV Line)": "伯班克机场北", "Redlands - University": "雷德兰兹大学", "Oceanside": "欧申赛德", "Lancaster": "兰开斯特", "Palmdale": "帕姆代尔", "Orange": "橙市", "Tustin": "塔斯廷", "San Clemente": "圣克莱门特", "Oxnard": "奥克斯纳德", "Northridge": "北岭", "Van Nuys": "范奈斯", "Chatsworth": "查茨沃斯", "Moorpark": "穆尔帕克", "Simi Valley": "西米谷", "Camarillo": "卡马里奥", "Buena Park": "布埃纳帕克", "Norwalk / Santa Fe Springs": "诺沃克", "Santa Clarita": "圣克拉丽塔", "L.A. Union Station": "洛杉矶联合车站", "Los Angeles Union Station": "洛杉矶联合车站", "Montclair": "蒙特克莱尔", "Claremont": "克莱蒙特",
         "Pomona North": "波莫纳北站", "Pomona Downtown": "波莫纳市中心", "Rancho Cucamonga": "兰乔库卡蒙格", "Fontana": "丰塔纳", "Rialto": "里亚尔托",
         "San Bernardino Depot": "圣贝纳迪诺", "San Bernardino-Downtown": "圣贝纳迪诺市中心", "Ontario-East": "安大略东站", "Riverside-Downtown": "河滨市中心",
         "Fullerton": "富勒顿", "Anaheim-ARTIC": "阿纳海姆", "Irvine": "欧文", "Burbank-Airport-South": "伯班克机场", "Covina": "科维纳", "Baldwin Park": "鲍德温公园",
         "El Monte": "埃尔蒙特", "Cal State LA": "加州州立大学洛杉矶分校", "Industry": "工业市", "Glendale": "格伦代尔", "Santa Ana": "圣塔安娜"}


DEPS = {"base": "", "svc": {}, "d": {}}   # 发车时刻（stations/deps.json），点开车站详情时才加载
HORIZON = 21


def gtfs_deps(z, prefix, station_of, line_of):
    """把一个 GTFS 里每个车站接下来 HORIZON 天的发车整理进 DEPS。station_of(stop_row) → 我们的车站 id 或 None。"""
    import datetime as dt
    rd = lambda n: list(csv.DictReader(io.TextIOWrapper(z.open(n), "utf-8-sig"))) if n in z.namelist() else []
    base = (dt.datetime.utcnow() - dt.timedelta(hours=8)).date()
    DEPS["base"] = base.strftime("%Y%m%d")
    days = [base + dt.timedelta(days=i) for i in range(HORIZON)]
    act = {}
    wk = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for c in rd("calendar.txt"):
        for i, d in enumerate(days):
            ds = d.strftime("%Y%m%d")
            if c["start_date"] <= ds <= c["end_date"] and c.get(wk[d.weekday()]) == "1":
                act.setdefault(c["service_id"], set()).add(i)
    idx = {d.strftime("%Y%m%d"): i for i, d in enumerate(days)}
    for c in rd("calendar_dates.txt"):
        i = idx.get(c["date"])
        if i is None:
            continue
        if c["exception_type"] == "1":
            act.setdefault(c["service_id"], set()).add(i)
        else:
            act.get(c["service_id"], set()).discard(i)
    routes = {r["route_id"]: r for r in rd("routes.txt")}
    trips = {t["trip_id"]: t for t in rd("trips.txt") if act.get(t["service_id"])}
    stops = {x["stop_id"]: x for x in rd("stops.txt")}
    seq = {}
    for r in rd("stop_times.txt"):
        if r["trip_id"] in trips:
            seq.setdefault(r["trip_id"], []).append(r)
    n = 0
    for tid, rows in seq.items():
        t = trips[tid]
        rows.sort(key=lambda x: int(x["stop_sequence"]))
        sk = prefix + t["service_id"]
        DEPS["svc"][sk] = sorted(act[t["service_id"]])
        line = line_of(routes.get(t["route_id"], {}))
        last = stops.get(rows[-1]["stop_id"], {})
        head = t.get("trip_headsign") or re.sub(r"\s+(Metrolink )?Station$", "", last.get("stop_name", "")).strip()
        for r in rows[:-1]:
            sid = station_of(stops.get(r["stop_id"], {}))
            tm = (r.get("departure_time") or r.get("arrival_time") or "")[:5]
            if not sid or not tm:
                continue
            DEPS["d"].setdefault(sid, []).append([tm, line, head, sk, t.get("trip_short_name") or ""])
            n += 1
    print("  departures", prefix, n)


def get(url, timeout=180):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout) as r:
                return r.read()
        except Exception as e:
            if i == 2:
                raise
            print("retry", url[:80], e, flush=True)
            time.sleep(5)


def load(p):
    try:
        return json.load(open(os.path.join(ROOT, p), encoding="utf-8"))
    except Exception as e:
        print("skip", p, e)
        return None


def amtrak_zh():
    try:
        s = open(os.path.join(ROOT, "amtrak.html"), encoding="utf-8").read()
        m = re.search(r"var ZH = \{(.*?)\};", s, re.S)
        return dict(re.findall(r"([A-Z]{3}): '([^']+)'", m.group(1))) if m else {}
    except Exception:
        return {}


def shift(days, off):
    return "".join(days[((i - off) % 7 + 7) % 7] for i in range(7))


def amtrak(out):
    d = load("amtrak/data.json")
    if not d:
        return
    zh = amtrak_zh()
    rz = {r["i"]: (r["zh"].split("（")[0], r["c"]) for r in d["routes"]}
    today = time.strftime("%Y%m%d", time.gmtime(time.time() - 8 * 3600))
    merged = {}
    for t in d["trips"]:
        if t["to"] < today:
            continue
        k = t["no"] + "|" + ",".join(x[0] + x[2] for x in t["st"])
        m = merged.setdefault(k, {"t": t, "days": [0] * 7})
        for i in range(7):
            if t["days"][i] == "1":
                m["days"][i] = 1
    dep = {}
    seen = {}
    for m in merged.values():
        t, days = m["t"], "".join(str(x) for x in m["days"])
        last = t["st"][-1][0]
        for x in t["st"][:-1]:
            kk = (x[0], x[2] or x[1], t["no"])
            sd = shift(days, x[3])
            if kk in seen:   # 同一班车不同时期的时刻表：合并开行日
                e = seen[kk]
                e[4] = "".join("1" if a == "1" or b == "1" else "0" for a, b in zip(e[4], sd))
                continue
            e = [x[2] or x[1], t["no"], rz.get(t["r"], ("", ""))[0], zh.get(last, d["stations"].get(last, {}).get("n", last)).split("（")[0], sd]
            seen[kk] = e
            dep.setdefault(x[0], []).append(e)
    for code, s in d["stations"].items():
        ds = sorted(dep.get(code, []), key=lambda x: x[0])
        lines = sorted({x[2] for x in ds})
        out.append({"k": "amtrak", "id": code, "n": s["n"], "zh": zh.get(code, ""), "ll": s["ll"], "l": lines, "dep": ds[:40]})


def transit(out, path, layer, kind):
    d = load(path)
    if not d:
        return
    L = [x for x in d["layers"] if x["k"] == layer]
    if not L:
        return
    L = L[0]
    for s in L["st"]:
        lines = [ln["n"] for i, ln in enumerate(L["lines"]) if s["id"] in (ln.get("st") or []) or i in (s.get("ln") or [])]
        out.append({"k": kind, "id": s["id"], "n": s["en"], "zh": s.get("zh", ""), "ll": s["ll"], "l": lines})


def metrolink(out):
    urls = []
    try:
        for r in csv.DictReader(io.StringIO(get(CATALOG).decode("utf-8-sig", "replace"))):
            prov = (r.get("provider") or "").lower()
            if (r.get("data_type") or "").lower() == "gtfs" and ("metrolink" in prov or "southern california regional rail" in prov) and "louis" not in prov \
                    and (r.get("location.subdivision_name") or "California") == "California" and (r.get("urls.authentication_type") or "0") in ("0", ""):
                urls += [u for u in (r.get("urls.direct_download"), r.get("urls.latest")) if u]
    except Exception as e:
        print("catalog", e)
    for url in urls + ML_FALLBACK:
        try:
            z = zipfile.ZipFile(io.BytesIO(get(url)))
            rd = lambda n: list(csv.DictReader(io.TextIOWrapper(z.open(n), "utf-8-sig")))
            routes = {r["route_id"]: r for r in rd("routes.txt")}
            trips = {t["trip_id"]: t["route_id"] for t in rd("trips.txt")}
            stops = {s["stop_id"]: s for s in rd("stops.txt")}
            serve = {}
            for r in rd("stop_times.txt"):
                rid = trips.get(r["trip_id"])
                if rid:
                    s = stops.get(r["stop_id"], {})
                    key = s.get("parent_station") or r["stop_id"]
                    serve.setdefault(key, set()).add(rid)
            n0 = len(out)
            for sid, rids in serve.items():
                s = stops.get(sid)
                if not s:
                    continue
                nm = re.sub(r"\s+(Metrolink )?Station$", "", s["stop_name"]).strip()
                names = sorted({(routes[r].get("route_long_name") or routes[r].get("route_short_name") or r).replace("Metrolink ", "").replace(" Line", " 线") for r in rids if r in routes})
                out.append({"k": "metrolink", "id": "ML:" + sid, "n": nm, "zh": ML_ZH.get(nm, ""), "ll": [round(float(s["stop_lat"]), 5), round(float(s["stop_lon"]), 5)], "l": names})
            print("metrolink", url, len(out) - n0, "stations")
            if len(out) > n0:
                gtfs_deps(z, "ML", lambda st: ("ML:" + (st.get("parent_station") or st.get("stop_id"))) if st else None,
                          lambda r: (r.get("route_long_name") or r.get("route_short_name") or "").replace("Metrolink ", "").replace(" Line", " 线"))
                return
        except Exception as e:
            print("  ✗", url, e)


def caltrain():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from build_sj_transit import clean, catalog_urls, FEEDS
    except Exception as e:
        print("caltrain import", e)
        return
    fb = [f for f in FEEDS if f[0] == "caltrain"][0]
    for url in catalog_urls(fb[1]) + fb[2]:
        try:
            z = zipfile.ZipFile(io.BytesIO(get(url)))
            stops = {x["stop_id"]: x for x in csv.DictReader(io.TextIOWrapper(z.open("stops.txt"), "utf-8-sig"))}

            def st_of(st):
                if not st:
                    return None
                par = stops.get(st.get("parent_station") or "")
                return "caltrain:" + clean((par or st).get("stop_name", "")).lower()
            gtfs_deps(z, "CT", st_of, lambda r: "Caltrain " + (r.get("route_short_name") or r.get("route_long_name") or ""))
            return
        except Exception as e:
            print("  ✗ caltrain", url, e)


def main():
    out = []
    amtrak(out)
    transit(out, "sf/transit.json", "bart", "bart")
    transit(out, "sf/transit.json", "muni", "muni")
    transit(out, "sj/transit.json", "vta", "vta")
    transit(out, "sj/transit.json", "caltrain", "caltrain")
    metrolink(out)
    caltrain()
    for k in DEPS["d"]:
        DEPS["d"][k].sort(key=lambda x: x[0])
    with open(os.path.join(ROOT, "stations", "deps.json"), "w", encoding="utf-8") as f:
        json.dump(DEPS, f, ensure_ascii=False, separators=(",", ":"))
    print("stations/deps.json：", len(DEPS["d"]), "stations", os.path.getsize(os.path.join(ROOT, "stations", "deps.json")) // 1024, "KB")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "st": out}, f, ensure_ascii=False, separators=(",", ":"))
    c = {}
    for s in out:
        c[s["k"]] = c.get(s["k"], 0) + 1
    print("stations/near.json：", c, os.path.getsize(OUT) // 1024, "KB")


if __name__ == "__main__":
    sys.exit(main())
