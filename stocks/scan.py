#!/usr/bin/env python3
"""
每日短线股票池扫描器 (runs in GitHub Actions after the US close)

Universe : S&P 500 + Nasdaq-100 (+ stocks/watchlist.txt)
Data     : Yahoo Finance via yfinance (no API key needed)
Signals  : 回踩金坑 / 挤压突破 / 强势新高 / RSI2 超跌反弹 / 血筹码
Output   : stocks/data/latest.json (+ dated copy in stocks/data/history/)

Every signal's historical stats are computed on the same universe with strict
no-lookahead: signal uses data up to close t, the trade enters at the next open (t+1)
and is measured to close t+h, minus a round-trip cost.  Repeated signals on the same
stock are counted once, and because signals cluster on the same days the uncertainty
is measured across non-overlapping time blocks, not across individual trades.  Each
signal is also measured separately for each market regime (进攻 / 谨慎 / 防守), and
today's picks are ranked by the edge their signal had in regimes like today's.

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
CHANGES_CACHE = os.path.join(HERE, "sp500_changes.json")   # 标普 500 历次调入 / 调出（维基百科），用来减轻幸存者偏差
WATCHLIST = os.path.join(HERE, "watchlist.txt")

MIN_PRICE = 10.0
MIN_DOLLAR_VOL = 20e6          # 20-day average dollar volume
STATS_YEARS = 5                # years of history used for signal statistics (download adds a warm-up year)
MAX_PER_SIGNAL = 12
COST = 0.001                   # round-trip cost + slippage per trade
MIN_BLOCKS = 15                # fewer independent time blocks than this → "样本太少"
MAX_PICKS = 8                  # 精选 list size
MAX_PER_SECTOR = 2
EARN_FILE = os.path.join(os.path.dirname(HERE), "earnings", "data", "latest.json")

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

# ETFs shown in 我的自选 (not part of the signal universe)
ETFS = {
    "VOO": "Vanguard S&P 500 ETF", "VTI": "Vanguard Total Stock Market ETF", "SPY": "SPDR S&P 500 ETF", "QQQ": "Invesco QQQ (Nasdaq-100)",
    "IWM": "iShares Russell 2000 (small caps)", "DIA": "SPDR Dow Jones ETF", "SCHD": "Schwab US Dividend Equity ETF",
    "TLT": "iShares 20+ Year Treasury Bond", "GLD": "SPDR Gold Shares", "SMH": "VanEck Semiconductor ETF",
    "XLK": "Technology Select Sector", "XLF": "Financial Select Sector", "XLE": "Energy Select Sector", "XLV": "Health Care Select Sector",
}
# NYSE full-day holidays (used to know which session the data should have reached)
NYSE_HOLIDAYS = {
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
}
CLOSE_DONE = dt.time(16, 20)   # a daily bar is final a little after the 4:00 pm ET close


def now_et():
    from zoneinfo import ZoneInfo
    return dt.datetime.now(ZoneInfo("America/New_York"))


def is_session(d):
    return d.weekday() < 5 and d.isoformat() not in NYSE_HOLIDAYS


def expected_session(now):
    """the latest session whose daily bar should already be final"""
    d = now.date()
    if not (is_session(d) and now.time() >= CLOSE_DONE):
        d -= dt.timedelta(days=1)
        while not is_session(d):
            d -= dt.timedelta(days=1)
    return d


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
            meta[sym] = {"name": str(row.get("Security", "")), "sector": str(row.get("GICS Sector", "")), "sp500": True}
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


def fetch_sp500_changes():
    """标普 500 的历次成分股变动（维基百科 List of S&P 500 companies 的第二张表）→ {ticker: 最近一次调入日期}，
    以及窗口内被调出、现在不在名单里的股票数量。抓不到就用上次存下的。"""
    rows = []
    try:
        html = http_get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        for t in pd.read_html(io.StringIO(html)):
            flat = [" ".join(str(x) for x in (c if isinstance(c, tuple) else (c,))).lower() for c in t.columns]
            if not (any("added" in c for c in flat) and any("removed" in c for c in flat)):
                continue
            ci = lambda *keys: next((i for i, c in enumerate(flat) if all(k in c for k in keys)), None)
            i_date, i_add, i_rem = ci("date"), ci("added", "ticker"), ci("removed", "ticker")
            if i_date is None or i_add is None:
                continue
            for _, r in t.iterrows():
                d = pd.to_datetime(str(r.iloc[i_date]).split("[")[0].strip(), errors="coerce")
                if pd.isna(d):
                    continue
                add = str(r.iloc[i_add]).strip().replace(".", "-") if i_add is not None else ""
                rem = str(r.iloc[i_rem]).strip().replace(".", "-") if i_rem is not None else ""
                rows.append({"d": d.date().isoformat(), "add": "" if add in ("nan", "") else add, "rem": "" if rem in ("nan", "") else rem})
            break
        if len(rows) >= 50:
            with open(CHANGES_CACHE, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))
            print(f"S&P 500 changes: {len(rows)} rows")
    except Exception as e:  # noqa: BLE001
        print("WARN: S&P 500 changes fetch failed:", e)
    if len(rows) < 50 and os.path.exists(CHANGES_CACHE):
        with open(CHANGES_CACHE, encoding="utf-8") as f:
            rows = json.load(f)
        print("Using cached sp500_changes.json")
    return rows


def membership(rows, tickers, cutoff, sp500):
    """每只股票「从哪天起算」：窗口内才调入标普 500 的，调入之前的信号和基准都不算（避免「涨上去了才被选进指数」的偏差）。
    只在纳指 100 里的股票没有可靠的历史变动表，照旧全算。"""
    since, removed = {}, set()
    for r in sorted(rows, key=lambda r: r["d"]):
        d = pd.Timestamp(r["d"])
        if r["add"] and r["add"] in tickers and r["add"] in sp500:
            since[r["add"]] = d                       # 多次进出时取最近一次调入
        if r["rem"] and d >= cutoff and r["rem"] not in sp500:
            removed.add(r["rem"])
    since = {t: d for t, d in since.items() if d > cutoff}
    return since, removed


# ----------------------------------------------------------------------------- data
def download(tickers, period="6y"):
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
    # Yahoo's batch endpoint sometimes returns the newest bar for only part of the
    # tickers; re-fetch recent bars for the laggards and merge them in.
    DIAG["before"] = _date_counts(out)
    if out:
        newest = max(d.index[-1] for d in out.values())
        lag = [t for t, d in out.items() if d.index[-1] < newest]
        DIAG["refetch"] = len(lag)
        for i in range(0, len(lag), 50):
            part = lag[i:i + 50]
            try:
                df = yf.download(part, period="10d", interval="1d", auto_adjust=True, group_by="ticker",
                                 threads=True, progress=False)
            except Exception as e:  # noqa: BLE001
                print("refetch failed", e)
                continue
            for t in part:
                try:
                    d = df[t] if isinstance(df.columns, pd.MultiIndex) else df
                    d = d[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
                    new = d[d.index > out[t].index[-1]]
                    if len(new):
                        out[t] = pd.concat([out[t], new])
                except Exception:  # noqa: BLE001
                    pass
        DIAG["after"] = _date_counts(out)
        print("date counts before/after refetch:", DIAG["before"], DIAG["after"])
    return out


DIAG = {}


def _date_counts(frames):
    c = {}
    for d in frames.values():
        k = str(d.index[-1].date())
        c[k] = c.get(k, 0) + 1
    return dict(sorted(c.items())[-4:])


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


# ----------------------------------------------------------------------------- regime
def regime_label(above200, sma50_up, vix, b50):
    if above200 and sma50_up and vix < 20 and b50 >= 0.5:
        return "进攻"
    if (not above200) or vix >= 28 or b50 < 0.3:
        return "防守"
    return "谨慎"


def regime_series(frames, spy, vix):
    """the same 进攻 / 谨慎 / 防守 rule the page shows today, evaluated on every past day"""
    cl = pd.DataFrame({t: x["close"] for t, x in frames.items()})
    s50 = pd.DataFrame({t: x["sma50"] for t, x in frames.items()})
    b50 = (cl > s50).astype(float).where(s50.notna()).mean(axis=1)
    if spy is None:
        return pd.Series("谨慎", index=cl.index)
    sp = spy.reindex(cl.index).ffill()
    vx = vix["close"].reindex(cl.index).ffill().fillna(18) if vix is not None else pd.Series(18.0, index=cl.index)
    up200 = sp["close"] > sp["sma200"]
    s50up = sp["sma50"] > sp["sma50"].shift(5)
    lab = [regime_label(bool(a), bool(b), float(v), float(c)) for a, b, v, c in zip(up200, s50up, vx, b50.fillna(0.5))]
    return pd.Series(lab, index=cl.index)


# ----------------------------------------------------------------------------- stats
def block_stats(ev, h, n_days):
    """ev: DataFrame with columns pos (trading-day index), ex, raw, base.  Trades whose holding periods
    overlap are not independent, so average them inside non-overlapping blocks of 2h trading days and
    measure the uncertainty across blocks."""
    st = {"horizon": h, "n": int(len(ev)), "blocks": 0}
    if len(ev) < 5:
        st["verdict"] = "样本太少"
        return st
    blk = (ev["pos"] // (2 * h)).astype(int)
    bm = ev.groupby(blk)["ex"].mean()
    nb = len(bm)
    edge = float(bm.mean())
    se = float(bm.std(ddof=1) / math.sqrt(nb)) if nb > 1 else float("nan")
    r = ev["raw"].values.astype(float)
    st.update({
        "blocks": nb, "mean": float(ev.groupby(blk)["raw"].mean().mean()), "base_mean": float(ev.groupby(blk)["base"].mean().mean()),
        "win": float((r > 0).mean()), "median": float(np.median(r)),
        "pf": float(r[r > 0].sum() / max(-r[r < 0].sum(), 1e-9)),
        "edge": edge, "ci_lo": edge - 1.96 * se if se == se else None, "ci_hi": edge + 1.96 * se if se == se else None,
        "per_year": round(len(ev) / max(n_days / 252, 0.1), 1),
    })
    if nb < MIN_BLOCKS or se != se:
        st["verdict"] = "样本太少"
    elif st["ci_lo"] > 0:
        st["verdict"] = "有统计优势"
    elif st["ci_hi"] < 0:
        st["verdict"] = "跑输基准"
    else:
        st["verdict"] = "优势未证实"
    return st


MAXD = {"rsi2": 7, "blood": 126}   # max holding days (default 15)


def sim_exit(sig, A, i, stop, target, entry):
    """walk forward from the session after signal day i using the signal's real exit rules.
    A gap through the stop / target fills at the open.  Returns (exit index, gross return, status)
    or (last index, open return, "持有中") when the trade hasn't finished."""
    o, h, l, c, s5, e20 = A["open"], A["high"], A["low"], A["close"], A["sma5"], A["ema20"]
    n, maxd = len(c), MAXD.get(sig, 15)
    j = i
    for k in range(maxd):
        j = i + 1 + k
        if j >= n:
            return n - 1, c[n - 1] / entry - 1, "持有中"
        oo = entry if k == 0 else o[j]
        if l[j] <= stop or oo <= stop:
            return j, min(oo, stop) / entry - 1, "止损"
        if h[j] >= target or oo >= target:
            return j, max(oo, target) / entry - 1, "止盈"
        if sig == "rsi2" and c[j] > s5[j]:
            return j, c[j] / entry - 1, "规则离场"
        if sig == "momentum" and c[j] < e20[j]:
            return j, c[j] / entry - 1, "规则离场"
    return j, c[j] / entry - 1, "到期"


