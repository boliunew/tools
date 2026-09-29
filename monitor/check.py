#!/usr/bin/env python3
"""
网页 / 价格监控 (GitHub Actions)

Each open issue created by the repo owner with the "监控" form is one watch.
Runs every 4 hours (and immediately when an issue is opened/edited), checks the
page, and comments on the issue when something changes — GitHub then notifies
you by app push / email.  State lives in monitor/data/state.json.

Env: GITHUB_TOKEN, GITHUB_REPOSITORY, OWNER, EVENT_NAME, ISSUE_NUMBER, ISSUE_ACTION
"""
import datetime as dt
import difflib
import hashlib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "data", "state.json")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")
MODES = {"价格": "price", "内容变化": "content", "关键词出现": "appear", "关键词消失": "disappear"}
MODE_ZH = {v: k for k, v in MODES.items()}
FAIL_ALERT = 3
SITE_SELECTORS = [
    "#corePrice_feature_div .a-offscreen", "#corePriceDisplay_desktop_feature_div .a-offscreen",
    "#priceblock_ourprice", "#priceblock_dealprice", ".a-price .a-offscreen",           # Amazon
    "[data-testid='customer-price'] span", ".priceView-customer-price span",             # Best Buy
    "[itemprop='price']", "[data-test='product-price']", "[data-testid='price-wrap'] span",  # Walmart / Target
    ".price-current", ".product-price", ".price .amount", ".price",
]


def now_iso():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ----------------------------------------------------------------------------- GitHub API
class GH:
    def __init__(self):
        import requests
        self.s = requests.Session()
        self.s.headers.update({"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
                               "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
        self.repo = os.environ["GITHUB_REPOSITORY"]
        self.base = "https://api.github.com/repos/" + self.repo

    def open_issues(self):
        out, page = [], 1
        while True:
            r = self.s.get(self.base + "/issues", params={"state": "open", "per_page": 100, "page": page})
            r.raise_for_status()
            batch = [i for i in r.json() if "pull_request" not in i]
            out += batch
            if len(r.json()) < 100:
                return out
            page += 1

    def issue(self, n):
        r = self.s.get(f"{self.base}/issues/{n}")
        r.raise_for_status()
        return r.json()

    def comment(self, n, body):
        self.s.post(f"{self.base}/issues/{n}/comments", json={"body": body}).raise_for_status()

    def ensure_label(self, n):
        self.s.post(self.base + "/labels", json={"name": "watch", "color": "1f6f66", "description": "网页 / 价格监控"})
        self.s.post(f"{self.base}/issues/{n}/labels", json={"labels": ["watch"]})


# ----------------------------------------------------------------------------- issue parsing
def parse_body(body):
    fields, cur = {}, None
    for line in (body or "").splitlines():
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m:
            cur = m.group(1)
            fields[cur] = []
            continue
        if cur is not None:
            fields[cur].append(line)
    f = {k: "\n".join(v).strip() for k, v in fields.items()}
    f = {k: ("" if v in ("_No response_", "None") else v) for k, v in f.items()}

    def pick(prefix):
        for k, v in f.items():
            if k.startswith(prefix):
                return v
        return ""
    url = pick("网址")
    m = re.search(r"https?://\S+", url)
    url = m.group(0).rstrip(")>]") if m else ""
    mode_txt = pick("监控类型").strip()
    mode = next((v for k, v in MODES.items() if k in mode_txt), "price")
    target = None
    t = re.search(r"\d+(?:\.\d+)?", pick("目标价").replace(",", ""))
    if t:
        target = float(t.group(0))
    return {"url": url, "mode": mode, "target": target, "keyword": pick("关键词").strip(), "selector": pick("CSS").strip()}


def is_watch(issue):
    labels = [l["name"] for l in issue.get("labels", [])]
    return "watch" in labels or issue.get("title", "").startswith("监控")


# ----------------------------------------------------------------------------- page fetching
def fetch_requests(url):
    import requests
    r = requests.get(url, timeout=25, headers={
        "User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"})
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}")
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    return r.text


def fetch_browser(url):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="chrome", headless=True)
        except Exception:  # noqa: BLE001
            b = p.chromium.launch(headless=True)
        pg = b.new_page(user_agent=UA, locale="en-US")
        pg.goto(url, timeout=45000, wait_until="domcontentloaded")
        pg.wait_for_timeout(4000)
        html = pg.content()
        b.close()
        return html


