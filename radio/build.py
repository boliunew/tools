"""Daily commute radio: turns the site's data into short spoken segments.

Segments are synthesized with edge-tts (fallback: gTTS), joined with ffmpeg,
uploaded as assets of the GitHub release tagged `radio` (so audio never bloats
the git history), and described in radio/data/today.json for radio.html.

Env:
  RADIO_FAKE_TTS=1   use ffmpeg tones instead of real speech (offline testing)
  RADIO_NO_UPLOAD=1  skip the release upload (local testing)
  GITHUB_REPOSITORY  owner/repo for asset URLs (default boliunew/tools)
"""
import asyncio
import datetime as dt
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_JSON = os.path.join(ROOT, "radio", "data", "today.json")
REPO = os.environ.get("GITHUB_REPOSITORY", "boliunew/tools")
TAG = "radio"
TZ = ZoneInfo("America/Los_Angeles")
VOICES = {"zh": "zh-CN-XiaoxiaoNeural", "en": "en-US-JennyNeural", "es": "es-MX-DaliaNeural"}
RATES = {"zh": "+0%", "en": "-12%", "es": "-12%"}
GTTS_LANG = {"zh": "zh-CN", "en": "en", "es": "es"}
WEEK = "一二三四五六日"


def load(rel):
    try:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:  # noqa: BLE001
        print("warn: cannot read", rel, e)
        return None


def pct(x, digits=1):
    return f"{abs(x) * 100:.{digits}f}%"


def updown(x):
    return "上涨" if x >= 0 else "下跌"


def short_name(n):
    n = re.sub(r",?\s+(Inc\.?|Corporation|Corp\.?|Ltd\.?|plc|Co\.?|Company|Holdings?|Group|N\.V\.|S\.A\.|Limited)\b.*$", "", n or "", flags=re.I)
    return n.strip() or n


def spell(t):
    return " ".join(list(t))


def md(d):
    return f"{d.month}月{d.day}日"


# ---------------------------------------------------------------- segments
def seg_intro(today, n):
    return {
        "id": "intro", "title": "☀️ 开场", "sub": f"{md(today)} 星期{WEEK[today.weekday()]}",
        "parts": [("zh", f"早上好！今天是{md(today)}，星期{WEEK[today.weekday()]}。这里是你的通勤电台，今天一共{n}段。"
                         "想跳过，就按方向盘上的下一首。")],
    }


def seg_market(stocks):
    if not stocks or stocks.get("demo"):
        return None
    r = stocks.get("regime") or {}
    d = dt.date.fromisoformat(stocks["date"])
    spy, qqq = r.get("spy") or {}, r.get("qqq") or {}
    txt = f"先看大盘，数据截至美股{md(d)}收盘。"
    if spy:
        txt += f"标普500 ETF {updown(spy['chg'])}{pct(spy['chg'])}，"
    if qqq:
        txt += f"纳指100 ETF {updown(qqq['chg'])}{pct(qqq['chg'])}。"
    if r.get("vix"):
        v = r["vix"]
        txt += f"恐慌指数VIX {v:.1f}，" + ("处在低位。" if v < 15 else "正常水平。" if v < 20 else "偏高，市场有点紧张。" if v < 30 else "很高，市场恐慌。")
    if r.get("breadth50") is not None:
        txt += f"标普成分股里，站上50日均线的只占{round(r['breadth50'] * 100)}%。" if r["breadth50"] < 0.4 else f"标普成分股里，{round(r['breadth50'] * 100)}%站上了50日均线。"
    if r.get("label"):
        txt += f"系统判断当前是「{r['label']}」环境：{r.get('desc', '')}"
    return {"id": "market", "title": "📊 大盘", "sub": r.get("label", ""), "parts": [("zh", txt)]}


def seg_pool(stocks):
    if not stocks or stocks.get("demo"):
        return None
    cands = sorted(stocks.get("candidates") or [], key=lambda c: -(c.get("score") or 0))
    sig = stocks.get("signals") or {}
    if not cands:
        return {"id": "pool", "title": "📈 股票池", "sub": "今天没有候选",
                "parts": [("zh", "股票池今天没有符合条件的候选，空仓也是一种操作。")]}
    cnt = {}
    for c in cands:
        cnt[c.get("primary")] = cnt.get(c.get("primary"), 0) + 1
    parts = [("zh", f"股票池一共扫描了{stocks.get('scanned', 0)}只股票，找到{len(cands)}个短线候选。"
                    + "其中" + "，".join(f"{sig.get(k, {}).get('name', k)}{v}个" for k, v in sorted(cnt.items(), key=lambda kv: -kv[1])) + "。"
                    + "评分最高的三个是：")]
    for i, c in enumerate(cands[:3]):
        nm = sig.get(c.get("primary"), {}).get("name", "")
        line = f"第{i + 1}，{short_name(c.get('name'))}，代码 {spell(c['t'])}，{nm}信号，收盘价{c['close']:.2f}美元"
        if c.get("stop"):
            line += f"，止损参考{c['stop']:.2f}"
        if c.get("earn"):
            line += "，注意近期有财报"
        parts.append(("zh", line + "。"))
    parts.append(("zh", "以上只是规则筛选的结果，不是投资建议。"))
    return {"id": "pool", "title": "📈 股票池", "sub": f"{len(cands)} 个候选", "parts": parts}


