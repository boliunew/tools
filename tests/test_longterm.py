"""长线评分：缺数据统一处理——核心指标缺了最高只评 C，次要指标缺了给一半分并写明"""
import numpy as np
import pandas as pd

from conftest import load

lt = load("longterm_build", "longterm/build.py")

YRS = ["2022-12-31", "2023-12-31", "2024-12-31", "2025-12-31"]
PX = pd.Series(np.linspace(80, 100, 1300), index=pd.bdate_range(end="2026-10-23", periods=1300))


def S(v):
    return dict(zip(YRS, v))


FULL = {"rev": S([100, 110, 121, 133]), "gp": S([50, 55, 60, 66]), "op": S([20, 22, 24, 27]), "ebit": S([20, 22, 24, 27]),
        "ni": S([15, 16, 18, 20]), "eps": S([3, 3.3, 3.6, 4]), "tax": S([.2] * 4), "eq": S([60, 65, 70, 75]),
        "ic": S([80, 85, 90, 95]), "ttm_eps": 4.2, "ebitda": 30, "total_debt": 20, "total_cash": 10}


def score(f, sector="Industrials"):
    return lt.score_one("X", f, PX, 0.5, sector, 25)


def test_missing_secondary_gets_half_and_flag():
    full = score(FULL)
    f = dict(FULL)
    f.pop("gp")
    o = score(f)
    assert o["parts"]["moat"] == full["parts"]["moat"] - (8 if full["gm"] >= 0.6 else 6 if full["gm"] >= 0.4 else 3) + 4
    assert "毛利率" in o["missing"]


def test_missing_core_caps_grade():
    f = dict(FULL)
    f.pop("ebit")
    f.pop("ni")
    o = score(f)
    assert o["grade"] in ("C", "D") and "资本回报率" in o["missing"]


def test_unknown_debt_is_not_treated_as_no_debt():
    f = dict(FULL)
    f.pop("total_debt")
    assert score(f)["parts"]["debt"] < 0
