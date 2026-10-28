#!/usr/bin/env python3
"""湾区实时路况 → bay-live/live.json（每 5 分钟由 .github/workflows/bay-live.yml 跑，推到 live-data 分支）

数据（都是公开、免密钥）：
  · CHP 加州高速巡警实时事故（Caltrans QuickMap 发布的 KML）
  · Caltrans 4 区高速路牌（CMS）上显示的行车时间 —— 和这块路牌过去显示过的最短时间比，判断堵不堵
  · Caltrans 4 区正在进行的封路 / 封车道
只用标准库。  python3 scripts/build_bay_live.py [输出目录]
"""
import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.request

UA = "boliunew-tools-baylive/1.0 (https://github.com/boliunew/tools)"
CHP = "https://quickmap.dot.ca.gov/data/chp-only.kml"
CMS = "https://cwwp2.dot.ca.gov/data/d4/cms/cmsStatusD04.json"
LCS = "https://cwwp2.dot.ca.gov/data/d4/lcs/lcsStatusD04.json"
BBOX = (36.95, -123.1, 38.6, -121.4)
TYPES = [  # CHP 事件类型关键词 → 中文
    ("hit and run", "肇事逃逸"), ("collision", "车祸"), ("sig alert", "SigAlert 长时间封道"), ("wrong way", "逆行车辆"),
    ("car fire", "车辆起火"), ("vehicle fire", "车辆起火"), ("fire", "火情"), ("hazard", "路面危险"), ("debris", "路面杂物"),
    ("animal", "动物在路上"), ("disabled", "抛锚车辆"), ("stall", "抛锚车辆"), ("pedestrian", "行人在高速上"), ("road/weather", "路况 / 天气"),
    ("closure", "封路"), ("spinout", "车辆打滑"), ("assist", "协助处理"), ("traffic break", "交警压速清障"), ("break", "交警压速清障"),
]


def get(url, timeout=90):
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            if i == 2:
                raise
            print("  retry", url, e, flush=True)
            time.sleep(5)


def inbox(lat, lon):
    return BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lon <= BBOX[3]


def type_zh(t):
    t2 = re.sub(r"^\d+\w*-", "", t).strip()
    tl = t.lower()
    for k, z in TYPES:
        if k in tl:
            return z, t2
    return "", t2


def chp():
    raw = get(CHP).decode("utf-8", "replace")
    out = []
    for pm in re.findall(r"<Placemark>(.*?)</Placemark>", raw, re.S):
        c = re.search(r"<coordinates>\s*([-\d.]+),([-\d.]+)", pm)
        if not c:
            continue
        lon, lat = float(c.group(1)), float(c.group(2))
        if not inbox(lat, lon):
            continue
        title = re.search(r'class="iw-title">(.*?)</h2>', pm, re.S)
        texts = re.findall(r'class="iw-text">(.*?)</p>', pm, re.S)
        iid = re.search(r"CHP Incident (\w+)", pm)
        t = html.unescape(title.group(1).strip()) if title else ""
        when, loc = "", ""
        if texts:
            parts = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip() for x in re.split(r"<br\s*/?>", texts[0])]
            when = parts[0] if parts else ""
            loc = " ".join(parts[1:]).strip()
        zh, en = type_zh(t)
        out.append({"id": iid.group(1) if iid else "", "ll": [round(lat, 5), round(lon, 5)], "t": en, "zh": zh, "at": re.sub(r"\s+", " ", when), "loc": re.sub(r"\s+", " ", loc)})
    return out


def cms_lines(m):
    L = []
    for ph in ("phase1", "phase2"):
        p = m.get(ph) or {}
        for i in (1, 2, 3):
            s = (p.get("%sLine%d" % (ph, i)) or "").strip()
            if s:
                L.append(re.sub(r"\s+", " ", s))
    return L


TT = re.compile(r"^(.*?)\s*(\d{1,3})(?:\s*-\s*(\d{1,3}))?\s*MINS?\b", re.I)


