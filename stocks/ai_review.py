#!/usr/bin/env python3
"""🤖 AI 盘后解读：每日股票池扫描之后，让 Cloudflare Workers AI 读一遍今天的数据，写一段中文解读，存到 stocks/data/ai.json（stocks.html 顶部显示）。

AI 看到的：大盘状态（SPY / QQQ / VIX / 宽度）、涨跌幅榜和板块、评分最高的候选股（信号、相对强度、RSI、止损目标、财报日、回测结论）、
各信号的回测统计、跟踪成绩、接下来几天的经济数据和财报、今天的商业 / 科技新闻标题。
AI 写的：大盘解读、板块和资金动向、对前几只候选股逐个点评（信号含义 + 风险）、这几天要留意的事。
规则：只根据给它的数据写，数字照抄不改；回测说「优势未证实」就要照实说；不给买卖建议，不预测涨跌。
没配 CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID 或 AI 失败时什么都不写（页面上就不显示这张卡）。

  python stocks/ai_review.py          正常运行
  python stocks/ai_review.py --dry    只打印，不写文件"""
import argparse
import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from brief.build import cf_ai, parse_json, notice, clip, load, md, la_now  # noqa: E402

OUT = os.path.join(HERE, "data", "ai.json")
SECTOR = {"Information Technology": "信息技术", "Health Care": "医疗保健", "Financials": "金融", "Consumer Discretionary": "可选消费",
          "Consumer Staples": "必需消费", "Industrials": "工业", "Energy": "能源", "Materials": "原材料", "Utilities": "公用事业",
          "Real Estate": "房地产", "Communication Services": "通信服务"}


def pct(x, d=1):
    return "—" if x is None else ("%+." + str(d) + "f%%") % (x * 100)


def context():
    S = load("stocks/data/latest.json")
    snap = load("stocks/data/snap.json")
    E = load("earnings/data/latest.json")
    L = load("news/data/latest.json")
    if not S.get("candidates") and not S.get("regime"):
        return None, None, None
    rg = S.get("regime") or {}
    lines = ["【数据日期】%s" % S.get("date")]
    spy, qqq = rg.get("spy") or {}, rg.get("qqq") or {}
    lines.append("【大盘】状态「%s」（%s）；SPY %s 收 %s，RSI14 %s，%s50日线、%s200日线；QQQ %s 收 %s，RSI14 %s，%s50日线；VIX %s；站上50日线的股票占 %s，站上200日线占 %s" % (
        rg.get("label"), rg.get("desc", ""), pct(spy.get("chg"), 2), spy.get("close"), spy.get("rsi14"), "在" if spy.get("above50") else "不在",
        "在" if spy.get("above200") else "不在", pct(qqq.get("chg"), 2), qqq.get("close"), qqq.get("rsi14"), "在" if qqq.get("above50") else "不在",
        rg.get("vix"), pct(rg.get("breadth50"), 0).lstrip("+"), pct(rg.get("breadth200"), 0).lstrip("+")))
    rows = [(k, v) for k, v in (snap.get("rows") or {}).items() if isinstance(v.get("d"), (int, float))]
    if rows:
        rows.sort(key=lambda kv: kv[1]["d"])
        lines.append("【涨幅前 6】" + "；".join("%s %s(%s)" % (k, pct(v["d"]), SECTOR.get(v.get("s"), v.get("s"))) for k, v in rows[::-1][:6]))
        lines.append("【跌幅前 6】" + "；".join("%s %s(%s)" % (k, pct(v["d"]), SECTOR.get(v.get("s"), v.get("s"))) for k, v in rows[:6]))
        sec = {}
        for k, v in rows:
            sec.setdefault(SECTOR.get(v.get("s"), v.get("s") or "其他"), []).append(v["d"])
        avg = sorted(((s, sum(x) / len(x), len(x)) for s, x in sec.items() if len(x) >= 5), key=lambda t: -t[1])
        lines.append("【板块当日平均涨跌】" + "；".join("%s %s" % (s, pct(a, 2)) for s, a, n in avg))
    sig = S.get("signals") or {}
    lines.append("【各信号回测（持有期内相对基准的平均超额收益 edge）】" + "；".join(
        "%s：edge %s，胜率 %s，结论「%s」" % (v.get("name"), pct((v.get("stats") or {}).get("edge"), 2), pct((v.get("stats") or {}).get("win"), 0).lstrip("+"), (v.get("stats") or {}).get("verdict"))
        for v in sig.values()))
    T = (S.get("tracking") or {})
    if T.get("summary"):
        s = T["summary"]
        lines.append("【实盘跟踪（自 %s）】共 %s 笔，已结束 %s 笔，胜率 %s，平均 %s，相对 SPY %s" % (
            T.get("since"), s.get("total"), s.get("closed"), pct(s.get("win"), 0).lstrip("+"), pct(s.get("mean"), 2), pct(s.get("vs_spy"), 2)))
    cands = sorted(S.get("candidates") or [], key=lambda c: -(c.get("score") or 0))[:6]
    lines.append("【评分最高的候选股】")
    for i, c in enumerate(cands):
        s = sig.get(c.get("primary"), {})
        earn = ("，财报 %s%s" % (c["earn"], {"pre": "盘前", "post": "盘后"}.get(c.get("earn_when"), ""))) if c.get("earn") else ""
        lines.append("C%d %s %s（%s）：收 %s（%s），信号「%s」（%s），相对强度 %s，RSI14 %s，量比 %s，止损 %s，目标 %s，风险回报 %s，等级 %s（%s）%s" % (
            i, c["t"], c.get("name"), SECTOR.get(c.get("sector"), c.get("sector")), c.get("close"), pct(c.get("chg")), s.get("name", c.get("primary")),
            clip(s.get("desc", ""), 60), c.get("rs"), c.get("rsi"), c.get("vr"), c.get("stop"), c.get("target"), c.get("r"),
            {"pick": "精选", "watch": "观察"}.get(c.get("tier"), c.get("tier")), c.get("why", ""), earn))
    today = la_now().date().isoformat()
    end = (dt.date.fromisoformat(today) + dt.timedelta(days=6)).isoformat()
    ev = []
    for d in E.get("days", []):
        if today <= d.get("date", "") <= end:
            for m in d.get("macro", []):
                ev.append("%s %s %s（重要性 %s）" % (md(d["date"]), m.get("time") or "", m.get("title"), m.get("imp")))
            big = sorted(d.get("earnings", []), key=lambda e: -(e.get("cap") or 0))[:4]
            if big:
                ev.append("%s 财报：%s" % (md(d["date"]), "、".join(e["t"] for e in big)))
    lines.append("【接下来几天】" + ("；".join(ev) or "无"))
    heads = [a for a in L.get("articles", []) if a.get("topic") in ("商业", "科技")][:12]
    if heads:
        lines.append("【今天的商业 / 科技新闻标题】" + "；".join(a["title"] for a in heads))
    return "\n".join(lines), [c["t"] for c in cands], S.get("date")


