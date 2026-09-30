#!/usr/bin/env python3
"""
每日短线股票池扫描器 (runs in GitHub Actions after the US close)

Universe : S&P 500 + Nasdaq-100 (+ stocks/watchlist.txt)
Data     : Yahoo Finance via yfinance (no API key needed)
Signals  : 回踩金坑 / 挤压突破 / 强势新高 / RSI2 超跌反弹 / 血筹码
Output   : stocks/data/latest.json (+ dated copy in stocks/data/history/)

Every signal's historical stats are computed on the same universe with strict
no-lookahead: signal uses data up to close t, forward return is close t -> close t+h.

Local test without network:  python stocks/scan.py --demo
"""
import argparse
import datetime as dt
import io
import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
HIST = os.path.join(DATA, "history")
UNIVERSE_CACHE = os.path.join(HERE, "universe.json")
WATCHLIST = os.path.join(HERE, "watchlist.txt")

MIN_PRICE = 10.0
MIN_DOLLAR_VOL = 20e6          # 20-day average dollar volume
STATS_YEARS = 2                # years of history used for signal statistics
MAX_PER_SIGNAL = 12
TRACK_DAYS = 20                # how many past trading days of picks to track

SIGNALS = {
    "squeeze": {
        "name": "挤压突破", "hold": "6–15 天", "horizon": 10,
        "desc": "布林带宽处于近 120 日最窄的 20%（波动收敛），今日放量（≥1.5 倍均量）收盘突破前 20 日高点，且相对强度排名 ≥ 60%。",
        "exit": "跌破止损离场；到达目标或持有 15 天后离场。",
    },
    "pit": {
        "name": "回踩金坑", "hold": "6–15 天", "horizon": 10,
        "desc": "上升趋势中（价格在 200 日线上方、EMA20 > EMA50），相对强度排名 ≥ 70%；近两日回踩 EMA20 后收回，今日收阳，RSI(14) 在 40–58 之间。",
        "exit": "跌破近 3 日低点离场；到达 2R 目标或持有 15 天后离场。",
    },
    "momentum": {
        "name": "强势新高", "hold": "5–15 天", "horizon": 10,
        "desc": "收盘创 55 日新高，放量（≥1.3 倍均量），相对强度排名前 15%，且距 EMA20 不超过 2.5 个 ATR（未过度延伸）。",
        "exit": "跌破 2 ATR 止损离场；持有 15 天或收盘跌破 EMA20 离场。",
    },
    "rsi2": {
        "name": "RSI2 超跌反弹", "hold": "2–7 天", "horizon": 5,
        "desc": "长期趋势向上（价格在 200 日线上方），但 RSI(2) < 10，短线被过度抛售（Connors 均值回归规则）。",
        "exit": "收盘站上 5 日均线即离场；最多持有 7 天。",
    },
    "blood": {
        "name": "血筹码", "hold": "最长 126 天", "horizon": 20,
        "desc": "你的 quant_system 规则：RSI(14) < 35，价格低于 EMA20 超过 5%，下影线占当日振幅 > 40%（恐慌后的承接）。",
        "exit": "−8% 止损，+20% 止盈，最长持有 126 天。",
    },
}
PRIORITY = ["squeeze", "pit", "momentum", "rsi2", "blood"]

FALLBACK_TICKERS = (
    "AAPL MSFT NVDA AMZN GOOGL META TSLA AVGO BRK-B JPM LLY V UNH XOM MA JNJ PG HD COST ABBV "
    "MRK ORCL CVX BAC KO PEP ADBE CRM NFLX AMD WMT TMO ACN MCD CSCO ABT LIN DHR INTU TXN "
    "QCOM WFC PM CAT IBM GE AMGN VZ NOW ISRG UNP SPGI GS HON AMAT BKNG PFE CMCSA LOW RTX "
    "T NEE UBER AXP BLK ELV SYK PGR MS TJX VRTX DE PLD C LMT ADP MDT BSX SCHW REGN MMC CB "
    "ADI PANW LRCX MU KLAC SBUX GILD BA CI SNPS CDNS MDLZ ANET SO DUK CRWD MELI PYPL ABNB"
).split()


