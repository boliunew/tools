#!/usr/bin/env python3
"""旧金山交通示意图（SVG）→ sf/bart.svg、sf/muni.svg、sf/bus.svg。python3 scripts/build_sf_maps.py

BART：全部 50 个车站（含奥克兰机场接驳线）。
Muni Metro：Market St 地铁和中央地铁全部地下站 + 地面段主要站，叮当车三条线，F 线有轨电车。
巴士：十几条主要线路的大致走向（按经纬度画，示意，不是逐站）。
"""
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "sf")
FONT = "-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',Roboto,sans-serif"


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class SVG:
    def __init__(self, w, h, bg="#FBFAF7"):
        self.w, self.h, self.parts = w, h, []
        self.parts.append('<rect width="%d" height="%d" fill="%s"/>' % (w, h, bg))

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, size=13, anchor="start", weight=400, color="#222", rot=0, sub=None):
        tr = ' transform="rotate(%g %g %g)"' % (rot, x, y) if rot else ""
        t = '<text x="%g" y="%g" font-size="%g" text-anchor="%s" font-weight="%d" fill="%s"%s>%s</text>' % (x, y, size, anchor, weight, color, tr, esc(s))
        if sub:
            t += '<text x="%g" y="%g" font-size="%g" text-anchor="%s" fill="#777"%s>%s</text>' % (x, y + size * 1.05, size * 0.78, anchor, tr.replace(str(y), str(y + size * 1.05)) if rot else "", esc(sub))
        self.add(t)

    def save(self, name):
        s = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" font-family="%s">' % (self.w, self.h, self.w, self.h, FONT)
             + "".join(self.parts) + "</svg>")
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(s)
        return len(s)


def multiline(svg, pts, colors, width=5, gap=5.5):
    """Draw several parallel coloured lines along a polyline (each colour offset sideways)."""
    n = len(colors)
    for i, c in enumerate(colors):
        off = (i - (n - 1) / 2) * gap
        q = []
        for j, (x, y) in enumerate(pts):
            # average normal of adjacent segments
            nx = ny = 0
            for a, b in ((j - 1, j), (j, j + 1)):
                if 0 <= a and b < len(pts):
                    dx, dy = pts[b][0] - pts[a][0], pts[b][1] - pts[a][1]
                    L = math.hypot(dx, dy) or 1
                    nx += -dy / L
                    ny += dx / L
            L = math.hypot(nx, ny) or 1
            q.append((x + nx / L * off, y + ny / L * off))
        svg.add('<polyline points="%s" fill="none" stroke="%s" stroke-width="%g" stroke-linejoin="round" stroke-linecap="round"/>' % (
            " ".join("%.1f,%.1f" % p for p in q), c, width))


def station(svg, x, y, name, sub=None, side="right", r=6, size=13, transfer=False, rot=0, dx=12, dy=4):
    svg.add('<circle cx="%g" cy="%g" r="%g" fill="#fff" stroke="#222" stroke-width="%g"/>' % (x, y, r + (2 if transfer else 0), 2.5 if transfer else 2))
    if side == "right":
        svg.text(x + dx, y + dy, name, size, "start", 600 if transfer else 400, sub=sub)
    elif side == "left":
        svg.text(x - dx, y + dy, name, size, "end", 600 if transfer else 400, sub=sub)
    elif side == "up":
        svg.text(x + 4, y - 12, name, size, "start", 600 if transfer else 400, rot=rot or -40)
    elif side == "down":
        svg.text(x - 4, y + 22, name, size, "end", 600 if transfer else 400, rot=rot or -40)


# ================================================================ BART
Y, R, G, O, B, AIR = "#F2C500", "#E2231A", "#4DB848", "#F7941D", "#00AEEF", "#B5A27A"