def main(dry=False):
    ctx, tickers, data_date = context()
    if not ctx:
        notice("AI 盘后解读：股票池数据为空，跳过")
        return 0
    system = ("你是一位冷静、务实的美股量化分析助理，读者是用 Python 自己做波段交易系统的散户。请根据给你的当日数据写中文盘后解读。"
              "规则：只根据给你的数据写，数字照抄、不要改、不要编；回测结论是「优势未证实」或「跑输基准」的信号必须照实说明，不要美化；"
              "不给买入卖出建议，不预测涨跌和目标价；语气平实，不渲染情绪。只输出 JSON。")
    user = (ctx + "\n\n输出 JSON：" +
            '{"market":"大盘解读，3–4 句：今天是什么环境、指数和宽度说明了什么、VIX 和情绪","sectors":"板块和资金动向，2 句",'
            '"picks":[{"id":"C编号","note":"2 句：这只为什么出现在名单上（信号含义、相对强度、量比）+ 主要风险（RSI 过热、临近财报、信号回测未证实等）"}],'
            '"watch":["这几天要留意的事，每条一句，2–4 条"],"lesson":"结合各信号回测和实盘跟踪，一句话提醒今天用这套系统要注意什么"}'
            "\npicks 点评评分最高的前 3–4 只。")
    text, model, err = cf_ai(system, user)
    if not text:
        notice("AI 盘后解读没生成：" + err)
        return 0
    try:
        J = parse_json(text)
    except Exception as e:
        notice("AI 盘后解读返回格式不对：%s" % e)
        return 0
    picks = []
    for p in (J.get("picks") or [])[:4]:
        m = re.fullmatch(r"C(\d+)", str(p.get("id", "")).strip())
        if m and int(m.group(1)) < len(tickers) and p.get("note"):
            picks.append({"t": tickers[int(m.group(1))], "note": clip(p["note"], 160)})
    out = {"date": data_date, "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "model": model,
           "market": clip(J.get("market", ""), 260), "sectors": clip(J.get("sectors", ""), 160), "picks": picks,
           "watch": [clip(w, 90) for w in (J.get("watch") or [])[:4] if isinstance(w, str)], "lesson": clip(J.get("lesson", ""), 120)}
    if not out["market"]:
        notice("AI 盘后解读内容为空，跳过")
        return 0
    notice("AI 盘后解读成功（%s）：点评 %d 只" % (model, len(picks)))
    if dry:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    sys.exit(main(ap.parse_args().dry))