def arrays(x):
    return {k: x[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close", "sma5", "ema20", "atr", "low3")}


def signal_stats(frames, sigs, cutoff, regimes, since=None):
    """per signal: overall stats + stats per market regime.  Every signal is replayed as a real trade:
    buy at the next open, exit by the signal's own stop / target / rule / time limit, minus COST.
    `ex` = trade return minus an equal-weight basket of every eligible stock over the same days.
    While a trade is open, new signals on the same stock are ignored."""
    idx = regimes.index
    pos = {d: k for k, d in enumerate(idx)}
    keep = np.asarray(idx >= cutoff)
    n_days = int(keep.sum())
    # equal-weight basket of eligible stocks (eligibility judged the day before)
    R = pd.DataFrame({t: x["close"].pct_change() for t, x in frames.items()}).reindex(idx)
    E = pd.DataFrame({t: sigs[t]["base"] for t in frames}).reindex(idx).fillna(False).astype(bool)
    since = since or {}
    for t, d0 in since.items():          # 调入标普 500 之前：不算进基准，也不算它的信号
        if t in E.columns:
            E.loc[E.index < d0, t] = False
    E = E.shift(1).fillna(False)
    ew = (1 + R.where(E).mean(axis=1).fillna(0)).cumprod().to_numpy()
    reg = regimes.to_numpy()
    events = {k: [] for k in SIGNALS}
    for t, x in frames.items():
        A = arrays(x)
        gi = np.array([pos.get(d, -1) for d in x.index])
        S = sigs[t]
        for key in SIGNALS:
            col = S[key].to_numpy()
            busy = -1
            d0 = since.get(t)
            for i in np.nonzero(col)[0]:
                if i <= busy or i + 1 >= len(col) or gi[i] < 0 or not keep[gi[i]]:
                    continue
                if d0 is not None and x.index[i] < d0:
                    continue
                row = {"close": A["close"][i], "atr": A["atr"][i], "low3": A["low3"][i], "sma5": A["sma5"][i]}
                stop, target, _ = levels(key, row)
                entry = A["open"][i + 1]
                j, r, status = sim_exit(key, A, i, stop, target, entry)
                busy = j
                if status == "持有中" or not np.isfinite(r):
                    continue
                g0, g1 = gi[i], gi[j]
                if g1 < 0:
                    continue
                base = ew[g1] / ew[g0] - 1
                raw = r - COST
                events[key].append((g0, raw, base, raw - base, reg[g0], j - i))
    out = {}
    for key, cfg in SIGNALS.items():
        h = cfg["horizon"]
        ev = pd.DataFrame(events[key], columns=["pos", "raw", "base", "ex", "reg", "days"])
        st = block_stats(ev, h, n_days)
        st["avg_days"] = round(float(ev["days"].mean()), 1) if len(ev) else None
        st["by_regime"] = {}
        for rg in ("进攻", "谨慎", "防守"):
            days = int(((reg == rg) & keep).sum())
            r = block_stats(ev[ev["reg"] == rg], h, days)
            r["days"] = days
            st["by_regime"][rg] = r
        out[key] = st
    out["_meta"] = {"since": str(idx[keep][0].date()) if keep.any() else None, "days": n_days, "cost": COST,
                    "regime_days": {rg: int(((reg == rg) & keep).sum()) for rg in ("进攻", "谨慎", "防守")}}
    return out


def evidence(st, regime):
    """what we believe about a signal today: its stats in today's regime if there are enough, else overall.
    "proven" = significant in today's regime, or significant overall and not negative in today's regime."""
    rg = (st.get("by_regime") or {}).get(regime) or {}
    enough = rg.get("blocks", 0) >= MIN_BLOCKS
    use = rg if enough else st
    proven = rg.get("verdict") == "有统计优势" or (st.get("verdict") == "有统计优势" and (not enough or (rg.get("edge") or 0) > 0))
    return {"edge": use.get("edge"), "src": "regime" if enough else "all", "proven": bool(proven),
            "verdict_rg": rg.get("verdict"), "edge_rg": rg.get("edge"), "blocks_rg": rg.get("blocks", 0)}


# ----------------------------------------------------------------------------- tracking
def track(frames, today, spy):
    """replay every saved pick: enter at the next open, exit at stop / target / rule / time limit.
    A gap through the stop or target fills at the open, not at the level."""
    rows = []
    if not os.path.isdir(HIST):
        return {"rows": [], "summary": {}, "by_sig": {}, "by_tier": {}}
    files = sorted(f for f in os.listdir(HIST) if f.endswith(".json") and f[:-5] < today)
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
            A = arrays(x)
            i = int(x.index.searchsorted(pd.Timestamp(p["date"]), side="right")) - 1
            entry = float(A["open"][i + 1])
            j, gross, status = sim_exit(p["sig"], A, i, p["stop"], p["target"], entry)
            days = j - i
            spy_r = None
            if spy is not None:
                sp = spy.reindex(after.index[:days])
                if len(sp) and sp["open"].iloc[0] == sp["open"].iloc[0] and sp["close"].iloc[-1] == sp["close"].iloc[-1]:
                    spy_r = float(sp["close"].iloc[-1] / sp["open"].iloc[0] - 1)
            ret = gross - (COST if status != "持有中" else COST / 2)
            rows.append({"date": p["date"], "t": p["t"], "sig": p["sig"], "tier": p.get("tier", "old"), "reg": p.get("reg"),
                         "entry": round(entry, 2), "ret": round(ret, 4), "spy": None if spy_r is None else round(spy_r, 4),
                         "status": status, "days": days})

    def summ(rs):
        closed = [r for r in rs if r["status"] != "持有中"]
        out = {"total": len(rs), "closed": len(closed)}
        if closed:
            rr = np.array([r["ret"] for r in closed])
            vs = [r["ret"] - r["spy"] for r in closed if r["spy"] is not None]
            out.update({"win": float((rr > 0).mean()), "mean": float(rr.mean()), "vs_spy": float(np.mean(vs)) if vs else None})
        return out
    by_sig = {k: summ([r for r in rows if r["sig"] == k]) for k in SIGNALS}
    by_tier = {k: summ([r for r in rows if r["tier"] == k]) for k in ("pick", "watch", "old")}
    rows.sort(key=lambda r: (r["date"], r["t"]), reverse=True)
    return {"rows": rows[:150], "summary": summ(rows), "by_sig": by_sig, "by_tier": by_tier,
            "since": files[0][:-5] if files else None}


def load_earnings():
    """report dates (and typical earnings-day move) from the earnings calendar job"""
    out = {}
    try:
        with open(EARN_FILE, encoding="utf-8") as f:
            d = json.load(f)
        for day in d.get("days", []):
            for e in day.get("earnings", []):
                st = e.get("stats") or {}
                out[e["t"]] = {"date": e["date"], "when": e.get("when", ""), "move": st.get("avg_abs_raw", st.get("avg_abs"))}
    except Exception as ex:  # noqa: BLE001
        print("earnings file:", ex)
    return out


def hold_end(asof, h):
    """last calendar day of a holding period of h trading days that starts at the next session"""
    d, n = asof, 0
    while n < h + 1:
        d += dt.timedelta(days=1)
        if is_session(d):
            n += 1
    return d


def earnings_soon(ticker, asof, until=None):
    try:
        import yfinance as yf
        cal = yf.Ticker(ticker).calendar
        dates = cal.get("Earnings Date") if isinstance(cal, dict) else None
        if dates:
            d = pd.Timestamp(dates[0]).date()
            if 0 <= (d - asof).days and d <= (until or asof + dt.timedelta(days=14)):
                return d.isoformat()
    except Exception:  # noqa: BLE001
        pass
    return None


# ----------------------------------------------------------------------------- watchlist snapshot
def snap_row(x, last_date, name, sector, rs=None, tags=None):
    x = x[x.index <= last_date]
    if len(x) < 70:
        return None
    c, last = x["close"], x.iloc[-1]

    def back(n):
        return round(float(c.iloc[-1] / c.iloc[-1 - n] - 1), 4) if len(c) > n else None
    prev_year = c[c.index.year < last_date.year]
    hi52 = float(c.iloc[-252:].max())
    prev = x.iloc[-2]
    above, was = last["close"] > last["sma200"], prev["close"] > prev["sma200"]
    return {"n": name, "s": sector, "c": round(float(last["close"]), 2), "d": round(float(last["chg"]), 4),
            "m1": back(21), "m3": back(63), "y": round(float(c.iloc[-1] / prev_year.iloc[-1] - 1), 4) if len(prev_year) else None,
            "h": round(float(last["close"]) / hi52 - 1, 4), "rsi": round(float(last["rsi14"]), 1),
            "a50": int(last["close"] > last["sma50"]), "a200": int(above),
            "m2": round(float(last["close"] / last["sma200"] - 1), 4) if last["sma200"] == last["sma200"] else None,
            "x2": (1 if above and not was else -1 if was and not above else 0),   # crossed the 200-day line today
            "rs": rs, "sig": tags or [], "sp": [round(float(v), 2) for v in c.iloc[-60::3]]}


def write_snapshot(frames, sigs, meta, extra, last_date, today):
    rows = {}
    for t, x in frames.items():
        tags = []
        if t in sigs and len(sigs[t]) and sigs[t].index[-1] == last_date:
            tags = [k for k in PRIORITY if bool(sigs[t].iloc[-1][k])]
        rs = x["rs"].iloc[-1] if "rs" in x and x.index[-1] == last_date else None
        r = snap_row(x, last_date, meta.get(t, {}).get("name", ""), meta.get(t, {}).get("sector", ""),
                     None if rs is None or rs != rs else int(round(float(rs))), tags)
        if r:
            rows[t] = r
    for t, x in extra.items():
        if x is not None:
            r = snap_row(x, last_date, ETFS.get(t, t), "ETF")
            if r:
                rows[t] = r
    with open(os.path.join(DATA, "snap.json"), "w", encoding="utf-8") as f:
        json.dump({"date": today, "rows": rows}, f, ensure_ascii=False, separators=(",", ":"))
    print("snapshot:", len(rows), "tickers")


# ----------------------------------------------------------------------------- long-term view (VOO 长线体检)
DD_BUCKETS = [(0.0, 0.02, "高点 2% 内"), (0.02, 0.05, "回撤 2–5%"), (0.05, 0.10, "回撤 5–10%"),
              (0.10, 0.20, "回撤 10–20%"), (0.20, 1.01, "回撤 >20%")]


def download_max(t):
    import yfinance as yf
    for attempt in range(3):
        try:
            df = yf.download(t, period="max", interval="1d", auto_adjust=True, progress=False, group_by="ticker")
            if isinstance(df.columns, pd.MultiIndex):
                df = df[t] if t in df.columns.get_level_values(0) else df.droplevel(1, axis=1)
            c = df["Close"].dropna()
            if len(c) > 2000:
                return c
        except Exception as e:  # noqa: BLE001
            print("max download retry", attempt, e)
        time.sleep(5)
    return None


def longterm(c):
    """SPY since 1993 (adjusted close = dividends reinvested): how far below the all-time high are we,
    and what happened over the next 1 / 3 years from similar spots in the past."""
    c = c[c > 0]
    if len(c) < 300:
        return None
    ath = c.cummax()
    dd = 1 - c / ath
    f1 = c.shift(-252) / c - 1
    f3 = (c.shift(-756) / c) ** (1 / 3) - 1

    def q(s, p):
        return round(float(s.quantile(p)), 4) if len(s) else None

    def win(s):
        return round(float((s > 0).mean()), 3) if len(s) else None

    def row(m, lab):
        a, b = f1[m].dropna(), f3[m].dropna()
        return {"lab": lab, "days": round(float(m.mean()), 3), "n1": int(len(a)), "med1": q(a, .5), "win1": win(a),
                "p10": q(a, .1), "p90": q(a, .9), "n3": int(len(b)), "med3": q(b, .5), "win3": win(b)}
    rows = [row((dd >= lo) & (dd < hi), lab) for lo, hi, lab in DD_BUCKETS]
    allrow = row(dd >= 0, "所有日子")
    now = float(dd.iloc[-1])
    k = next(i for i, (lo, hi, _) in enumerate(DD_BUCKETS) if lo <= now < hi)
    ath_date = c.index[c >= ath.iloc[-1]][-1]
    # calendar years: full-year return and the deepest drop inside that year (from the previous year-end)
    years, prev = [], None
    for y, g in c.groupby(c.index.year):
        if prev is not None:
            s = pd.concat([pd.Series([prev]), g.reset_index(drop=True)])
            years.append([int(y), round(float(g.iloc[-1] / prev - 1), 4), round(float((s / s.cummax()).min() - 1), 4)])
        prev = float(g.iloc[-1])
    full = [r for r in years if r[0] < c.index[-1].year]
    return {"since": int(c.index[0].year), "date": c.index[-1].date().isoformat(), "close": round(float(c.iloc[-1]), 2),
            "ath": round(float(ath.iloc[-1]), 2), "ath_date": ath_date.date().isoformat(),
            "since_ath": int((c.index > ath_date).sum()), "dd": round(now, 4), "rare": round(float((dd >= now).mean()), 3),
            "bucket": k, "rows": rows, "all": allrow, "years": years,
            "yr_med_dd": round(float(np.median([r[2] for r in full])), 4) if full else None,
            "yr_up": sum(1 for r in full if r[1] > 0), "yr_n": len(full)}


def breadth_history(frames, spy, last_date, n=126):
    """share of the pool above its 50- and 200-day average, day by day (with SPY for comparison)"""
    cl = pd.DataFrame({t: x["close"] for t, x in frames.items()})
    cl = cl[cl.index <= last_date].iloc[-n:]
    out = {"d0": cl.index[0].date().isoformat(), "n": len(cl)}
    for k, col in (("b50", "sma50"), ("b200", "sma200")):
        s = pd.DataFrame({t: x[col] for t, x in frames.items()}).reindex(cl.index)
        out[k] = [round(float(v), 3) for v in (cl > s).astype(float).where(s.notna()).mean(axis=1).fillna(0)]
    if spy is not None:
        out["spy"] = [round(float(v), 2) for v in spy["close"].reindex(cl.index).ffill().bfill()]
    return out


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
        spy_max = raw["SPY"]["Close"].copy()
    else:
        meta = fetch_universe()
        tickers = sorted(meta.keys())
        print("universe:", len(tickers))
        raw = download(tickers + ["SPY", "QQQ", "^VIX"] + [e for e in ETFS if e not in ("SPY", "QQQ")])
        if len(raw) < 50:
            print("ERROR: too little data downloaded; keeping previous results.")
            return 0
        spy_max = download_max("SPY")
        # never use a session that has not closed yet (a run during market hours sees a half-finished bar)
        now = now_et()
        if is_session(now.date()) and now.time() < CLOSE_DONE:
            for k in list(raw):
                raw[k] = raw[k][raw[k].index.date < now.date()]
            if spy_max is not None:
                spy_max = spy_max[spy_max.index.date < now.date()]
            DIAG["dropped_unfinished"] = now.date().isoformat()

    idx_frames = {k: indicators(raw.pop(k)) for k in ["SPY", "QQQ", "^VIX"] if k in raw}
    etf_frames = {k: indicators(raw.pop(k)) for k in list(ETFS) if k in raw}
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
    regimes = regime_series(frames, idx_frames.get("SPY"), idx_frames.get("^VIX"))
    sp500 = {t for t, m in meta.items() if m.get("sp500")}
    since, removed = membership(fetch_sp500_changes(), set(frames), cutoff, sp500) if sp500 else ({}, set())
    stats = signal_stats(frames, sigs, cutoff, regimes, since)
    smeta = stats.pop("_meta")
    smeta["pit"] = {"late_added": len(since), "removed_missing": len(removed), "sp500": len(sp500)}
    print(f"point-in-time: {len(since)} stocks counted only after joining the S&P 500; {len(removed)} removed stocks not in the data")

    # market regime (today)
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
    rlab = regime_label(bool(spy and spy["above200"]), bool(spy and spy["sma50_up"]), vix, regime["breadth50"])
    regime["label"] = rlab
    regime["desc"] = {
        "进攻": "大盘在 200 日线上方且 50 日线向上，波动率低，市场宽度健康，适合做多类短线信号。",
        "防守": "大盘趋势走弱或恐慌指数偏高，突破类信号失败率上升，宜降低仓位，只看超跌反弹或观望。",
        "谨慎": "大盘多空信号混杂，可以做，但要控制仓位、严格止损。"}[rlab]

    ev_now = {k: evidence(stats[k], rlab) for k in PRIORITY}
    cands = []
    for t, x in frames.items():
        if x.index[-1] != last_date:
            continue
        s = sigs[t].iloc[-1]
        tags = [k for k in PRIORITY if bool(s[k])]
        if not tags:
            continue
        last = x.iloc[-1]
        # the signal with the best evidence in today's regime leads
        prim = max(tags, key=lambda k: (ev_now[k]["proven"], ev_now[k]["edge"] if ev_now[k]["edge"] is not None else -1))
        stop, target, rr = levels(prim, last)
        ev = ev_now[prim]
        exp = ev["edge"] if ev["edge"] is not None else 0.0
        score = max(0.0, min(100.0, 50 + exp * 2500)) * 0.8 + 0.2 * float(last["rs"])
        tail = x.iloc[-60:]
        cands.append({
            "t": t, "name": meta.get(t, {}).get("name", ""), "sector": meta.get(t, {}).get("sector", ""),
            "close": round(float(last["close"]), 2), "chg": round(float(last["chg"]), 4),
            "rs": round(float(last["rs"]), 0), "vr": round(float(last["vr"]), 2), "rsi": round(float(last["rsi14"]), 1),
            "rsi2": round(float(last["rsi2"]), 1), "atr_pct": round(float(last["atr"] / last["close"]), 4),
            "tags": tags, "primary": prim, "stop": stop, "target": target, "r": rr, "score": round(score, 1),
            "exp": None if ev["edge"] is None else round(ev["edge"], 4), "exp_src": ev["src"], "proven": ev["proven"],
            "spark": [round(float(v), 2) for v in tail["close"]], "ema": [round(float(v), 2) for v in tail["ema20"]],
        })
    cands.sort(key=lambda c: (-int(c["proven"]), -c["score"]))
    per, kept = {}, []
    for c in cands:
        per[c["primary"]] = per.get(c["primary"], 0) + 1
        if per[c["primary"]] <= MAX_PER_SIGNAL:
            kept.append(c)

    # 精选: proven signal in today's regime, no earnings inside the holding window, ≤2 per sector, ≤8 names
    ER = {} if args.demo else load_earnings()
    nsec, npick = {}, 0
    for c in kept:
        end = hold_end(last_date.date(), SIGNALS[c["primary"]]["horizon"])
        e = ER.get(c["t"])
        if e and last_date.date().isoformat() < e["date"] <= end.isoformat():
            c["earn"], c["earn_when"], c["earn_move"] = e["date"], e["when"], e["move"]
        elif not args.demo and c["proven"] and c["t"] not in ER:
            c["earn"] = earnings_soon(c["t"], last_date.date(), end)
        if not c.get("earn"):
            c.pop("earn", None)
        why = None
        if not c["proven"]:
            why = "这个信号在当前市场环境下没有经过验证的优势"
        elif c.get("earn"):
            why = "持有期内要发财报，结果接近掷硬币"
        elif nsec.get(c["sector"], 0) >= MAX_PER_SECTOR:
            why = "同板块已经选了 %d 只，避免押注同一个方向" % MAX_PER_SECTOR
        elif npick >= MAX_PICKS:
            why = "精选名额已满（最多 %d 只）" % MAX_PICKS
        if why:
            c["tier"], c["why"] = "watch", why
        else:
            c["tier"] = "pick"
            nsec[c["sector"]] = nsec.get(c["sector"], 0) + 1
            npick += 1
    kept.sort(key=lambda c: (c["tier"] != "pick", -c["score"]))

    try:
        regime["hist"] = breadth_history(frames, idx_frames.get("SPY"), last_date)
    except Exception as e:  # noqa: BLE001
        print("WARN: breadth history failed:", e)
    lt = None
    try:
        if spy_max is not None:
            lt = longterm(spy_max[spy_max.index <= last_date])
            if lt:
                print("long-term: SPY since %s, %.1f%% below the high of %s" % (lt["since"], lt["dd"] * 100, lt["ath_date"]))
    except Exception as e:  # noqa: BLE001
        print("WARN: long-term stats failed:", e)

    tracking = track(frames, today, idx_frames.get("SPY"))
    stale = None
    if not args.demo:
        exp = expected_session(now_et())
        if last_date.date() < exp:
            stale = {"expected": exp.isoformat(), "have": today}
            print("WARNING: data only reaches", today, "but", exp, "has closed — Yahoo is lagging; a later run will retry.")
    write_snapshot(frames, sigs, meta, dict(etf_frames, SPY=idx_frames.get("SPY"), QQQ=idx_frames.get("QQQ")), last_date, today)
    result = {
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date": today, "stale": stale, "demo": bool(args.demo), "universe": len(meta), "scanned": len(frames),
        "regime": regime,
        "signals": {k: dict(SIGNALS[k], stats=stats[k], now=ev_now[k]) for k in PRIORITY}, "stats_meta": smeta,
        "candidates": kept, "tracking": tracking, "lt": lt, "diag": DIAG,
    }
    with open(os.path.join(DATA, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    if not args.demo:
        picks = [{"t": c["t"], "sig": c["primary"], "date": today, "entry": c["close"], "stop": c["stop"],
                  "target": c["target"], "tier": c["tier"], "reg": rlab} for c in kept]
        with open(os.path.join(HIST, today + ".json"), "w", encoding="utf-8") as f:
            json.dump({"date": today, "picks": picks}, f, ensure_ascii=False)
    print(f"{today}: {len(kept)} candidates ({npick} picks), regime={rlab}, stats since {smeta['since']}")
    for k in PRIORITY:
        s = stats[k]
        print(f"  {k:9s} n={s['n']:5d} blocks={s.get('blocks', 0):4d} edge={s.get('edge') or 0:+.4f} "
              f"[{s.get('ci_lo') or 0:+.4f},{s.get('ci_hi') or 0:+.4f}] {s['verdict']} | "
              + " ".join(f"{rg}:{(r.get('edge') or 0):+.4f}/{r.get('blocks', 0)}/{r['verdict']}" for rg, r in s["by_regime"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