BLOCK_HINTS = re.compile(r"(?i)(captcha|robot check|are you a human|access denied|unusual traffic|enable javascript|request blocked|press & hold)")


def parse_price(text):
    if text is None:
        return None
    t = str(text).replace(" ", " ")
    m = re.search(r"(\d{1,3}(?:[,\s]\d{3})+|\d+)(?:[.,](\d{1,2}))?", t)
    if not m:
        return None
    whole = re.sub(r"[,\s]", "", m.group(1))
    try:
        return float(whole + ("." + m.group(2) if m.group(2) else ""))
    except ValueError:
        return None


def walk_jsonld(obj, out):
    if isinstance(obj, dict):
        if "offers" in obj:
            offers = obj["offers"]
            for o in (offers if isinstance(offers, list) else [offers]):
                if isinstance(o, dict):
                    p = o.get("price", o.get("lowPrice"))
                    if p is None and isinstance(o.get("priceSpecification"), dict):
                        p = o["priceSpecification"].get("price")
                    v = parse_price(p)
                    if v:
                        out.append((v, o.get("priceCurrency", "")))
        for v in obj.values():
            walk_jsonld(v, out)
    elif isinstance(obj, list):
        for v in obj:
            walk_jsonld(v, out)


def analyse(html, w):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.get_text(" ", strip=True) if soup.title else "")[:120]
    res = {"title": title}
    price, cur, how = None, "", ""
    if w["selector"]:
        el = soup.select_one(w["selector"])
        if el is not None:
            price = parse_price(el.get("content") or el.get_text(" ", strip=True))
            how = "selector"
    if w["mode"] == "price" and price is None:
        found = []
        for s in soup.find_all("script", type="application/ld+json"):
            try:
                walk_jsonld(json.loads(s.string or s.get_text() or "{}"), found)
            except Exception:  # noqa: BLE001
                pass
        if found:
            price, cur, how = found[0][0], found[0][1], "json-ld"
    if w["mode"] == "price" and price is None:
        for attr, name in (("property", "product:price:amount"), ("property", "og:price:amount"), ("itemprop", "price")):
            el = soup.find("meta", attrs={attr: name})
            if el and parse_price(el.get("content")):
                price, how = parse_price(el.get("content")), "meta"
                c = soup.find("meta", attrs={"property": "product:price:currency"})
                cur = c.get("content", "") if c else ""
                break
    if w["mode"] == "price" and price is None:
        for sel in SITE_SELECTORS:
            el = soup.select_one(sel)
            if el is not None:
                v = parse_price(el.get("content") or el.get_text(" ", strip=True))
                if v:
                    price, how = v, "css"
                    break
    res.update({"price": price, "currency": cur or "USD", "how": how})

    for t in soup(["script", "style", "noscript", "svg", "template"]):
        t.decompose()
    scope = soup.select_one(w["selector"]) if w["selector"] else None
    if scope is None:
        for t in soup(["nav", "header", "footer", "aside"]):
            t.decompose()
        scope = soup.body or soup
    lines = [re.sub(r"\s+", " ", x).strip() for x in scope.get_text("\n").splitlines()]
    lines = [x for x in lines if x]
    text = "\n".join(lines)
    res["text_hash"] = hashlib.sha1(text.encode()).hexdigest()[:16]
    res["lines"] = lines[:400]
    if w["keyword"]:
        res["found"] = w["keyword"].lower() in text.lower()
    res["blocked"] = bool(BLOCK_HINTS.search(text[:4000])) and len(text) < 6000
    return res


