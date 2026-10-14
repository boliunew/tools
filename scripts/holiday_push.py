#!/usr/bin/env python3
"""🗓️ 节日提醒推送：每天早上看一眼 holidays/data.json，有要提醒的就推到手机。

什么时候提醒（太平洋时间）：
  · 中国放假、美国联邦假日：提前 7 天、前 1 天、当天
  · 美股休市：前 1 天
  · 夏令时切换、报税截止：前 1 天（报税另外提前 7 天）
  · 其他节日（传统节日、情人节、万圣节……）：当天
同一天的提醒合成一条，附一条冷知识。

怎么推送：
  · GitHub 上：在 issue「🗓️ 节日提醒」下留言并 @ 仓库主人 → GitHub App 推送到手机 + 邮件
  · 家里主机（LOCAL_ISSUES=1）：写进本地通知中心，ntfy 推送到手机
同一天只推一次（重跑不会重复）。

  python scripts/holiday_push.py            正常运行
  python scripts/holiday_push.py --dry      只打印，不推送
  python scripts/holiday_push.py --date 2026-12-24 --dry   模拟某一天
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "holidays", "data.json")
TITLE = "🗓️ 节日提醒"
LOCAL = bool(os.environ.get("LOCAL_ISSUES"))
OWNER = os.environ.get("OWNER", "boliunew")
PAGE = (os.environ.get("PUBLIC_URL", "").rstrip("/") or "https://boliunew.github.io/tools") + "/holidays.html"
WD = "一二三四五六日"


def today_la():
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("America/Los_Angeles")).date()
    except Exception:
        return (dt.datetime.utcnow() - dt.timedelta(hours=8)).date()


def md(d):
    return "%d月%d日（周%s）" % (d.month, d.day, WD[d.weekday()])


def lines_for(D, day):
    info = D.get("info", {})
    out, facts = [], []
    for x in D["items"]:
        a = dt.date.fromisoformat(x.get("from") or x["d"])
        b = dt.date.fromisoformat(x.get("to") or x["d"])
        n = (a - day).days
        flag = "🇨🇳" if x["c"] == "cn" else "🇺🇸"
        name = x["n"]
        I = info.get(x["c"] + ":" + re.sub(r"（补休）$", "", name))
        off = x["k"] == "off"
        when = None
        if off and n in (7, 1, 0):
            when = n
        elif x["k"] == "nyse" and n == 1:
            when = n
        elif name in ("夏令时开始", "夏令时结束") and n == 1:
            when = n
        elif name == "报税截止" and n in (7, 1, 0):
            when = n
        elif x["k"] in ("fest", "ca") and n == 0:
            when = n
        if when is None:
            continue
        if when == 0 and x["c"] == "cn" and off and x.get("len", 1) > 1:
            head = "今天起放%s假" % name
        elif when == 0:
            head = "今天是%s" % name
        elif when == 1:
            head = "明天是%s" % name
        else:
            head = "还有 7 天就是%s" % name
        detail = []
        if x["c"] == "cn" and off:
            detail.append(("放假 %d 天：%s – %s" % (x["len"], md(a), md(b))) if x["len"] > 1 else "放假 1 天")
            if x.get("work"):
                detail.append("调休上班：" + "、".join(md(dt.date.fromisoformat(w)) for w in x["work"]))
            if x.get("est"):
                detail.append("（放假安排是按往年规则估算的，以国务院公布为准）")
        elif x["c"] == "us" and off:
            detail.append("联邦假日：政府、银行、邮局放假")
        if x.get("nyse"):
            detail.append("美股休市")
        if name in ("夏令时开始", "夏令时结束"):
            detail.append(x.get("note", ""))
        if name == "报税截止":
            detail.append("Form 1040 截止；来不及可申请延期，但税要先交")
        if when == 0 and I and x["d"] == day.isoformat():
            detail.append(I["c"])
        out.append("%s %s %s" % (x["e"], flag, head) + ("\n   " + "；".join(d for d in detail if d) if detail else ""))
        if I and I.get("f"):
            facts.append(I["f"][day.toordinal() % len(I["f"])])
    return out, facts[:1]


# ------------------------------------------------------------------ delivery
def gh(method, path, body=None):
    repo = os.environ["GITHUB_REPOSITORY"]
    req = urllib.request.Request("https://api.github.com/repos/%s%s" % (repo, path), method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
                                          "Accept": "application/vnd.github+json", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    return json.loads(raw) if raw else None


INTRO = ("节日和假期提醒都会推到这里：中国放假、美国联邦假日提前 7 天 / 前 1 天 / 当天各提醒一次，"
         "美股休市和夏令时切换提前 1 天，其他节日当天提醒。\n\n完整列表：%s\n\n不想收了就关闭这个 issue。" % PAGE)


def deliver(text, tag):
    if LOCAL:
        sys.path.insert(0, os.path.join(ROOT, "selfhost"))
        import localgh
        iss = next((i for i in localgh.list_issues("all") if i["title"] == TITLE), None)
        if not iss:
            iss = localgh.create_issue(TITLE, INTRO)
        if iss.get("state") != "open":
            print("「%s」已关闭，不推送。" % TITLE)
            return
        full = localgh.get_issue(iss["number"], with_comments=True)
        if any(tag in (c.get("body") or "") for c in full.get("comment_list", [])):
            print("今天已经推过了。")
            return
        localgh.add_comment(iss["number"], text + "\n" + tag)
        print("已推送（ntfy）")
        return
    issues = gh("GET", "/issues?state=all&per_page=100&creator=github-actions%5Bbot%5D") or []
    iss = next((i for i in issues if i.get("title") == TITLE and "pull_request" not in i), None)
    if not iss:
        iss = gh("POST", "/issues", {"title": TITLE, "body": INTRO})
    if iss.get("state") != "open":
        print("「%s」已关闭，不推送。" % TITLE)
        return
    cs = gh("GET", "/issues/%d/comments?per_page=100" % iss["number"]) or []
    if any(tag in (c.get("body") or "") for c in cs):
        print("今天已经推过了。")
        return
    gh("POST", "/issues/%d/comments" % iss["number"], {"body": text + "\n\n@" + OWNER + "\n" + tag})
    print("已推送（GitHub issue #%d）" % iss["number"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--date")
    ap.add_argument("--test", action="store_true", help="发一条测试推送，看手机能不能收到")
    a = ap.parse_args()
    day = dt.date.fromisoformat(a.date) if a.date else today_la()
    with open(DATA, encoding="utf-8") as f:
        D = json.load(f)
    if a.test:
        nxt = []
        for k in range(1, 120):
            ls, _ = lines_for(D, day + dt.timedelta(days=k))
            if ls:
                nxt.append("%s：%s" % (md(day + dt.timedelta(days=k)), ls[0].split("\n")[0]))
            if len(nxt) >= 3:
                break
        text = "✅ 节日提醒已开启，手机能收到这条就说明推送通了。\n\n接下来会提醒：\n" + "\n".join(nxt) + "\n\n👉 " + PAGE
        print(text)
        if not a.dry:
            deliver(text, "<!-- hol:test-%s -->" % dt.datetime.utcnow().strftime("%Y%m%d%H%M%S"))
        return 0
    lines, facts = lines_for(D, day)
    if not lines:
        print("%s：没有要提醒的节日。" % day)
        return 0
    text = "\n".join(lines)
    if facts:
        text += "\n\n💡 " + facts[0]
    text += "\n\n👉 " + PAGE
    tag = "<!-- hol:%s -->" % day.isoformat()
    print(text)
    if not a.dry:
        deliver(text, tag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
