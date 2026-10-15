#!/usr/bin/env python3
"""
财报 + 经济日历 (GitHub Actions)

For the next 14 days:
  * US macro events (Nasdaq economic calendar; FOMC dates as fallback) with impact notes
  * Earnings of S&P 500 / Nasdaq-100 / watchlist companies (Nasdaq calendar; yfinance fallback)
For every upcoming reporter, from its own past earnings (yfinance):
  * average earnings-day move, beat rate, "beat but fell" rate (利好兑现下跌)
  * pre-earnings run-up vs reaction ("提前炒作" check), 5-day post drift
  * options-implied move for reports within 7 days (compared with the plain historical move)
  * sympathy stocks: tickers whose same-day moves track this company's earnings moves
After each report: actual EPS + reaction, checked against the frozen pre-release call.
Moves are relative to SPY unless noted.  Output: earnings/data/latest.json (+ history.json for the scorecard)

Offline test:  python earnings/build.py --demo
"""
import argparse
import datetime as dt
import html
import json
import math
import os
import re
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "data", "latest.json")
HIST = os.path.join(HERE, "data", "history.json")   # frozen predictions + actual results, for the scorecard
UNIVERSE = os.path.join(ROOT, "stocks", "universe.json")
WATCHLIST = os.path.join(ROOT, "stocks", "watchlist.txt")
DAYS_AHEAD = 14
PAST_DAYS = 5            # business days of results to show
NY = ZoneInfo("America/New_York")
MAX_REPORTERS = 160
MIN_CAP = 20e9            # also include non-universe companies above this market cap
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept": "application/json, text/plain, */*", "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}
DIAG = {}

FOMC_2026 = ["2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09"]

MACRO = [
    (r"\bCPI\b|Consumer Price Index", "CPI", "高", "CPI 通胀数据",
     "高于预期 → 降息预期后移、长债收益率上行，通常利空成长科技、小盘股和地产，利好美元；低于预期则相反，科技和小盘往往领涨。",
     ["QQQ", "IWM", "TLT", "XHB", "XLF"]),
    (r"PCE", "PCE", "高", "PCE 物价指数",
     "美联储最看重的通胀指标。核心 PCE 超预期会强化「更久维持高利率」的判断，压制估值高的成长股。",
     ["QQQ", "TLT", "IWM"]),
    (r"Nonfarm Payrolls|Non-Farm", "NFP", "高", "非农就业报告",
     "就业大超预期 → 经济强但降息推迟，利率敏感股承压；远弱于预期 → 衰退担忧，周期股、小盘股下跌、国债上涨。温和数据对股市最友好。",
     ["SPY", "IWM", "TLT", "XLY", "KRE"]),
    (r"Unemployment Rate", "UNRATE", "中", "失业率",
     "失业率跳升会触发衰退交易（萨姆规则），利好国债、黄金，利空周期股。",
     ["IWM", "TLT", "GLD"]),
    (r"Interest Rate Decision|FOMC Statement|FOMC Economic Projections|Federal Funds Rate", "FOMC", "高", "美联储利率决议",
     "关注利率决定、点阵图和鲍威尔发布会措辞。鹰派 → 美元、收益率上行，科技股承压；鸽派 → 成长股、黄金、比特币受益。决议当天波动往往在发布会期间。",
     ["SPY", "QQQ", "XLF", "TLT", "GLD"]),
    (r"(Fed|FOMC|Powell).*(Speaks|Speech|Testif)|FOMC Meeting Minutes", "FEDSPEAK", "低", "美联储官员讲话 / 会议纪要",
     "留意对降息节奏的表态；鲍威尔本人或纪要中的意外措辞可能引起短线波动。",
     ["SPY", "TLT"]),
    (r"\bPPI\b|Producer Price", "PPI", "中", "PPI 生产者物价",
     "上游通胀的先行信号，大幅超预期会放大市场对 CPI 的担忧。",
     ["QQQ", "TLT"]),
    (r"Retail Sales", "RETAIL", "中", "零售销售",
     "消费占美国 GDP 约七成。数据强 → 利好零售、可选消费；过强也会推高利率预期。",
     ["XRT", "XLY", "AMZN", "WMT", "COST"]),
    (r"\bGDP\b", "GDP", "中", "GDP",
     "季度经济增速。大幅低于预期会加剧衰退担忧，利好国债、利空周期股。",
     ["SPY", "IWM", "TLT"]),
    (r"ISM (Manufacturing|Services|Non-Manufacturing)", "ISM", "中", "ISM 采购经理指数",
     "50 以上表示扩张。制造业 ISM 影响工业、材料股；服务业 ISM 中的价格分项是通胀线索。",
     ["XLI", "XLB", "CAT", "DE"]),
    (r"JOLTS", "JOLTS", "中", "JOLTS 职位空缺",
     "劳动力市场松紧的指标，空缺下降代表就业降温，利好降息预期。",
     ["IWM", "TLT"]),
    (r"Initial Jobless Claims", "CLAIMS", "低", "首次申领失业金人数",
     "每周四公布。连续大幅上升是就业转弱的早期信号。",
     ["IWM"]),
    (r"Michigan|Consumer Confidence|Consumer Sentiment", "SENT", "低", "消费者信心",
     "关注其中的通胀预期分项，突然走高会引起美联储警惕。",
     ["XLY", "XRT"]),
    (r"Crude Oil Inventories|EIA Crude", "OIL", "低", "EIA 原油库存",
     "库存意外下降 → 油价上涨，利好能源股；意外累积则相反。",
     ["XLE", "XOM", "CVX", "OXY", "USO"]),
]


# ----------------------------------------------------------------------------- helpers
def http_json(url, timeout=20):
    import requests
    r = requests.get(url, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r.json()


def money(s):
    if s is None:
        return None
    s = str(s).replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        m = re.match(r"\(([\d.]+)\)", s)
        return -float(m.group(1)) if m else None


def load_universe():
    meta = {}
    if os.path.exists(UNIVERSE):
        with open(UNIVERSE, encoding="utf-8") as f:
            meta = json.load(f)
    watch = set()
    if os.path.exists(WATCHLIST):
        with open(WATCHLIST, encoding="utf-8") as f:
            for line in f:
                s = line.split("#")[0].strip().upper().replace(".", "-")
                if s:
                    watch.add(s)
    return meta, watch


def business_days(start, n):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


# ----------------------------------------------------------------------------- calendars
def nasdaq_earnings(days):
    rows = []
    for d in days:
        try:
            j = http_json(f"https://api.nasdaq.com/api/calendar/earnings?date={d.isoformat()}")
            for r in ((j.get("data") or {}).get("rows") or []):
                t = (r.get("time") or "").lower()
                rows.append({
                    "t": (r.get("symbol") or "").upper().replace(".", "-"), "name": r.get("name") or "",
                    "date": d.isoformat(), "when": "pre" if "pre" in t else "post" if "after" in t else "",
                    "cap": money(r.get("marketCap")), "eps_est": money(r.get("epsForecast")),
                    "n_est": r.get("noOfEsts"), "last_eps": money(r.get("lastYearEPS")), "fq": r.get("fiscalQuarterEnding"),
                })
            time.sleep(0.4)
        except Exception as e:  # noqa: BLE001
            print("nasdaq earnings", d, e)
    return rows


def yf_earnings_fallback(tickers, days):
    import yfinance as yf
    first, last = days[0], days[-1]
    rows = []
    for t in tickers:
        try:
            cal = yf.Ticker(t).calendar
            ds = cal.get("Earnings Date") if isinstance(cal, dict) else None
            if ds:
                d = pd.Timestamp(ds[0]).date()
                if first <= d <= last:
                    rows.append({"t": t, "name": "", "date": d.isoformat(), "when": "", "cap": None,
                                 "eps_est": cal.get("Earnings Average"), "n_est": None, "last_eps": None, "fq": ""})
        except Exception:  # noqa: BLE001
            pass
    return rows


def cleanv(v):
    """Nasdaq fills empty cells with '&nbsp;' — turn that into an empty string"""
    return html.unescape(str(v or "")).replace("\xa0", " ").strip()


def nasdaq_macro(days):
    out = []
    for d in days:
        try:
            j = http_json(f"https://api.nasdaq.com/api/calendar/economicevents?date={d.isoformat()}")
            for r in ((j.get("data") or {}).get("rows") or []):
                if "united states" not in (r.get("country") or "").lower():
                    continue
                out.append({"date": d.isoformat(), "time": r.get("gmt") or "", "name": cleanv(r.get("eventName")),
                            "actual": cleanv(r.get("actual")), "consensus": cleanv(r.get("consensus")), "previous": cleanv(r.get("previous"))})
            time.sleep(0.4)
        except Exception as e:  # noqa: BLE001
            print("nasdaq macro", d, e)
    return out


def to_et(date_s, time_s, is_gmt):
    try:
        hh, mm = [int(x) for x in time_s.split(":")[:2]]
    except Exception:  # noqa: BLE001
        return time_s
    if not is_gmt:
        return f"{hh:02d}:{mm:02d}"
    t = dt.datetime.fromisoformat(date_s).replace(hour=hh, minute=mm, tzinfo=dt.timezone.utc)
    return t.astimezone(NY).strftime("%H:%M")


def group_macro(raw, days):
    # Nasdaq labels the column "gmt"; detect whether the times are GMT by checking 8:30-ET releases
    anchors = [r["time"] for r in raw if re.search(r"CPI|Payrolls|Jobless Claims|Retail Sales", r["name"])]
    is_gmt = any(a.startswith(("12:30", "13:30")) for a in anchors)
    DIAG["macro_time_is_gmt"] = is_gmt
    groups = {}
    for r in raw:
        for pat, key, imp, title, note, syms in MACRO:
            if re.search(pat, r["name"], re.I):
                gk = (r["date"], key)
                g = groups.setdefault(gk, {"date": r["date"], "key": key, "imp": imp, "title": title, "note": note,
                                           "syms": syms, "time": to_et(r["date"], r["time"], is_gmt), "lines": []})
                g["lines"].append({"name": r["name"], "actual": r["actual"], "consensus": r["consensus"], "previous": r["previous"]})
                break
    have_fomc = any(k == "FOMC" for (_, k) in groups)
    if not have_fomc:
        for d in days:
            if d.isoformat() in FOMC_2026:
                pat, key, imp, title, note, syms = [m for m in MACRO if m[1] == "FOMC"][0]
                groups[(d.isoformat(), key)] = {"date": d.isoformat(), "key": key, "imp": imp, "title": title, "note": note,
                                                "syms": syms, "time": "14:00", "lines": [{"name": "FOMC 利率决议（官方日程）", "actual": "", "consensus": "", "previous": ""}]}
    order = {"高": 0, "中": 1, "低": 2}
    return sorted(groups.values(), key=lambda g: (g["date"], order[g["imp"]], g["time"]))


# ----------------------------------------------------------------------------- history
def download(tickers, period="4y"):
    import yfinance as yf
    out = {}
    for i in range(0, len(tickers), 100):
        part = tickers[i:i + 100]
        try:
            df = yf.download(part, period=period, interval="1d", auto_adjust=True, group_by="ticker", threads=True, progress=False)
        except Exception as e:  # noqa: BLE001
            print("download", e)
            continue
        for t in part:
            try:
                d = df[t] if isinstance(df.columns, pd.MultiIndex) else df
                d = d[["Open", "Close"]].dropna()
                if len(d) > 200:
                    d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
                    out[t] = d
            except Exception:  # noqa: BLE001
                pass
    return out


def nanf(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def earnings_table(t, limit=20):
    import yfinance as yf
    return yf.Ticker(t).get_earnings_dates(limit=limit)


def past_earnings(t, df=None):
    """list of {day, after (True/False/None = unknown), surprise, eps, est}"""
    if df is None:
        df = earnings_table(t)
    ev = []
    if df is None or df.empty:
        return ev
    for ts, row in df.iterrows():
        ts = pd.Timestamp(ts)
        rep = nanf(row.get("Reported EPS"))
        local = ts.tz_convert(NY) if ts.tzinfo else ts
        # yfinance puts 00:00 when the release time is unknown → decide later from the price gaps
        after = None if (local.hour == 0 and local.minute == 0) else local.hour >= 12
        day = (local.tz_localize(None) if local.tzinfo else local).normalize()
        ev.append({"day": day, "after": after, "surprise": nanf(row.get("Surprise(%)")),
                   "eps": rep, "est": nanf(row.get("EPS Estimate"))})
    return ev


def react_pos(idx, o, c, day, after):
    """Index of the session that reacts to a release on `day`.
    The stated time (pre/post) is trusted unless the other candidate session gapped far more —
    yfinance times are sometimes wrong.  Unknown time → the session with the larger opening gap."""
    pos = int(idx.searchsorted(day))
    if pos >= len(idx):
        return None
    if idx[pos] != day:
        return pos                               # released on a non-trading day
    if pos < 1 or pos + 1 >= len(idx):
        return pos if after is False else None
    g0, g1 = abs(o[pos] / c[pos - 1] - 1), abs(o[pos + 1] / c[pos] - 1)
    if after is None:
        return pos + 1 if g1 > g0 else pos
    if after and g0 > 0.02 and g0 > 2.5 * g1:
        return pos
    if not after and g1 > 0.02 and g1 > 2.5 * g0:
        return pos + 1
    return pos + 1 if after else pos


def reaction_stats(ev, px, spy):
    """compute per-event moves; `move` is relative to SPY, `raw` is the plain move"""
    idx = px.index
    c, o = px["Close"].values, px["Open"].values
    sc = spy.reindex(idx)["Close"].values
    rows = []
    for e in ev:
        if e["eps"] is None:
            continue                             # not reported yet
        r = react_pos(idx, o, c, e["day"], e["after"])
        if r is None or r < 11 or r + 5 >= len(idx):
            continue
        if np.isnan(sc[[r - 11, r - 1, r, r + 5]]).any():
            continue
        raw = c[r] / c[r - 1] - 1
        move = raw - (sc[r] / sc[r - 1] - 1)
        gap = o[r] / c[r - 1] - 1
        pre = c[r - 1] / c[r - 11] - 1 - (sc[r - 1] / sc[r - 11] - 1)
        drift = c[r + 5] / c[r] - 1 - (sc[r + 5] / sc[r] - 1)
        rows.append({"date": str(idx[r].date()), "move": move, "raw": raw, "gap": gap, "pre": pre, "drift": drift,
                     "surprise": e["surprise"], "after": bool(idx[r] != e["day"])})
    return rows


def summarize(rows):
    if len(rows) < 4:
        return None
    mv = np.array([r["move"] for r in rows])
    raw = np.array([r["raw"] for r in rows])
    pre = np.array([r["pre"] for r in rows])
    dr = np.array([r["drift"] for r in rows])
    with_sur = [r for r in rows if r["surprise"] is not None]
    beats = [r for r in with_sur if r["surprise"] > 0]
    beat_fell = [r for r in beats if r["move"] < 0]
    hot = [r for r in rows if r["pre"] > 0.03]
    s = {
        "n": len(rows), "avg_abs": float(np.mean(np.abs(mv))), "max_abs": float(np.max(np.abs(mv))),
        "avg_abs_raw": float(np.mean(np.abs(raw))),
        "up_rate": float(np.mean(mv > 0)), "avg_move": float(np.mean(mv)),
        "beats": len(beats), "beat_rate": len(beats) / len(with_sur) if with_sur else None,
        "beat_fell": len(beat_fell), "avg_pre": float(np.mean(pre)), "avg_drift": float(np.mean(dr)),
        "hot_n": len(hot), "hot_avg": float(np.mean([r["move"] for r in hot])) if hot else None,
        "corr_pre_move": float(np.corrcoef(pre, mv)[0, 1]) if len(rows) >= 8 and np.std(pre) > 0 and np.std(mv) > 0 else None,
        "after_share": float(np.mean([r["after"] for r in rows])),
        "recent": [{"date": r["date"], "move": round(r["move"], 4), "pre": round(r["pre"], 4), "surprise": None if r["surprise"] is None else round(r["surprise"], 1)} for r in rows[:8]],
    }
    return s


def sympathy(t, rows, excess, meta):
    days = [pd.Timestamp(r["date"]) for r in rows]
    days = [d for d in days if d in excess.index]
    if len(days) < 8 or t not in excess.columns:
        return []
    # with only 8–12 events, picking the best of ~500 tickers finds 0.55 correlations by pure luck
    floor = 0.55 if len(days) >= 14 else 0.65 if len(days) >= 11 else 0.72
    sub = excess.loc[days]
    x = sub[t]
    if x.std() == 0 or x.isna().any():
        return []
    others = sub.drop(columns=[t, "SPY"], errors="ignore").dropna(axis=1, thresh=len(days) - 1)
    others = others.loc[:, others.std() > 0]
    with np.errstate(all="ignore"):
        corr = others.corrwith(x)
    corr = corr[corr >= floor].sort_values(ascending=False)
    sec = meta.get(t, {}).get("sector", "")
    out = []
    for o, c in corr.items():
        if sec and meta.get(o, {}).get("sector", "") != sec and c < 0.75:
            continue
        y = others[o].fillna(0)
        beta = float(np.polyfit(x.values, y.values, 1)[0])
        same = float(np.mean(np.sign(x.values) == np.sign(y.values)))
        if same < 0.7 or beta < 0.15:
            continue
        out.append({"t": o, "name": meta.get(o, {}).get("name", ""), "corr": round(float(c), 2), "beta": round(beta, 2),
                    "same": round(same, 2), "n": len(days)})
        if len(out) >= 5:
            break
    return out


def next_bday(d):
    d += dt.timedelta(days=1)
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


def react_date(e):
    """first session that can trade on the news; unknown time → assume after the close (the later, safer day)"""
    d = dt.date.fromisoformat(e["date"])
    return d if e.get("when") == "pre" else next_bday(d)


def implied_move(t, react_day, price):
    """at-the-money straddle of the first expiry on/after the reaction session — an expiry on the
    report date itself would expire before an after-close release and price no earnings move at all"""
    import yfinance as yf
    tk = yf.Ticker(t)
    exps = [e for e in (tk.options or []) if pd.Timestamp(e).date() >= react_day]
    if not exps:
        return None
    ch = tk.option_chain(exps[0])
    calls, puts = ch.calls, ch.puts
    if calls.empty or puts.empty:
        return None
    k = calls.iloc[(calls["strike"] - price).abs().argsort()[:1]]["strike"].values[0]
    def mid(df):
        r = df[df["strike"] == k]
        if r.empty:
            return None
        b, a, l = float(r["bid"].values[0] or 0), float(r["ask"].values[0] or 0), float(r["lastPrice"].values[0] or 0)
        return (b + a) / 2 if b > 0 and a > 0 else l
    c, p = mid(calls), mid(puts)
    if not c or not p:
        return None
    return {"move": (c + p) / price, "expiry": exps[0]}


# ----------------------------------------------------------------------------- outcomes
def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return default


def key_of(e):
    return f'{e["t"]}|{e["date"]}'


SNAP_KEYS = ("t", "name", "sector", "date", "when", "when_guess", "cap", "eps_est", "watch", "stats", "sym",
             "implied", "pre_now", "price", "comment", "tags")


def snapshot(e):
    return {k: e[k] for k in SNAP_KEYS if k in e}


def slim(item):
    """old history rows: keep only what the scorecard needs"""
    return {k: item[k] for k in ("t", "date", "when", "cap", "implied", "tags", "res", "checks", "eps_est", "late") if k in item}


def outcome(item, px, spy, ev, today, now_ny):
    """actual result of a past report, or None while the reaction session hasn't closed yet"""
    t = item["t"]
    if t not in px or spy is None:
        return None
    d = px[t]
    idx, c, o = d.index, d["Close"].values, d["Open"].values
    after = {"pre": False, "post": True}.get(item.get("when"))
    if item.get("when_guess"):
        after = None
    r = react_pos(idx, o, c, pd.Timestamp(item["date"]), after)
    if r is None or r < 1:
        return None
    rday = idx[r].date()
    if rday > today or (rday == today and now_ny.hour * 60 + now_ny.minute < 16 * 60 + 20):
        return None                              # today's bar is still moving
    sc = spy.reindex(idx)["Close"].values
    if np.isnan(sc[[r - 1, r]]).any():
        return None
    raw = c[r] / c[r - 1] - 1
    res = {"day": str(rday), "raw": round(float(raw), 4), "ex": round(float(raw - (sc[r] / sc[r - 1] - 1)), 4),
           "gap": round(float(o[r] / c[r - 1] - 1), 4)}
    for e in ev or []:
        if e["eps"] is not None and abs((e["day"].date() - dt.date.fromisoformat(item["date"])).days) <= 3:
            res.update({"eps": e["eps"], "est": e["est"], "surprise": None if e["surprise"] is None else round(e["surprise"], 1)})
            break
    return res


CHECKS = {
    "vol": "实际波动没超出期权定价",
    "sell_news": "「利好出尽型」超预期后跑输大盘",
    "runup": "「已提前炒作」财报日跑输大盘",
    "up": "「财报日常涨」当天跑赢大盘",
    "down": "「财报日常跌」当天跑输大盘",
    "big": "「大波动」当天相对大盘波动超过 5%",
}


def checks_for(item):
    r, tags, out = item["res"], item.get("tags") or [], []
    sur = r.get("surprise")
    im = item.get("implied")
    if im:
        out.append({"k": "vol", "ok": abs(r["raw"]) <= im["move"],
                    "txt": f"实际波动 ±{abs(r['raw']) * 100:.1f}%，期权定价 ±{im['move'] * 100:.1f}%"})
    if "利好出尽型" in tags and sur is not None and sur > 0:
        out.append({"k": "sell_news", "ok": r["ex"] < 0, "txt": "利好出尽：" + ("应验，超预期但跑输大盘" if r["ex"] < 0 else "没应验，超预期并且跑赢大盘")})
    if "已提前炒作" in tags:
        out.append({"k": "runup", "ok": r["ex"] < 0, "txt": "提前炒作后回吐：" + ("应验" if r["ex"] < 0 else "没应验")})
    if "财报日常涨" in tags:
        out.append({"k": "up", "ok": r["ex"] > 0, "txt": "财报日常涨：" + ("应验" if r["ex"] > 0 else "没应验")})
    if "财报日常跌" in tags:
        out.append({"k": "down", "ok": r["ex"] < 0, "txt": "财报日常跌：" + ("应验" if r["ex"] < 0 else "没应验")})
    if "大波动" in tags:
        out.append({"k": "big", "ok": abs(r["ex"]) >= 0.05, "txt": "大波动：" + ("应验" if abs(r["ex"]) >= 0.05 else "这次波动不大")})
    return out


def scorecard(hist):
    done = [h for h in hist.values() if h.get("res") and not h.get("late")]
    if not done:
        return {"n": 0, "rows": []}
    ex = [h["res"]["ex"] for h in done]
    beats = [h for h in done if (h["res"].get("surprise") or 0) > 0]
    base = {
        "vol": None,
        "sell_news": float(np.mean([h["res"]["ex"] < 0 for h in beats])) if beats else None,
        "runup": float(np.mean([x < 0 for x in ex])), "down": float(np.mean([x < 0 for x in ex])),
        "up": float(np.mean([x > 0 for x in ex])), "big": float(np.mean([abs(x) >= 0.05 for x in ex])),
    }
    rows = []
    for k, label in CHECKS.items():
        cs = [c for h in done for c in (h.get("checks") or []) if c["k"] == k]
        if cs:
            rows.append({"k": k, "label": label, "n": len(cs), "hit": round(sum(c["ok"] for c in cs) / len(cs), 3),
                         "base": None if base[k] is None else round(base[k], 3)})
    first = min(h["date"] for h in done)
    return {"n": len(done), "since": first, "rows": rows}


# ----------------------------------------------------------------------------- commentary
def pct(x, d=1):
    return f"{x * 100:+.{d}f}%"


def comment(e):
    s, lines, tags = e.get("stats"), [], []
    if not s:
        return ["历史财报样本不足，无法给出统计评语。"], ["样本不足"]
    hist = s["avg_abs"]
    raw = s.get("avg_abs_raw", hist)
    if e.get("implied"):
        # the straddle prices the stock's own move, so compare it with the plain (not market-adjusted) history
        im = e["implied"]["move"]
        ratio = im / raw if raw else 1
        lines.append(f"期权为这次财报定价 ±{im * 100:.1f}% 的波动，过去 {s['n']} 次财报日平均实际波动 ±{raw * 100:.1f}%"
                     + ("，期权偏贵（市场押注这次波动更大）。" if ratio > 1.25 else "，期权偏便宜（市场可能低估了波动）。" if ratio < 0.8 else "，定价和历史差不多。"))
    else:
        lines.append(f"过去 {s['n']} 次财报日平均波动 ±{raw * 100:.1f}%（扣除大盘后 ±{hist * 100:.1f}%），最大一次相对大盘 {s['max_abs'] * 100:.1f}%。")
    if hist >= 0.07:
        tags.append("大波动")
    if s["beats"] >= 3:
        rate = s["beat_fell"] / s["beats"]
        few = s["beats"] < 6
        lines.append(f"业绩超预期 {s['beats']} 次，其中 {s['beat_fell']} 次股价反而跑输大盘（利好兑现下跌率 {rate * 100:.0f}%）。"
                     + ("样本太少，仅供参考。" if few else
                        "典型「利好出尽」型：好消息常常早已被价格消化。" if rate >= 0.45 else "超预期后通常能兑现上涨。" if rate <= 0.25 else ""))
        if rate >= 0.45 and not few:
            tags.append("利好出尽型")
    pre_now = e.get("pre_now")
    if pre_now is not None:
        msg = f"财报前 10 个交易日相对大盘 {pct(pre_now)}"
        if s["hot_n"] >= 2 and s["hot_avg"] is not None:
            msg += f"；历史上财报前先涨超 3% 的 {s['hot_n']} 次里，财报当天平均 {pct(s['hot_avg'])}"
            if pre_now > 0.03 and s["hot_avg"] < 0:
                msg += "，这次也已提前走强，小心提前透支。"
                tags.append("已提前炒作")
            else:
                msg += "。"
        else:
            msg += "。"
        lines.append(msg)
    if s["corr_pre_move"] is not None and s["corr_pre_move"] <= -0.3:
        lines.append(f"财报前涨幅和财报日表现呈负相关（相关系数 {s['corr_pre_move']:.2f}）：之前涨得越多，发布后越容易跌。")
    if abs(s["avg_drift"]) >= 0.01:
        lines.append(f"财报后 5 个交易日平均再{'涨' if s['avg_drift'] > 0 else '跌'} {abs(s['avg_drift']) * 100:.1f}%（相对大盘）"
                     + ("，有财报后漂移效应。" if s["avg_drift"] > 0 else "，发布后容易继续回吐。"))
    if s["n"] >= 8:
        if s["up_rate"] >= 0.7:
            tags.append("财报日常涨")
        elif s["up_rate"] <= 0.3:
            tags.append("财报日常跌")
    return lines, tags


# ----------------------------------------------------------------------------- demo data
def demo_inputs(days, past):
    rng = np.random.default_rng(3)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=1000)
    names = ["SPY"] + [f"D{i:02d}" for i in range(40)]
    px = {}
    for k, t in enumerate(names):
        r = rng.normal(0.0004, 0.012 if t == "SPY" else 0.018, len(idx))
        c = 100 * np.exp(np.cumsum(r))
        o = c * (1 + rng.normal(0, 0.004, len(idx)))
        px[t] = pd.DataFrame({"Open": o, "Close": c}, index=idx)
    # quarterly earnings with a sympathy relation D00 -> D01, D02; D06..D11 already reported in the past window
    evs = {}
    alld = past + days
    earn = []
    for i in range(12):
        t = f"D{i:02d}"
        date = past[i % len(past)] if i >= 6 else days[i % len(days)]
        earn.append({"t": t, "name": f"Demo Corp {i}", "date": date.isoformat(), "when": ["pre", "post", ""][i % 3],
                     "cap": 5e10 + i * 1e10, "eps_est": 1.2 + i / 10, "n_est": 12, "last_eps": 1.0, "fq": "Sep/2026"})
    for e in earn:
        t, ev = e["t"], []
        for q in range(14):
            if q == 0:
                d0 = pd.Timestamp(e["date"])
                if d0 > idx[-2]:
                    continue
                pos = idx.get_loc(d0) + (0 if e["when"] == "pre" else 1)
                day = d0
            else:
                pos = len(idx) - (q * 63 + 20)
                day = idx[pos]
            jump = rng.normal(0.0, 0.07)
            px[t].iloc[pos:, 1] *= (1 + jump)
            px[t].iloc[pos, 0] = px[t].iloc[pos - 1, 1] * (1 + jump * 0.8)
            if t == "D00":
                for s, b in (("D01", 0.6), ("D02", 0.45)):
                    px[s].iloc[pos:, 1] *= (1 + b * jump + rng.normal(0, 0.01))
            ev.append({"day": day, "after": {"pre": False, "post": True}.get(e["when"]), "surprise": float(rng.normal(3, 6)),
                       "eps": 1.3, "est": 1.25})
        evs[t] = ev
    macro = [{"date": days[1].isoformat(), "time": "12:30", "name": "CPI (MoM) (Sep)", "actual": "", "consensus": "0.3%", "previous": "0.4%"},
             {"date": days[1].isoformat(), "time": "12:30", "name": "Core CPI (YoY) (Sep)", "actual": "", "consensus": "3.1%", "previous": "3.2%"},
             {"date": days[3].isoformat(), "time": "12:30", "name": "Initial Jobless Claims", "actual": "", "consensus": "225K", "previous": "231K"},
             {"date": past[-1].isoformat(), "time": "12:30", "name": "Retail Sales (MoM) (Sep)", "actual": "0.6%", "consensus": "0.3%", "previous": "0.1%"},
             {"date": past[-2].isoformat(), "time": "12:30", "name": "Initial Jobless Claims", "actual": "219K", "consensus": "225K", "previous": "231K"},
             {"date": days[4].isoformat(), "time": "12:30", "name": "Nonfarm Payrolls (Sep)", "actual": "", "consensus": "120K", "previous": "142K"}]
    meta = {t: {"name": f"Demo Corp {t[1:]}", "sector": "Tech"} for t in names}
    return earn, macro, px, evs, meta


# ----------------------------------------------------------------------------- main
def enrich(e, px, spy, evmap, excess, meta, watch, today, live):
    t = e["t"]
    e["name"] = e["name"] or meta.get(t, {}).get("name", "")
    e["sector"] = meta.get(t, {}).get("sector", "")
    e["watch"] = t in watch
    if t in px and spy is not None and evmap.get(t):
        rows = reaction_stats(evmap[t], px[t], spy)
        e["stats"] = summarize(rows)
        if e["stats"]:
            e["sym"] = sympathy(t, rows, excess, meta)
            if not e.get("when"):
                a = e["stats"]["after_share"]
                if a >= 0.75 or a <= 0.25:
                    e["when"], e["when_guess"] = ("post" if a >= 0.75 else "pre"), True
        d = px[t]
        if len(d) > 11:
            sc = spy.reindex(d.index)["Close"]
            e["pre_now"] = float(d["Close"].iloc[-1] / d["Close"].iloc[-11] - 1 - (sc.iloc[-1] / sc.iloc[-11] - 1))
            e["price"] = round(float(d["Close"].iloc[-1]), 2)
    if live and e.get("price") and 0 <= (dt.date.fromisoformat(e["date"]) - today).days <= 7:
        try:
            im = implied_move(t, react_date(e), e["price"])
            if im:
                e["implied"] = {"move": round(im["move"], 4), "expiry": im["expiry"]}
        except Exception as ex:  # noqa: BLE001
            print("options", t, ex)
    if not live and e.get("stats") and e["t"] in ("D00", "D03", "D06", "D07", "D09"):
        e["implied"] = {"move": round(e["stats"]["avg_abs_raw"] * (1.5 if e["t"] in ("D00", "D06") else 0.7), 4), "expiry": e["date"]}
    e["comment"], e["tags"] = comment(e)
    return e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()
    live = not args.demo
    now_ny = dt.datetime.now(NY)
    today = now_ny.date()
    days = business_days(today, DAYS_AHEAD)
    past = []
    d = today
    while len(past) < PAST_DAYS:
        d -= dt.timedelta(days=1)
        if d.weekday() < 5:
            past.insert(0, d)

    hist = {} if args.demo else load_json(HIST, {})
    if not args.demo:
        # seed from the previous output: any call it made before that report's reaction session opened
        prev = load_json(OUT, {})
        try:
            pgen = dt.datetime.strptime(prev.get("generated", ""), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
        except ValueError:
            pgen = None
        for pd_ in (prev.get("days") or []) if pgen and not prev.get("demo") else []:
            for e in pd_.get("earnings") or []:
                k = key_of(e)
                if k in hist or "res" in e:
                    continue
                if pgen < dt.datetime.combine(react_date(e), dt.time(9, 30), NY):
                    hist[k] = snapshot(e)
                else:   # the call was made after the market already reacted → show the result, never score it
                    hist[k] = {x: e[x] for x in ("t", "name", "sector", "date", "when", "cap", "eps_est", "watch") if x in e}
                    hist[k]["late"] = True
    if args.demo:
        earn, raw_macro, px, evmap, meta = demo_inputs(days, past)
        watch = set()
    else:
        meta, watch = load_universe()
        earn = nasdaq_earnings(days)
        DIAG["nasdaq_earnings_rows"] = len(earn)
        raw_macro = nasdaq_macro(past + days)
        DIAG["nasdaq_macro_rows"] = len(raw_macro)
        if not earn:
            earn = yf_earnings_fallback(sorted(set(meta) | watch), days)
            DIAG["yf_fallback_rows"] = len(earn)
    uni = set(meta) | watch
    earn = [e for e in earn if e["t"] in uni or (e["cap"] or 0) >= MIN_CAP]
    seen, dedup = set(), []
    for e in sorted(earn, key=lambda x: -(x["cap"] or 0)):
        if e["t"] not in seen:
            seen.add(e["t"])
            dedup.append(e)
    earn = dedup[:MAX_REPORTERS]
    DIAG["reporters"] = len(earn)

    # history rows whose result is still missing (price or EPS)
    pending = [h for h in hist.values() if not (h.get("res") and h["res"].get("eps") is not None)
               and (today - dt.date.fromisoformat(h["date"])).days <= 10]
    if live:
        px = download(sorted(set(meta) | {e["t"] for e in earn} | {h["t"] for h in pending} | {"SPY"}))
        evmap = {}
        for t in sorted({e["t"] for e in earn} | {h["t"] for h in pending}):
            try:
                evmap[t] = past_earnings(t)
            except Exception as ex:  # noqa: BLE001
                print("earnings history", t, ex)
            time.sleep(0.3)
    spy = px.get("SPY")
    rets = pd.DataFrame({t: d["Close"].pct_change() for t, d in px.items()})
    excess = rets.sub(rets["SPY"], axis=0) if "SPY" in rets else rets

    for e in earn:
        enrich(e, px, spy, evmap, excess, meta, watch, today, live)
        # keep the latest pre-release prediction; freeze it once the reaction session opens
        k = key_of(e)
        opens = dt.datetime.combine(react_date(e), dt.time(9, 30), NY)
        if now_ny < opens and not (hist.get(k) or {}).get("res"):
            hist[k] = snapshot(e)
        elif k not in hist and args.demo:
            hist[k] = snapshot(e)

    # results for everything that has already reported
    filled = 0
    for k, h in hist.items():
        if h.get("res") and h["res"].get("eps") is not None:
            continue
        if (today - dt.date.fromisoformat(h["date"])).days > 10:
            continue
        r = outcome(h, px, spy, evmap.get(h["t"]), today, now_ny)
        if r:
            h["res"] = r
            h["checks"] = checks_for(h)
            filled += 1
    DIAG["results_filled"] = filled

    # prune: full detail for two weeks, a slim row for a year
    for k in list(hist):
        age = (today - dt.date.fromisoformat(hist[k]["date"])).days
        if age > 400:
            del hist[k]
        elif age > 14:
            hist[k] = slim(hist[k])

    macro = group_macro(raw_macro, past + days)
    out_days = []
    for d in days:
        ds = d.isoformat()
        ers = []
        for e in earn:
            if e["date"] != ds:
                continue
            h = hist.get(key_of(e))
            ers.append(h if h and h.get("res") else e)   # already reported today → show the frozen call + result
        out_days.append({"date": ds, "macro": [m for m in macro if m["date"] == ds],
                         "earnings": sorted(ers, key=lambda x: -(x.get("cap") or 0))})
    out_past = []
    for d in past:
        ds = d.isoformat()
        ers = [h for h in hist.values() if h["date"] == ds]
        out_past.append({"date": ds, "macro": [m for m in macro if m["date"] == ds],
                         "earnings": sorted(ers, key=lambda x: -(x.get("cap") or 0))})
    res = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "demo": bool(args.demo),
           "days": out_days, "past": out_past, "score": scorecard(hist), "diag": DIAG}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, separators=(",", ":"), default=lambda o: None)
    if live:
        with open(HIST, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, separators=(",", ":"), default=lambda o: None)
    print(f"{len(earn)} reporters, {len(macro)} macro events, {len(hist)} history rows; diag={DIAG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
