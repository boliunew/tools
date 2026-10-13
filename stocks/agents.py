#!/usr/bin/env python3
"""
🤖 AI 研判：让 TradingAgents 的多个 AI 分析师给今天股票池里最值得看的几只写研判。

Runs after stocks/scan.py. Reads stocks/data/latest.json, picks the top few
candidates (same rule as the page's「值得细看」: 盈亏比 ≥ 1、两周内无财报, by score)
plus anything in AGENTS_EXTRA, and runs TradingAgents (github.com/TauricResearch/TradingAgents)
on each: market / news / fundamentals analysts → bull vs bear debate → trader → risk
team → portfolio manager. Output: stocks/data/agents.json (+ dated copy in history/).

Needs ONE LLM API key in the environment (it is NOT free — every run calls the model):
  DEEPSEEK_API_KEY   cheapest, default if present  (~ a few cents per stock)
  OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY / OPENROUTER_API_KEY …
  or a local model: TRADINGAGENTS_LLM_PROVIDER=ollama (no key, slow on a mini PC)
Without a key the script writes a "not configured" status and exits 0.

Settings (env, all optional):
  AGENTS_N=3                    how many pool stocks per day
  AGENTS_EXTRA=VOO,NVDA         always analyse these too
  AGENTS_ANALYSTS=market,news,fundamentals   (add social for Reddit/StockTwits)
  TRADINGAGENTS_LLM_PROVIDER / _QUICK_THINK_LLM / _DEEP_THINK_LLM   override model choice

  python stocks/agents.py            normal run
  python stocks/agents.py --demo     fake output, no key / network needed (page preview)
  python stocks/agents.py NVDA AAPL  analyse exactly these tickers
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
HIST = os.path.join(DATA, "history")
LATEST = os.path.join(DATA, "latest.json")
OUT = os.path.join(DATA, "agents.json")

# provider -> (key env, quick model, deep model). Order = auto-detect priority (cheap first).
PROVIDERS = [
    ("deepseek",   "DEEPSEEK_API_KEY",   "deepseek-flash",     "deepseek-v4-pro"),
    ("google",     "GOOGLE_API_KEY",     "gemini-3.8-flash",   "gemini-3.8-flash"),
    ("openai",     "OPENAI_API_KEY",     "gpt-6-luna",         "gpt-6-sol"),
    ("anthropic",  "ANTHROPIC_API_KEY",  "claude-haiku-4-5",   "claude-sonnet-5"),
    ("openrouter", "OPENROUTER_API_KEY", None,                 None),   # set models yourself
]

RATING_ZH = {"Buy": "买入", "Overweight": "增持", "Hold": "持有", "Underweight": "减持", "Sell": "卖出", "REVIEW": "看不懂"}
MAX_TEXT = 6000      # chars kept per report in the json


def now_iso():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write(obj):
    os.makedirs(HIST, exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    if obj.get("date") and obj.get("items"):
        with open(os.path.join(HIST, "agents-%s.json" % obj["date"]), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)


def load_json(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def pick_provider():
    """Return (provider, quick, deep) or None when nothing is configured."""
    env = os.environ.get("TRADINGAGENTS_LLM_PROVIDER", "").strip()
    q = os.environ.get("TRADINGAGENTS_QUICK_THINK_LLM", "").strip() or None
    d = os.environ.get("TRADINGAGENTS_DEEP_THINK_LLM", "").strip() or None
    if env:
        for p, key, dq, dd in PROVIDERS:
            if p == env:
                if key and not os.environ.get(key):
                    return None
                return p, q or dq, d or dd
        return env, q, d          # ollama / openai_compatible / anything else: trust the user
    for p, key, dq, dd in PROVIDERS:
        if os.environ.get(key):
            return p, q or dq, d or dd
    return None


def choose_tickers(latest, n, extra):
    cands = latest.get("candidates") or []
    good = [c for c in cands if (c.get("r") or 0) >= 1 and not c.get("earn")]
    good.sort(key=lambda c: -(c.get("score") or 0))
    if len(good) < n:   # not enough clean ones — top up with the best of the rest
        rest = sorted([c for c in cands if c not in good], key=lambda c: -(c.get("score") or 0))
        good += rest[: n - len(good)]
    out, seen = [], set()
    for c in good[:n]:
        out.append({"t": c["t"], "name": c.get("name", ""), "sig": c.get("primary"), "close": c.get("close"),
                    "stop": c.get("stop"), "target": c.get("target"), "src": "pool"})
        seen.add(c["t"])
    for t in extra:
        if t and t not in seen:
            out.append({"t": t, "name": "", "sig": None, "close": None, "src": "extra"})
            seen.add(t)
    return out


def clip(s, n=MAX_TEXT):
    s = (s or "").strip()
    return s if len(s) <= n else s[:n].rstrip() + "\n\n…（已截断）"


def gist(text):
    """First meaningful sentence(s) of the PM decision, without the rating line / headings."""
    lines = []
    for ln in (text or "").splitlines():
        s = ln.strip().strip("*").strip()
        if not s or s.startswith("#") or re.match(r"(?i)^[-*\s]*\**\s*(final\s+)?rating", s) or re.match(r"^[-*]?\s*\**评级", s):
            continue
        s = re.sub(r"\*\*|__|`", "", s).lstrip("-• ").strip()
        if len(s) < 8:
            continue
        lines.append(s)
        if sum(len(x) for x in lines) > 160:
            break
    g = " ".join(lines)
    return g[:220] + ("…" if len(g) > 220 else "")


def run_real(picks, date, prov, analysts):
    from tradingagents.default_config import build_default_config
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    import tradingagents

    p, quick, deep = prov
    cfg = build_default_config()
    cfg["llm_provider"] = p
    if quick:
        cfg["quick_think_llm"] = quick
    if deep:
        cfg["deep_think_llm"] = deep
    cfg["output_language"] = os.environ.get("TRADINGAGENTS_OUTPUT_LANGUAGE") or "Simplified Chinese"
    cfg["max_debate_rounds"] = int(os.environ.get("TRADINGAGENTS_MAX_DEBATE_ROUNDS") or 1)
    cfg["max_risk_discuss_rounds"] = int(os.environ.get("TRADINGAGENTS_MAX_RISK_ROUNDS") or 1)
    base = os.environ.get("TOOLS_DATA")
    if base:   # home server: keep TradingAgents' logs/memory/cache next to the other local data
        root = os.path.join(base, "tradingagents")
        cfg["results_dir"] = os.path.join(root, "logs")
        cfg["data_cache_dir"] = os.path.join(root, "cache")
        cfg["memory_log_path"] = os.path.join(root, "memory", "trading_memory.md")

    ta = TradingAgentsGraph(selected_analysts=tuple(analysts), debug=False, config=cfg)
    items = []
    for pk in picks:
        t0 = time.time()
        print("→ %s …" % pk["t"], flush=True)
        try:
            state, rating = ta.propagate(pk["t"], date)
            dec = state.get("final_trade_decision") or ""
            items.append(dict(pk, ok=True, rating=rating, rating_zh=RATING_ZH.get(rating, rating), gist=gist(dec),
                              decision=clip(dec),
                              plan=clip(state.get("trader_investment_plan"), 3000),
                              reports={k: clip(state.get(k + "_report"), 4000)
                                       for k in ("market", "news", "fundamentals", "sentiment") if state.get(k + "_report")},
                              secs=round(time.time() - t0)))
            print("  %s (%ds)" % (rating, time.time() - t0), flush=True)
        except Exception as e:
            traceback.print_exc()
            items.append(dict(pk, ok=False, error="%s: %s" % (type(e).__name__, str(e)[:300]), secs=round(time.time() - t0)))
    return items, getattr(tradingagents, "__version__", "?")


def run_demo(picks):
    import random
    rnd = random.Random(7)
    items = []
    for pk in picks:
        r = rnd.choice(["Buy", "Overweight", "Hold", "Underweight"])
        dec = ("**Rating**: %s\n\n%s 技术面处于回踩后企稳阶段，新闻面没有重大利空，基本面营收增速放缓但现金流稳健。"
               "多空双方的主要分歧在于估值：多方认为盈利上修空间仍在，空方担心板块轮动。建议小仓位试探，跌破止损位离场。") % (r, pk["t"])
        items.append(dict(pk, ok=True, rating=r, rating_zh=RATING_ZH[r], gist=gist(dec), decision=dec,
                          plan="分两笔建仓：今日收盘价附近买入一半，回踩 EMA20 再买一半。止损设在近 3 日低点下方。",
                          reports={"market": "（示例）RSI 52，价格在 50 日线上方，MACD 柱转正。",
                                   "news": "（示例）近一周没有重大公司新闻，行业新闻偏中性。",
                                   "fundamentals": "（示例）最近一季营收同比 +8%，毛利率持平，自由现金流为正。"},
                          secs=0))
    return items, "demo"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="*")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-run even if today's file is complete")
    a = ap.parse_args()

    latest = load_json(LATEST) or {}
    date = latest.get("date") or dt.date.today().isoformat()
    n = int(os.environ.get("AGENTS_N") or 3)
    extra = [x.strip().upper() for x in (os.environ.get("AGENTS_EXTRA") or "").split(",") if x.strip()]
    analysts = [x.strip() for x in (os.environ.get("AGENTS_ANALYSTS") or "market,news,fundamentals").split(",") if x.strip()]

    if a.tickers:
        picks = [{"t": t.upper(), "name": "", "sig": None, "close": None, "src": "manual"} for t in a.tickers]
    else:
        picks = choose_tickers(latest, n, extra)
    if not picks:
        print("股票池里今天没有候选，跳过。")
        write({"generated": now_iso(), "date": date, "status": "empty", "items": []})
        return 0

    prov = None if a.demo else pick_provider()
    if not a.demo and not prov:
        print("没有配置大模型 API key（DEEPSEEK_API_KEY / OPENAI_API_KEY / …），跳过 AI 研判。")
        old = load_json(OUT) or {}
        if old.get("items"):   # keep the last real result on the page, just flag it
            old["status_note"] = "not_configured"
            write(old)
        else:
            write({"generated": now_iso(), "date": date, "status": "not_configured", "items": []})
        return 0

    old = load_json(OUT) or {}
    if not a.force and not a.demo and not a.tickers and old.get("date") == date and old.get("status") == "ok" \
            and all(any(i.get("t") == p["t"] and i.get("ok") for i in old.get("items", [])) for p in picks):
        print("今天（%s）的研判已经做过了，跳过。加 --force 重跑。" % date)
        return 0

    print("AI 研判 %s：%s  模型 %s" % (date, ", ".join(p["t"] for p in picks), prov and "%s / %s / %s" % prov or "demo"), flush=True)
    if a.demo:
        items, ver = run_demo(picks)
    else:
        items, ver = run_real(picks, date, prov, analysts)

    ok = sum(1 for i in items if i.get("ok"))
    write({
        "generated": now_iso(), "date": date, "demo": bool(a.demo),
        "status": "ok" if ok else "failed",
        "engine": "TradingAgents " + ver,
        "model": None if a.demo else {"provider": prov[0], "quick": prov[1], "deep": prov[2]},
        "analysts": analysts,
        "items": items,
    })
    print("完成：%d/%d 成功 → %s" % (ok, len(items), os.path.relpath(OUT)))
    return 0 if ok or not items else 1


if __name__ == "__main__":
    sys.exit(main())
