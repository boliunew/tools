"""RSI：信号日报和股票池两套代码必须算出一样的结果（之前旧机器人就是 RSI 算错了）"""
import datetime as dt
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from conftest import load

scan = load("scan", "stocks/scan.py")
sb = load("signal_bot", "stocks/signal_bot.py")


def prices(n=300, seed=7):
    r = np.random.default_rng(seed)
    return pd.Series(100 * np.cumprod(1 + r.normal(0, 0.02, n)), index=pd.bdate_range("2025-01-01", periods=n))


def test_rsi_two_implementations_agree():
    c = prices()
    a, b = sb.rsi_wilder(c, 14).iloc[30:], scan.rsi(c, 14).iloc[30:]
    assert np.allclose(a, b, atol=1e-6)


def test_rsi_bounds_and_direction():
    up = pd.Series(np.linspace(100, 150, 60))
    down = pd.Series(np.linspace(150, 100, 60))
    assert sb.rsi_wilder(up, 14).iloc[-1] > 95
    assert sb.rsi_wilder(down, 14).iloc[-1] < 5


def test_unfinished_bar_dropped_during_session():
    df = pd.DataFrame({"Close": [1, 2, 3]}, index=pd.to_datetime(["2026-10-20", "2026-10-21", "2026-10-22"]))
    et = ZoneInfo("America/New_York")
    assert len(sb.drop_unfinished_bar(df, dt.datetime(2026, 10, 22, 11, 0, tzinfo=et))) == 2
    assert len(sb.drop_unfinished_bar(df, dt.datetime(2026, 10, 22, 17, 0, tzinfo=et))) == 3


def test_signal_hysteresis():
    cfg, st, out = sb.CONFIG, {}, []
    for r in [40, 32, 35, 36, 38, 34]:
        st, txt, _ = sb.decide({"rsi": r, "trend": True, "trend_prev": True, "accum": False}, st, cfg)
        out.append(st["oversold"])
    assert out == [False, True, True, True, False, False]