# ----------------------------------------------------------------------------- universe
def http_get(url, timeout=30):
    import requests
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 (stock-scanner; GitHub Actions)"})
    r.raise_for_status()
    return r.text


def fetch_universe():
    meta = {}
    try:
        html = http_get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        t = pd.read_html(io.StringIO(html))[0]
        for _, row in t.iterrows():
            sym = str(row["Symbol"]).strip().replace(".", "-")
            meta[sym] = {"name": str(row.get("Security", "")), "sector": str(row.get("GICS Sector", ""))}
        print(f"S&P 500: {len(t)} tickers")
    except Exception as e:  # noqa: BLE001
        print("WARN: S&P 500 list fetch failed:", e)
    try:
        html = http_get("https://en.wikipedia.org/wiki/Nasdaq-100")
        for t in pd.read_html(io.StringIO(html)):
            cols = [str(c) for c in t.columns]
            tc = next((c for c in cols if c.lower() in ("ticker", "symbol")), None)
            if tc and len(t) > 90:
                nc = next((c for c in cols if c.lower() in ("company", "security")), None)
                sc = next((c for c in cols if "sector" in c.lower()), None)
                for _, row in t.iterrows():
                    sym = str(row[tc]).strip().replace(".", "-")
                    if sym not in meta:
                        meta[sym] = {"name": str(row[nc]) if nc else "", "sector": str(row[sc]) if sc else ""}
                print(f"Nasdaq-100: {len(t)} tickers")
                break
    except Exception as e:  # noqa: BLE001
        print("WARN: Nasdaq-100 list fetch failed:", e)

    if len(meta) >= 300:
        with open(UNIVERSE_CACHE, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=0, sort_keys=True)
    elif os.path.exists(UNIVERSE_CACHE):
        print("Using cached universe.json")
        with open(UNIVERSE_CACHE, encoding="utf-8") as f:
            meta = json.load(f)
    else:
        print("Using built-in fallback universe")
        meta = {t: {"name": "", "sector": ""} for t in FALLBACK_TICKERS}

    if os.path.exists(WATCHLIST):
        with open(WATCHLIST, encoding="utf-8") as f:
            for line in f:
                s = line.split("#")[0].strip().upper().replace(".", "-")
                if s and s not in meta:
                    meta[s] = {"name": "", "sector": "自选"}
    return meta


# ----------------------------------------------------------------------------- data
def download(tickers, period="3y"):
    import yfinance as yf
    out = {}
    chunk = 100
    for i in range(0, len(tickers), chunk):
        part = tickers[i:i + chunk]
        for attempt in range(3):
            try:
                df = yf.download(part, period=period, interval="1d", auto_adjust=True, group_by="ticker",
                                 threads=True, progress=False)
                break
            except Exception as e:  # noqa: BLE001
                print("download retry", attempt, e)
                time.sleep(5)
        else:
            continue
        for t in part:
            try:
                d = df[t] if isinstance(df.columns, pd.MultiIndex) else df
                d = d[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
                for c in ("Open", "High", "Low"):
                    d[c] = d[c].fillna(d["Close"])
                d["Volume"] = d["Volume"].fillna(0)
                if len(d) > 260:
                    out[t] = d
            except Exception:  # noqa: BLE001
                pass
        print(f"downloaded {min(i + chunk, len(tickers))}/{len(tickers)} -> {len(out)} ok")
    return out


def demo_data(n=90, days=780, seed=None):
    rng = np.random.default_rng(seed if seed is not None else 7)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    out, meta = {}, {}
    sectors = ["Information Technology", "Health Care", "Financials", "Industrials", "Energy", "Consumer Discretionary"]
    names = [f"D{i:02d}" for i in range(n)] + ["SPY", "QQQ", "^VIX"]
    for k, t in enumerate(names):
        drift = rng.normal(0.0004, 0.0008)
        vol = rng.uniform(0.012, 0.03)
        r = rng.normal(drift, vol, days)
        # regime shifts and volatility squeezes to create realistic setups
        for _ in range(4):
            a = rng.integers(200, days - 40)
            r[a:a + 25] *= 0.35
            r[a + 25:a + 30] += rng.normal(0.006, 0.004, 5)
        close = 50 * np.exp(np.cumsum(r)) * rng.uniform(0.5, 6)
        if t == "^VIX":
            close = 15 + 5 * np.sin(np.arange(days) / 40) + rng.normal(0, 1, days)
        rngd = np.abs(rng.normal(0, vol, days)) * close
        high = close + rngd * rng.uniform(0.2, 1, days)
        low = close - rngd * rng.uniform(0.2, 1, days)
        opn = low + (high - low) * rng.uniform(0, 1, days)
        v = rng.lognormal(15, 0.4, days) * (1 + 3 * (np.abs(r) > 2 * vol))
        out[t] = pd.DataFrame({"Open": opn, "High": high, "Low": low, "Close": close, "Volume": v}, index=idx)
        meta[t] = {"name": f"Demo Corp {t}", "sector": sectors[k % len(sectors)]}
    return out, meta


# ----------------------------------------------------------------------------- indicators
def rma(x, n):
    return x.ewm(alpha=1.0 / n, adjust=False).mean()


def rsi(close, n):
    d = close.diff()
    up, dn = d.clip(lower=0), (-d).clip(lower=0)
    rs = rma(up, n) / rma(dn, n).replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100)


