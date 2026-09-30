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
import urllib.request
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
LOC = {"name": "Upland", "lat": 34.0975, "lon": -117.6484}
CLOCK_TAG = "radio-clock2"  # bump when the clip texts change


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
INTROS = [
    "今天是{date}，{wk}。欢迎收听你的通勤电台，今天准备了{n}段内容，想跳过就按方向盘上的下一首。",
    "{date}，{wk}，通勤电台准时上线。今天一共{n}段，不想听的直接按下一首。",
    "这里是你的通勤电台。今天是{date}，{wk}，一共{n}段，方向盘上的下一首可以随时跳过。",
    "{wk}，{date}。通勤电台陪你上路，今天有{n}段，按下一首可以跳段。",
]
DAYNOTE = {0: "新的一周开始了，加油！", 2: "一周过半了。", 4: "周五了，坚持一下就周末了！", 5: "周末还出门，辛苦了。", 6: "周末还出门，辛苦了。"}
OUTROS = [
    "今天的通勤电台就到这里。开车注意安全，我们下次见！",
    "好了，今天就播到这里。路上慢点开，注意安全！",
    "电台播完了。祝你一路顺风，今天顺顺利利！",
    "今天的内容就这些。专心开车，安全第一，下次见！",
]


def seg_intro(today, n):
    rnd = random.Random(today.toordinal() * 7 + 1)
    wk = f"星期{WEEK[today.weekday()]}"
    txt = rnd.choice(INTROS).format(date=md(today), wk=wk, n=n)
    if today.weekday() in DAYNOTE:
        txt = DAYNOTE[today.weekday()] + txt
    return {"id": "intro", "title": "☀️ 开场", "sub": f"{md(today)} {wk}", "parts": [("zh", txt)]}


WMO = {0: "晴", 1: "大致晴朗", 2: "多云", 3: "阴天", 45: "有雾", 48: "有雾", 51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨",
       56: "冻毛毛雨", 57: "冻毛毛雨", 61: "小雨", 63: "中雨", 65: "大雨", 66: "冻雨", 67: "冻雨", 71: "小雪", 73: "中雪",
       75: "大雪", 77: "雪粒", 80: "小阵雨", 81: "阵雨", 82: "强阵雨", 85: "阵雪", 86: "阵雪", 95: "雷阵雨", 96: "雷阵雨伴冰雹", 99: "雷阵雨伴冰雹"}


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "boliunew-tools-radio/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def f2c(f):
    return round((f - 32) * 5 / 9)


def hm(iso):
    t = dt.datetime.fromisoformat(iso)
    h = t.hour % 12 or 12
    return f"{h}点{t.minute:02d}分" if t.minute else f"{h}点"


