#!/usr/bin/env python3
"""🩺 每日体检：检查每份自动更新的数据是不是新鲜、内容是不是正常，自动任务有没有失败，地图底图还能不能用。
结果写进 status/health.json（status.html 用）。有异常时在 issue「🩺 系统体检」下留言 @ 仓库主人 →
GitHub App 推送到手机 + 邮件；问题没变就不重复提醒；全部恢复时再发一条「恢复正常」。

  python scripts/health_check.py          正常运行（GitHub Actions 里）
  python scripts/health_check.py --dry    只检查、只打印，不写文件也不留言
只用标准库。"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "status", "health.json")
REPO = os.environ.get("GITHUB_REPOSITORY", "boliunew/tools")
OWNER = os.environ.get("OWNER", REPO.split("/")[0])
TOKEN = os.environ.get("GITHUB_TOKEN", "")
TITLE = "🩺 系统体检"
PAGE = "https://%s.github.io/%s/status.html" % (OWNER, REPO.split("/")[1])
UA = "boliunew-tools-health/1.0"
NOW = dt.datetime.now(dt.timezone.utc)


def la_now():
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("America/Los_Angeles"))
    except Exception:
        return NOW - dt.timedelta(hours=7)


def get(url, timeout=25, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read()
        return (b, r.headers.get("Content-Type", "")) if raw else b.decode("utf-8", "replace")


def load(path):
    if path.startswith("http"):
        return json.loads(get(path + ("&" if "?" in path else "?") + "t=%d" % NOW.timestamp()))
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return json.load(f)


def when(v):
    """generated / updated / date 字段 → UTC datetime（只有日期的按太平洋时间当天结束算）"""
    if isinstance(v, (int, float)):
        return dt.datetime.fromtimestamp(v / (1000 if v > 1e11 else 1), dt.timezone.utc)
    s = str(v).strip()
    if len(s) == 10:
        return dt.datetime.fromisoformat(s).replace(hour=23, minute=59, tzinfo=dt.timezone(dt.timedelta(hours=-7)))
    t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def last_trading_day():
    """最近一个已经收盘、扫描也该跑完的交易日（不算美股假日，假日那天会多宽限一天）"""
    t = la_now()
    d = t.date() if t.hour >= 19 else t.date() - dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def prev_weekday(d):
    d -= dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


# (key, emoji, 名称, 数据, 时间字段, 最长几小时算正常, 内容检查（表达式, 最少条数）, 页面, workflow 文件)
CHECKS = [
    ("brief", "☀️", "每日简报", "brief/data/index.json", "generated", 30, ("len(d['dates'])", 1), "brief.html", "brief.yml"),
    ("news_today", "📌", "今日大事", "news/data/today.json", "generated", 8, ("len(d['big'])", 5), "news.html", "news.yml"),
    ("news_world", "🌍", "国际局势", "news/data/world.json", "generated", 8, ("sum(len(r['stories']) for r in d['regions'])", 30), "news.html#world", "news.yml"),
    ("news_en", "📰", "英文新闻精选", "news/data/latest.json", "generated", 30, ("len(d.get('items') or d.get('articles') or [])", 10), "news.html#en", "news.yml"),
    ("stocks", "📈", "今日股票池", "stocks/data/latest.json", "stock", 0, ("d.get('scanned') or 0", 400), "stocks.html", "stock-scan.yml"),
    ("earnings", "📅", "财报与经济日历", "earnings/data/latest.json", "generated", 60, None, "earnings.html", "earnings.yml"),
    ("deals", "🏷️", "打折雷达", "deals/data/meta.json", "updated", 30, None, "deals.html", "deals.yml"),
    ("radio", "🚗", "通勤电台", "radio/data/today.json", "generated", 30, None, "radio.html", "radio.yml"),
    ("card", "🎴", "每日一句", "card/today.json", "date", 30, None, "card.html", "news.yml"),
    ("monitor", "🔔", "网页监控", "monitor/data/state.json", "generated", 12, None, "monitor.html", "monitor.yml"),
    ("bay_live", "🚗", "湾区实时路况", "https://raw.githubusercontent.com/%s/live-data/bay/live.json" % REPO, "generated", 3, None, "sf.html#map", "bay-live.yml"),
    ("longterm", "🐢", "长线池", "longterm/data/latest.json", "generated", 24 * 8, None, "stocks.html", "longterm.yml"),
    ("amtrak", "🚆", "Amtrak 时刻表", "amtrak/data.json", "generated", 24 * 9, None, "amtrak.html", "amtrak.yml"),
    ("stations", "📍", "附近车站", "stations/near.json", "generated", 24 * 9, ("len(d['st'])", 800), "amtrak.html", "stations.yml"),
    ("ferry", "⛴️", "旧金山渡轮", "sf/ferry.json", "generated", 24 * 5, None, "sf.html#map", "ferry.yml"),
    ("rankings", "🎬", "电影 / 音乐 Top 500", "rankings/data/movies.json", "updated", 24 * 9, None, "kb.html", "rankings.yml"),
    ("holidays", "🗓️", "节假日", "holidays/data.json", "generated", 24 * 20, None, "holidays.html", "holidays.yml"),
    ("sky", "🔭", "天象（知识库首页）", "kb/sky.json", "generated", 24 * 35, None, "kb.html", "kb.yml"),
    ("bay_roads", "🛣️", "湾区高速路线", "bay/roads.json", "generated", 24 * 40, None, "sf.html#map", "bay-roads.yml"),
]

# 地图底图和几个页面直接调用的外部接口：取一次，确认真的回来了图片 / 数据（CARTO 那种「看起来成功、其实是水印」的情况）
EXTERNAL = [
    ("tile_street", "🗺️", "街道底图（Esri）", "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/6/24/10", "image"),
    ("tile_gray", "🗺️", "浅灰底图（Esri）", "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/6/24/10", "image"),
    ("tile_sat", "🛰️", "卫星图（Esri）", "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/6/24/10", "image"),
    ("amtraker", "🚆", "Amtrak 实时列车接口", "https://api-v3.amtraker.com/v3/trains", "json"),
    ("bart", "🚇", "BART 实时到站接口", "https://api.bart.gov/api/etd.aspx?cmd=etd&orig=EMBR&key=MW9S-E7SL-26DU-VV8V&json=y", "json"),
]


def check_data():
    out = []
    for key, e, name, path, field, max_h, content, page, wf in CHECKS:
        r = {"k": key, "e": e, "n": name, "page": page, "wf": wf, "ok": True, "msg": "", "at": None}
        try:
            d = load(path)
            if field == "stock":
                at = when(d["generated"])
                want = last_trading_day()
                got = dt.date.fromisoformat(d["date"])
                r["at"] = at.strftime("%Y-%m-%dT%H:%M:%SZ")
                r["detail"] = "数据日期 %s" % d["date"]
                if got < prev_weekday(want):   # 宽限一个交易日（美股假日、扫描晚跑）
                    r["ok"], r["msg"] = False, "股票数据停在 %s，应该至少到 %s" % (got, prev_weekday(want))
            else:
                at = when(d[field])
                r["at"] = at.strftime("%Y-%m-%dT%H:%M:%SZ")
                age = (NOW - at).total_seconds() / 3600
                if age > max_h:
                    r["ok"], r["msg"] = False, "已经 %s 没更新（超过 %s）" % (fmt_h(age), fmt_h(max_h))
            if content and r["ok"]:
                n = eval(content[0], {}, {"d": d})
                r["detail"] = (r.get("detail", "") + " · " if r.get("detail") else "") + "%d 条" % n
                if n < content[1]:
                    r["ok"], r["msg"] = False, "内容太少：只有 %d 条（正常至少 %d）" % (n, content[1])
        except Exception as ex:  # noqa: BLE001
            r["ok"], r["msg"] = False, "读不到数据：%s" % str(ex)[:120]
        out.append(r)
    return out


def check_external():
    out = []
    for key, e, name, url, kind in EXTERNAL:
        r = {"k": key, "e": e, "n": name, "ok": True, "msg": ""}
        try:
            body, ctype = get(url, raw=True)
            if kind == "image":
                if "image" not in ctype or len(body) < 2000:
                    r["ok"], r["msg"] = False, "没有返回正常的图片（%s，%d 字节）" % (ctype or "?", len(body))
            else:
                json.loads(body.decode("utf-8", "replace"))
        except Exception as ex:  # noqa: BLE001
            r["ok"], r["msg"] = False, "连不上：%s" % str(ex)[:120]
        out.append(r)
    return out


def gh(method, path, body=None):
    if not TOKEN:
        return None
    req = urllib.request.Request("https://api.github.com/repos/" + REPO + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + TOKEN, "Accept": "application/vnd.github+json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        t = r.read()
        return json.loads(t) if t else None


def check_runs():
    """过去 26 小时里失败的自动任务（每个 workflow 只看最近一次，后来成功了就不算）"""
    out = []
    try:
        since = (NOW - dt.timedelta(hours=26)).strftime("%Y-%m-%dT%H:%M:%SZ")
        runs = (gh("GET", "/actions/runs?per_page=100&created=%3E" + since) or {}).get("workflow_runs", [])
        latest = {}
        for r in runs:
            if r.get("status") != "completed" or r.get("event") == "pull_request":
                continue
            p = r.get("path", "").split("/")[-1]
            if p in ("health.yml",) or "traffic-probe" in r.get("name", ""):
                continue
            if p not in latest or r["created_at"] > latest[p]["created_at"]:
                latest[p] = r
        for p, r in sorted(latest.items()):
            if r.get("conclusion") not in ("success", "skipped", "cancelled", "neutral"):
                out.append({"wf": p, "n": r.get("name", p), "conclusion": r.get("conclusion"), "url": r.get("html_url"), "at": r.get("created_at")})
    except Exception as ex:  # noqa: BLE001
        print("读不到任务记录：", ex)
    return out


def fmt_h(h):
    return "%d 天" % round(h / 24) if h >= 48 else "%d 小时" % round(h)


def notify(problems, prev_sig, sig):
    """有新问题 → 留言提醒；问题全部消失 → 留言「恢复正常」；没变化 → 不打扰"""
    if not TOKEN or sig == prev_sig:
        return
    issues = gh("GET", "/issues?state=all&per_page=100&creator=github-actions%5Bbot%5D") or []
    iss = next((i for i in issues if i.get("title") == TITLE and "pull_request" not in i), None)
    if not iss:
        if not problems:
            return
        iss = gh("POST", "/issues", {"title": TITLE, "body": "每天自动体检，发现数据没更新、任务失败、地图或接口坏了，就在这里留言提醒（GitHub App 推送 + 邮件）。\n\n状态页：" + PAGE})
    if problems:
        if iss.get("state") == "closed":
            gh("PATCH", "/issues/%d" % iss["number"], {"state": "open"})
        text = "### 🩺 体检发现 %d 个问题\n\n" % len(problems) + "\n".join("- " + p for p in problems) + \
            "\n\n大部分会在下一次自动任务里自己恢复；连着两三天还在，就找 Claude 看看。\n\n[打开状态页](%s)\n\n@%s" % (PAGE, OWNER)
    else:
        text = "### ✅ 全部恢复正常\n\n之前的问题都没了。[状态页](%s)\n\n@%s" % (PAGE, OWNER)
    gh("POST", "/issues/%d/comments" % iss["number"], {"body": text})
    if not problems:
        gh("PATCH", "/issues/%d" % iss["number"], {"state": "closed"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    data, ext, runs = check_data(), check_external(), check_runs()
    problems = ["%s %s：%s" % (r["e"], r["n"], r["msg"]) for r in data if not r["ok"]] + \
               ["%s %s：%s" % (r["e"], r["n"], r["msg"]) for r in ext if not r["ok"]] + \
               ["⚙️ 自动任务「%s」上次运行失败（%s）" % (r["n"], r["url"]) for r in runs]
    sig = "|".join(sorted(p.split("：")[0] for p in problems))   # 只按「哪些东西有问题」判断变没变，不因为小时数变化重复提醒
    prev = {}
    try:
        prev = json.load(open(OUT, encoding="utf-8"))
    except Exception:
        pass
    out = {"generated": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), "ok": not problems, "problems": problems, "sig": sig,
           "data": data, "external": ext, "failed_runs": runs,
           "since": prev.get("since") if prev.get("ok") is (not problems) and prev.get("since") else NOW.strftime("%Y-%m-%dT%H:%M:%SZ")}
    for p in problems:
        print("✗", p)
    print("体检：%d 项数据、%d 个外部接口、%d 个失败任务 → %s" % (len(data), len(ext), len(runs), "全部正常 ✅" if not problems else "%d 个问题" % len(problems)))
    if a.dry:
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    try:
        notify(problems, prev.get("sig"), sig)
    except Exception as ex:  # noqa: BLE001
        print("提醒发送失败：", ex)
    return 0


if __name__ == "__main__":
    sys.exit(main())
