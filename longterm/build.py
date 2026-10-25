#!/usr/bin/env python3
"""
长线池 (weekly, GitHub Actions)

Scores every S&P 500 / Nasdaq-100 stock with the long-term framework from voo_long_term.py:
  moat 0–35       quality (60% ROIC + 40% ROE), gross margin, operating-margin stability
  valuation 0–25  trailing P/E vs a fair multiple = average of the stock's own median annual P/E and
                  today's median P/E of its sector (Yahoo has only ~4 years of statements, a window that
                  includes the 2021 peak and the 2022 earnings dip, so the own-history median alone runs high)
  technical 0–20  above 200-day, 50 > 200, 6-month relative strength
  drawdown 0–10   distance from the 52-week high (a 10–30% pullback in a good business scores best)
  growth 0–10     revenue CAGR over the available annual statements
  debt penalty    net debt / EBITDA above 2× (financials exempt)
Grades: S ≥ 80, A ≥ 70, B ≥ 60, C ≥ 50, D below.

Every week's S/A list is saved; each name is then tracked from the week it first appeared against VOO
over the same period, and names already on the list are flagged for review when the P/E has returned
above its median or the grade has slipped below B.

Yahoo's free data only has ~4–5 years of annual statements, so the median P/E is short-history.

Offline test:  python longterm/build.py --demo
"""
import argparse
import datetime as dt
import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")
HIST = os.path.join(DATA, "history")
OUT = os.path.join(DATA, "latest.json")
CACHE = os.path.join(DATA, "fund_cache.json")
UNIVERSE = os.path.join(ROOT, "stocks", "universe.json")
WATCHLIST = os.path.join(ROOT, "stocks", "watchlist.txt")
BENCH = "VOO"
CACHE_DAYS = 6          # refetch statements older than this
DIAG = {}


# ----------------------------------------------------------------------------- data
def load_universe():
    meta = {}
    if os.path.exists(UNIVERSE):
        with open(UNIVERSE, encoding="utf-8") as f:
            meta = json.load(f)
    if os.path.exists(WATCHLIST):
        with open(WATCHLIST, encoding="utf-8") as f:
            for line in f:
                s = line.split("#")[0].strip().upper().replace(".", "-")
                if s and s not in meta:
                    meta[s] = {"name": "", "sector": ""}
    return meta


def download(tickers, period="6y"):
    import yfinance as yf
    out = {}
    for i in range(0, len(tickers), 100):
        part = tickers[i:i + 100]
        for attempt in range(3):
            try:
                df = yf.download(part, period=period, interval="1d", auto_adjust=True, group_by="ticker", threads=True, progress=False)
                break
            except Exception as e:  # noqa: BLE001
                print("download retry", attempt, e)
                time.sleep(5)
        else:
            continue
        for t in part:
            try:
                d = df[t] if isinstance(df.columns, pd.MultiIndex) else df
                c = d["Close"].dropna()
                if len(c) > 260:
                    c.index = pd.to_datetime(c.index).tz_localize(None).normalize()
                    out[t] = c
            except Exception:  # noqa: BLE001
                pass
    return out


def row(df, *names):
    """first matching statement line as {year-end Timestamp: value}, oldest first"""
    if df is None or getattr(df, "empty", True):
        return {}
    for n in names:
        if n in df.index:
            s = pd.to_numeric(df.loc[n], errors="coerce").dropna()
            return {pd.Timestamp(k): float(v) for k, v in sorted(s.items())}
    return {}