def cms(base):
    d = json.loads(get(CMS))
    signs, now = [], int(time.time())
    for x in d.get("data", []):
        c = x.get("cms", {})
        loc, msg = c.get("location", {}), c.get("message", {})
        try:
            lat, lon = float(loc.get("latitude")), float(loc.get("longitude"))
        except (TypeError, ValueError):
            continue
        if c.get("inService") != "true" or (msg.get("display") or "").lower() == "blank":
            continue
        lines = cms_lines(msg)
        if not lines:
            continue
        tts, prev = [], ""
        for ln in lines:
            m = TT.match(ln)
            if m:
                dest = (m.group(1) or prev).strip(" -:.")
                mins = int(m.group(3) or m.group(2))
                if dest and 0 < mins < 300:
                    key = "%s|%s" % (c.get("index"), dest.upper())
                    b = base.get(key) or {"min": mins, "n": 0}
                    b["min"] = min(b["min"], mins)
                    b["n"] = b.get("n", 0) + 1
                    b["seen"] = now
                    base[key] = b
                    tts.append({"to": dest, "m": mins, "base": b["min"] if b["n"] >= 8 else None})
            else:
                prev = ln
        signs.append({"ll": [round(lat, 5), round(lon, 5)], "rt": loc.get("route", ""), "dir": loc.get("direction", ""),
                      "near": loc.get("nearbyPlace", ""), "cty": loc.get("county", ""), "msg": lines[:6], "tt": tts})
    # 一年没再见过的路牌目的地，清掉
    for k in [k for k, v in base.items() if now - v.get("seen", now) > 365 * 86400]:
        del base[k]
    return signs


def lcs():
    d = json.loads(get(LCS, timeout=180))
    now, out = int(time.time()), []
    for x in d.get("data", []):
        l = x.get("lcs", {})
        cl = l.get("closure", {})
        ts = cl.get("closureTimestamp", {})
        on = (cl.get("code1097") or {}).get("isCode1097") == "true" and (cl.get("code1098") or {}).get("isCode1098") != "true" and (cl.get("code1022") or {}).get("isCode1022") != "true"
        try:
            st, en = int(ts.get("closureStartEpoch") or 0), int(ts.get("closureEndEpoch") or 0)
        except ValueError:
            st, en = 0, 0
        if not on:
            continue
        if en and now > en + 6 * 3600:
            continue  # 早就该结束了的，大多是没回报撤除
        b, e = l.get("location", {}).get("begin", {}), l.get("location", {}).get("end", {})
        try:
            ll = [round(float(b["beginLatitude"]), 5), round(float(b["beginLongitude"]), 5)]
            ll2 = [round(float(e["endLatitude"]), 5), round(float(e["endLongitude"]), 5)]
        except (KeyError, TypeError, ValueError):
            continue
        out.append({"ll": ll, "ll2": ll2, "rt": b.get("beginRoute", ""), "dir": l.get("location", {}).get("travelFlowDirection", ""),
                    "near": b.get("beginNearbyPlace", ""), "cty": b.get("beginCounty", ""), "fac": cl.get("facility", ""),
                    "type": cl.get("typeOfClosure", ""), "work": cl.get("typeOfWork", ""), "lanes": cl.get("lanesClosed", ""),
                    "total": cl.get("totalExistingLanes", ""), "end": en, "delay": cl.get("estimatedDelay", "")})
    return out


def main():
    od = sys.argv[1] if len(sys.argv) > 1 else "bay-live"
    os.makedirs(od, exist_ok=True)
    bp = os.path.join(od, "cms_base.json")
    try:
        base = json.load(open(bp))
    except Exception:
        base = {}
    out = {"generated": int(time.time()), "err": []}
    for k, fn in (("inc", chp), ("cms", lambda: cms(base)), ("lcs", lcs)):
        try:
            out[k] = fn()
        except Exception as e:
            print("✗", k, e, flush=True)
            out[k] = []
            out["err"].append(k)
    with open(os.path.join(od, "live.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    with open(bp, "w") as f:
        json.dump(base, f, separators=(",", ":"))
    print("live.json：事故 %d · 路牌 %d（带行车时间 %d）· 封路 %d · 基准 %d · 出错 %s" % (
        len(out["inc"]), len(out["cms"]), sum(1 for s in out["cms"] if s["tt"]), len(out["lcs"]), len(base), out["err"] or "无"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