def indicators(d):
    c, h, l, o, v = d["Close"], d["High"], d["Low"], d["Open"], d["Volume"]
    x = pd.DataFrame(index=d.index)
    x["close"], x["high"], x["low"], x["open"], x["vol"] = c, h, l, o, v
    x["chg"] = c.pct_change()
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    x["atr"] = rma(tr, 14)
    x["ema20"] = c.ewm(span=20, adjust=False).mean()
    x["ema50"] = c.ewm(span=50, adjust=False).mean()
    x["sma5"] = c.rolling(5).mean()
    x["sma50"] = c.rolling(50).mean()
    x["sma200"] = c.rolling(200).mean()
    x["rsi14"] = rsi(c, 14)
    x["rsi2"] = rsi(c, 2)
    sd = c.rolling(20).std()
    x["bbw"] = 4 * sd / c.rolling(20).mean()
    x["squeeze"] = (x["bbw"] <= x["bbw"].rolling(120).quantile(0.2)).astype(float)
    x["hi20p"] = h.rolling(20).max().shift(1)
    x["hi55"] = c.rolling(55).max()
    x["vavg"] = v.rolling(20).mean().shift(1)
    x["vr"] = v / x["vavg"]
    x["dvol"] = (c * v).rolling(20).mean()
    x["ret63"] = c / c.shift(63) - 1
    rng_ = (h - l).replace(0, np.nan)
    x["lshadow"] = ((pd.concat([o, c], axis=1).min(axis=1) - l) / rng_).fillna(0)
    return x


def signal_frame(x):
    base = (x["close"] >= MIN_PRICE) & (x["dvol"] >= MIN_DOLLAR_VOL)
    up = (x["close"] > x["sma200"]) & (x["ema20"] > x["ema50"])
    rs = x["rs"]
    s = pd.DataFrame(index=x.index)
    s["squeeze"] = base & (x["squeeze"].rolling(5).max() == 1) & (x["close"] > x["hi20p"]) & (x["vr"] >= 1.5) \
        & (rs >= 60) & (x["close"] > x["sma50"])
    s["pit"] = base & up & (rs >= 70) & (x["low"].rolling(2).min() <= x["ema20"] * 1.005) & (x["close"] > x["ema20"]) \
        & (x["close"] > x["open"]) & x["rsi14"].between(40, 58) & ((x["close"] - x["ema20"]) < 0.8 * x["atr"])
    s["momentum"] = base & up & (x["close"] >= x["hi55"]) & (x["vr"] >= 1.3) & (rs >= 85) \
        & ((x["close"] - x["ema20"]) <= 2.5 * x["atr"])
    s["rsi2"] = base & (x["close"] > x["sma200"]) & (x["rsi2"] < 10) & (rs >= 50)
    s["blood"] = base & (x["rsi14"] < 35) & (x["close"] < x["ema20"] * 0.95) & (x["lshadow"] > 0.4)
    s["base"] = base
    return s.fillna(False).astype(bool)