def fetch_fund(t):
    import yfinance as yf
    tk = yf.Ticker(t)
    info = {}
    try:
        info = tk.info or {}
    except Exception as e:  # noqa: BLE001
        print("info", t, e)
    inc = tk.income_stmt
    bal = tk.balance_sheet
    f = {
        "name": info.get("shortName") or info.get("longName") or "",
        "sector": info.get("sector") or "",
        "ttm_eps": info.get("trailingEps"), "cap": info.get("marketCap"),
        "total_debt": info.get("totalDebt"), "total_cash": info.get("totalCash"), "ebitda": info.get("ebitda"),
        "rev": row(inc, "Total Revenue", "Operating Revenue"),
        "gp": row(inc, "Gross Profit"),
        "op": row(inc, "Operating Income", "EBIT"),
        "ebit": row(inc, "EBIT", "Operating Income"),
        "ni": row(inc, "Net Income Common Stockholders", "Net Income"),
        "eps": row(inc, "Diluted EPS", "Basic EPS"),
        "tax": row(inc, "Tax Rate For Calcs"),
        "eq": row(bal, "Stockholders Equity", "Common Stock Equity"),
        "ic": row(bal, "Invested Capital"),
    }
    for k in ("rev", "gp", "op", "ebit", "ni", "eps", "tax", "eq", "ic"):
        f[k] = {str(d.date()): v for d, v in f[k].items()}
    f["fetched"] = dt.date.today().isoformat()
    return f


def fundamentals(tickers):
    cache = {}
    if os.path.exists(CACHE):
        try:
            with open(CACHE, encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:  # noqa: BLE001
            cache = {}
    today = dt.date.today()
    todo = [t for t in tickers if t not in cache or (today - dt.date.fromisoformat(cache[t].get("fetched", "2000-01-01"))).days > CACHE_DAYS]
    DIAG["fund_fetch"] = len(todo)
    fails = 0
    for i, t in enumerate(todo):
        try:
            cache[t] = fetch_fund(t)
        except Exception as e:  # noqa: BLE001
            fails += 1
            print("fund", t, e)
        time.sleep(0.6)
        if i % 50 == 0:
            print(f"fundamentals {i}/{len(todo)}")
            with open(CACHE, "w", encoding="utf-8") as f:
                json.dump(cache, f, separators=(",", ":"))
    DIAG["fund_fail"] = fails
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, separators=(",", ":"))
    return cache


# ----------------------------------------------------------------------------- scoring
def ser(d):
    return pd.Series({pd.Timestamp(k): v for k, v in (d or {}).items()}, dtype=float).sort_index()


def price_on(px, day):
    s = px[px.index <= day]
    return float(s.iloc[-1]) if len(s) else None


def lin(x, x0, x1, y0, y1):
    """linear map clamped to [min(y0,y1), max(y0,y1)]"""
    if x is None or x != x:
        return None
    t = (x - x0) / (x1 - x0)
    return max(min(y0, y1), min(max(y0, y1), y0 + t * (y1 - y0)))


