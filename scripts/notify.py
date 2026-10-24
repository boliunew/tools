#!/usr/bin/env python3
"""📲 统一推送：所有提醒都发到 Telegram。只用标准库。

  from notify import tg        # 先 sys.path.insert(0, <仓库>/scripts)
  ok = tg("**标题**\n正文 [链接](https://…)", kind="alert")

  · 文字用 GitHub 评论那种 Markdown 写就行（**粗体**、[文字](链接)、`代码`、### 标题、- 列表），这里转成 Telegram 的格式。
  · 超过 4000 字自动拆成几条。
  · kind 用来单独开关：仓库根目录 notify.json 里 {"off": ["holiday"]} 就不发节日提醒。
    种类：signal 信号日报 · alert 股价提醒 · monitor 网页监控 · deals 打折关注 · holiday 节日提醒 ·
          health 系统体检 · brief 每日简报 · ai AI 盘后解读 · earnings 财报提醒
  · 没配 TG_BOT_TOKEN / TG_CHAT_ID、被关掉、或发送失败时返回 False，调用方照旧走 GitHub 留言。

  python scripts/notify.py "测试消息"          命令行发一条（kind=test）
"""
import html
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KINDS = {"signal": "信号日报", "alert": "股价提醒", "monitor": "网页监控", "deals": "打折关注", "holiday": "节日提醒",
         "health": "系统体检", "brief": "每日简报", "ai": "AI 盘后解读", "earnings": "财报提醒", "test": "测试"}


def enabled(kind):
    try:
        with open(os.path.join(ROOT, "notify.json"), encoding="utf-8") as f:
            off = set(json.load(f).get("off") or [])
    except Exception:
        off = set()
    return kind not in off


def configured():
    return bool(os.environ.get("TG_BOT_TOKEN", "").strip() and os.environ.get("TG_CHAT_ID", "").strip())


def md2html(md):
    """GitHub 评论里常用的 Markdown → Telegram HTML（只支持 b / i / a / code / pre）"""
    out = []
    for line in (md or "").replace("\r", "").split("\n"):
        s = line
        if re.match(r"^\s*<!--.*-->\s*$", s):          # 隐藏标记（去重用的）不发
            continue
        s = re.sub(r"<!--.*?-->", "", s)
        s = re.sub(r"^\s*@[\w-]+\s*$", "", s)          # 单独一行的 @提及 去掉
        hdr = re.match(r"^\s*#{1,6}\s+(.*)$", s)
        if hdr:
            s = "**" + hdr.group(1) + "**"
        s = re.sub(r"^(\s*)[-*]\s+", r"\1• ", s)
        s = re.sub(r"^\s*>\s?", "▎", s)
        s = re.sub(r"^\s*\|?\s*:?-{3,}.*$", "", s)      # 表格分隔线
        tokens = []

        def keep(m, fmt):
            tokens.append(fmt(m))
            return "\x00%d\x00" % (len(tokens) - 1)
        s = re.sub(r"`([^`]+)`", lambda m: keep(m, lambda m: "<code>%s</code>" % html.escape(m.group(1))), s)
        s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", lambda m: keep(m, lambda m: '<a href="%s">%s</a>' % (html.escape(m.group(2), quote=True), html.escape(m.group(1)))), s)
        s = html.escape(s, quote=False)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", s)
        s = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"<i>\1</i>", s)
        s = re.sub(r"\x00(\d+)\x00", lambda m: tokens[int(m.group(1))], s)
        out.append(s)
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _send(text, parse_html=True):
    tok, chat = os.environ["TG_BOT_TOKEN"].strip(), os.environ["TG_CHAT_ID"].strip()
    body = {"chat_id": chat, "text": text, "disable_web_page_preview": True}
    if parse_html:
        body["parse_mode"] = "HTML"
    req = urllib.request.Request("https://api.telegram.org/bot%s/sendMessage" % tok, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8")).get("ok", False)


def chunks(text, n=4000):
    parts, cur = [], ""
    for para in text.split("\n"):
        if len(cur) + len(para) + 1 > n and cur:
            parts.append(cur)
            cur = ""
        while len(para) > n:
            parts.append(para[:n])
            para = para[n:]
        cur = (cur + "\n" + para) if cur else para
    if cur:
        parts.append(cur)
    return parts


def tg(markdown, kind="test", html_ready=False):
    """发一条推送；成功返回 True。markdown 是 GitHub 评论风格的文字（html_ready=True 表示已经是 Telegram HTML）。"""
    if not configured() or not enabled(kind):
        return False
    text = markdown if html_ready else md2html(markdown)
    ok = True
    for part in chunks(text):
        try:
            ok = _send(part) and ok
        except Exception as e:  # HTML 格式出错时退回纯文本再试一次
            try:
                ok = _send(re.sub(r"<[^>]+>", "", part), parse_html=False) and ok
            except Exception as e2:  # noqa: BLE001
                msg = "Telegram 推送失败（%s）：%s / %s" % (KINDS.get(kind, kind), str(e)[:120], str(e2)[:120])
                print(("::warning title=推送::" if os.environ.get("GITHUB_ACTIONS") else "") + msg)
                return False
    if ok and os.environ.get("GITHUB_ACTIONS"):
        print("::notice title=推送::已发到 Telegram（%s）" % KINDS.get(kind, kind))
    return ok


def strip_mention(body, owner=None):
    """已经发到 Telegram 时，GitHub 留言只留作记录：去掉 @提及，免得 GitHub 再推一遍"""
    return re.sub(r"(^|\s)@%s\b" % re.escape(owner or os.environ.get("OWNER", "boliunew")), r"\1", body or "").strip()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    msg = " ".join(sys.argv[1:]) or "✅ 测试：工具箱的推送能发到 Telegram 了"
    print("sent" if tg(msg, "test") else "not sent（没配 TG_BOT_TOKEN / TG_CHAT_ID？）")