def seg_weather():
    try:
        w = fetch_json("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
                       "&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m"
                       "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max,sunset,wind_speed_10m_max"
                       "&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=America%%2FLos_Angeles&forecast_days=1" % (LOC["lat"], LOC["lon"]))
    except Exception as e:  # noqa: BLE001
        print("weather failed:", e)
        return None
    try:
        aq = fetch_json("https://air-quality-api.open-meteo.com/v1/air-quality?latitude=%s&longitude=%s&current=us_aqi&timezone=America%%2FLos_Angeles" % (LOC["lat"], LOC["lon"]))
        aqi = (aq.get("current") or {}).get("us_aqi")
    except Exception as e:  # noqa: BLE001
        print("air quality failed:", e)
        aqi = None
    c, d = w.get("current") or {}, w.get("daily") or {}
    g = lambda k: (d.get(k) or [None])[0]  # noqa: E731
    code, tmax, tmin, rain, uv, wind = g("weather_code"), g("temperature_2m_max"), g("temperature_2m_min"), g("precipitation_probability_max"), g("uv_index_max"), g("wind_speed_10m_max")
    sky = WMO.get(code, "")
    txt = f"{LOC['name']}今天{sky}。"
    if c.get("temperature_2m") is not None:
        txt += f"现在气温华氏{round(c['temperature_2m'])}度，大约{f2c(c['temperature_2m'])}摄氏度"
        if c.get("apparent_temperature") is not None and abs(c["apparent_temperature"] - c["temperature_2m"]) >= 4:
            txt += f"，体感{round(c['apparent_temperature'])}度"
        txt += "。"
    if tmax is not None and tmin is not None:
        txt += f"白天最高{round(tmax)}度，约{f2c(tmax)}摄氏度；最低{round(tmin)}度。"
    if rain is not None:
        txt += f"降雨概率{int(rain)}%。" if rain >= 20 else "基本不会下雨。"
    tips = []
    if rain is not None and rain >= 50:
        tips.append("记得带伞，路面湿滑，车速放慢")
    if tmax is not None and tmax >= 95:
        tips.append("天气很热，注意防暑，别把东西留在车里")
    elif tmin is not None and tmin <= 45:
        tips.append("早晚比较冷，多穿一件")
    if wind is not None and wind >= 25:
        tips.append(f"风很大，阵风可能超过每小时{round(wind)}英里，开车握稳方向盘")
    if uv is not None and uv >= 8:
        tips.append("紫外线很强，注意防晒")
    if aqi is not None:
        lv = "良好" if aqi <= 50 else "中等" if aqi <= 100 else "对敏感人群不健康" if aqi <= 150 else "不健康" if aqi <= 200 else "非常不健康"
        txt += f"空气质量{lv}，指数{int(aqi)}。"
        if aqi > 150:
            tips.append("空气不好，车内空调切换到内循环")
    if g("sunset"):
        txt += f"今天日落时间是傍晚{hm(g('sunset'))}。"
    if tips:
        txt += "提醒一下：" + "；".join(tips) + "。"
    sub = f"{LOC['name']} {sky} " + (f"{round(tmax)}°/{round(tmin)}°F" if tmax is not None and tmin is not None else "")
    return {"id": "weather", "title": "🌤️ 天气", "sub": sub.strip(), "parts": [("zh", txt)]}


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


def vocab_data():
    s = open(os.path.join(ROOT, "vocab.html"), encoding="utf-8").read()
    tag = '<script type="application/json" id="data">'
    a = s.index(tag) + len(tag)
    return json.loads(s[a:s.index("</script>", a)])


def short_def(zh):
    d = re.sub(r"^[a-z]+\.\s*", "", (zh or "").split("；")[0].split("\n")[0])
    return "，".join(re.split(r"[,，]\s*", d)[:3])


