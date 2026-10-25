"""
signal_bot.py — 美股信号日报 Telegram 机器人
==================================================
每天收盘后，检查一组股票，然后推送一条简洁的信号报告到 Telegram。

相比截图里的旧版本，主要改进：
  1. 只用【已收盘】的日K计算 RSI，盘中跑也不会算进未完成的 K 线。
     这修复了 RSI 乱跳的问题，比如 AAPL 价格不变 RSI 却 +16。
  2. 信号带缓冲区（滞后）：RSI 跌破 33 才触发买入，回到 37 以上才取消，
     所以信号不会在盘中来回翻转。
  3. 自动去重：最新一根收盘K没有变化，就不推送。
     周末、节假日、盘前重复跑都不会刷屏。
  4. 有进有出：除了超卖买入，还有“过热”和“趋势破位”提示。
  5. 手机友好：一只股票一行，没有表格，不会错位。

用法：
  pip install yfinance pandas requests
  python signal_bot.py              # 正常运行：有新收盘数据才推送
  python signal_bot.py --dry-run    # 只打印，不推送、不保存状态
  python signal_bot.py --force      # 不管有没有新数据都推送

Telegram 配置（二选一）：
  - 设置环境变量 TG_BOT_TOKEN 和 TG_CHAT_ID
    （GitHub 上：仓库 Settings → Secrets and variables → Actions 里加这两个 secret）
  - 或者直接填在下面的 CONFIG 里
没配 Telegram 时只打印报告、正常退出，不会让工作流报错。
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

# ============================== 配置 ==============================
CONFIG = {
    "TICKERS": ["NVDA", "AMD", "MSFT", "GOOGL", "AAPL", "TSLA"],

    "TG_BOT_TOKEN": os.getenv("TG_BOT_TOKEN", ""),   # 例：123456:ABC-xyz
    "TG_CHAT_ID":   os.getenv("TG_CHAT_ID", ""),     # 例：123456789

    # RSI 参数（Wilder 平滑，与 TradingView 一致）
    "RSI_PERIOD": 14,
    "OVERSOLD_ENTER": 33,   # 跌破 → 进入超卖状态
    "OVERSOLD_EXIT": 37,    # 回到这里以上 → 退出超卖状态
    "OVERBOUGHT_ENTER": 70,
    "OVERBOUGHT_EXIT": 65,

    # 趋势：收盘价在 50 日均线上方，并且 50 日均线比 10 天前高
    "TREND_MA": 50,
    "TREND_SLOPE_DAYS": 10,

    # 吸筹：Chaikin 资金流 CMF(20) 大于这个值，代表资金在流入
    "CMF_PERIOD": 20,
    "CMF_THRESHOLD": 0.05,

    # 状态文件：GitHub 上存在 stocks/data/ 里由工作流提交；家里主机存在 $TOOLS_DATA 里
    "STATE_FILE": str(Path(os.environ["TOOLS_DATA"]) / "signal_bot_state.json") if os.environ.get("TOOLS_DATA")
                  else str(Path(__file__).resolve().parent / "data" / "signal_bot_state.json"),
}

ET = ZoneInfo("America/New_York")


# ============================== 数据 ==============================
def fetch_history(ticker: str) -> pd.DataFrame:
    """下载约 1 年日K，只保留已经收盘的 K 线。"""
    import yfinance as yf

    df = yf.Ticker(ticker).history(period="1y", interval="1d", auto_adjust=True)
    if df.empty:
        raise ValueError(f"{ticker}: 没有拿到数据")
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return drop_unfinished_bar(df)


def drop_unfinished_bar(df: pd.DataFrame, now_et: datetime | None = None) -> pd.DataFrame:
    """如果最后一根是今天的K线，而美东时间还没到 16:10，就去掉它（盘中数据不算）。"""
    now_et = now_et or datetime.now(ET)
    if len(df) and df.index[-1].date() == now_et.date():
        if (now_et.hour, now_et.minute) < (16, 10):
            df = df.iloc[:-1]
    return df


# ============================== 指标 ==============================
def rsi_wilder(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = gain / loss.replace(0, 1e-12)
    return 100 - 100 / (1 + rs)


def chaikin_money_flow(df: pd.DataFrame, period: int) -> pd.Series:
    rng = (df["High"] - df["Low"]).replace(0, 1e-12)
    mfm = ((df["Close"] - df["Low"]) - (df["High"] - df["Close"])) / rng
    mfv = mfm * df["Volume"]
    return mfv.rolling(period).sum() / df["Volume"].rolling(period).sum()


def analyze(df: pd.DataFrame, cfg: dict) -> dict:
    close = df["Close"]
    ma = close.rolling(cfg["TREND_MA"]).mean()
    rsi = rsi_wilder(close, cfg["RSI_PERIOD"])
    cmf = chaikin_money_flow(df, cfg["CMF_PERIOD"])

    def trend_at(i: int) -> bool:
        return bool(close.iloc[i] > ma.iloc[i] and ma.iloc[i] > ma.iloc[i - cfg["TREND_SLOPE_DAYS"]])

    return {
        "date": df.index[-1].strftime("%Y-%m-%d"),
        "price": float(close.iloc[-1]),
        "chg_pct": float(close.iloc[-1] / close.iloc[-2] - 1) * 100,
        "rsi": float(rsi.iloc[-1]),
        "cmf": float(cmf.iloc[-1]),
        "trend": trend_at(-1),
        "trend_prev": trend_at(-2),
        "accum": bool(cmf.iloc[-1] > cfg["CMF_THRESHOLD"]),
    }


# ============================== 信号（带状态） ==============================
def decide(a: dict, prev: dict, cfg: dict) -> tuple[dict, str | None, str]:
    """返回 (新状态, 信号文字或None, 图标)。prev 是这只股票上次的状态。"""
    rsi = a["rsi"]

    # 超卖状态：滞后判断，避免来回跳
    oversold = prev.get("oversold", False)
    if not oversold and rsi < cfg["OVERSOLD_ENTER"]:
        oversold = True
    elif oversold and rsi > cfg["OVERSOLD_EXIT"]:
        oversold = False

    overbought = prev.get("overbought", False)
    if not overbought and rsi > cfg["OVERBOUGHT_ENTER"]:
        overbought = True
    elif overbought and rsi < cfg["OVERBOUGHT_EXIT"]:
        overbought = False

    state = {"oversold": oversold, "overbought": overbought, "trend": a["trend"]}

    # 优先级：破位 > 超卖买入 > 过热
    if a["trend_prev"] and not a["trend"]:
        return state, "趋势破位，跌回50日线下 → 减仓/止损检查", "🔴"
    if oversold and a["trend"]:
        if a["accum"]:
            return state, "上升趋势中超卖 + 资金流入 → 可买入", "🟢"
        return state, "上升趋势中超卖，但无吸筹 → 轻仓试探", "🟡"
    if oversold and not a["trend"]:
        return state, "超卖但趋势向下 → 不接飞刀，观察", "⚪"
    if overbought:
        return state, "RSI过热 → 勿追高，可考虑分批止盈", "🟠"
    return state, None, "⚪"


# ============================== 消息 ==============================
def fmt_line(t: str, a: dict, text: str | None, icon: str) -> str:
    tr = "✅" if a["trend"] else "❌"
    ac = "✅" if a["accum"] else "❌"
    base = f"{icon} <b>{t}</b> {a['price']:.2f} ({a['chg_pct']:+.1f}%) RSI {a['rsi']:.0f}"
    meta = f"   趋势{tr} 吸筹{ac}"
    if text:
        return f"{base}\n{meta}\n   → {text}"
    return f"{base}{meta}"


def build_message(rows: list, date: str) -> str:
    actionable = [r for r in rows if r[2]]
    quiet = [r for r in rows if not r[2]]
    lines = [f"📊 <b>信号日报</b>  {date} 收盘", ""]
    if actionable:
        lines += [fmt_line(*r) for r in actionable]
    else:
        lines.append("今天没有需要操作的信号。")
    if quiet:
        lines += ["", "<i>无信号：</i>"]
        lines += [fmt_line(*r) for r in quiet]
    return "\n".join(lines)


def send_telegram(text: str, cfg: dict) -> None:
    token, chat = cfg["TG_BOT_TOKEN"], cfg["TG_CHAT_ID"]
    if not token or not chat:
        raise RuntimeError("没有设置 TG_BOT_TOKEN / TG_CHAT_ID")
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat, "text": text, "parse_mode": "HTML",
              "disable_web_page_preview": True},
        timeout=20,
    )
    if not r.ok:
        # 不打印令牌；Telegram 的报错一般是 chat not found（没先给机器人发过消息 / ID 填错）或 Unauthorized（令牌错）
        msg = "Telegram 推送失败：HTTP %s %s" % (r.status_code, r.text[:200])
        if os.environ.get("GITHUB_ACTIONS"):
            print("::error title=信号日报::" + msg)
        raise RuntimeError(msg)


# ============================== 主流程 ==============================
def load_state(path: str) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"last_sent_date": None, "tickers": {}}


def run(cfg: dict, dry_run: bool = False, force: bool = False, fetch=fetch_history) -> str | None:
    state = load_state(cfg["STATE_FILE"])
    rows, new_states, dates, errors = [], {}, [], []

    for t in cfg["TICKERS"]:
        try:
            a = analyze(fetch(t), cfg)
        except Exception as e:  # 单只股票失败不影响其他
            errors.append(f"{t}: {e}")
            continue
        prev = state["tickers"].get(t, {})
        # 同一根K线重复跑时，用上一根K线时的状态做判断，保证结果一致
        if prev.get("date") == a["date"]:
            prev = prev.get("prev_state", {})
        new_state, text, icon = decide(a, prev, cfg)
        new_states[t] = {**new_state, "date": a["date"], "prev_state": prev}
        rows.append((t, a, text, icon))
        dates.append(a["date"])

    if not rows:
        print("全部股票都拿不到数据：", errors)
        if os.environ.get("GITHUB_ACTIONS"):
            print("::warning title=信号日报::全部股票都拿不到数据：" + "；".join(errors)[:300])
        return None

    latest = max(dates)
    if latest == state.get("last_sent_date") and not force:
        print(f"{latest} 的收盘数据已经推送过了，跳过（加 --force 可强制推送）")
        return None

    msg = build_message(rows, latest)
    if errors:
        msg += "\n\n⚠️ 数据失败：" + "；".join(errors)
    print(msg)

    if not dry_run and not (cfg["TG_BOT_TOKEN"] and cfg["TG_CHAT_ID"]):
        print("\n⚠️ 没有设置 TG_BOT_TOKEN / TG_CHAT_ID，只打印不推送")
        return msg
    if not dry_run:
        try:   # 📱 同时推到工具箱 App
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
            from notify import push_app
            push_app(msg, "signal")
        except Exception as e:  # noqa: BLE001
            print("App 推送跳过：", e)
        send_telegram(msg, cfg)
        Path(cfg["STATE_FILE"]).parent.mkdir(parents=True, exist_ok=True)
        state["tickers"].update(new_states)
        state["last_sent_date"] = latest
        Path(cfg["STATE_FILE"]).write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        print("\n✅ 已推送")
        if os.environ.get("GITHUB_ACTIONS"):
            print("::notice title=信号日报::已推送到 Telegram（%s，%d 只）" % (latest, len(rows)))
    return msg


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows 控制台中文/emoji
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="只打印，不推送")
    p.add_argument("--force", action="store_true", help="即使已推送过也再推一次")
    args = p.parse_args()
    run(CONFIG, dry_run=args.dry_run, force=args.force)