def bart():
    s = SVG(1100, 1300)
    s.text(30, 44, "BART 湾区捷运 · 全部 50 站", 26, weight=700)
    s.text(30, 70, "示意图，不按比例。各线终点在晚上和周末可能不同，以 bart.gov 为准。", 13, color="#666")
    # coordinates
    E = (230, 600)
    sf = ["Embarcadero", "Montgomery St", "Powell St", "Civic Center/UN Plaza", "16th St Mission", "24th St Mission", "Glen Park", "Balboa Park", "Daly City", "Colma", "South San Francisco", "San Bruno"]
    sfz = ["内河码头 · 渡轮大厦", "蒙哥马利 · 金融区", "鲍威尔 · 联合广场 / 叮当车", "市政中心 · 市政厅", "16 街 · 米慎区", "24 街 · 米慎区", "格伦公园", "巴尔博亚公园", "戴利城", "科尔马", "南旧金山", "圣布鲁诺"]
    P = {}
    for i, n in enumerate(sf):
        P[n] = (E[0], E[1] + i * 46)
    P["SFO Airport"] = (150, P["San Bruno"][1] + 60)
    P["Millbrae"] = (E[0], P["San Bruno"][1] + 108)
    P["West Oakland"] = (440, 600)
    P["12th St/Oakland City Center"] = (540, 540)
    P["19th St/Oakland"] = (540, 490)
    P["MacArthur"] = (540, 440)
    rich = ["Ashby", "Downtown Berkeley", "North Berkeley", "El Cerrito Plaza", "El Cerrito del Norte", "Richmond"]
    for i, n in enumerate(rich):
        P[n] = (540, 390 - i * 46)
    ant = ["Rockridge", "Orinda", "Lafayette", "Walnut Creek", "Pleasant Hill/Contra Costa Centre", "Concord", "North Concord/Martinez", "Pittsburg/Bay Point", "Pittsburg Center", "Antioch"]
    for i, n in enumerate(ant):
        P[n] = (610 + i * 38, 440)
    P["Lake Merritt"] = (580, 660)
    sb = ["Fruitvale", "Coliseum", "San Leandro", "Bay Fair"]
    for i, n in enumerate(sb):
        P[n] = (625 + i * 45, 705 + i * 45)
    P["Oakland Airport (OAK)"] = (590, 810)
    dub = ["Castro Valley", "West Dublin/Pleasanton", "Dublin/Pleasanton"]
    for i, n in enumerate(dub):
        P[n] = (810 + i * 55, P["Bay Fair"][1])
    fre = ["Hayward", "South Hayward", "Union City", "Fremont", "Warm Springs/South Fremont", "Milpitas", "Berryessa/North San José"]
    for i, n in enumerate(fre):
        P[n] = (P["Bay Fair"][0], P["Bay Fair"][1] + 48 + i * 48)

    # water hint
    s.add('<path d="M330 120 C 300 420, 300 800, 330 1240 L 420 1240 C 460 900, 470 700, 470 640 C 470 560, 430 380, 470 120 Z" fill="#DCEBF3"/>')
    s.text(385, 980, "旧金山湾", 15, "middle", color="#7FA9C0", rot=-90)
    s.text(335, 578, "跨湾隧道 Transbay Tube", 11, "middle", color="#5D87A0")

    def L(names):
        return [P[n] for n in names]

    multiline(s, L(sf[8:] ) + [P["Millbrae"]], [Y, R])
    multiline(s, [P["San Bruno"], P["SFO Airport"]], [Y, R])
    multiline(s, L(sf[:9]), [Y, R, G, B])
    multiline(s, [E, P["West Oakland"]], [Y, R, G, B])
    multiline(s, [P["West Oakland"], P["12th St/Oakland City Center"]], [Y, R])
    multiline(s, [P["12th St/Oakland City Center"], P["19th St/Oakland"], P["MacArthur"]], [Y, R, O])
    multiline(s, L(["MacArthur"] + rich), [R, O])
    multiline(s, L(["MacArthur"] + ant), [Y])
    multiline(s, [P["12th St/Oakland City Center"], (552, 560), P["Lake Merritt"]], [O])
    multiline(s, [P["West Oakland"], P["Lake Merritt"]], [G, B])
    multiline(s, L(["Lake Merritt"] + sb), [O, G, B])
    multiline(s, L(["Bay Fair"] + dub), [B])
    multiline(s, L(["Bay Fair"] + fre), [O, G])
    s.add('<polyline points="%g,%g %g,%g" stroke="%s" stroke-width="5" stroke-dasharray="7 4" fill="none"/>' % (P["Coliseum"] + P["Oakland Airport (OAK)"] + (AIR,)))

    big = {"Embarcadero", "Montgomery St", "Powell St", "Civic Center/UN Plaza", "Balboa Park", "Daly City", "SFO Airport", "Millbrae", "West Oakland",
           "12th St/Oakland City Center", "19th St/Oakland", "MacArthur", "Lake Merritt", "Coliseum", "Bay Fair", "Downtown Berkeley", "Richmond", "Antioch", "Dublin/Pleasanton", "Berryessa/North San José"}
    for i, n in enumerate(sf):
        station(s, *P[n], n, sub=sfz[i], side="right" if n == "San Bruno" else "left", transfer=n in big)
    station(s, *P["SFO Airport"], "SFO Airport", sub="旧金山国际机场 ✈", side="left", transfer=True)
    station(s, *P["Millbrae"], "Millbrae", sub="密尔布雷 · 换乘 Caltrain", side="right", transfer=True)
    station(s, *P["West Oakland"], "West Oakland", sub="西奥克兰", side="left", transfer=True, dx=-6, dy=34)
    station(s, *P["12th St/Oakland City Center"], "12th St/Oakland City Center", sub="奥克兰市中心", side="left", transfer=True, dy=-4)
    station(s, *P["19th St/Oakland"], "19th St/Oakland", side="left", transfer=True)
    station(s, *P["MacArthur"], "MacArthur", side="left", transfer=True)
    zr = {"Downtown Berkeley": "伯克利市中心 · 加州大学", "Richmond": "列治文 · 换乘 Amtrak"}
    for n in rich:
        station(s, *P[n], n, sub=zr.get(n), side="left", transfer=n in big)
    for n in ant:
        station(s, *P[n], n, side="up", transfer=n in big)
    s.text(P["Antioch"][0] - 10, P["Antioch"][1] + 30, "→ 安提阿", 12, "end", color="#777")
    s.text(P["Walnut Creek"][0] - 10, P["Walnut Creek"][1] + 30, "核桃溪", 12, "middle", color="#777")
    station(s, *P["Lake Merritt"], "Lake Merritt", sub="梅里特湖 · 唐人街", side="left", transfer=True)
    zs = {"Fruitvale": "果谷", "Coliseum": "体育场 · 换乘 Amtrak", "San Leandro": "圣利安德罗", "Bay Fair": "湾景"}
    for n in sb:
        station(s, *P[n], n, sub=zs[n], side="right" if n != "Bay Fair" else "left", transfer=n in big, dx=10 if n != "Bay Fair" else 12, dy=-12 if n != "Bay Fair" else 4)
    station(s, *P["Oakland Airport (OAK)"], "Oakland Airport (OAK)", sub="奥克兰机场 ✈（接驳线）", side="left", transfer=True)
    for n in dub:
        station(s, *P[n], n, side="up", transfer=n in big)
    s.text(P["Dublin/Pleasanton"][0], P["Dublin/Pleasanton"][1] + 26, "都柏林", 12, "middle", color="#777")
    zf = {"Hayward": "海沃德", "Fremont": "弗里蒙特", "Milpitas": "米尔皮塔斯 · 换乘 VTA", "Berryessa/North San José": "北圣何塞"}
    for n in fre:
        station(s, *P[n], n, sub=zf.get(n), side="right", transfer=n in big)

    # legend
    lg = [(Y, "黄线  Antioch ⇄ SFO / Millbrae"), (R, "红线  Richmond ⇄ SFO / Millbrae"), (G, "绿线  Berryessa ⇄ Daly City"),
          (O, "橙线  Richmond ⇄ Berryessa"), (B, "蓝线  Dublin/Pleasanton ⇄ Daly City"), (AIR, "机场线  Coliseum ⇄ 奥克兰机场")]
    x0, y0 = 50, 150
    s.add('<rect x="%d" y="%d" width="340" height="%d" rx="12" fill="#fff" stroke="#ddd"/>' % (x0 - 20, y0 - 30, 30 * len(lg) + 50))
    s.text(x0, y0 - 6, "线路", 14, weight=700)
    for i, (c, t) in enumerate(lg):
        yy = y0 + 22 + i * 30
        s.add('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="6" stroke-linecap="round"%s/>' % (x0, yy - 4, x0 + 30, yy - 4, c, ' stroke-dasharray="7 4"' if c == AIR else ""))
        s.text(x0 + 42, yy, t, 13)
    s.text(30, 1285, "粗圈 = 换乘站或主要站。旧金山市内的 8 个站（Embarcadero 到 Balboa Park）有 4 条线经过，班次最密。", 12, color="#666")
    return s.save("bart.svg")


