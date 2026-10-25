"""Telegram 推送：GitHub 评论风格的 Markdown 要转对，HTML 要转义"""
from conftest import load

notify = load("notify", "scripts/notify.py")


def test_md2html():
    out = notify.md2html("### 🔔 VOO 跌到 650\n**收盘 648**·[股票池](https://x.io/a?b=1&c=2)\n- 第一 <b>x</b>\n\n@boliunew\n<!-- tag -->")
    assert "<b>🔔 VOO 跌到 650</b>" in out
    assert '<a href="https://x.io/a?b=1&amp;c=2">股票池</a>' in out
    assert "&lt;b&gt;x&lt;/b&gt;" in out
    assert "@boliunew" not in out and "tag" not in out


def test_chunks_split_long_text():
    parts = notify.chunks("\n".join(["x" * 100] * 100), 1000)
    assert all(len(p) <= 1000 for p in parts) and sum(len(p) for p in parts) >= 100 * 100