def score_one(t, f, px, rs6, sector, sec_pe):
    rev, gp, op, ebit, ni, eps, tax, eq, ic = (ser(f.get(k)) for k in ("rev", "gp", "op", "ebit", "ni", "eps", "tax", "eq", "ic"))
    fin = sector in ("Financials", "Financial Services")
    price = float(px.iloc[-1])
    out = {"t": t, "price": round(price, 2), "parts": {}, "why": [], "warn": []}
    # 缺数据的统一规则：核心指标（资本回报率、估值）缺了给 0 分，并且最高只能评 C；
    # 次要指标（毛利率、利润率稳定性、收入增长、负债）缺了给该项一半的分，并在提示里写明缺了什么。
    missing = []

    # ---- moat 0–35
    roic = None
    if len(ebit) and len(ic):
        yrs = sorted(set(ebit.index) & set(ic.index))[-3:]
        vals = []
        for y in yrs:
            tr = tax.get(y, 0.21) if len(tax) else 0.21
            tr = 0.21 if tr != tr or tr < 0 or tr > 0.5 else tr
            if ic[y] > 0:
                vals.append(ebit[y] * (1 - tr) / ic[y])
        roic = float(np.mean(vals)) if vals else None
    roe = None
    if len(ni) and len(eq):
        yrs = sorted(set(ni.index) & set(eq.index))[-3:]
        vals = [ni[y] / eq[y] for y in yrs if eq[y] > 0]
        roe = float(min(np.mean(vals), 0.6)) if vals and len(vals) == len(yrs) else None   # negative equity → ROE meaningless
    if roic is not None and roe is not None and not fin:
        q = 0.6 * roic + 0.4 * roe
    elif fin and roe is not None:
        q = roe                                      # banks: invested capital is not meaningful
    else:
        q = roic if roic is not None else roe
    qpts = 0 if q is None else 20 if q >= 0.25 else 15 if q >= 0.15 else 9 if q >= 0.10 else 4 if q >= 0.05 else 0
    gm = None
    if len(gp) and len(rev):
        y = sorted(set(gp.index) & set(rev.index))
        if y and rev[y[-1]] > 0:
            gm = gp[y[-1]] / rev[y[-1]]
    if gm is None and not fin:
        missing.append("毛利率")
    gpts = 4 if gm is None else 8 if gm >= 0.6 else 6 if gm >= 0.4 else 3 if gm >= 0.25 else 0
    opm = None
    spts = 0
    if len(op) and len(rev):
        y = sorted(set(op.index) & set(rev.index))
        m = np.array([op[k] / rev[k] for k in y if rev[k] > 0])
        if len(m) >= 3:
            opm = float(m[-1])
            spts = 7 if (m > 0).all() and m.std() < 0.05 else 4 if (m > 0).all() else 0
    if opm is None:
        if not fin:
            missing.append("利润率历史")
        spts = 3.5
    if q is None:
        missing.append("资本回报率")
    moat = qpts + gpts + spts      # 银行保险没有毛利率这类指标：按「次要指标给一半」处理，但不算缺数据
    out["parts"]["moat"] = moat
    out.update({"roic": None if roic is None else round(roic, 3), "roe": None if roe is None else round(roe, 3),
                "q": None if q is None else round(q, 3), "gm": None if gm is None else round(gm, 3), "opm": None if opm is None else round(opm, 3)})
    if q is not None and q >= 0.15:
        out["why"].append(f"资本回报率 {q * 100:.0f}%")
    if spts == 7:
        out["why"].append("利润率常年稳定")

    # ---- valuation 0–25: trailing P/E vs its own median annual P/E
    pes = []
    for y, e in eps.items():
        p = price_on(px, y)
        if e > 0 and p:
            pes.append(p / e)
    ttm = f.get("ttm_eps")
    pe = price / ttm if ttm and ttm > 0 else None
    med_pe = float(np.median(pes)) if len(pes) >= 3 else None
    anchors = [x for x in (med_pe, sec_pe) if x]
    fair_pe = float(np.mean(anchors)) if anchors else None
    vpts = 0
    if pe and fair_pe:
        ratio = pe / fair_pe
        vpts = round(lin(ratio, 0.7, 1.3, 25, 0), 1)
        out["fair"] = round(fair_pe * ttm, 2)
        out["disc"] = round(ratio - 1, 4)
        if ratio <= 0.85:
            out["why"].append(f"市盈率 {pe:.0f}，比合理市盈率 {fair_pe:.0f} 低 {(1 - ratio) * 100:.0f}%")
        elif ratio >= 1.15:
            out["warn"].append(f"市盈率 {pe:.0f} 高于合理市盈率 {fair_pe:.0f}")
    elif pe is None:
        out["warn"].append("最近一年亏损或没有盈利数据")
    else:
        out["warn"].append("没有可比的估值数据")
    out["parts"]["value"] = vpts
    out.update({"pe": None if pe is None else round(pe, 1), "med_pe": None if med_pe is None else round(med_pe, 1), "pe_n": len(pes),
                "sec_pe": None if not sec_pe else round(sec_pe, 1), "fair_pe": None if fair_pe is None else round(fair_pe, 1)})

    # ---- technical 0–20
    s200 = px.rolling(200).mean().iloc[-1]
    s50 = px.rolling(50).mean().iloc[-1]
    tpts = float((8 if price > s200 else 0) + (6 if s50 > s200 else 0) + round(6 * float(rs6 or 0), 1))
    out["parts"]["tech"] = tpts

    # ---- drawdown 0–10
    hi = float(px.iloc[-252:].max())
    dd = 1 - price / hi
    dpts = 10 if 0.10 <= dd <= 0.30 else 6 if 0.05 <= dd < 0.10 else 4 if dd > 0.30 else 3
    out["parts"]["dd"] = dpts
    out["dd"] = round(dd, 4)
    if 0.10 <= dd <= 0.30 and moat >= 25:
        out["why"].append(f"好公司回调 {dd * 100:.0f}%")

    # ---- growth 0–10
    cagr = None
    if len(rev) >= 3 and rev.iloc[0] > 0 and rev.iloc[-1] > 0:
        yrs = (rev.index[-1] - rev.index[0]).days / 365.25
        cagr = (rev.iloc[-1] / rev.iloc[0]) ** (1 / yrs) - 1 if yrs > 0.9 else None
    if cagr is None:
        missing.append("收入增长")
    gpts2 = 5 if cagr is None else 10 if cagr >= 0.15 else 7 if cagr >= 0.08 else 4 if cagr >= 0.03 else 2 if cagr >= 0 else 0
    out["parts"]["growth"] = gpts2
    out["cagr"] = None if cagr is None else round(cagr, 3)
    if cagr is not None and cagr >= 0.12:
        out["why"].append(f"收入年增 {cagr * 100:.0f}%")

    # ---- debt penalty
    pen = 0
    nde = None
    if not fin and f.get("ebitda") and f["ebitda"] > 0 and f.get("total_debt") is not None:
        nde = ((f.get("total_debt") or 0) - (f.get("total_cash") or 0)) / f["ebitda"]
        pen = -10 if nde > 3 else -5 if nde > 2 else 0
        if pen:
            out["warn"].append(f"净负债是 EBITDA 的 {nde:.1f} 倍")
    if nde is None and not fin:
        missing.append("负债")
        pen = -2.5   # 负债情况不明：扣一半的轻度分（-5 的一半），不当成「没负债」
    out["parts"]["debt"] = pen
    out["nde"] = None if nde is None else round(nde, 2)

    sc = moat + vpts + tpts + dpts + gpts2 + pen
    out["score"] = round(float(sc), 1)
    grade = "S" if sc >= 80 else "A" if sc >= 70 else "B" if sc >= 60 else "C" if sc >= 50 else "D"
    if (q is None or not (pe and fair_pe)) and grade in ("S", "A", "B"):
        grade = "C"   # 核心数据不全，不给高评级
        out["warn"].append("核心数据不全，评级最高给到 C")
    out["grade"] = grade
    if missing:
        out["warn"].append("缺数据：" + "、".join(missing))
    out["missing"] = missing
    out["data_ok"] = q is not None and len(rev) >= 3
    return out


