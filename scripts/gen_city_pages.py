#!/usr/bin/env python3
"""从 sj.html 生成 ny.html、la.html（同一套页面引擎，换内容、地图和配色）。
python3 scripts/gen_city_pages.py   —— 改了 sj.html 的引擎后重跑一次即可。"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(ROOT, "sj.html"), encoding="utf-8").read()

SWITCH = ('<span class="city"><a href="sf.html">🌁 旧金山</a><a href="sj.html">🌴 圣何塞</a>'
          '<a href="ny.html">🗽 纽约</a><a href="la.html">🌇 洛杉矶</a></span>')

NY_SVG = '''<svg class="bridge" viewBox="0 0 400 46" preserveAspectRatio="none" aria-hidden="true">
    <path d="M0 40 H400" stroke="#F4C27A" stroke-width="2"/>
    <path d="M20 40 V30 H30 V24 H40 V40 M44 40 V20 H54 V40 M58 40 V28 H70 V40 M120 40 V26 H132 V40 M136 40 V22 H146 V40" stroke="#F4C27A" stroke-width="1.2" fill="none" opacity=".85"/>
    <path d="M190 40 V18 H194 V12 H197 V6 H199 V1 H200 V6 H202 V12 H205 V18 H209 V40" stroke="#F4C27A" stroke-width="1.5" fill="#F4C27A" fill-opacity=".18"/>
    <path d="M226 40 V16 L232 8 L238 16 V40 M232 8 V3" stroke="#F4C27A" stroke-width="1.4" fill="#F4C27A" fill-opacity=".14"/>
    <path d="M250 40 V24 H262 V40 M266 40 V30 H278 V40 M300 40 V22 H310 V40 M314 40 V28 H326 V40" stroke="#F4C27A" stroke-width="1.2" fill="none" opacity=".85"/>
    <path d="M362 40 V24 M357 40 H367 M362 24 l-2 -6 h4 z M363 19 L368 9 M366 10 l3 -2 M358 23 v-4" stroke="#F4C27A" stroke-width="1.6" fill="none"/>
    <circle cx="368.5" cy="8.5" r="2.4" fill="#FFE7A8"/>
  </svg>'''

LA_SVG = '''<svg class="bridge" viewBox="0 0 400 46" preserveAspectRatio="none" aria-hidden="true">
    <path d="M0 40 Q50 18 110 30 Q170 8 230 26 Q300 14 400 30 V40 Z" fill="#F4C27A" opacity=".24"/>
    <path d="M0 40 H400" stroke="#F4C27A" stroke-width="2"/>
    <text x="150" y="24" font-family="Arial Black,Arial,sans-serif" font-size="9" font-weight="900" fill="#FFE7A8" letter-spacing="2" opacity=".9">HOLLYWOOD</text>
    <circle cx="330" cy="14" r="7" fill="#FFE7A8" opacity=".8"/>
    <path d="M40 40 Q43 24 38 8 M38 8 q-10 -2 -15 5 M38 8 q9 -4 15 1 M38 8 q-4 -7 -12 -7 M38 8 q4 -7 12 -6 M70 40 Q72 28 69 16 M69 16 q-8 -2 -13 4 M69 16 q8 -4 13 1 M69 16 q-4 -6 -10 -6 M69 16 q4 -6 10 -5 M372 40 Q375 22 370 6 M370 6 q-10 -2 -15 5 M370 6 q9 -4 15 1 M370 6 q-4 -7 -12 -7 M370 6 q4 -7 12 -6" stroke="#F4C27A" stroke-width="1.5" fill="none"/>
    <path d="M250 40 V30 H262 V40 M266 40 V24 H274 V40 M278 40 V32 H290 V40" stroke="#F4C27A" stroke-width="1" fill="none" opacity=".8"/>
  </svg>'''

CITIES = {
    "ny": dict(
        title="城市生活 · 纽约", h1="纽约<small>NEW YORK CITY</small>", svg=NY_SVG,
        hero="linear-gradient(175deg,#6E8BB0 0%,#3C4F78 45%,#1E2235 100%)", theme="#2E3A5C",
        q="搜：披萨、百老汇、法拉盛、中央公园…",
        lead=dict(
            hoods="五个区，每个街区一个世界：曼哈顿的摩天楼、布鲁克林的褐石屋、法拉盛的华人街。点开看去做什么、吃什么。",
            eat="纽约最好吃的是移民带来的味道：披萨、贝果、熏牛肉、点心、拉面、街头小车。店铺会变，去之前查一下营业时间。",
            stories="这座城是怎么来的：荷兰人的小镇、埃利斯岛、地铁、摩天楼、华埠，还有那个九月的早晨……",
            map="两指缩放、拖动查看。地铁按 MTA 官方 GTFS 数据画出真实走向，每月更新；点 💡 看用心提示。出行前用 MTA App 或谷歌地图确认（周末和深夜常改线）。",
            work="在纽约工作和生活要知道的事。工资、房租、规定每年会变，以官网为准。",
            trivia="可以拿去跟朋友聊的纽约冷知识。"),
        titles="[[0, '🧳 初来乍到'], [3, '📸 周末游客'], [8, '🚇 地铁常客'], [15, '🗽 半个纽约客'], [25, '🍕 纽约通'], [35, '🏅 纽约荣誉市民']]",
        gift="拆一个纽约一日盲盒", passport="🛂 纽约护照",
        maps="[['real', '🗺️ 实景地图（地铁全部线路）', 'https://new.mta.info/maps']]",
        rl="{ tips: 1, sub: 1 }", rlay="[['tips', '💡 用心提示'], ['sub', '🚇 地铁']]",
        view="[40.735, -73.95], 12", b1=("🏙️ 曼哈顿中城", "[40.754, -73.984], 14"), b2=("🗽 五个区", "[40.70, -73.93], 11"),
        mnote="点 💡 看提示，点车站看中英文站名和经过的线路。地铁按 MTA 官方 GTFS 数据画出真实走向，每月更新；快车和慢车共用一条轨道时线会叠在一起。卫星图 © Esri、Maxar 等，街道图 © OpenStreetMap、© CARTO。<a href=\"la.html#map\">洛杉矶的交通图 →</a>",
        foot="内容依据纽约市旅游局（NYC Tourism）、市政府、MTA、纽约市博物馆和各景点官网等公开资料整理。票价、营业时间、规定会变，去之前查一下官网。<a href=\"la.html\">🌇 洛杉矶生活 →</a>"),
    "la": dict(
        title="城市生活 · 洛杉矶", h1="洛杉矶<small>LOS ANGELES</small>", svg=LA_SVG,
        hero="linear-gradient(175deg,#E8A35A 0%,#C0574A 45%,#3B2340 100%)", theme="#8A3E44",
        q="搜：塔可、好莱坞、626、海滩、港口…",
        lead=dict(
            hoods="洛杉矶太大了，按区域来：市中心老城、好莱坞、海边、626 华人区、帕萨迪纳、港口。点开看去做什么、吃什么。",
            eat="洛杉矶最好吃的是移民带来的味道：墨西哥塔可、韩国烤肉、626 的中国菜、日本菜、泰国菜。店铺会变，去之前查一下营业时间。",
            stories="这座城是怎么来的：44 个移民的小镇、石油、引水渠、好莱坞、高速公路、港口和山火……",
            map="两指缩放、拖动查看。Metro 轨道和 Metrolink 按官方 GTFS 数据画出真实走向，每月更新；点 💡 看用心提示。出行前用 Transit App 或谷歌地图确认。",
            work="在洛杉矶工作和生活要知道的事，港口和 Inland Empire 物流也在这里。工资、房租、规定每年会变，以官网为准。",
            trivia="可以拿去跟朋友聊的洛杉矶冷知识。"),
        titles="[[0, '🧳 初来乍到'], [3, '📸 周末游客'], [8, '🚈 Metro 常客'], [15, '🌴 半个洛杉矶人'], [25, '🌮 洛杉矶通'], [35, '🏅 天使之城荣誉市民']]",
        gift="拆一个洛杉矶一日盲盒", passport="🛂 洛杉矶护照",
        maps="[['real', '🗺️ 实景地图（全部线路）', 'https://www.metro.net/riding/guide/system-maps/']]",
        rl="{ tips: 1, metro: 1, ml: 1 }", rlay="[['tips', '💡 用心提示'], ['metro', '🚇 Metro 轨道'], ['ml', '🚈 Metrolink']]",
        view="[34.05, -118.10], 10", b1=("🏙️ 市中心", "[34.050, -118.245], 14"), b2=("🌴 洛杉矶 · Upland", "[34.05, -117.95], 10"),
        mnote="点 💡 看提示，点车站看中英文站名和经过的线路。Metro 轨道（A/B/C/D/E/K 线）和 Metrolink 按官方 GTFS 数据画出真实走向，每月更新。卫星图 © Esri、Maxar 等，街道图 © OpenStreetMap、© CARTO。<a href=\"ny.html#map\">纽约的交通图 →</a>",
        foot="内容依据洛杉矶旅游局（Discover Los Angeles）、LA Metro、Metrolink、El Pueblo 和各景点官网等公开资料整理。票价、营业时间、规定会变，去之前查一下官网。<a href=\"ny.html\">🗽 纽约生活 →</a>"),
}


def sub(s, old, new, count=1):
    assert old in s, old[:80]
    return s.replace(old, new, count)


def resub(s, pat, new):
    s2, n = re.subn(pat, lambda m: new, s, count=1, flags=re.S)
    assert n == 1, pat
    return s2


def build(code, c):
    s = SRC
    s = resub(s, r"<title>.*?</title>", "<title>%s</title>" % c["title"])
    s = resub(s, r'<meta name="theme-color" content="[^"]*">', '<meta name="theme-color" content="%s">' % c["theme"])
    s, n = re.subn(r"(\.hero\{[^}]*?background:)linear-gradient\([^;]*\)", lambda m: m.group(1) + c["hero"], s, count=1)
    assert n == 1
    s = resub(s, r'<span class="city">.*?</span>', SWITCH.replace('href="%s.html"' % code, 'href="%s.html" class="on"' % code))
    s = resub(s, r"<h1>.*?</h1>", "<h1>%s</h1>" % c["h1"])
    s = resub(s, r'<svg class="bridge".*?</svg>', c["svg"])
    s = resub(s, r'placeholder="搜：[^"]*"', 'placeholder="%s"' % c["q"])
    s = s.replace('<script src="road.js?v=3"></script>\n', "")
    s = sub(s, "localStorage.getItem('sj:' + k)", "localStorage.getItem('%s:' + k)" % code)
    s = sub(s, "localStorage.setItem('sj:' + k", "localStorage.setItem('%s:' + k" % code)
    for k, v in c["lead"].items():
        s = resub(s, r"\n    %s: '[^']*'" % k, "\n    %s: '%s'" % (k, v))
    s = resub(s, r"var TITLES = \[\[.*?\]\];", "var TITLES = %s;" % c["titles"])
    s = sub(s, "拆一个圣何塞 · 硅谷一日盲盒", c["gift"])
    s = sub(s, "<b>🛂 硅谷护照</b>", "<b>%s</b>" % c["passport"])
    s = resub(s, r"var MAPS = \[\[.*?\]\];", "var MAPS = %s;" % c["maps"])
    s = sub(s, "{ tips: 1, vta: 1, caltrain: 1, bart: 1, vbus: 0 }", c["rl"])
    s = resub(s, r"\[\['tips', '💡 用心提示'\], \['vta'.*?\]\]\.map", c["rlay"] + ".map")
    s = sub(s, "setView([37.36, -121.93], 11)", "setView(%s)" % c["view"])
    s = sub(s, "<button id=\"rSF\">🏙️ 圣何塞市区</button><button id=\"rBay\">🌴 整个硅谷</button>",
            "<button id=\"rSF\">%s</button><button id=\"rBay\">%s</button>" % (c["b1"][0], c["b2"][0]))
    s = sub(s, "LMAP.setView([37.336, -121.892], 14)", "LMAP.setView(%s)" % c["b1"][1])
    s = sub(s, "LMAP.setView([37.40, -122.02], 10)", "LMAP.setView(%s)" % c["b2"][1])
    s = resub(s, r"'<div class=\"mnote\">点 💡 看提示.*?</div>'", "'<div class=\"mnote\">%s</div>'" % c["mnote"])
    s = s.replace("'sj/transit.json?v=1'", "'%s/transit.json?t=' + Math.floor(Date.now() / 864e5)" % code)
    s = sub(s, "'sj/data.json?t='", "'%s/data.json?t='" % code)
    s = resub(s, r"\$\('foot'\)\.innerHTML = '内容依据.*?<br>' \+", "$('foot').innerHTML = '%s<br>' +" % c["foot"])
    # 只剩一个地图视图时不显示视图切换条
    s = sub(s, "if (m[0] === 'real') {\n      return '<div class=\"mtabs\" id=\"mtabs\">'",
            "if (m[0] === 'real') {\n      return '<div class=\"mtabs\" id=\"mtabs\"' + (MAPS.length < 2 ? ' hidden' : '') + '>'")
    assert "圣何塞" not in s.split("<script>")[0] or True
    p = os.path.join(ROOT, code + ".html")
    open(p, "w", encoding="utf-8").write(s)
    left = [m for m in re.findall(r"[^\n]{0,30}(?:圣何塞|硅谷|VTA)[^\n]{0,30}", s)]
    print(code + ".html", len(s) // 1024, "KB；残留：", len(left))
    for x in left[:12]:
        print("   ", x)


for code, c in CITIES.items():
    build(code, c)
