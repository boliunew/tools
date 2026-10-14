#!/usr/bin/env python3
"""中美节假日 → holidays/data.json（holidays.html 用）

中国：国务院公布的法定假日 + 调休上班日（python-holidays 收录；还没公布的年份按规则估算，标「预计」），
      传统节日（农历，lunardate 换算）。
美国：联邦假日、加州州假、美股（NYSE）休市日、常见节日（母亲节、万圣节、夏令时切换……）。

  pip install holidays lunardate
  python scripts/build_holidays.py

每月 1 号和 15 号由 .github/workflows/holidays.yml 自动重跑（国务院通常 11 月公布下一年的放假安排）。
"""
import datetime as dt
import json
import os
import re

import holidays
from lunardate import LunarDate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "holidays", "data.json")
D = dt.date
ONE = dt.timedelta(days=1)

CN_EMOJI = {"元旦": "🎆", "春节": "🧧", "清明节": "🌿", "劳动节": "🛠️", "端午节": "🐉", "中秋节": "🥮", "国庆节": "🇨🇳"}
US_ZH = {
    "New Year's Day": ("元旦", "🎆"), "Martin Luther King Jr. Day": ("马丁·路德·金纪念日", "✊"),
    "Washington's Birthday": ("总统日", "🎩"), "Presidents' Day": ("总统日", "🎩"), "Memorial Day": ("阵亡将士纪念日", "🎖️"),
    "Juneteenth National Independence Day": ("六月节（解放日）", "🕊️"), "Independence Day": ("独立日", "🎇"),
    "Labor Day": ("劳动节", "🛠️"), "Columbus Day": ("哥伦布日", "⛵"), "Veterans Day": ("退伍军人节", "🎖️"),
    "Thanksgiving Day": ("感恩节", "🦃"), "Christmas Day": ("圣诞节", "🎄"), "Good Friday": ("耶稣受难日", "✝️"),
    "Cesar Chavez Day": ("塞萨尔·查维斯日", "🌾"), "Day After Thanksgiving": ("感恩节次日", "🛍️"), "Diwali": ("排灯节", "🪔"),
    "Native American Day": ("美洲原住民日", "🪶"), "Susan B. Anthony Day": None, "Lincoln's Birthday": ("林肯诞辰", "🎩"),
}
TRAD = [   # (农历月, 日, 名字, emoji, 说明)
    (1, 15, "元宵节", "🏮", "正月十五，吃汤圆、看花灯"),
    (2, 2, "龙抬头", "🐲", "二月初二，理发图个好彩头"),
    (7, 7, "七夕", "💞", "七月初七，中国情人节"),
    (7, 15, "中元节", "🕯️", "七月十五，祭祖"),
    (9, 9, "重阳节", "🍂", "九月初九，登高、敬老"),
    (12, 8, "腊八节", "🥣", "腊月初八，喝腊八粥"),
    (12, 23, "小年", "🧹", "腊月廿三（北方），祭灶、扫尘"),
]


def nth_weekday(y, m, wd, n):   # n-th weekday (0=Mon) of month; n=-1 → last
    if n > 0:
        d = D(y, m, 1)
        d += dt.timedelta(days=(wd - d.weekday()) % 7)
        return d + dt.timedelta(weeks=n - 1)
    d = D(y, m + 1, 1) - ONE if m < 12 else D(y, 12, 31)
    return d - dt.timedelta(days=(d.weekday() - wd) % 7)


def easter(y):   # Anonymous Gregorian algorithm
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mo = (h + l - 7 * m + 114) // 31
    return D(y, mo, (h + l - 7 * m + 114) % 31 + 1)


def china(years):
    out = []
    official = set(getattr(holidays.China(years=years[0]), "special_public_holidays", {}).keys())
    for y in years:
        cn = holidays.China(years=y)
        listed = dict(cn.items())
        work = set()
        for d, n in listed.items():
            for m in re.finditer(r"由 (\d{4}-\d\d-\d\d) 调休", n):
                work.add(D.fromisoformat(m.group(1)))
        def off(d):
            return d in listed or (d.weekday() >= 5 and d not in work)
        seen = set()
        for d0 in sorted(listed):
            if d0 in seen or d0.year != y:
                continue
            a = d0
            while off(a - ONE):
                a -= ONE
            b = d0
            while off(b + ONE):
                b += ONE
            days, x = [], a
            while x <= b:
                days.append(x)
                seen.add(x)
                x += ONE
            names = [listed[x] for x in days if x in listed]
            main = next((re.sub(r"（.*?）", "", n) for n in names if not n.startswith(("休息日", "农历除夕"))), names[0])
            main = re.sub(r"（.*?）", "", main)
            mk = sorted(w for w in work if any(n for x in days if x in listed for n in [listed[x]] if w.isoformat() in n))
            core = next(x for x in days if x in listed and not listed[x].startswith("休息日"))
            out.append({"c": "cn", "k": "off", "d": core.isoformat(), "from": a.isoformat(), "to": b.isoformat(), "n": main,
                        "e": CN_EMOJI.get(main, "🎉"), "len": len(days), "work": [w.isoformat() for w in mk],
                        "est": y not in official})
    # 传统节日（农历）+ 除夕
    for ly in range(years[0] - 1, years[-1] + 1):
        for m, d, n, e, note in TRAD:
            try:
                s = LunarDate(ly, m, d).to_solar_date()
            except ValueError:
                continue
            if s.year in years:
                out.append({"c": "cn", "k": "fest", "d": s.isoformat(), "n": n, "e": e, "note": note})
        eve = LunarDate(ly + 1, 1, 1).to_solar_date() - ONE
        if eve.year in years:
            out.append({"c": "cn", "k": "fest", "d": eve.isoformat(), "n": "除夕", "e": "🧨", "note": "腊月最后一天，年夜饭、守岁"})
    return out