# ================================================================ Muni Metro + 叮当车 + F 线
J, K, LL, M, N, T, F, CC = "#E0A100", "#5DA9DD", "#8E4F9C", "#0A8F5A", "#1D4E89", "#C8102E", "#D35400", "#7A4B2A"


def muni():
    s = SVG(1100, 900)
    s.text(30, 44, "Muni Metro 轻轨 · 叮当车 · F 线有轨电车", 26, weight=700)
    s.text(30, 70, "示意图。地下站全部标出，地面段只标主要站（地面段每隔几个路口就有一站）。线路有时调整，以 sfmta.com 为准。", 13, color="#666")
    y0 = 470
    sub = [("West Portal", "西门户"), ("Forest Hill", "森林山"), ("Castro", "卡斯特罗"), ("Church", "教堂街"), ("Van Ness", "范尼斯"),
           ("Civic Center", "市政中心"), ("Powell", "鲍威尔"), ("Montgomery", "蒙哥马利"), ("Embarcadero", "内河码头")]
    P = {n: (170 + i * 72, y0) for i, (n, _) in enumerate(sub)}
    # Market St subway box
    s.add('<rect x="%d" y="%d" width="%d" height="66" rx="33" fill="#EEF2F6" stroke="#C9D3DD"/>' % (140, y0 - 33, P["Embarcadero"][0] - 140 + 30))
    s.text(30, 92, "灰色长条 = Market St 地铁隧道，Civic Center 到 Embarcadero 四个站和 BART 共用（BART 在下层）。", 13, color="#666")
    # N Judah west
    nw = [("Duboce & Church", ""), ("Carl & Cole", "科尔谷"), ("UCSF / 9th Ave", "内日落区 · 金门公园"), ("Sunset Blvd", ""), ("Ocean Beach", "海洋海滩")]
    PN = [(P["Church"][0], 360)] + [(P["Church"][0] - 70 - i * 70, 330) for i in range(4)]
    PN = [(P["Church"][0], 380), (300, 330), (230, 330), (160, 330), (90, 330)]
    multiline(s, [P["Church"], (P["Church"][0], 400)] + PN, [N])
    # N east to Caltrain
    ne = [("Folsom", ""), ("Brannan", ""), ("2nd & King", "甲骨文球场（巨人队）"), ("4th & King", "Caltrain 火车站")]
    PE = [(840, 540), (890, 580), (940, 620), (990, 660)]
    multiline(s, [P["Embarcadero"], (800, 500)] + PE, [N])
    # J Church south
    PJ = [(P["Church"][0], 560), (P["Church"][0], 610), (P["Church"][0], 660), (P["Church"][0], 715), (P["Church"][0], 790)]
    multiline(s, [P["Church"]] + PJ, [J])
    # K / M / L west
    WP = P["West Portal"]
    SFC = (WP[0], 560)
    multiline(s, [WP, SFC], [K, M])
    PK = [(250, 640), (310, 720), PJ[-1]]
    multiline(s, [SFC] + PK, [K])
    PM = [(90, 620), (90, 680), (90, 740), (200, 820), PJ[-1]]
    multiline(s, [SFC] + PM, [M])
    PL = [(90, y0), (40, y0 + 40)]
    multiline(s, [WP, (100, y0)] + [(40, y0)], [LL])
    # subway trunk lines
    multiline(s, [WP, P["Church"]], [K, LL, M])
    multiline(s, [P["Church"], P["Embarcadero"]], [J, K, LL, M, N])
    # T Third / Central Subway
    tx = 1040
    PT = [(tx, 150), (tx, 215), (tx, 280), (tx, 345)]
    tn = [("Chinatown–Rose Pak", "唐人街（中央地铁）"), ("Union Square/Market St", "联合广场 · 地下通道连 Powell 站"), ("Yerba Buena/Moscone", "芳草地 · 莫斯康会展中心"), ("4th & Brannan", "")]
    PT2 = [(tx, 410), (990, 660), (990, 720), (990, 780), (990, 850)]
    multiline(s, PT + [(tx, 600), (990, 660)], [T])
    multiline(s, [(990, 660), (990, 850)], [T])
    # F line along Market and Embarcadero to Wharf
    fy = y0 - 50
    FB, P39, FW = (P["Embarcadero"][0] + 30, 300), (820, 200), (730, 200)
    s.add('<polyline points="%g,%g %g,%g %g,%g %g,%g %g,%g" fill="none" stroke="%s" stroke-width="5" stroke-dasharray="10 5" stroke-linecap="round"/>' % (
        P["Castro"][0], fy, FB[0], fy, FB[0], FB[1], P39[0], P39[1], FW[0], FW[1], F))
    # cable cars
    pm = (P["Powell"][0], y0 - 33)
    s.add('<polyline points="%g,%g %g,%g %g,%g %g,%g" fill="none" stroke="%s" stroke-width="5" stroke-linecap="round"/>' % (pm[0], pm[1], pm[0], 300, 540, 200, 500, 140, CC))
    s.add('<polyline points="%g,%g %g,%g %g,%g" fill="none" stroke="%s" stroke-width="5" stroke-linecap="round"/>' % (pm[0] + 7, pm[1], pm[0] + 7, 300, 660, 140, CC))
    s.add('<polyline points="%g,%g %g,%g" fill="none" stroke="%s" stroke-width="5" stroke-linecap="round"/>' % (450, 250, 760, 250, CC))

    # stations
    for i, (n, z) in enumerate(sub):
        station(s, *P[n], n, side="down", transfer=True, rot=-35)
    for (x, y), (n, z) in zip(PN, nw):
        station(s, x, y, n, sub=z or None, side="up" if n != "Duboce & Church" else "right")
    for (x, y), (n, z) in zip(PE, ne):
        station(s, x, y, n, sub=z or None, side="left", transfer=n == "4th & King")
    jn = [("Church & 18th", "多洛雷斯公园"), ("Church & 24th", "诺伊谷"), ("30th St", ""), ("Glen Park", "近 Glen Park BART"), ("Balboa Park", "换乘 BART")]
    for (x, y), (n, z) in zip(PJ, jn):
        station(s, x, y, n, sub=z or None, side="right", transfer=n == "Balboa Park")
    station(s, *SFC, "St Francis Circle", side="right")
    station(s, *PK[0], "Ocean Ave", sub="K 线沿 Ocean Ave", side="right")
    station(s, *PK[1], "City College", sub="城市学院", side="left")
    for (x, y), (n, z) in zip(PM[:3], [("Stonestown", "购物中心"), ("SF State", "旧金山州立大学"), ("Broad & Plymouth", "")]):
        station(s, x, y, n, sub=z or None, side="right")
    station(s, 40, y0, "SF Zoo", sub="动物园（L 线沿 Taraval St）", side="up", rot=-35)
    for (x, y), (n, z) in zip(PT, tn):
        station(s, x, y, n, sub=z or None, side="left", transfer=True)
    for (x, y), (n, z) in zip(PT2[2:], [("UCSF / Chase Center", "勇士队球馆"), ("20th St", "狗镇 Dogpatch"), ("Sunnydale", "T 线南端（沿 3rd St 经湾景区）")]):
        station(s, x, y, n, sub=z, side="left")
    # F / cable car labels
    s.text(P["Van Ness"][0] + 10, fy - 14, "F 线（地面，沿 Market St）：Castro ⇄ 渔人码头", 12, weight=600, color=F)
    station(s, *FW, "Fisherman's Wharf", sub="渔人码头 · F 线终点", side="left", r=5)
    station(s, *FB, "Ferry Building", sub="渡轮大厦", side="right", r=5)
    station(s, *P39, "Pier 39", sub="海狮", side="right", r=5)
    station(s, 500, 140, "Hyde & Beach", sub="Powell-Hyde 终点 · 途经九曲花街", side="left", r=5)
    station(s, 660, 140, "Taylor & Bay", sub="Powell-Mason 终点", side="left", r=5)
    station(s, 450, 250, "Van Ness", sub="California 线西端", side="left", r=5)
    station(s, 760, 250, "Drumm St", sub="California 线东端", side="right", r=5)
    s.text(pm[0] + 14, 385, "Powell & Market 叮当车起点", 12, weight=600, color=CC)
    s.text(530, 270, "California 线（经唐人街、诺布山）", 11.5, "middle", color=CC)

    lg = [(J, "J Church：Balboa Park ⇄ Embarcadero"), (K, "K Ingleside：Balboa Park ⇄ 市中心"), (LL, "L Taraval：动物园 ⇄ 市中心"),
          (M, "M Ocean View：Balboa Park ⇄ 市中心"), (N, "N Judah：海洋海滩 ⇄ Caltrain 4th & King"), (T, "T Third：唐人街 ⇄ Sunnydale"),
          (F, "F 线复古有轨电车（地面）"), (CC, "叮当车 3 条线")]
    x0, yl = 30, 600
    s.add('<rect x="%d" y="%d" width="0" height="0"/>' % (x0, yl))
    bx, by = 506, 610
    s.add('<rect x="%d" y="%d" width="320" height="%d" rx="12" fill="#fff" stroke="#ddd"/>' % (bx - 16, by - 28, 24 * len(lg) + 44))
    s.text(bx, by - 6, "线路", 14, weight=700)
    for i, (c, t) in enumerate(lg):
        yy = by + 18 + i * 24
        s.add('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="6" stroke-linecap="round"%s/>' % (bx, yy - 4, bx + 26, yy - 4, c, ' stroke-dasharray="8 4"' if c == F else ""))
        s.text(bx + 36, yy, t, 12.5)
    return s.save("muni.svg")


