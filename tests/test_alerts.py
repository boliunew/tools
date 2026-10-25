"""股价提醒：标题怎么写都要解析对"""
from conftest import load

alerts = load("alerts", "stocks/alerts.py")


def test_parse_titles():
    cases = {
        "股价提醒: VOO 跌到 650": ("VOO", "below", 650),
        "股价提醒：NVDA 涨到 250.5": ("NVDA", "above", 250.5),
        "股价提醒 QQQ RSI 30": ("QQQ", "rsi", 30),
        "股价提醒: SPY 200日线": ("SPY", "ma200", None),
        "股价提醒: TSLA 单日涨跌 5": ("TSLA", "move", 5),
        "股价提醒: BRK.B 回撤 10": ("BRK-B", "dd", 10),
        "股价提醒: AAPL 信号": ("AAPL", "sig", None),
    }
    for title, (t, kind, v) in cases.items():
        a = alerts.parse(title)
        assert a and (a["t"], a["kind"], a["v"]) == (t, kind, v), title


def test_parse_rejects_nonsense():
    assert alerts.parse("股价提醒: 随便说说") is None
    assert alerts.parse("股价提醒: VOO 跌到") is None