def seg_review(now):
    gid = os.environ.get("VOCAB_GIST_ID", "").strip()
    if not gid:
        return None
    try:
        g = fetch_json(f"https://api.github.com/gists/{gid}")
        f = (g.get("files") or {}).get("ctxvocab.json") or {}
        db = json.loads(f["content"]) if not f.get("truncated") else fetch_json(f["raw_url"])
    except Exception as e:  # noqa: BLE001
        print("vocab gist failed:", e)
        return None
    day = int((now.timestamp() + now.utcoffset().total_seconds()) // 86400)
    cards = db.get("cards") or {}
    due = [w for w, c in cards.items() if not c.get("k") and (c.get("due") or 0) <= day]
    if not due:
        return None
    retr = lambda c: (1 + 19 / 81 * max(0, day - (c.get("last") or 0)) / max(0.1, c.get("s") or 0.1)) ** -0.5  # noqa: E731
    due.sort(key=lambda w: retr(cards[w]))
    V = vocab_data()
    by = {e[0]: i for i, e in enumerate(V["w"])}
    parts, picked = [("zh", f"下面复习你今天到期的单词。今天一共有{len(due)}个要复习，先听最容易忘的几个。")], []
    for w in due[:6]:
        ctx = (db.get("ctx") or {}).get(w) or []
        if w in by:
            e = V["w"][by[w]]
            zh = short_def(e[2])
            ex = ctx[0]["en"] if ctx else next((V["s"][j][0] for j in e[3] if len(V["s"][j][0]) <= 160), "")
        elif w in (db.get("custom") or {}):
            zh = short_def(db["custom"][w].get("zh", ""))
            ex = ctx[0]["en"] if ctx else ""
        else:
            continue
        picked.append(w)
        parts += [("en", w), ("zh", f"意思是：{zh}。" if zh else "")]
        if ex:
            parts += [("zh", "例句：" if not ctx else "你收藏的那句："), ("en", ex)]
    parts = [p for p in parts if p[1]]
    if not picked:
        return None
    parts.append(("zh", "到了公司或者回到家，打开语境词库把今天的复习做完吧。"))
    return {"id": "review", "title": "🔁 今日复习", "sub": " · ".join(picked), "parts": parts}


def seg_outro(today):
    rnd = random.Random(today.toordinal() * 13 + 5)
    return {"id": "outro", "title": "👋 结束", "sub": "开车注意安全", "parts": [("zh", rnd.choice(OUTROS))]}


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


def clock_texts():
    out = {}
    for h in range(24):
        per = "凌晨" if h < 5 else "早上" if h < 9 else "上午" if h < 12 else "中午" if h == 12 else "下午" if h < 18 else "晚上"
        hi = "夜深了，" if h < 5 else "早上好！" if h < 11 else "中午好！" if h < 13 else "下午好！" if h < 18 else "晚上好！"
        hh = h % 12 or 12
        out[f"h{h:02d}.mp3"] = f"{hi}现在是{per}{hh}点"
    for m in range(60):
        out[f"m{m:02d}.mp3"] = "整。" if m == 0 else (f"零{m}分。" if m < 10 else f"{m}分。")
    return out


def ensure_clock(tmp):
    """Hour/minute clips (made once) so the player can announce the real current time."""
    base = f"https://github.com/{REPO}/releases/download/{CLOCK_TAG}/"
    if os.environ.get("RADIO_NO_UPLOAD"):
        return None
    gh = shutil.which("gh")
    have = subprocess.run([gh, "release", "view", CLOCK_TAG, "--json", "assets", "-q", ".assets[].name"], capture_output=True, text=True)
    texts = clock_texts()
    if have.returncode == 0 and len(set(have.stdout.split()) & set(texts)) == len(texts):
        return base
    for old in ("radio-clock",):
        subprocess.run([gh, "release", "delete", old, "--yes", "--cleanup-tag"], capture_output=True)
    if have.returncode != 0:
        run([gh, "release", "create", CLOCK_TAG, "--title", "通勤电台报时音频", "--notes", "报时用的小时/分钟语音片段（一次性生成）。", "--latest=false"])
    d = os.path.join(tmp, "clock")
    os.makedirs(d, exist_ok=True)
    paths = []
    for name, text in texts.items():
        p = os.path.join(d, name)
        raw = p + ".raw.mp3"
        tts(text, "zh", raw)
        run(["ffmpeg", "-y", "-i", raw, "-ar", "24000", "-ac", "1", "-b:a", "48k", p])
        paths.append(p)
    for i in range(0, len(paths), 20):
        run([gh, "release", "upload", CLOCK_TAG, "--clobber", *paths[i:i + 20]])
    return base


def main():
    now = dt.datetime.now(TZ)
    today = now.date()
    stocks, earn, news = load("stocks/data/latest.json"), load("earnings/data/latest.json"), load("news/data/latest.json")
    body = [s for s in (seg_weather(), seg_market(stocks), seg_pool(stocks), seg_calendar(earn, today), seg_news(news, today), seg_review(now), seg_words(today)) if s]
    segs = [seg_intro(today, len(body) + 2)] + body + [seg_outro(today)]

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

    clock = None
    try:
        clock = ensure_clock(tmp)
    except Exception as e:  # noqa: BLE001
        print("clock clips failed:", e)
    doc = {
        "clock": clock,
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date": today.isoformat(), "engine": ",".join(sorted(engines)),
        "total": round(sum(s["dur"] for s in out_segs), 1),
        "full": f"https://github.com/{REPO}/releases/download/{TAG}/full.mp3?v={stamp}" if not os.environ.get("RADIO_NO_UPLOAD") else "_local/full.mp3",
        "segments": out_segs,
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    # playlist for VLC & other players: steering-wheel next/prev skips segments, titles show on the car display
    with open(os.path.join(os.path.dirname(OUT_JSON), "today.m3u"), "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n#PLAYLIST:通勤电台 " + today.isoformat() + "\n")
        for s in out_segs:
            f.write(f"#EXTINF:{int(round(s['dur']))},通勤电台 - {s['title']} {s.get('sub', '')}".rstrip() + "\n" + s["url"] + "\n")
    print("done:", len(out_segs), "segments,", doc["total"], "s, engine", doc["engine"])


if __name__ == "__main__":
    sys.exit(main())
