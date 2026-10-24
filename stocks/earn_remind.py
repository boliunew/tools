#!/usr/bin/env python3
"""📅 财报提醒：下一个交易日要发财报的股票，前一天收盘后推送到 Telegram。

关心的股票 = 今日股票池候选 + 「股价提醒」里的股票 + stocks/watchlist.txt + 当天市值最大的 10 家（大盘风向标）。
同一个财报日只提醒一次（记在 earnings/data/remind.json）。在 earnings.yml 里、财报日历更新之后运行。
  python stocks/earn_remind.py          正常运行
  python stocks/earn_remind.py --dry    只打印"""
import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
STATE = os.path.join(ROOT, "earnings", "data", "remind.json")
WK = "一二三四五六日"


def load(p, d):
    try:
        with open(os.path.join(ROOT, p), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def la_now():
    from zoneinfo import ZoneInfo
    return dt.datetime.now(ZoneInfo("America/Los_Angeles"))


def main(dry=False):
    now = la_now()
    E = load("earnings/data/latest.json", {})
    days = sorted((d for d in E.get("days", []) if d.get("date", "") > now.date().isoformat() and d.get("earnings")), key=lambda d: d["date"])
    if not days:
        print("没有接下来的财报日")
        return 0
    nxt = days[0]
    gap = (dt.date.fromisoformat(nxt["date"]) - now.date()).days
    # 只在「下一个交易日」的前一天提醒：平日下午收盘后，或周末提醒周一的
    if gap > 3 or (gap > 1 and now.weekday() < 4):
        print("下一个财报日 %s 还早" % nxt["date"])
        return 0
    if now.weekday() < 5 and now.hour < 13 and not dry:
        print("还没收盘，等下午再提醒")
        return 0
    st = load("earnings/data/remind.json", {})
    if st.get("last") == nxt["date"] and not dry:
        print("%s 已经提醒过" % nxt["date"])
        return 0
    care = {}
    for c in load("stocks/data/latest.json", {}).get("candidates", []):
        care[c["t"]] = "股票池"
    for a in (load("stocks/data/alerts.json", {}).get("items") or {}).values():
        if a.get("t"):
            care[a["t"]] = "你的提醒"
    try:
        for line in open(os.path.join(HERE, "watchlist.txt"), encoding="utf-8"):
            t = line.split("#")[0].strip().upper()
            if t:
                care.setdefault(t, "关注")
    except FileNotFoundError:
        pass
    allx = sorted(nxt["earnings"], key=lambda e: -(e.get("cap") or 0))
    for e in allx[:10]:
        care.setdefault(e["t"], "当天市值最大")
    hits = [e for e in allx if e["t"] in care]
    when = {"pre": "盘前", "post": "盘后"}
    d = dt.date.fromisoformat(nxt["date"])
    lines = ["📅 **财报提醒 · %d月%d日 周%s**（共 %d 家发财报）" % (d.month, d.day, WK[d.weekday()], len(allx)), ""]
    for e in hits[:15]:
        s = e.get("stats") or {}
        mv = (" · 历史财报日平均波动 ±%.1f%%" % (s["avg_abs"] * 100)) if s.get("avg_abs") else ""
        lines.append("• **%s** %s（%s）%s · %s%s" % (e["t"], (e.get("name") or "")[:24], when.get(e.get("when"), "时间未定"),
                                                   (" · 预期 EPS %s" % e["eps_est"]) if e.get("eps_est") is not None else "", care[e["t"]], mv))
    lines += ["", "[打开财报日历](https://boliunew.github.io/tools/earnings.html)"]
    text = "\n".join(lines)
    print(text)
    if dry:
        return 0
    from notify import tg
    if tg(text, "earnings"):
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump({"last": nxt["date"], "sent": now.isoformat()}, f)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    sys.exit(main(ap.parse_args().dry))