def seg_calendar(earn, today):
    if not earn or earn.get("demo"):
        return None
    days = earn.get("days") or []
    iso = today.isoformat()
    pick = [d for d in days if d["date"] >= iso][:2]
    if not pick:
        return None
    parts, n_items = [], 0
    for d in pick:
        dd = dt.date.fromisoformat(d["date"])
        label = "今天" if d["date"] == iso else ("明天" if dd == today + dt.timedelta(days=1) else md(dd))
        macro = [m for m in d.get("macro") or [] if m.get("imp") == "高"]
        big = sorted([e for e in d.get("earnings") or [] if (e.get("cap") or 0) >= 1e11 or e.get("watch")], key=lambda e: -(e.get("cap") or 0))[:3]
        if not macro and not big:
            continue
        txt = f"{label}，"
        if macro:
            txt += "重要数据有：" + "；".join(f"美东{m.get('time', '')}公布{m.get('title', '')}" for m in macro[:3]) + "。"
            n_items += len(macro[:3])
        if big:
            txt += ("另外，" if macro else "") + f"有{len(big)}家大公司发财报。"
        parts.append(("zh", txt))
        for e in big:
            when = {"pre": "盘前", "post": "盘后"}.get(e.get("when"), "")
            line = f"{short_name(e.get('name'))}，代码 {spell(e['t'])}，{when}发财报。"
            imp = e.get("implied") or {}
            if imp.get("move"):
                line += f"期权定价波动正负{pct(imp['move'])}。"
            tags = e.get("tags") or []
            if tags:
                line += "标签：" + "、".join(tags[:3]) + "。"
            parts.append(("zh", line))
            n_items += 1
    if not parts:
        parts = [("zh", "今明两天没有重要经济数据，也没有千亿市值以上的公司发财报。")]
    return {"id": "calendar", "title": "🗓️ 财报与数据", "sub": f"{n_items} 件大事" if n_items else "今明两天清静", "parts": parts}


def seg_news(news, today):
    if not news:
        return None
    arts = news.get("articles") or []
    pref = [a for a in arts if a.get("level") in ("B1", "B2")] or arts
    seen, chosen = set(), []
    for a in sorted(pref, key=lambda a: a.get("time") or "", reverse=True):
        if a.get("source") in seen:
            continue
        seen.add(a.get("source"))
        chosen.append(a)
        if len(chosen) == 3:
            break
    if not chosen:
        return None
    parts = [("zh", "接下来是三条英文新闻，用慢速朗读，练练听力。")]
    for i, a in enumerate(chosen):
        parts.append(("zh", f"第{i + 1}条，来自{a.get('source', '')}，{a.get('topic', '')}，难度{a.get('level', '')}。"))
        parts.append(("en", a["title"].strip()))
        summ = re.split(r"(?<=[.!?])\s", (a.get("summary") or "").strip())[0][:240]
        if summ and len(summ) > 30:
            parts.append(("en", summ))
    return {"id": "news", "title": "📰 英文新闻", "sub": " · ".join(a.get("source", "") for a in chosen), "parts": parts}


def seg_words(today):
    en = load("radio/words_en.json") or []
    es = load("radio/words_es.json") or []
    rnd = random.Random(today.toordinal())
    parts, subs = [], []
    if en:
        w, ipa, zh, lv = rnd.choice(en)
        parts += [("zh", "今日英语单词。"), ("en", w), ("zh", f"意思是：{zh.replace('；', '，')}。拼写是："), ("en", ", ".join(list(w))), ("zh", "再听一遍。"), ("en", w)]
        subs.append(w)
    if es:
        w, zh, theme = rnd.choice(es)
        parts += [("zh", "今日西语单词。"), ("es", w), ("zh", f"意思是：{zh.replace('；', '，')}。跟着读一遍。"), ("es", w)]
        subs.append(w)
    if not parts:
        return None
    return {"id": "words", "title": "🔤 今日单词", "sub": " · ".join(subs), "parts": parts}


def seg_outro():
    return {"id": "outro", "title": "👋 结束", "sub": "开车注意安全",
            "parts": [("zh", "今天的通勤电台就到这里。开车注意安全，祝你今天顺顺利利！")]}


# ---------------------------------------------------------------- audio
def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