# ----------------------------------------------------------------------------- tracking
def track(px, bench, today, current):
    """each name from the week it first made the S/A list (consecutive weeks merge), vs VOO"""
    if not os.path.isdir(HIST) or bench is None:
        return {"rows": [], "summary": {}}
    files = sorted(f for f in os.listdir(HIST) if f.endswith(".json") and f[:-5] < today)
    first = {}
    for fn in files:
        try:
            with open(os.path.join(HIST, fn), encoding="utf-8") as f:
                h = json.load(f)
        except Exception:  # noqa: BLE001
            continue
        for r in h.get("list", []):
            first.setdefault(r["t"], (h["date"], r["price"], r["grade"]))
    rows = []
    for t, (d0, p0, g0) in first.items():
        if t not in px:
            continue
        b = bench[bench.index > pd.Timestamp(d0)]
        if b.empty:
            continue
        b0 = price_on(bench, pd.Timestamp(d0))
        ret = float(px[t].iloc[-1]) / p0 - 1
        bret = float(bench.iloc[-1]) / b0 - 1 if b0 else None
        cur = current.get(t)
        rows.append({"t": t, "since": d0, "grade0": g0, "grade": cur["grade"] if cur else None, "ret": round(ret, 4),
                     "voo": None if bret is None else round(bret, 4), "still": bool(cur and cur["grade"] in ("S", "A"))})
    rows.sort(key=lambda r: r["since"])
    summ = {}
    if rows:
        ex = [r["ret"] - r["voo"] for r in rows if r["voo"] is not None]
        summ = {"n": len(rows), "mean": float(np.mean([r["ret"] for r in rows])), "vs_voo": float(np.mean(ex)) if ex else None,
                "beat": float(np.mean([x > 0 for x in ex])) if ex else None, "since": rows[0]["since"]}
    return {"rows": rows, "summary": summ}


