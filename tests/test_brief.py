"""每日简报的 AI 返回解析：几种格式都要能读出来，读不出来就退回规则版"""
from conftest import load

bb = load("brief_build", "brief/build.py")


def test_ai_text_formats():
    j = '{"a":1}'
    assert bb.ai_text({"response": j}) == j
    assert bb.ai_text({"output": [{"type": "reasoning"}, {"type": "message", "content": [{"text": j}]}]}) == j
    assert bb.ai_text({"choices": [{"message": {"content": j}}]}) == j


def test_parse_json_strips_noise():
    assert bb.parse_json('想一想<think>x</think>```json\n{"ok": true}\n```') == {"ok": True}