def check_page(w):
    errors = []
    names = {"fetch_requests": "直接访问", "fetch_browser": "浏览器模拟"}
    for fetcher in (fetch_requests, fetch_browser):
        try:
            html = fetcher(w["url"])
            r = analyse(html, w)
            need_price = w["mode"] == "price" and r["price"] is None
            need_kw = w["mode"] in ("appear", "disappear") and not w["keyword"]
            if need_kw:
                return {"ok": False, "error": "关键词监控需要填写关键词"}
            if r["blocked"] or need_price:
                errors.append(names.get(fetcher.__name__, "访问") + "：" + ("被网站拦截（验证码）" if r["blocked"] else "页面上找不到价格"))
                continue
            r["ok"], r["via"] = True, fetcher.__name__
            return r
        except Exception as e:  # noqa: BLE001
            errors.append(names.get(fetcher.__name__, "访问") + f"：{type(e).__name__} {str(e)[:120]}")
    return {"ok": False, "error": "；".join(errors)}


# ----------------------------------------------------------------------------- change logic
def fmt(p, cur="USD"):
    sym = {"USD": "$", "CNY": "¥", "EUR": "€", "GBP": "£", "JPY": "¥", "CAD": "C$"}.get((cur or "USD").upper(), "")
    return f"{sym}{p:,.2f}" if sym else f"{p:,.2f} {cur}"


def evaluate(n, w, st, r, first):
    """Update state entry `st` with result `r`; return a comment body or None."""
    st["checked"] = now_iso()
    if not r["ok"]:
        st["fails"] = st.get("fails", 0) + 1
        st["error"] = r["error"]
        if first:
            return (f"⚠️ 无法读取这个网页：{r['error']}\n\n常见原因：网站拦截了自动访问，或者价格是登录后才显示。"
                    "可以试试填写 CSS 选择器，或者改用「内容变化」「关键词」类型。修改后编辑这个 issue 即可重新检查。")
        if st["fails"] == FAIL_ALERT:
            return f"⚠️ 已连续 {FAIL_ALERT} 次无法访问：{r['error']}\n\n会继续尝试，恢复后自动通知。"
        return None
    recovered = st.get("fails", 0) >= FAIL_ALERT
    st["fails"], st["error"] = 0, ""
    st["page_title"] = r.get("title", "")
    msg = None
    mode = w["mode"]
    if mode == "price":
        p, cur = r["price"], r["currency"]
        last = st.get("price")
        hist = st.setdefault("history", [])
        if not hist or hist[-1][1] != p or hist[-1][0][:10] != st["checked"][:10]:
            hist.append([st["checked"], p])
            del hist[:-300]
        st.update({"price": p, "currency": cur, "low": min(p, st.get("low", p)), "high": max(p, st.get("high", p))})
        if first:
            msg = f"✅ 已开始监控，当前价格 **{fmt(p, cur)}**" + (f"，目标价 {fmt(w['target'], cur)}" if w["target"] else "") + "。"
        elif last is not None and p < last:
            if w["target"] is None:
                msg = f"⬇️ **降价了！** {fmt(last, cur)} → **{fmt(p, cur)}**（{(p / last - 1) * 100:+.1f}%）"
            elif p <= w["target"] and (last > w["target"] or not st.get("alerted")):
                msg = f"🎯 **到达目标价！** 现价 **{fmt(p, cur)}**（目标 {fmt(w['target'], cur)}，之前 {fmt(last, cur)}）"
            elif p <= w["target"] and p < last * 0.99:
                msg = f"⬇️ **继续降价** {fmt(last, cur)} → **{fmt(p, cur)}**（已低于目标价 {fmt(w['target'], cur)}）"
        elif last is not None and p > last and st.get("alerted") and w["target"] and p > w["target"]:
            st["alerted"] = False
        if msg and "目标" in msg:
            st["alerted"] = True
        if w["target"] and p > w["target"]:
            st["alerted"] = False
    elif mode == "content":
        old_lines = st.get("lines", [])
        if first:
            msg = f"✅ 已开始监控页面内容（{len(r['lines'])} 行文字）。内容变化时会在这里通知。"
        elif r["text_hash"] != st.get("text_hash"):
            diff = [l for l in difflib.unified_diff(old_lines, r["lines"], lineterm="", n=0) if not l.startswith(("---", "+++", "@@"))]
            if diff:
                body = "\n".join(diff[:25]) + ("\n…" if len(diff) > 25 else "")
                msg = f"🔔 **页面内容有变化**\n\n```diff\n{body}\n```"
        st["text_hash"], st["lines"] = r["text_hash"], r["lines"][:400]
        st["changes"] = st.get("changes", 0) + (1 if msg and not first else 0)
    else:
        found, prev = r.get("found"), st.get("found")
        kw = w["keyword"]
        if first:
            msg = f"✅ 已开始监控关键词「{kw}」，目前页面上{'有' if found else '没有'}这个词。"
        elif mode == "appear" and found and not prev:
            msg = f"🔔 **关键词「{kw}」出现了！**"
        elif mode == "disappear" and prev and not found:
            msg = f"🔔 **关键词「{kw}」消失了！**"
        st["found"] = found
    if recovered and not msg:
        msg = "✅ 网页恢复访问，继续监控。"
    return msg