def levels(sig, x):
    c, a = float(x["close"]), float(x["atr"])
    if sig == "pit":
        stop = min(float(x["low3"]), c - 0.8 * a) - 0.2 * a
        target = c + 2 * (c - stop)
    elif sig == "squeeze":
        stop, target = c - 1.5 * a, c + 3 * a
    elif sig == "momentum":
        stop, target = c - 2 * a, c + 4 * a
    elif sig == "rsi2":
        stop, target = c - 2.5 * a, max(float(x["sma5"]), c + 0.5 * a)
    else:  # blood
        stop, target = c * 0.92, c * 1.20
    risk = max(c - stop, 1e-9)
    return round(stop, 2), round(target, 2), round((target - c) / risk, 2)


# ----------------------------------------------------------------------------- stats
def signal_stats(frames, sigs, cutoff):
    out = {}
    base_by_h = {}
    for key, cfg in SIGNALS.items():
        h = cfg["horizon"]
        rets, base = [], base_by_h.get(h)
        collect_base = base is None
        if collect_base:
            base = []
        for t, x in frames.items():
            s = sigs[t]
            fwd = x["close"].shift(-h) / x["close"] - 1
            ok = (x.index >= cutoff) & fwd.notna()
            r = fwd[ok & s[key]]
            rets.extend(r.values.tolist())
            if collect_base:
                base.extend(fwd[ok & s["base"]].values.tolist())
        base_by_h[h] = base
        r = np.array(rets)
        b = np.array(base) if len(base) else np.array([0.0])
        n = len(r)
        st = {"horizon": h, "n": n, "base_mean": float(b.mean()), "base_win": float((b > 0).mean())}
        if n >= 5:
            mean, sd = float(r.mean()), float(r.std(ddof=1))
            se = sd / math.sqrt(n)
            edge = mean - st["base_mean"]
            st.update({
                "mean": mean, "median": float(np.median(r)), "win": float((r > 0).mean()),
                "edge": edge, "ci_lo": edge - 1.96 * se, "ci_hi": edge + 1.96 * se,
                "pf": float(r[r > 0].sum() / max(-r[r < 0].sum(), 1e-9)),
            })
            if n < 30:
                st["verdict"] = "样本太少"
            elif st["ci_lo"] > 0:
                st["verdict"] = "有统计优势"
            elif st["ci_hi"] < 0:
                st["verdict"] = "跑输基准"
            else:
                st["verdict"] = "优势未证实"
        else:
            st["verdict"] = "样本太少"
        out[key] = st
    return out


# ----------------------------------------------------------------------------- tracking
def track(frames, today):
    rows = []
    if not os.path.isdir(HIST):
        return {"rows": [], "summary": {}}
    files = sorted(f for f in os.listdir(HIST) if f.endswith(".json") and f[:-5] < today)[-TRACK_DAYS:]
    for fn in files:
        try:
            with open(os.path.join(HIST, fn), encoding="utf-8") as f:
                picks = json.load(f).get("picks", [])
        except Exception:  # noqa: BLE001
            continue
        for p in picks:
            x = frames.get(p["t"])
            if x is None:
                continue
            after = x[x.index > pd.Timestamp(p["date"])]
            if after.empty:
                continue
            maxd = {"rsi2": 7, "blood": 126}.get(p["sig"], 15)
            status, exit_px, days = "持有中", float(after["close"].iloc[-1]), len(after)
            for i, (_, bar) in enumerate(after.iterrows()):
                if bar["low"] <= p["stop"]:
                    status, exit_px, days = "止损", p["stop"], i + 1
                    break
                if bar["high"] >= p["target"]:
                    status, exit_px, days = "止盈", p["target"], i + 1
                    break
                if p["sig"] == "rsi2" and bar["close"] > bar["sma5"]:
                    status, exit_px, days = "规则离场", float(bar["close"]), i + 1
                    break
                if i + 1 >= maxd:
                    status, exit_px, days = "到期", float(bar["close"]), i + 1
                    break
            rows.append({"date": p["date"], "t": p["t"], "sig": p["sig"], "entry": p["entry"],
                         "ret": round(exit_px / p["entry"] - 1, 4), "status": status, "days": days})
    closed = [r for r in rows if r["status"] != "持有中"]
    summary = {"total": len(rows), "closed": len(closed)}
    if closed:
        rr = np.array([r["ret"] for r in closed])
        summary.update({"win": float((rr > 0).mean()), "mean": float(rr.mean())})
    rows.sort(key=lambda r: (r["date"], r["t"]), reverse=True)
    return {"rows": rows[:120], "summary": summary}


