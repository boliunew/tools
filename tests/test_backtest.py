"""幸存者偏差修正：这几年才调入标普 500 的股票，只从调入那天起算"""
import pandas as pd

from conftest import load

scan = load("scan", "stocks/scan.py")


def test_membership_point_in_time():
    rows = [
        {"d": "2019-01-01", "add": "OLD", "rem": "X1"},     # 窗口之前调入：全算
        {"d": "2024-03-01", "add": "NEW", "rem": "GONE"},   # 窗口内调入：从 2024-03-01 起算；GONE 被调出
        {"d": "2023-01-01", "add": "BACK", "rem": ""},
        {"d": "2024-01-01", "add": "", "rem": "BACK"},
        {"d": "2025-01-01", "add": "BACK", "rem": ""},      # 进出多次：取最近一次调入
    ]
    since, removed = scan.membership(rows, {"OLD", "NEW", "BACK", "NDXONLY"}, pd.Timestamp("2021-10-23"), {"OLD", "NEW", "BACK"})
    assert {k: str(v.date()) for k, v in since.items()} == {"NEW": "2024-03-01", "BACK": "2025-01-01"}
    assert removed == {"GONE"}