# ----------------------------------------------------------------------------- main
def main():
    gh = GH()
    owner = os.environ.get("OWNER", "").lower()
    event, num, action = os.environ.get("EVENT_NAME", ""), os.environ.get("ISSUE_NUMBER", ""), os.environ.get("ISSUE_ACTION", "")
    state = {"watches": {}}
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as f:
            state = json.load(f)
    W = state.setdefault("watches", {})

    if event == "issues" and num:
        issues = [gh.issue(num)]
        if action == "closed" or issues[0]["state"] != "open":
            W.pop(str(num), None)
            issues = []
    else:
        issues = [i for i in gh.open_issues() if is_watch(i)]
        open_nums = {str(i["number"]) for i in issues}
        for k in list(W):
            if k not in open_nums:
                W.pop(k)

    for iss in issues:
        n = str(iss["number"])
        if not is_watch(iss) or iss["user"]["login"].lower() != owner:
            print("skip issue", n, "(not a watch by the owner)")
            continue
        w = parse_body(iss.get("body", ""))
        name = re.sub(r"^监控[:：]\s*", "", iss["title"]).strip()
        if not w["url"]:
            if n not in W:
                gh.comment(iss["number"], "⚠️ 没有找到网址，请编辑这个 issue 填写「网址」。")
                W[n] = {"error": "缺少网址", "fails": 1}
            continue
        if "watch" not in [l["name"] for l in iss.get("labels", [])]:
            gh.ensure_label(iss["number"])
        prev = W.get(n)
        reset = prev is None or action == "edited" or prev.get("url") != w["url"] or prev.get("mode") != w["mode"]
        st = {} if reset else prev
        st.update({"name": name, "url": w["url"], "mode": w["mode"], "target": w["target"], "keyword": w["keyword"],
                   "selector": w["selector"], "issue": iss["number"], "issue_url": iss["html_url"]})
        if reset and prev and prev.get("history") and prev.get("url") == w["url"]:
            st["history"] = prev["history"]
        print(f"#{n} {w['mode']} {w['url'][:80]}")
        r = check_page(w)
        msg = evaluate(n, w, st, r, first=reset)
        if msg:
            try:
                gh.comment(iss["number"], msg)
            except Exception as e:  # noqa: BLE001
                print("comment failed", e)
        W[n] = st
        print("  ->", "ok" if r["ok"] else r["error"], (msg or "")[:80])
        time.sleep(2)

    state["generated"] = now_iso()
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    public = {"generated": state["generated"], "watches": W}
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(public, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