def usa(years):
    out = []
    nyse = holidays.financial_holidays("NYSE", years=years)
    for y in years:
        fed = holidays.US(years=y)
        ca = holidays.US(subdiv="CA", years=y)
        rows = []
        for d in sorted(set(fed) | set(ca)):
            if d.year != y:
                continue
            for name in (ca.get_list(d) if d in ca else []) + (fed.get_list(d) if d in fed else []):
                obs = "(observed)" in name
                base = name.replace(" (observed)", "").strip()
                zh = US_ZH.get(base)
                if zh is None or any(r[1] == zh[0] and r[0] == d for r in rows):
                    continue
                rows.append((d, zh[0], zh[1], base, obs, d in fed))
        obs_of = {r[1]: r[0] for r in rows if r[4]}
        for d, zh, e, base, obs, is_fed in rows:
            if not obs and zh in obs_of and abs((obs_of[zh] - d).days) <= 3:
                continue   # 正日子在周末：只留补休那天
            note = "联邦假日：政府、银行、邮局放假" if is_fed else "加州州假：州政府放假，大多数公司照常上班"
            if obs:
                note = "正日子在周末，这天补休。" + note
            out.append({"c": "us", "k": "off" if is_fed else "ca", "d": d.isoformat(), "n": zh + ("（补休）" if obs else ""),
                        "e": e, "en": base, "nyse": d in nyse, "note": note})
        for d, name in sorted(nyse.items()):
            if d.year == y and d not in fed:
                zh = US_ZH.get(name.replace(" (observed)", ""), (name, "📉"))
                out.append({"c": "us", "k": "nyse", "d": d.isoformat(), "n": zh[0], "e": zh[1], "en": name, "nyse": True,
                            "note": "不是联邦假日，但美股休市"})
        th = nth_weekday(y, 11, 3, 4)
        obsv = [
            (D(y, 2, 14), "情人节", "💝", "Valentine's Day"),
            (D(y, 3, 17), "圣帕特里克节", "☘️", "St. Patrick's Day，穿绿色"),
            (easter(y), "复活节", "🐣", "Easter（星期日）"),
            (nth_weekday(y, 5, 6, 2), "母亲节", "💐", "五月第二个星期日"),
            (nth_weekday(y, 6, 6, 3), "父亲节", "👔", "六月第三个星期日"),
            (D(y, 10, 31), "万圣节", "🎃", "Halloween，晚上孩子们挨家要糖"),
            (th + ONE, "黑色星期五", "🛍️", "感恩节次日，一年里最大的购物打折日"),
            (th + dt.timedelta(days=4), "网络星期一", "💻", "Cyber Monday，网购打折"),
            (D(y, 12, 24), "平安夜", "🕯️", "Christmas Eve"),
            (D(y, 12, 31), "跨年夜", "🥂", "New Year's Eve"),
            (nth_weekday(y, 3, 6, 2), "夏令时开始", "⏰", "凌晨 2 点拨快 1 小时（少睡一小时）"),
            (nth_weekday(y, 11, 6, 1), "夏令时结束", "⏰", "凌晨 2 点拨慢 1 小时（多睡一小时）"),
            (D(y, 4, 15), "报税截止", "🧾", "个人所得税申报截止日（遇周末顺延）"),
        ]
        for d, n, e, note in obsv:
            if n == "报税截止":
                while d.weekday() >= 5 or d in fed:
                    d += ONE
            out.append({"c": "us", "k": "fest", "d": d.isoformat(), "n": n, "e": e, "note": note})
    return out


def main():
    y0 = dt.date.today().year
    years = [y0, y0 + 1, y0 + 2]
    items = china(years) + usa(years)
    items.sort(key=lambda x: (x["d"], x["c"]))
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from holiday_info import INFO
    used = {x["c"] + ":" + re.sub(r"（补休）$", "", x["n"]) for x in items}
    miss = sorted(k for k in used if k not in INFO)
    if miss:
        print("⚠️ 这些节日还没写由来：", "、".join(miss))
    info = {k: v for k, v in INFO.items() if k in used}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"generated": dt.date.today().isoformat(), "years": years, "items": items, "info": info}, f, ensure_ascii=False, separators=(",", ":"))
    est = sorted({x["d"][:4] for x in items if x.get("est")})
    print("holidays/data.json：%d 条（%s）；中国放假安排为预计的年份：%s" % (len(items), years, ", ".join(est) or "无"))


if __name__ == "__main__":
    main()
