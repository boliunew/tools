#!/usr/bin/env python3
"""☀️ 每日简报：每天早上用网站已有的数据自动拼出一期简报，写进 brief/data/（brief.html 读）。

不需要 AI，也不需要任何授权：
  🤖 AI 与科技   ← news/data/latest.json 里 BBC / NPR / 卫报的科技新闻（机翻成中文）
  📈 美股市场   ← stocks/data/latest.json（大盘状态）+ stocks/data/snap.json（涨跌最大的个股）+ 财报日历
  🏦 宏观经济   ← earnings/data/latest.json 的经济数据日历（最近公布的结果 + 接下来几天）
  🌍 世界大事   ← news/data/today.json「今日大事」（多家媒体同时报道的排前面）
  📌 今日一件事 ← 近 3 天有「高」重要性的经济数据就选它，否则选报道媒体最多的那条新闻
  🗓️ 本周关注   ← 只在周一：本周的重要经济数据 + 市值最大的财报

  python brief/build.py          正常运行
  python brief/build.py --dry    只打印，不写文件
只用标准库。"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "data")
SITE = (os.environ.get("PUBLIC_URL", "").rstrip("/") or "https://boliunew.github.io/tools")
UA = "Mozilla/5.0 (boliunew-tools brief)"
WK = "一二三四五六日"
KEEP_DAYS = 30

AI_WORDS = re.compile(r"\b(AI|A\.I\.|artificial intelligence|OpenAI|ChatGPT|Anthropic|Claude|Gemini|DeepMind|Nvidia|chip|chips|semiconductor|"
                      r"robot|robotics|model|LLM|data cent(?:er|re)s?|Microsoft|Google|Apple|Meta|Amazon|Tesla|xAI|Grok|quantum|cyber|hack)", re.I)
SKIP_TECH = re.compile(r"\b(podcast|quiz|newsletter|live:|in pictures|review:|the week in)\b", re.I)


def la_now():
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("America/Los_Angeles"))
    except Exception:
        return dt.datetime.utcnow() - dt.timedelta(hours=7)


def load(rel):
    try:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("⚠️ 读不到 %s：%s" % (rel, e))
        return {}


def parse_t(s):
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def pct(x, digits=2):
    return ("%+." + str(digits) + "f%%") % (x * 100)


def md(d):
    """'2026-10-27' → '10/27 周二'"""
    t = dt.date.fromisoformat(d)
    return "%d/%d 周%s" % (t.month, t.day, WK[t.weekday()])


def clip(s, n):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[:n - 1].rstrip("，,。. ") + "…"


# ----------------------------------------------------------------------------- 机翻（谷歌免费接口 → MyMemory），带缓存
TCACHE_PATH = os.path.join(OUT, "tcache.json")


def http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def translate(text, cache):
    text = (text or "").strip()
    if not text:
        return ""
    if text in cache:
        return cache[text]
    try:
        q = urllib.parse.urlencode({"client": "gtx", "sl": "en", "tl": "zh-CN", "dt": "t", "q": text[:1800]})
        d = json.loads(http_get("https://translate.googleapis.com/translate_a/single?" + q))
        zh = "".join(seg[0] for seg in (d[0] or []) if seg and seg[0]).strip()
        if zh and zh != text:
            cache[text] = zh
            return zh
    except Exception:
        pass
    try:
        q = urllib.parse.urlencode({"q": text[:450], "langpair": "en|zh-CN"})
        d = json.loads(http_get("https://api.mymemory.translated.net/get?" + q))
        zh = (d.get("responseData") or {}).get("translatedText") or ""
        if d.get("responseStatus") in (200, "200") and zh and not re.search(r"MYMEMORY WARNING|QUOTA", zh, re.I):
            cache[text] = html.unescape(zh)
            return cache[text]
    except Exception:
        pass
    return ""


# ----------------------------------------------------------------------------- 各板块
def sec_ai(now_utc, cache):
    L = load("news/data/latest.json")
    arts = [a for a in L.get("articles", []) if a.get("topic") == "科技" and not SKIP_TECH.search(a.get("title", ""))]
    fresh = []
    for a in arts:
        t = parse_t(a.get("time"))
        age = (now_utc - t).total_seconds() / 3600 if t else 99
        if age > 48:
            continue
        score = (3 if AI_WORDS.search(a.get("title", "") + " " + a.get("summary", "")) else 0) - age / 12
        fresh.append((score, a))
    fresh.sort(key=lambda x: -x[0])
    items, seen = [], set()
    for _, a in fresh:
        key = re.sub(r"\W+", "", a["title"].lower())[:40]
        if key in seen:
            continue
        seen.add(key)
        zt = translate(a["title"], cache) or a["title"]
        zs = translate(a.get("summary", ""), cache) or a.get("summary", "")
        items.append({"t": clip(zt, 60), "d": clip(zs, 140), "src": [{"n": a.get("source", "来源"), "u": a.get("link", "")}]})
        if len(items) >= 3:
            break
    return items


def sec_market(today):
    S = load("stocks/data/latest.json")
    snap = load("stocks/data/snap.json")
    E = load("earnings/data/latest.json")
    items = []
    rg = S.get("regime") or {}
    spy, qqq = rg.get("spy") or {}, rg.get("qqq") or {}
    day = S.get("date") or snap.get("date")
    if spy.get("close"):
        t = "%s 收盘：标普500 ETF（SPY）%s，纳指100 ETF（QQQ）%s" % (md(day) if day else "上个交易日", pct(spy.get("chg", 0)), pct(qqq.get("chg", 0)))
        bits = []
        if rg.get("label"):
            bits.append("大盘状态「%s」：%s" % (rg["label"], rg.get("desc", "").rstrip("。")))
        if rg.get("vix") is not None:
            bits.append("VIX 恐慌指数 %.1f" % rg["vix"])
        if rg.get("breadth50") is not None:
            bits.append("%d%% 的股票站在 50 日均线上方" % round(rg["breadth50"] * 100))
        items.append({"t": t, "d": "；".join(bits) + "。", "src": [{"n": "今日股票池", "u": SITE + "/stocks.html"}]})
    rows = [(k, v) for k, v in (snap.get("rows") or {}).items() if isinstance(v.get("d"), (int, float))]
    if rows:
        rows.sort(key=lambda kv: kv[1]["d"])
        up = rows[::-1][:3]
        dn = rows[:3]

        def fmt(kv):
            return "%s %s" % (kv[0], pct(kv[1]["d"], 1))
        why = []
        secs = {}
        for k, v in up + dn:
            secs.setdefault(v.get("s", ""), []).append(k)
        ZH = {"Information Technology": "信息技术", "Health Care": "医疗保健", "Financials": "金融", "Consumer Discretionary": "可选消费",
              "Consumer Staples": "必需消费", "Industrials": "工业", "Energy": "能源", "Materials": "原材料", "Utilities": "公用事业",
              "Real Estate": "房地产", "Communication Services": "通信服务"}
        crowd = [ZH.get(s, s) for s, ks in secs.items() if s and len(ks) >= 2]
        if crowd:
            why.append("%s 板块的股票在涨跌榜上占了不止一席" % "、".join(crowd))
        items.append({"t": "涨幅最大：%s；跌幅最大：%s" % ("、".join(fmt(x) for x in up), "、".join(fmt(x) for x in dn)),
                      "d": ("扫描范围约 %d 只股票（标普 500 为主）。" % len(rows)) + ("".join(w + "。" for w in why)),
                      "src": [{"n": "今日股票池", "u": SITE + "/stocks.html"}]})
    nxt = next((d for d in E.get("days", []) if d.get("date", "") >= today and d.get("earnings")), None)
    if nxt:
        er = sorted(nxt["earnings"], key=lambda e: -(e.get("cap") or 0))[:5]
        when = {"pre": "盘前", "post": "盘后"}
        names = "、".join("%s（%s）" % (e["t"], when.get(e.get("when"), "时间未定")) for e in er)
        label = "今天" if nxt["date"] == today else md(nxt["date"])
        items.append({"t": "%s的重要财报：%s" % (label, names),
                      "d": "按市值挑出最大的几家，共 %d 家公司发布财报。财报日个股波动通常比平时大得多。" % len(nxt["earnings"]),
                      "src": [{"n": "财报与经济日历", "u": SITE + "/earnings.html"}]})
    return items


def macro_events(E):
    out = []
    for d in E.get("past", []) + E.get("days", []):
        for m in d.get("macro", []):
            out.append(dict(m, date=m.get("date") or d.get("date")))
    seen, uniq = set(), []
    for m in out:
        k = (m["date"], m.get("key"), m.get("title"))
        if k not in seen:
            seen.add(k)
            uniq.append(m)
    return uniq


def sec_macro(today):
    E = load("earnings/data/latest.json")
    ev = macro_events(E)
    items = []
    done = [m for m in ev if m["date"] <= today and any(l.get("actual") for l in m.get("lines", []))]
    if done:
        m = max(done, key=lambda m: (m["date"], m.get("time") or ""))
        ln = [l for l in m.get("lines", []) if l.get("actual")][:2]
        res = "；".join("%s 实际 %s（预期 %s，前值 %s）" % (l.get("name", ""), l.get("actual"), l.get("consensus") or "—", l.get("previous") or "—") for l in ln)
        items.append({"t": "最近公布：%s（%s）" % (m.get("title", ""), md(m["date"])), "d": clip(res + "。" + (m.get("note") or ""), 160),
                      "src": [{"n": "财报与经济日历", "u": SITE + "/earnings.html"}]})
    end = (dt.date.fromisoformat(today) + dt.timedelta(days=5)).isoformat()
    up = [m for m in ev if today <= m["date"] <= end and not any(l.get("actual") for l in m.get("lines", []))]
    order = {"高": 0, "中": 1, "低": 2}
    up.sort(key=lambda m: (order.get(m.get("imp"), 3), m["date"], m.get("time") or ""))
    for m in sorted(up[:3], key=lambda m: (m["date"], m.get("time") or "")):
        items.append({"t": "%s %s：%s（重要性：%s）" % (md(m["date"]), m.get("time") or "", m.get("title", ""), m.get("imp", "—")),
                      "d": m.get("note") or "", "src": [{"n": "财报与经济日历", "u": SITE + "/earnings.html"}]})
    return items, up


def sec_world():
    T = load("news/data/today.json")
    items = []
    for g in (T.get("big") or [])[:4]:
        src = [{"n": g.get("source", "来源"), "u": g.get("link", "")}]
        for o in (g.get("others") or [])[:1]:
            src.append({"n": o.get("source", "来源"), "u": o.get("link", "")})
        n = g.get("n") or 1
        d = clip(g.get("summary", ""), 130)
        if n > 1:
            d += "（%d 家媒体同时报道）" % n
        items.append({"t": clip(g.get("title", ""), 60), "d": d, "src": src, "_n": n})
    return items


# ----------------------------------------------------------------------------- AI 整理（Cloudflare Workers AI，可选）
# 设置了 CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID 就让 AI 从候选新闻里挑重点、写中文的「发生了什么 + 为什么重要」。
# 只交给 AI 挑新闻和写文字；股价、涨跌幅、经济数据这些数字仍然直接取自数据，不让 AI 改。任何一步失败都退回规则版。
AI_MODELS = ["@cf/openai/gpt-oss-120b", "@cf/meta/llama-3.3-70b-instruct-fp8-fast", "@cf/qwen/qwen3-30b-a3b-fp8"]


def notice(msg):
    if os.environ.get("GITHUB_ACTIONS"):
        print("::notice title=每日简报::" + msg.replace("%", "%25").replace("\n", "%0A"))
    else:
        print(msg)


def tech_pool(now_utc):
    L = load("news/data/latest.json")
    out = []
    for a in L.get("articles", []):
        if a.get("topic") not in ("科技", "商业") or SKIP_TECH.search(a.get("title", "")):
            continue
        t = parse_t(a.get("time"))
        if not t or (now_utc - t).total_seconds() > 48 * 3600:
            continue
        out.append(a)
    out.sort(key=lambda a: a.get("time", ""), reverse=True)
    return out[:18]


def world_pool():
    T = load("news/data/today.json")
    W = load("news/data/world.json")
    out, seen = [], set()
    for g in (T.get("big") or [])[:12]:
        out.append(g)
        seen.add((g.get("link") or "").split("?")[0])
    for r in W.get("regions", []):
        for g in r.get("stories", [])[:4]:
            k = (g.get("link") or "").split("?")[0]
            if k and k not in seen and (g.get("imp") or g.get("n", 1) >= 3):
                out.append(g)
                seen.add(k)
    return out[:20]


def cf_ai(system, user):
    tok = re.sub(r"^(Bearer\s+)", "", os.environ.get("CLOUDFLARE_API_TOKEN", "").strip(), flags=re.I).strip()
    acc = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip().strip("/")
    if not tok or not acc:
        return None, None, "没有设置 Cloudflare 的 secret"
    errs = []
    for model in AI_MODELS:
        url = "https://api.cloudflare.com/client/v4/accounts/%s/ai/run/%s" % (acc, model)
        bodies = [{"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "max_tokens": 3000, "temperature": 0.3}]
        if "gpt-oss" in model:
            bodies.insert(0, {"instructions": system, "input": user, "reasoning": {"effort": "low"}})
        for body in bodies:
            try:
                req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                             headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    d = json.loads(r.read().decode("utf-8"))
                text = ai_text(d.get("result"))
                if text:
                    return text, model, ""
                errs.append("%s：返回里没有文字" % model)
            except urllib.error.HTTPError as e:
                errs.append("%s：HTTP %s %s" % (model, e.code, e.read()[:200].decode("utf-8", "replace")))
            except Exception as e:
                errs.append("%s：%s" % (model, str(e)[:150]))
    if any("HTTP 401" in e or "HTTP 403" in e for e in errs):
        return None, None, cf_diagnose(tok, acc)
    return None, None, "；".join(errs)


def cf_diagnose(tok, acc):
    """401/403 时查清楚是令牌、Account ID 还是权限的问题（不会打印令牌内容）"""
    def call(path):
        req = urllib.request.Request("https://api.cloudflare.com/client/v4" + path, headers={"Authorization": "Bearer " + tok})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode("utf-8"))
            except Exception:
                return e.code, {}
        except Exception as e:
            return 0, {"errors": [{"message": str(e)[:100]}]}
    out = ["Cloudflare 拒绝了请求。诊断："]
    out.append("令牌长度 %d、Account ID 长度 %d（Account ID 应为 32 位 0-9a-f：%s）" % (
        len(tok), len(acc), "格式正确" if re.fullmatch(r"[0-9a-f]{32}", acc) else "格式不对"))
    shape = []
    if re.search(r"\s", tok): shape.append("含空格或换行")
    if re.search(r"[\"'`]", tok): shape.append("含引号")
    if re.search(r"[^A-Za-z0-9_\-]", tok): shape.append("含特殊字符")
    m = re.match(r"^([a-z]{2,6})_", tok)
    if m: shape.append("前缀 %s_" % m.group(1))
    out.append("令牌格式：%s" % ("、".join(shape) or "只有字母数字"))
    st2, d2 = call("/accounts/%s/tokens/verify" % acc)
    out.append("按账户令牌验证：%s" % ("有效" if st2 == 200 and d2.get("success") else "HTTP %s %s" % (st2, json.dumps(d2.get("errors"), ensure_ascii=False)[:100])))
    st, d = call("/user/tokens/verify")
    out.append("令牌本身：%s" % ("有效（%s）" % (d.get("result") or {}).get("status", "") if st == 200 and d.get("success") else "无效 / 复制错了（HTTP %s %s）" % (st, json.dumps(d.get("errors"), ensure_ascii=False)[:120])))
    st, d = call("/accounts")
    if st == 200:
        ids = [a.get("id", "") for a in d.get("result") or []]
        out.append("令牌能看到 %d 个账户；Account ID %s其中" % (len(ids), "在" if acc in ids else "【不在】"))
    else:
        out.append("列账户：HTTP %s（缺 Account Settings 读权限时正常）" % st)
    st, d = call("/accounts/%s/ai/models/search?per_page=1" % acc)
    out.append("Workers AI 权限：%s" % ("有" if st == 200 else "没有或 Account ID 不对（HTTP %s %s）" % (st, json.dumps(d.get("errors"), ensure_ascii=False)[:120])))
    return " ｜ ".join(out)


def ai_text(res):
    """兼容几种返回格式：{response}、{output:[{type:message, content:[{text}]}]}、{choices:[{message:{content}}]}"""
    if not res:
        return ""
    if isinstance(res, str):
        return res
    r = res.get("response")
    if isinstance(r, str) and r.strip():
        return r
    if isinstance(r, (dict, list)):
        return json.dumps(r, ensure_ascii=False)
    for o in res.get("output") or []:
        if o.get("type") == "message":
            t = "".join(c.get("text", "") for c in o.get("content") or [] if isinstance(c, dict))
            if t.strip():
                return t
    ch = res.get("choices") or []
    if ch and isinstance(ch[0], dict):
        return ((ch[0].get("message") or {}).get("content")) or ch[0].get("text") or ""
    return ""


def parse_json(text):
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    i, j = text.find("{"), text.rfind("}")
    if i < 0 or j <= i:
        raise ValueError("找不到 JSON")
    return json.loads(text[i:j + 1])


# ----------------------------------------------------------------------------- 抓原文正文（只用标准库）
from html.parser import HTMLParser


class _Paras(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "aside", "figure", "figcaption", "form", "button", "noscript"}

    def __init__(self):
        super().__init__()
        self.depth_skip = 0
        self.in_p = 0
        self.in_article = 0
        self.buf = []
        self.paras = []   # (in_article, text)

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth_skip += 1
        elif tag == "article":
            self.in_article += 1
        elif tag == "p" and not self.depth_skip:
            self.in_p += 1
            self.buf = []

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth_skip:
            self.depth_skip -= 1
        elif tag == "article" and self.in_article:
            self.in_article -= 1
        elif tag == "p" and self.in_p:
            self.in_p -= 1
            t = re.sub(r"\s+", " ", "".join(self.buf)).strip()
            if len(t) >= 50:
                self.paras.append((self.in_article > 0, t))

    def handle_data(self, data):
        if self.in_p and not self.depth_skip:
            self.buf.append(data)


BOILER = re.compile(r"(sign up|newsletter|cookie|subscribe|all rights reserved|follow us|click here|support (the|our) journalism|"
                    r"this article (was|is)|related:|read more:|copyright|terms of (use|service))", re.I)


def article_text(url, limit=3500):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
                                                   "Accept-Language": "en-US,en;q=0.9"})
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read(2_000_000).decode("utf-8", "replace")
        p = _Paras()
        p.feed(raw)
        paras = [t for a, t in p.paras if a] or [t for a, t in p.paras]
        paras = [t for t in paras if not BOILER.search(t)]
        text = "\n".join(paras)
        return text[:limit] if len(text) >= 300 else ""
    except Exception:
        return ""


def ai_rewrite(items):
    """第二步：把选中新闻的正文抓下来，让 AI 根据正文重写标题和总结。抓不到正文的保留第一步写的。"""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(6) as ex:
        texts = list(ex.map(lambda it: article_text(it["src"][0]["u"]), items))
    got = [i for i, t in enumerate(texts) if t]
    if not got:
        return 0, "一篇正文都没抓到"
    parts = []
    for i in got:
        parts.append("【%d】原标题：%s\n来源：%s\n正文：\n%s" % (i, items[i]["_en"], items[i]["src"][0]["n"], texts[i]))
    system = ("你是给美股散户投资者兼量化交易系统开发者写每日简报的中文编辑。根据给你的新闻正文写简短、准确的中文总结："
              "先说清楚发生了什么（谁、做了什么、关键数字或时间），再用一句话说为什么重要（对科技行业、市场或世界格局的影响）。"
              "只根据正文写，不编造正文里没有的事实；保持中立，不给投资建议，不预测涨跌。只输出 JSON。")
    user = ("\n\n".join(parts) + "\n\n输出格式：" + '{"items":[{"i":编号,"t":"中文标题（不超过 30 字）","d":"2–3 句总结（不超过 130 字）"}]}'
            + "\n每篇都要写，编号用上面【】里的数字。")
    text, model, err = cf_ai(system, user)
    if not text:
        return 0, err
    try:
        J = parse_json(text)
    except Exception as e:
        return 0, "返回的不是合法 JSON：%s" % e
    n = 0
    for x in J.get("items") or []:
        try:
            i = int(x.get("i"))
        except Exception:
            continue
        if i in got and 0 <= i < len(items):
            t, d = clip(x.get("t", ""), 40), clip(x.get("d", ""), 170)
            if t and d and re.search(r"[\u4e00-\u9fff]", t + d):
                items[i]["t"], items[i]["d"] = t, d
                items[i]["full"] = True
                n += 1
    return n, "抓到 %d/%d 篇正文" % (len(got), len(items))


def ai_curate(now_utc, market, macro):
    tp, wp = tech_pool(now_utc), world_pool()
    if len(tp) < 3 and len(wp) < 3:
        return None, "候选新闻太少"
    lines = ["【科技 / 商业候选】"]
    for i, a in enumerate(tp):
        lines.append("T%d | %s | %s | %s" % (i, a.get("source", ""), a.get("title", ""), clip(a.get("summary", ""), 220)))
    lines.append("\n【国际候选】（n = 同时报道的媒体数）")
    for i, g in enumerate(wp):
        lines.append("W%d | n=%s | %s | %s" % (i, g.get("n", 1), g.get("en") or g.get("title", ""), clip(g.get("en_summary") or g.get("summary", ""), 220)))
    lines.append("\n【今天的市场与经济数据（只作背景，不要改写数字）】")
    for it in market + macro:
        lines.append("- " + it["t"] + "：" + clip(it.get("d", ""), 120))
    system = ("你是一位给美股散户投资者兼量化交易系统开发者写每日简报的中文编辑。读者想跟上世界的重要动态，但不想被信息焦虑淹没。"
              "原则：只挑真正重要、对科技行业 / 市场 / 世界格局有实质影响的事，宁少勿多；不要标题党、不要情绪化；地缘政治保持中立客观；"
              "不给投资建议、不预测涨跌；只根据给你的候选内容写，不要编造候选里没有的事实和数字。只输出 JSON，不要任何其他文字。")
    user = ("\n".join(lines) + "\n\n请按下面的格式输出 JSON：\n"
            '{"ai":[{"id":"T编号","t":"一句话中文标题（不超过 30 字）","d":"1–2 句：发生了什么 + 为什么重要（不超过 90 字）"}],'
            '"world":[{"id":"W编号","t":"…","d":"…"}],'
            '"pick":{"id":"T或W编号","t":"…","d":"为什么今天最值得深入了解（不超过 80 字）"}}\n'
            "要求：ai 选 2–4 条（优先 AI、芯片、大型科技公司、重要新产品；没有足够重要的就少选），world 选 3–4 条（优先对市场或世界格局有影响的、报道媒体多的；"
            "同一件事只选一次），pick 从你选中的条目里挑 1 条。")
    text, model, err = cf_ai(system, user)
    if not text:
        return None, err
    try:
        J = parse_json(text)
    except Exception as e:
        return None, "%s 返回的不是合法 JSON：%s" % (model, e)

    def items(lst, pool, prefix, lo, hi):
        out, used = [], set()
        for x in (lst or [])[:hi]:
            m = re.fullmatch(prefix + r"(\d+)", str(x.get("id", "")).strip())
            if not m or int(m.group(1)) >= len(pool) or m.group(1) in used:
                continue
            used.add(m.group(1))
            g = pool[int(m.group(1))]
            t, d = clip(x.get("t", ""), 40), clip(x.get("d", ""), 130)
            if not t or not re.search(r"[\u4e00-\u9fff]", t + d):
                continue
            src = [{"n": g.get("source", "来源"), "u": g.get("link", "")}]
            for o in (g.get("others") or [])[:1]:
                src.append({"n": o.get("source", "来源"), "u": o.get("link", "")})
            out.append({"t": t, "d": d, "src": src, "_en": g.get("en") or g.get("title", "")})
        return out if len(out) >= lo else None
    ai = items(J.get("ai"), tp, "T", 1, 4)
    world = items(J.get("world"), wp, "W", 2, 4)
    if not ai or not world:
        return None, "%s 选出的条目不够或格式不对" % model
    pk = J.get("pick") or {}
    pick = {"t": clip(pk.get("t", ""), 40), "d": clip(pk.get("d", ""), 120)} if pk.get("t") else {}
    n, msg = ai_rewrite(ai + world)
    notice("读全文重写：%d 条（%s）" % (n, msg))
    for it in ai + world:
        it.pop("_en", None)
    return {"ai": ai, "world": world, "pick": pick, "model": model}, ""


def push_brief(D):
    """📲 每天第一次生成时推一条到 Telegram：每个板块最重要的一条 + 今日一件事"""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    try:
        from notify import tg
    except Exception:
        return
    t = dt.date.fromisoformat(D["date"])
    lines = ["☀️ **每日简报 · %d月%d日 周%s**%s" % (t.month, t.day, WK[t.weekday()], "（AI 整理）" if D.get("ai") else ""), ""]
    for s in D["sections"]:
        if s["items"]:
            lines.append("%s：%s" % (s["title"], s["items"][0]["t"]))
    if D.get("pick", {}).get("t"):
        lines += ["", "📌 **今日一件事**：" + D["pick"]["t"]]
    if D.get("week"):
        lines += ["", "🗓️ 本周关注 %d 件" % len(D["week"])]
    lines += ["", "[看全文](%s/brief.html)" % SITE]
    tg("\n".join(lines), "brief")


def build(dry=False, no_ai=False):
    now_utc = dt.datetime.now(dt.timezone.utc)
    today = la_now().date().isoformat()
    try:
        cache = json.load(open(TCACHE_PATH, encoding="utf-8"))
    except Exception:
        cache = {}
    ai = sec_ai(now_utc, cache)
    market = sec_market(today)
    macro, upcoming = sec_macro(today)
    world = sec_world()

    hi = [m for m in upcoming if m.get("imp") == "高" and m["date"] <= (dt.date.fromisoformat(today) + dt.timedelta(days=3)).isoformat()]
    if hi:
        m = hi[0]
        pick = {"t": "%s：%s" % (md(m["date"]), m.get("title", "")), "d": (m.get("note") or "") + " 这是近几天最可能让整个市场大幅波动的事件，公布前后留意仓位。"}
    elif world:
        w = max(world, key=lambda x: x["_n"])
        pick = {"t": w["t"], "d": "今天报道媒体最多的一件事。" + w["d"]}
    else:
        pick = {}
    for w in world:
        w.pop("_n", None)

    used_ai = None
    if not no_ai:
        res, err = ai_curate(now_utc, market, macro)
        if res:
            ai, world, used_ai = res["ai"], res["world"], res["model"]
            if res["pick"] and not hi:   # 近 3 天有高重要性经济数据时仍然把它当「今日一件事」
                pick = res["pick"]
            notice("AI 整理成功（%s）：科技 %d 条、国际 %d 条" % (used_ai, len(ai), len(world)))
        else:
            notice("AI 整理没用上，改用规则版：" + err)

    week = []
    if dt.date.fromisoformat(today).weekday() == 0:
        E = load("earnings/data/latest.json")
        fri = (dt.date.fromisoformat(today) + dt.timedelta(days=4)).isoformat()
        for m in sorted([m for m in macro_events(E) if today <= m["date"] <= fri and m.get("imp") in ("高", "中")], key=lambda m: (m["date"], m.get("time") or "")):
            week.append({"t": "%s %s" % (md(m["date"]), m.get("title", "")), "d": m.get("note") or ""})
        for d in E.get("days", []):
            if today <= d.get("date", "") <= fri and d.get("earnings"):
                big = sorted(d["earnings"], key=lambda e: -(e.get("cap") or 0))[:4]
                week.append({"t": "%s 财报：%s" % (md(d["date"]), "、".join(e["t"] for e in big)), "d": "当天共 %d 家公司发布财报，这里列市值最大的几家。" % len(d["earnings"])})

    secs = [("ai", "🤖 AI 与科技", ai), ("market", "📈 美股市场", market), ("macro", "🏦 宏观经济", macro), ("world", "🌍 世界大事", world)]
    D = {"date": today, "generated": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"), "auto": True, "ai": used_ai,
         "sections": [{"key": k, "title": t, "items": it} for k, t, it in secs], "pick": pick, "week": week}
    n = sum(len(s["items"]) for s in D["sections"])
    print("%s：%s，共 %d 条%s" % (today, " / ".join("%s %d" % (t, len(it)) for _, t, it in secs), n, "，含本周关注 %d 条" % len(week) if week else ""))
    if n < 4:
        print("❌ 内容太少（上游数据可能没更新），这次不写入")
        return 1
    if dry:
        print(json.dumps(D, ensure_ascii=False, indent=1)[:4000])
        return 0

    os.makedirs(OUT, exist_ok=True)
    first_today = not os.path.exists(os.path.join(OUT, today + ".json"))
    with open(os.path.join(OUT, today + ".json"), "w", encoding="utf-8") as f:
        json.dump(D, f, ensure_ascii=False, indent=1)
    # index.json：只放日期列表（最新在前，最多 30 天），清理旧文件
    dates = sorted({fn[:-5] for fn in os.listdir(OUT) if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", fn)}, reverse=True)
    keep, drop = dates[:KEEP_DAYS], dates[KEEP_DAYS:]
    for d in drop:
        os.remove(os.path.join(OUT, d + ".json"))
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"generated": D["generated"], "dates": keep}, f, ensure_ascii=False)
    # 翻译缓存只留最近 300 条，避免越存越大
    keep_cache = dict(list(cache.items())[-300:])
    with open(TCACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(keep_cache, f, ensure_ascii=False)
    print("✅ 已写入 brief/data/%s.json（共保留 %d 期）" % (today, len(keep)))
    if first_today or os.environ.get("BRIEF_PUSH") == "1":
        push_brief(D)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--no-ai", action="store_true", help="不调用 AI，只用规则版")
    a = ap.parse_args()
    sys.exit(build(a.dry, a.no_ai))