# ================================================================ 主要巴士（按经纬度）
def bus():
    k = 7600
    lat0, lon0 = 37.815, -122.522
    cosl = math.cos(math.radians(37.76))

    def p(lon, lat):
        return ((lon - lon0) * k * cosl + 30, (lat0 - lat) * k + 110)

    W, H = int(p(-122.355, 0)[0]) + 30, int(p(0, 37.700)[1]) + 140
    s = SVG(W, H, bg="#DCEBF3")
    coast = [(-122.514, 37.708), (-122.509, 37.735), (-122.511, 37.760), (-122.512, 37.776), (-122.507, 37.786), (-122.494, 37.789),
             (-122.484, 37.791), (-122.479, 37.808), (-122.466, 37.806), (-122.447, 37.807), (-122.431, 37.808), (-122.421, 37.809),
             (-122.411, 37.810), (-122.405, 37.809), (-122.399, 37.803), (-122.393, 37.794), (-122.388, 37.785), (-122.386, 37.770),
             (-122.383, 37.756), (-122.370, 37.742), (-122.359, 37.729), (-122.375, 37.720), (-122.383, 37.711), (-122.390, 37.708)]
    s.add('<polygon points="%s" fill="#F6F4EE" stroke="#B9C7D0" stroke-width="2"/>' % " ".join("%.1f,%.1f" % p(*c) for c in coast))
    # Golden Gate Park & Presidio
    a, b = p(-122.511, 37.774), p(-122.453, 37.765)
    s.add('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#CFE5C4"/>' % (a[0], a[1], b[0] - a[0], b[1] - a[1]))
    s.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 5, "金门公园", 14, "middle", color="#5E8B52")
    pr = [(-122.484, 37.791), (-122.479, 37.807), (-122.447, 37.806), (-122.447, 37.788), (-122.484, 37.786)]
    s.add('<polygon points="%s" fill="#D8E9CF"/>' % " ".join("%.1f,%.1f" % p(*c) for c in pr))
    s.text(*p(-122.467, 37.797), "Presidio 要塞", 13, "middle", color="#5E8B52")
    # Golden Gate Bridge
    g1, g2 = p(-122.478, 37.808), p(-122.478, 37.832)
    s.add('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#D2452F" stroke-width="5"/>' % (g1 + g2[:1] + (g1[1] - 90,)))
    s.text(g1[0] + 10, g1[1] - 60, "金门大桥", 13, color="#C0362C", weight=600)
    # Market St axis
    ms = [p(-122.395, 37.794), p(-122.417, 37.779), p(-122.435, 37.764)]
    s.add('<polyline points="%s" fill="none" stroke="#9AA4AE" stroke-width="7" stroke-linecap="round"/>' % " ".join("%.1f,%.1f" % x for x in ms))
    s.text(*p(-122.408, 37.784), "Market St", 12, color="#6B7580", rot=-38)

    routes = [  # (no, colour, name, [(lon,lat)...], label position index, desc)
        ("38", "#C0392B", "Geary", [(-122.396, 37.789), (-122.407, 37.787), (-122.447, 37.783), (-122.493, 37.780), (-122.509, 37.780)], "市中心 ⇄ 列治文区海边，最繁忙的巴士线（有 38R 快线）"),
        ("1", "#2E86C1", "California", [(-122.397, 37.795), (-122.433, 37.790), (-122.447, 37.788), (-122.493, 37.784)], "金融区 ⇄ 唐人街 ⇄ 列治文区"),
        ("5", "#16A085", "Fulton", [(-122.396, 37.789), (-122.418, 37.780), (-122.447, 37.776), (-122.510, 37.773)], "市中心 ⇄ 沿金门公园北边 ⇄ 海洋海滩（有 5R）"),
        ("7", "#8E44AD", "Haight-Noriega", [(-122.396, 37.791), (-122.418, 37.776), (-122.433, 37.771), (-122.453, 37.769), (-122.470, 37.762), (-122.507, 37.754)], "市中心 ⇄ 海特街 ⇄ 日落区海边"),
        ("14", "#D35400", "Mission", [(-122.396, 37.789), (-122.413, 37.776), (-122.419, 37.765), (-122.418, 37.749), (-122.433, 37.724), (-122.448, 37.706)], "市中心 ⇄ 米慎区 ⇄ 戴利城（有 14R）"),
        ("22", "#27AE60", "Fillmore", [(-122.436, 37.801), (-122.433, 37.785), (-122.432, 37.770), (-122.420, 37.765), (-122.391, 37.766)], "码头区 ⇄ 菲尔莫尔街 ⇄ 16 街 ⇄ 教会湾"),
        ("30", "#F39C12", "Stockton", [(-122.395, 37.777), (-122.406, 37.786), (-122.407, 37.796), (-122.410, 37.803), (-122.441, 37.802)], "Caltrain ⇄ 唐人街 ⇄ 北滩 ⇄ 码头区"),
        ("8", "#7F8C8D", "Bayshore", [(-122.416, 37.806), (-122.405, 37.795), (-122.403, 37.784), (-122.405, 37.760), (-122.402, 37.735), (-122.404, 37.711)], "渔人码头 ⇄ 唐人街 ⇄ 南边的访谷区"),
        ("28", "#1F618D", "19th Ave", [(-122.430, 37.805), (-122.449, 37.800), (-122.476, 37.805), (-122.477, 37.785), (-122.476, 37.745), (-122.475, 37.722), (-122.469, 37.706)], "金门大桥收费站 ⇄ 19 大道 ⇄ 戴利城 BART"),
        ("49", "#A04000", "Van Ness-Mission", [(-122.424, 37.806), (-122.424, 37.775), (-122.419, 37.765), (-122.418, 37.749), (-122.440, 37.728), (-122.452, 37.722)], "Fort Mason ⇄ 范尼斯大道 ⇄ 米慎区 ⇄ 城市学院"),
        ("29", "#B7950B", "Sunset", [(-122.477, 37.796), (-122.494, 37.776), (-122.494, 37.745), (-122.482, 37.727), (-122.448, 37.722), (-122.395, 37.722)], "要塞 ⇄ 日落大道 ⇄ 巴尔博亚公园 ⇄ 湾景区"),
        ("24", "#5D6D7E", "Divisadero", [(-122.441, 37.791), (-122.439, 37.770), (-122.435, 37.755), (-122.420, 37.751)], "太平洋高地 ⇄ 迪维萨德罗街 ⇄ 诺伊谷"),
    ]
    for no, c, nm, pts, desc in routes:
        q = [p(*x) for x in pts]
        s.add('<polyline points="%s" fill="none" stroke="#fff" stroke-width="9" stroke-linejoin="round" stroke-linecap="round"/>' % " ".join("%.1f,%.1f" % x for x in q))
        s.add('<polyline points="%s" fill="none" stroke="%s" stroke-width="5" stroke-linejoin="round" stroke-linecap="round" opacity=".92"/>' % (" ".join("%.1f,%.1f" % x for x in q), c))
        for end in ((q[-1],) if no in ("38", "5", "7", "14") else (q[0], q[-1])):
            s.add('<circle cx="%.1f" cy="%.1f" r="12" fill="%s" stroke="#fff" stroke-width="2"/>' % (end[0], end[1], c))
            s.add('<text x="%.1f" y="%.1f" font-size="11" font-weight="700" fill="#fff" text-anchor="middle">%s</text>' % (end[0], end[1] + 4, no))
    # landmarks
    for lon, lat, t in [(-122.4075, 37.788, "联合广场"), (-122.406, 37.794, "唐人街"), (-122.415, 37.808, "渔人码头"), (-122.394, 37.796, "渡轮大厦"),
                        (-122.419, 37.759, "米慎区"), (-122.435, 37.761, "卡斯特罗"), (-122.447, 37.770, "海特街"), (-122.4895, 37.783, "列治文区"),
                        (-122.490, 37.752, "日落区"), (-122.392, 37.778, "甲骨文球场"), (-122.447, 37.721, "Balboa Park BART"), (-122.3965, 37.7895, "Salesforce 公交中心")]:
        x, y = p(lon, lat)
        s.add('<circle cx="%.1f" cy="%.1f" r="3" fill="#333"/>' % (x, y))
        s.text(x + 6, y - 5, t, 12.5, weight=600, color="#333")
    s.text(*p(-122.519, 37.740), "太平洋", 16, color="#7FA9C0", rot=-90)
    s.text(*p(-122.372, 37.790), "旧金山湾", 15, color="#7FA9C0")
    s.text(30, 40, "Muni 主要巴士线路 · 大致走向", 26, weight=700)
    s.text(30, 66, "按真实地理画的示意图，只画主线，不是逐站。圆圈里的数字是线路号，标在终点；38、5、7、14 路的另一头都在市中心 Salesforce 公交中心附近。", 13, color="#555")
    # list
    y = H - 120
    s.add('<rect x="20" y="%d" width="%d" height="112" rx="12" fill="#fff" opacity=".95"/>' % (y - 8, W - 40))
    for i, (no, c, nm, pts, desc) in enumerate(routes):
        col, row = i % 2, i // 2
        xx, yy = 36 + col * (W - 60) / 2, y + 12 + row * 17
        s.add('<rect x="%.1f" y="%.1f" width="26" height="14" rx="4" fill="%s"/>' % (xx, yy - 11, c))
        s.add('<text x="%.1f" y="%.1f" font-size="10.5" font-weight="700" fill="#fff" text-anchor="middle">%s</text>' % (xx + 13, yy, no))
        s.text(xx + 32, yy, "%s · %s" % (nm, desc), 11)
    return s.save("bus.svg")


def main():
    os.makedirs(OUT, exist_ok=True)
    print("bart.svg %d B · muni.svg %d B · bus.svg %d B" % (bart(), muni(), bus()))


if __name__ == "__main__":
    main()