# ----------------------------------------------------------------------------- demo
def demo():
    rng = np.random.default_rng(5)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=1500)
    meta, px, fund = {}, {}, {}
    secs = ["Information Technology", "Health Care", "Financials", "Industrials", "Consumer Staples"]
    for i in range(60):
        t = f"L{i:02d}"
        r = rng.normal(0.0004, 0.016, len(idx))
        c = pd.Series(80 * np.exp(np.cumsum(r)), index=idx)
        px[t] = c
        meta[t] = {"name": f"Demo Long {i}", "sector": secs[i % 5]}
        years = [idx[-1] - pd.DateOffset(years=k) for k in (4, 3, 2, 1)]
        base_rev = rng.uniform(5e9, 5e10)
        g = rng.normal(0.08, 0.06)
        eps0 = c.iloc[-1] / rng.uniform(12, 35)
        fund[t] = {
            "name": f"Demo Long {i}", "sector": secs[i % 5], "ttm_eps": float(eps0), "cap": 1e11,
            "total_debt": 2e10, "total_cash": 5e9, "ebitda": float(rng.uniform(2e9, 2e10)),
            "rev": {str(y.date()): base_rev * (1 + g) ** k for k, y in enumerate(years)},
            "gp": {str(y.date()): base_rev * (1 + g) ** k * rng.uniform(0.3, 0.7) for k, y in enumerate(years)},
            "op": {str(y.date()): base_rev * (1 + g) ** k * rng.uniform(0.08, 0.3) for k, y in enumerate(years)},
            "ebit": {str(y.date()): base_rev * (1 + g) ** k * 0.2 for k, y in enumerate(years)},
            "ni": {str(y.date()): base_rev * (1 + g) ** k * 0.14 for k, y in enumerate(years)},
            "eps": {str(y.date()): float(eps0 * rng.uniform(0.7, 1.1)) for y in years},
            "tax": {}, "eq": {str(y.date()): base_rev * rng.uniform(0.4, 1.2) for y in years},
            "ic": {str(y.date()): base_rev * rng.uniform(0.6, 1.5) for y in years},
        }
    px[BENCH] = pd.Series(300 * np.exp(np.cumsum(rng.normal(0.0004, 0.011, len(idx)))), index=idx)
    return meta, px, fund


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()
    os.makedirs(HIST, exist_ok=True)
    if args.demo:
        meta, px, fund = demo()
    else:
        meta = load_universe()
        tickers = sorted(meta)
        px = download(tickers + [BENCH])
        DIAG["prices"] = len(px)
        fund = fundamentals([t for t in tickers if t in px])
    bench = px.get(BENCH)
    # 6-month return percentile across the pool
    r6 = pd.Series({t: float(c.iloc[-1] / c.iloc[-127] - 1) for t, c in px.items() if t != BENCH and len(c) > 130})
    rs6 = r6.rank(pct=True)
    last = max(c.index[-1] for c in px.values())
    today = last.date().isoformat()

    # today's median P/E per sector (profitable companies, P/E under 150)
    by_sec = {}
    for t, f in fund.items():
        if t in px and f.get("ttm_eps") and f["ttm_eps"] > 0:
            pe = float(px[t].iloc[-1]) / f["ttm_eps"]
            if 0 < pe < 150:
                by_sec.setdefault(meta.get(t, {}).get("sector") or f.get("sector") or "", []).append(pe)
    sec_pe = {k: float(np.median(v)) for k, v in by_sec.items() if len(v) >= 5}
    DIAG["sector_pe"] = {k: round(v, 1) for k, v in sec_pe.items()}

    res = []
    for t in sorted(fund):
        if t not in px or t == BENCH:
            continue
        f = fund[t]
        sector = meta.get(t, {}).get("sector") or f.get("sector") or ""
        try:
            r = score_one(t, f, px[t], rs6.get(t), sector, sec_pe.get(sector))
        except Exception as e:  # noqa: BLE001
            print("score", t, e)
            continue
        r["name"] = meta.get(t, {}).get("name") or f.get("name", "")
        r["sector"] = sector
        r["cap"] = f.get("cap")
        res.append(r)
    res.sort(key=lambda r: -r["score"])
    # one line per company (GOOG/GOOGL, FOX/FOXA, NWS/NWSA …)
    seen, dedup = set(), []
    for r in res:
        k = (fund[r["t"]].get("name") or r["t"]).strip().lower()
        if k in seen:
            continue
        seen.add(k)
        dedup.append(r)
    res = dedup
    cur = {r["t"]: r for r in res}

    # review flags for names that were on an earlier list
    prev = set()
    if os.path.isdir(HIST):
        for fn in sorted(os.listdir(HIST)):
            if fn.endswith(".json") and fn[:-5] < today:
                try:
                    with open(os.path.join(HIST, fn), encoding="utf-8") as f:
                        prev |= {r["t"] for r in json.load(f).get("list", [])}
                except Exception:  # noqa: BLE001
                    pass
    review = []
    for t in sorted(prev):
        r = cur.get(t)
        if not r:
            continue
        why = []
        if r["grade"] not in ("S", "A", "B"):
            why.append(f"评分降到 {r['grade']} 级（{r['score']:.0f} 分）")
        if r.get("pe") and r.get("fair_pe") and r["pe"] >= r["fair_pe"] * 1.1:
            why.append(f"市盈率 {r['pe']:.0f} 已回到合理市盈率 {r['fair_pe']:.0f} 以上")
        if why:
            review.append({"t": t, "grade": r["grade"], "why": why})

    top = [r for r in res if r["grade"] in ("S", "A") and r["data_ok"]]
    tracking = track(px, bench, today, cur)
    counts = {g: sum(1 for r in res if r["grade"] == g) for g in "SABCD"}
    out = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "date": today, "demo": bool(args.demo),
           "n": len(res), "counts": counts, "list": top, "near": [r["t"] for r in top if (r.get("disc") is not None and r["disc"] <= 0)],
           "b_list": [{k: r.get(k) for k in ("t", "name", "sector", "score", "grade", "price", "disc", "pe", "med_pe")} for r in res if r["grade"] == "B"][:40],
           "review": review, "tracking": tracking, "diag": DIAG}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    if not args.demo:
        with open(os.path.join(HIST, today + ".json"), "w", encoding="utf-8") as f:
            json.dump({"date": today, "list": [{"t": r["t"], "price": r["price"], "grade": r["grade"], "score": r["score"]} for r in top]}, f)
    print(f"{today}: scored {len(res)}, grades {counts}, list {len(top)}, below fair {len(out['near'])}, review {len(review)}; diag={DIAG}")
    for r in top[:15]:
        print(f"  {r['t']:6s} {r['grade']} {r['score']:5.1f} {r['parts']} pe={r.get('pe')} fair={r.get('fair_pe')} disc={r.get('disc')} {r['why']} {r['warn']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