def earnings_soon(ticker, asof):
    try:
        import yfinance as yf
        cal = yf.Ticker(ticker).calendar
        dates = cal.get("Earnings Date") if isinstance(cal, dict) else None
        if dates:
            d = pd.Timestamp(dates[0]).date()
            if 0 <= (d - asof).days <= 14:
                return d.isoformat()
    except Exception:  # noqa: BLE001
        pass
    return None


# ----------------------------------------------------------------------------- main
def mkt_line(x):
    last = x.iloc[-1]
    return {"close": round(float(last["close"]), 2), "chg": round(float(last["chg"]), 4),
            "above50": bool(last["close"] > last["sma50"]), "above200": bool(last["close"] > last["sma200"]),
            "rsi14": round(float(last["rsi14"]), 1),
            "sma50_up": bool(x["sma50"].iloc[-1] > x["sma50"].iloc[-6])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="use synthetic data (no network)")
    args = ap.parse_args()
    os.makedirs(HIST, exist_ok=True)

    if args.demo:
        raw, meta = demo_data()
    else:
        meta = fetch_universe()
        tickers = sorted(meta.keys())
        print("universe:", len(tickers))
        raw = download(tickers + ["SPY", "QQQ", "^VIX"])
        if len(raw) < 50:
            print("ERROR: too little data downloaded; keeping previous results.")
            return 0

    idx_frames = {k: indicators(raw.pop(k)) for k in ["SPY", "QQQ", "^VIX"] if k in raw}
    frames = {t: indicators(d) for t, d in raw.items()}
    # cross-sectional relative strength percentile (0-100) per date
    ret = pd.DataFrame({t: x["ret63"] for t, x in frames.items()})
    rs = ret.rank(axis=1, pct=True) * 100
    for t, x in frames.items():
        x["rs"] = rs[t]
        x["low3"] = x["low"].rolling(3).min()
    sigs = {t: signal_frame(x) for t, x in frames.items()}

    # "today" = the latest date that most tickers actually have (a few may lag or run ahead)
    from collections import Counter
    counts = Counter(x.index[-1] for x in frames.values())
    last_date = max(d for d, n in counts.items() if n >= 0.5 * len(frames)) if counts else None
    if last_date is None or counts[last_date] < 0.5 * len(frames):
        last_date = counts.most_common(1)[0][0]
    for t in list(frames):
        x = frames[t]
        if x.index[-1] > last_date:          # trim bars newer than the common date
            frames[t] = x[x.index <= last_date]
            sigs[t] = sigs[t][sigs[t].index <= last_date]
    print("dates:", {str(k.date()): v for k, v in counts.most_common(4)}, "-> using", last_date.date())
    today = last_date.date().isoformat()
    cutoff = last_date - pd.DateOffset(years=STATS_YEARS)
    stats = signal_stats(frames, sigs, cutoff)

    cands = []
    for t, x in frames.items():
        if x.index[-1] != last_date:
            continue
        s = sigs[t].iloc[-1]
        tags = [k for k in PRIORITY if bool(s[k])]
        if not tags:
            continue
        last = x.iloc[-1]
        prim = tags[0]
        stop, target, rr = levels(prim, last)
        edge = stats[prim].get("edge", 0.0) or 0.0
        score = (0.45 * float(last["rs"]) + 0.20 * min(float(last["vr"]), 3) / 3 * 100
                 + 0.20 * (100 if last["close"] > last["sma200"] else 40)
                 + 0.15 * max(0, min(100, 50 + edge * 1000)))
        tail = x.iloc[-60:]
        cands.append({
            "t": t, "name": meta.get(t, {}).get("name", ""), "sector": meta.get(t, {}).get("sector", ""),
            "close": round(float(last["close"]), 2), "chg": round(float(last["chg"]), 4),
            "rs": round(float(last["rs"]), 0), "vr": round(float(last["vr"]), 2), "rsi": round(float(last["rsi14"]), 1),
            "rsi2": round(float(last["rsi2"]), 1), "atr_pct": round(float(last["atr"] / last["close"]), 4),
            "tags": tags, "primary": prim, "stop": stop, "target": target, "r": rr, "score": round(score, 1),
            "spark": [round(float(v), 2) for v in tail["close"]], "ema": [round(float(v), 2) for v in tail["ema20"]],
        })
    # cap per primary signal
    cands.sort(key=lambda c: -c["score"])
    per, kept = {}, []
    for c in cands:
        per[c["primary"]] = per.get(c["primary"], 0) + 1
        if per[c["primary"]] <= MAX_PER_SIGNAL:
            kept.append(c)
    if not args.demo:
        for c in kept:
            c["earn"] = earnings_soon(c["t"], last_date.date())

    # market regime
    regime = {}
    for k, key in (("SPY", "spy"), ("QQQ", "qqq")):
        if k in idx_frames:
            regime[key] = mkt_line(idx_frames[k])
    if "^VIX" in idx_frames:
        regime["vix"] = round(float(idx_frames["^VIX"]["close"].iloc[-1]), 2)
    lastrows = [x.iloc[-1] for x in frames.values() if x.index[-1] == last_date]
    regime["breadth50"] = round(float(np.mean([r["close"] > r["sma50"] for r in lastrows])), 3)
    regime["breadth200"] = round(float(np.mean([r["close"] > r["sma200"] for r in lastrows])), 3)
    spy, vix = regime.get("spy"), regime.get("vix", 18)
    if spy and spy["above200"] and spy["sma50_up"] and vix < 20 and regime["breadth50"] >= 0.5:
        regime["label"], regime["desc"] = "进攻", "大盘在 200 日线上方且 50 日线向上，波动率低，市场宽度健康，适合做多类短线信号。"
    elif (spy and not spy["above200"]) or vix >= 28 or regime["breadth50"] < 0.3:
        regime["label"], regime["desc"] = "防守", "大盘趋势走弱或恐慌指数偏高，突破类信号失败率上升，宜降低仓位，只看超跌反弹或观望。"
    else:
        regime["label"], regime["desc"] = "谨慎", "大盘多空信号混杂，可以做，但要控制仓位、严格止损。"

    tracking = track(frames, today)
    result = {
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date": today, "demo": bool(args.demo), "universe": len(meta), "scanned": len(frames),
        "regime": regime,
        "signals": {k: dict(SIGNALS[k], stats=stats[k]) for k in PRIORITY},
        "candidates": kept, "tracking": tracking,
    }
    with open(os.path.join(DATA, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    if not args.demo:
        picks = [{"t": c["t"], "sig": c["primary"], "date": today, "entry": c["close"], "stop": c["stop"],
                  "target": c["target"]} for c in kept]
        with open(os.path.join(HIST, today + ".json"), "w", encoding="utf-8") as f:
            json.dump({"date": today, "picks": picks}, f, ensure_ascii=False)
    print(f"{today}: {len(kept)} candidates, regime={regime['label']}")
    for k in PRIORITY:
        s = stats[k]
        print(f"  {k:9s} n={s['n']:5d} mean={s.get('mean', 0):+.4f} win={s.get('win', 0):.2f} "
              f"edge={s.get('edge', 0):+.4f} [{s.get('ci_lo', 0):+.4f},{s.get('ci_hi', 0):+.4f}] {s['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