async def tts_edge(text, lang, path):
    import edge_tts  # noqa: PLC0415
    await edge_tts.Communicate(text, VOICES[lang], rate=RATES[lang]).save(path)


def tts(text, lang, path):
    if os.environ.get("RADIO_FAKE_TTS"):
        secs = max(0.6, min(8.0, len(text) * (0.18 if lang == "zh" else 0.06)))
        freq = {"zh": 440, "en": 660, "es": 550}[lang]
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={secs:.2f}", "-ar", "24000", "-ac", "1", "-b:a", "48k", path])
        return "fake"
    for attempt in range(3):
        try:
            asyncio.run(tts_edge(text, lang, path))
            if os.path.getsize(path) > 1000:
                return "edge"
        except Exception as e:  # noqa: BLE001
            print(f"edge-tts failed ({attempt + 1}/3):", e)
    from gtts import gTTS  # noqa: PLC0415
    gTTS(text, lang=GTTS_LANG[lang], slow=(lang != "zh")).save(path)
    return "gtts"


def probe_dur(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
                         check=True, capture_output=True, text=True).stdout.strip()
    return round(float(out or 0), 1)


def concat(files, out, tmp):
    lst = os.path.join(tmp, "list_" + os.path.basename(out) + ".txt")
    with open(lst, "w") as f:
        for p in files:
            f.write(f"file '{p}'\n")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-ar", "24000", "-ac", "1", "-b:a", "48k", out])


def upload(paths, keep_names):
    gh = shutil.which("gh")
    if not gh:
        raise SystemExit("gh CLI not found")
    if subprocess.run([gh, "release", "view", TAG], capture_output=True).returncode != 0:
        run([gh, "release", "create", TAG, "--title", "通勤电台（自动更新）", "--notes", "每天自动生成的通勤电台音频，由 radio/build.py 上传。", "--latest=false"])
    run([gh, "release", "upload", TAG, "--clobber", *paths])
    names = subprocess.run([gh, "release", "view", TAG, "--json", "assets", "-q", ".assets[].name"], capture_output=True, text=True).stdout.split()
    for n in names:
        if n not in keep_names:
            subprocess.run([gh, "release", "delete-asset", TAG, n, "-y"], capture_output=True)


def main():
    now = dt.datetime.now(TZ)
    today = now.date()
    stocks, earn, news = load("stocks/data/latest.json"), load("earnings/data/latest.json"), load("news/data/latest.json")
    body = [s for s in (seg_market(stocks), seg_pool(stocks), seg_calendar(earn, today), seg_news(news, today), seg_words(today)) if s]
    segs = [seg_intro(today, len(body) + 2)] + body + [seg_outro()]

    tmp = tempfile.mkdtemp(prefix="radio_")
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.5", "-b:a", "48k", os.path.join(tmp, "gap.mp3")])
    engines, seg_files, out_segs = set(), [], []
    stamp = now.strftime("%Y%m%d%H%M")
    for i, s in enumerate(segs, 1):
        files = []
        for j, (lang, text) in enumerate(s["parts"]):
            p = os.path.join(tmp, f"s{i}_{j}.mp3")
            engines.add(tts(text, lang, p))
            files += [p, os.path.join(tmp, "gap.mp3")]
        name = f"seg{i:02d}.mp3"
        out = os.path.join(tmp, name)
        concat(files, out, tmp)
        seg_files.append(out)
        out_segs.append({
            "id": s["id"], "title": s["title"], "sub": s.get("sub", ""), "dur": probe_dur(out),
            "url": f"https://github.com/{REPO}/releases/download/{TAG}/{name}?v={stamp}",
            "text": [{"lang": l, "t": t} for l, t in s["parts"]],
        })
        print(f"seg {i}: {s['title']} {out_segs[-1]['dur']}s")
    full = os.path.join(tmp, "full.mp3")
    concat(seg_files, full, tmp)

    if not os.environ.get("RADIO_NO_UPLOAD"):
        upload(seg_files + [full], {os.path.basename(p) for p in seg_files + [full]})
    else:
        keep = os.path.join(ROOT, "radio", "_local")
        os.makedirs(keep, exist_ok=True)
        for p in seg_files + [full]:
            shutil.copy(p, keep)
        for s, p in zip(out_segs, seg_files):
            s["url"] = "_local/" + os.path.basename(p)

    doc = {
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date": today.isoformat(), "engine": ",".join(sorted(engines)),
        "total": round(sum(s["dur"] for s in out_segs), 1),
        "full": f"https://github.com/{REPO}/releases/download/{TAG}/full.mp3?v={stamp}" if not os.environ.get("RADIO_NO_UPLOAD") else "_local/full.mp3",
        "segments": out_segs,
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print("done:", len(out_segs), "segments,", doc["total"], "s, engine", doc["engine"])


if __name__ == "__main__":
    sys.exit(main())
