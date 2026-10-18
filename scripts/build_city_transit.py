#!/usr/bin/env python3
"""🗺️ 城市实景交通图（纽约、洛杉矶）→ ny/transit.json、la/transit.json（ny.html、la.html 用）

线路走向和车站来自各家官方公开的 GTFS（通过 Mobility Database 公开目录找下载地址，失败时用备用地址）：
  · 纽约：MTA 地铁（含斯塔滕岛铁路）
  · 洛杉矶：LA Metro 轨道（A/B/C/D/E/K 线）、Metrolink 通勤火车
车站按 GTFS 的母站（parent_station）合并——纽约有好几个「86 St」，不能按名字合。
💡 用心提示在下面 TIPS 里手写。只用标准库。
  python3 scripts/build_city_transit.py [ny|la]
"""
import csv
import io
import json
import os
import re
import sys
import time
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "boliunew-tools-city/1.0 (https://github.com/boliunew/tools)"
CATALOG = "https://share.mobilitydata.org/catalogs-csv"

TIPS = {
    "ny": [
        (40.7553, -73.9868, "🎭", "时代广场", "最热闹也最游客的地方。扮成卡通人物、自由女神的人主动拉你合影，拍完就要钱；「送你一张 CD」的也一样，直接走开。百老汇剧院都在附近，TKTS 红色台阶下面卖当天打折票。", 1),
        (40.7527, -73.9772, "🌌", "中央车站（Grand Central）", "1913 年的车站大厅，天花板上的星座是画反了的。地下美食街的生蚝吧很有名；大厅一角的「耳语回廊」：站在对角说悄悄话，对面听得清清楚楚。", 0),
        (40.7506, -73.9935, "🚉", "宾州车站 / 莫伊尼汉大厅", "Amtrak、长岛铁路、新泽西捷运都在这里。新的莫伊尼汉大厅在马路对面，宽敞明亮，等车去那边。人很多，看好行李。", 0),
        (40.7013, -74.0130, "⛴️", "斯塔滕岛渡轮：免费看自由女神", "曼哈顿南端 Whitehall 码头，24 小时运行、完全免费，25 分钟单程，船从自由女神像旁边开过。往南坐船右边，回程坐左边。到对岸不用下船就能坐回来（要下船再上）。", 0),
        (40.7033, -74.0170, "🗽", "去自由女神像和埃利斯岛", "唯一的官方渡轮从炮台公园出发（Statue City Cruises），一定在官网买票，周边拉客卖「船票」的多半是普通游船。想上皇冠要提前几个月订。", 0),
        (40.7115, -74.0134, "🕊️", "9/11 纪念池", "两个巨大的方形瀑布池在原来双子塔的位置，免费，四周刻着遇难者的名字。旁边的博物馆要买票。", 0),
        (40.7114, -74.0110, "🕊️", "Oculus 车站", "像白色鸟骨架的世贸中心交通枢纽，免费进去看，连着地铁和去新泽西的 PATH 火车。", 0),
        (40.7116, -74.0047, "🌉", "布鲁克林大桥步行", "从曼哈顿这头走到布鲁克林，大约 1.1 英里、半小时。早上 8 点前或傍晚人少；别站进自行车道，会被骂。", 0),
        (40.7033, -73.9894, "📸", "DUMBO 网红机位", "Washington St 和 Water St 路口，从两栋红砖楼中间看曼哈顿大桥，帝国大厦正好在桥洞里。旁边是布鲁克林大桥公园和旋转木马。", 0),
        (40.6967, -73.9973, "🌇", "布鲁克林高地长廊", "安静的高地步道，正对曼哈顿下城天际线，看日落和夜景的好地方。", 0),
        (40.7740, -73.9708, "⛲", "中央公园 Bethesda 喷泉", "公园的心脏，旁边是湖，可以租船；往北走是 Bow Bridge。公园很大，坐地铁到不同的边进去。", 0),
        (40.7794, -73.9632, "🏛️", "大都会博物馆", "纽约州居民可以按自愿付费入场，外州游客按标准票价。一天看不完，先挑埃及馆（丹铎神庙）和屋顶花园。", 0),
        (40.7813, -73.9740, "🦖", "自然历史博物馆", "恐龙化石大厅和蓝鲸模型，《博物馆奇妙夜》就是在这里。", 0),
        (40.7398, -74.0080, "🌿", "High Line 空中公园", "旧高架货运铁路改成的步道，从肉库区一路走到哈德逊城，免费。南头是惠特尼美术馆，中间有切尔西市场。", 0),
        (40.7424, -74.0060, "🦞", "切尔西市场", "老饼干厂（奥利奥的诞生地）改成的美食市场，龙虾、塔可、甜点，雨天好去处。", 0),
        (40.7538, -74.0021, "🏙️", "哈德逊城 / Edge 观景台", "新开发区，Edge 是悬在半空的玻璃地板观景台。", 0),
        (40.7484, -73.9857, "🏢", "帝国大厦", "1931 年的老牌摩天楼，86 层露天观景台。想拍帝国大厦本身，去洛克菲勒中心顶楼（Top of the Rock）看它更好。", 0),
        (40.7593, -73.9794, "🎄", "洛克菲勒中心", "冬天的大圣诞树和溜冰场；顶楼 Top of the Rock 观景台能拍到帝国大厦和中央公园。", 0),
        (40.7536, -73.9832, "🚻", "布莱恩特公园：最干净的公厕", "纽约公厕很少，这里的公厕干净、有人打理。冬天有免费溜冰场，夏天有露天电影。旁边是纽约公共图书馆（门口两只石狮子）。", 0),
        (40.7158, -73.9970, "🥟", "曼哈顿华埠", "Mott St、Mosco St 一带：点心、烧腊、几块钱一盘的煎饺。往北过 Canal St 就是小意大利。", 0),
        (40.7596, -73.8303, "🏮", "法拉盛：纽约最大的华人区", "7 号线坐到底 Flushing-Main St。新世界商场、金城商场的美食广场，各地中国菜都有，比曼哈顿华埠更「国内」。", 0),
        (40.7612, -73.9644, "🚡", "罗斯福岛缆车", "刷地铁的卡（OMNY）就能坐，在东河上空看中城天际线，单程几分钟，价格和坐一次地铁一样。", 0),
        (40.7308, -73.9973, "🎷", "华盛顿广场", "格林威治村的中心，大理石拱门、街头艺人。附近的老爵士俱乐部（Village Vanguard 等）晚上去听现场。", 0),
        (40.8100, -73.9500, "🎤", "哈莱姆 Apollo 剧院", "周三晚上的「业余之夜」很有名。周日上午可以去黑人教堂听福音合唱（安静坐后排，尊重礼拜）。", 0),
        (40.5755, -73.9707, "🎢", "科尼岛", "海滩、木栈道、1927 年的木头过山车 Cyclone、Nathan's 热狗（1916 年开张）。D/F/N/Q 线都到终点站。", 0),
        (40.8296, -73.9262, "⚾", "洋基体育场", "4/B/D 线直达 161 St–Yankee Stadium。", 0),
        (40.7571, -73.8458, "⚾", "大都会队 Citi Field", "7 号线 Mets–Willets Point 站；旁边就是举办美网的法拉盛草原公园。", 0),
        (40.7145, -73.9681, "🍔", "威廉斯堡", "布鲁克林的文青区：Domino 公园看曼哈顿天际线，周末（暖和的季节）有 Smorgasburg 露天美食市集。L 线到 Bedford Av。", 0),
        (40.6996, -73.8085, "✈️", "JFK 机场怎么进城", "AirTrain 到 Jamaica 站换地铁 E 线或长岛铁路（LIRR），比打车便宜很多。AirTrain 出站时单独收费。黄色出租车从 JFK 到曼哈顿是固定价（另加过路费和小费）。", 0),
        (40.7769, -73.8740, "🚌", "拉瓜迪亚机场：免费大巴", "Q70「LaGuardia Link」巴士免费，接到地铁 7 号线和 E/F/M/R 线的 Jackson Hts 站。", 0),
        (40.7484, -73.9930, "⚠️", "地铁晚上坐中间车厢", "深夜人少时，坐列车中间、有列车员（conductor）的那节车厢；站台上找黄色「Off-Hours Waiting Area」标志等车。", 1),
    ],
    "la": [
        (34.0562, -118.2365, "🚉", "联合车站（Union Station）", "1939 年建成的「最后一座大火车站」，大厅很美。Amtrak、Metrolink（从 Upland 来就到这里）、地铁 A/B/D 线、去 LAX 的 FlyAway 大巴都在这里。", 0),
        (34.0575, -118.2378, "🌮", "Olvera Street：洛杉矶出生的地方", "1781 年建城的老广场就在这里，墨西哥市场、塔可、吉他手，城里最老的房子 Avila Adobe 免费参观。", 0),
        (34.0623, -118.2383, "🏮", "老唐人街", "1938 年建的「新唐人街」，中央广场的牌楼和灯笼。现在有很多新开的咖啡馆和小店，A 线 Chinatown 站。", 0),
        (34.0508, -118.2490, "🍜", "Grand Central Market", "1917 年开到现在的室内市场，几十家摊位：塔可、拉面、蛋堡、披萨。对面就是 Angels Flight。", 0),
        (34.0515, -118.2500, "🚃", "Angels Flight：世界最短的铁路", "1901 年的小缆车，只有 298 英尺长，坐一次几十美分到一美元多（刷 TAP 有折扣）。《爱乐之城》里出现过。", 0),
        (34.0553, -118.2498, "🎵", "迪士尼音乐厅 + The Broad", "盖瑞设计的不锈钢音乐厅，外面的楼梯和屋顶花园免费逛；隔壁 The Broad 当代美术馆免费，但要提前在官网预约。", 0),
        (34.0500, -118.2400, "🍣", "小东京", "日式拉面、寿司、和果子，日裔美国人国家博物馆。8 月有日系文化节 Nisei Week。", 0),
        (34.0430, -118.2440, "⚠️", "Skid Row 一带", "市中心东南边几条街是无家可归者聚集区，白天开车经过就好，别步行穿过，晚上尤其要绕开。", 1),
        (34.1017, -118.3387, "⭐", "好莱坞星光大道", "两千多颗星从 Hollywood/Highland 一路往两边铺。TCL 中国剧院门口有明星手印脚印。街上扮超级英雄合影的人会要钱。B 线 Hollywood/Highland 站。", 1),
        (34.1184, -118.3004, "🔭", "格里菲斯天文台", "免费入场，看好莱坞标志、市中心天际线和日落最好的地方。周末停车很难，坐 DASH Observatory 小巴（便宜）上山。", 0),
        (34.1281, -118.3290, "🅷", "好莱坞标志机位", "Lake Hollywood Park 是离标志最近的合法观景点。不能走到字母跟前，被抓会罚款。", 0),
        (34.0630, -118.3593, "💡", "LACMA「城市之光」", "202 盏老路灯排成的装置艺术，在美术馆门口，24 小时免费看，晚上灯亮最美。旁边是拉布雷亚沥青坑，冰河时期的猛犸象化石。", 0),
        (34.0780, -118.4741, "🏛️", "盖蒂中心", "山顶上的美术馆，免费入场（停车收费），坐白色小火车上山。花园和俯瞰全城的景色比展品还出名。", 0),
        (34.0094, -118.4973, "🎡", "圣莫尼卡码头", "66 号公路的终点牌子就在码头上，摩天轮、海滩。E 线坐到终点 Downtown Santa Monica 站，走几分钟就到。", 0),
        (33.9850, -118.4695, "🛹", "威尼斯海滩", "木板路、肌肉海滩、滑板公园、涂鸦墙。往南几个街口是安静的威尼斯运河。晚上人少后别在木板路一带久留。", 0),
        (34.0618, -118.3089, "🥩", "韩国城", "韩国烤肉、豆腐汤、KTV，很多营业到深夜。D 线 Wilshire/Western 站。", 0),
        (34.0739, -118.2400, "⚾", "道奇体育场", "比赛日从联合车站坐 Dodger Stadium Express 专线巴士上山，比自己开车停车省事多了。", 0),
        (34.1458, -118.1500, "🌹", "帕萨迪纳老城", "老砖楼里的餐厅和店，1 月 1 日的玫瑰花车游行就走这条 Colorado Blvd。A 线 Memorial Park 站。", 0),
        (34.1290, -118.1145, "🌸", "亨廷顿图书馆和花园", "流芳园是中国以外最大的中式园林之一，还有日式花园、沙漠植物园。每月第一个周四免费，要提前预约。", 0),
        (34.1400, -118.0450, "🍢", "626 夜市", "夏天几个周末在阿卡迪亚的圣塔安妮塔赛马场举办，台式小吃、烤串、奶茶，人山人海。日期以官网为准。", 0),
        (34.0966, -118.1064, "🥟", "圣盖博谷（626）", "Alhambra、San Gabriel、Arcadia、Rowland Heights 一带是全美最大的华人聚居区之一，川湘、上海、台湾、港式茶餐厅应有尽有。鼎泰丰在美国的第一家店就开在阿卡迪亚。", 0),
        (33.7529, -118.1903, "🚢", "长滩：玛丽皇后号", "1936 年的远洋邮轮，现在是酒店和博物馆。旁边是太平洋水族馆。A 线南端终点就是长滩市中心。", 0),
        (33.7490, -118.2715, "🏗️", "洛杉矶港 / 长滩港", "美国最繁忙的集装箱港口群，从文森特·托马斯大桥和 San Pedro 海边能看到一排排吊机和集装箱船——这些柜很多最后会到 Inland Empire 的仓库。", 0),
        (33.9416, -118.4085, "✈️", "LAX：打车和网约车", "Uber、Lyft 和出租车都在「LAX-it」接客区上车，从航站楼坐免费的绿色接驳车过去。去市中心可以坐 FlyAway 大巴到联合车站。", 0),
        (34.0383, -118.8747, "🏖️", "马里布 El Matador 海滩", "PCH 1 号公路边的小海滩，礁石拱门，日落很美。停车位很少，下去的台阶陡。离岸流危险，别随便下水。", 0),
        (34.1122, -118.3391, "🎶", "好莱坞露天剧场", "夏天的露天音乐会，可以自带野餐。散场时交通很堵，坐 Park & Ride 专线巴士更好。", 0),
        (34.0975, -117.6484, "🏠", "Upland：从家出发", "Metrolink San Bernardino 线大约一小时到联合车站；开车走 I-10 或 I-210 进城，早晚高峰往西 / 往东都很堵。", 0),
        (34.2364, -117.6589, "🏔️", "Baldy 山", "Upland 北边半小时车程，冬天能滑雪，夏天坐缆车上山徒步。冬天上山要带雪链。", 0),
        (34.0700, -118.2550, "🚗", "高峰期别上 101 / 110 / 10", "工作日早 7–9 点、傍晚 3–7 点，市中心周围的高速和 405 几乎都是停车场。能坐 Metro 就坐 Metro。", 1),
    ],
}

CITIES = {
    "ny": {"feeds": [("sub", "🚇 地铁", ["mta new york city transit"], "subway", ["https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip"], {"1", "2"})]},
    "la": {"feeds": [("metro", "🚇 Metro 轨道", ["los angeles county metropolitan", "la metro"], "rail", ["https://gitlab.com/LACMTA/gtfs_rail/-/raw/master/gtfs_rail.zip"], {"0", "1"}),
                     ("ml", "🚈 Metrolink", ["metrolink", "southern california regional rail"], "", ["https://metrolinktrains.com/globalassets/about/gtfs/gtfs.zip"], {"2"})]},
}


def get(url, timeout=240):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout) as r:
                return r.read()
        except Exception as e:
            if i == 2:
                raise
            print("  retry", url[:80], e, flush=True)
            time.sleep(5)


_CAT = None


def catalog(kws, name_kw):
    global _CAT
    if _CAT is None:
        try:
            _CAT = list(csv.DictReader(io.StringIO(get(CATALOG).decode("utf-8-sig", "replace"))))
        except Exception as e:
            print("catalog", e)
            _CAT = []
    out = []
    for r in _CAT:
        prov, nm = (r.get("provider") or "").lower(), (r.get("name") or "").lower()
        if (r.get("data_type") or "").lower() != "gtfs" or (r.get("status") or "").lower() in ("deprecated", "inactive"):
            continue
        if (r.get("urls.authentication_type") or "0") not in ("0", "") or "louis" in prov:
            continue
        if any(k in prov for k in kws) and (not name_kw or name_kw in nm or name_kw in prov):
            out += [u for u in (r.get("urls.direct_download"), r.get("urls.latest")) if u and u not in out]
    return out


def simplify(pts, eps):
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    st = [(0, len(pts) - 1)]
    while st:
        a, b = st.pop()
        ax, ay = pts[a]
        bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy or 1e-18
        best, bi = -1, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
            d = (ax + t * dx - px) ** 2 + (ay + t * dy - py) ** 2
            if d > best:
                best, bi = d, i
        if best > eps * eps:
            keep[bi] = True
            st += [(a, bi), (bi, b)]
    return [p for p, k in zip(pts, keep) if k]


def parse(kind, name, url, types):
    print("%s ← %s" % (kind, url), flush=True)
    z = zipfile.ZipFile(io.BytesIO(get(url)))
    rd = lambda n: list(csv.DictReader(io.TextIOWrapper(z.open(n), "utf-8-sig"))) if n in z.namelist() else []
    routes = {r["route_id"]: r for r in rd("routes.txt") if (r.get("route_type") or "").strip() in types}
    if not routes:
        raise RuntimeError("没有需要的线路类型")
    trips = {t["trip_id"]: t for t in rd("trips.txt") if t["route_id"] in routes}
    stops = {s["stop_id"]: s for s in rd("stops.txt")}
    seq = {}
    for r in rd("stop_times.txt"):
        if r["trip_id"] in trips:
            seq.setdefault(r["trip_id"], []).append(r["stop_id"])
    need = {t.get("shape_id") for t in trips.values()}
    shp = {}
    for r in rd("shapes.txt"):
        if r["shape_id"] in need:
            shp.setdefault(r["shape_id"], []).append((int(r["shape_pt_sequence"]), float(r["shape_pt_lat"]), float(r["shape_pt_lon"])))
    lines, stn = [], {}
    order = sorted(routes.values(), key=lambda r: (r.get("route_sort_order") or "9999").zfill(5) + (r.get("route_short_name") or r["route_id"]).zfill(4))
    for r in order:
        rt = [t for t in trips.values() if t["route_id"] == r["route_id"] and t["trip_id"] in seq]
        if not rt:
            continue
        best = max(rt, key=lambda t: (len(shp.get(t.get("shape_id"), [])), len(seq[t["trip_id"]])))
        pts = sorted(shp.get(best.get("shape_id"), []))
        if pts:
            path = [[round(a, 5), round(b, 5)] for a, b in simplify([(a, b) for _, a, b in pts], 0.0002)]
        else:
            sq = max(rt, key=lambda t: len(seq[t["trip_id"]]))
            path = [[round(float(stops[s]["stop_lat"]), 5), round(float(stops[s]["stop_lon"]), 5)] for s in seq[sq["trip_id"]] if s in stops]
        sn, ln = (r.get("route_short_name") or "").strip(), (r.get("route_long_name") or "").strip()
        col = r.get("route_color") or ""
        col = "#" + col if len(col) == 6 and col.upper() not in ("FFFFFF", "000000") else "#56606E"
        if kind == "ml":
            nm = ln.replace("Metrolink ", "").replace(" Line", " 线")
        elif sn:
            nm = sn + (" 线" if re.match(r"^[A-Z0-9]{1,3}X?$", sn) else "") + (" · " + ln if ln and ln != sn else "")
        else:
            nm = ln
        idx = len(lines)
        lines.append({"n": nm, "c": col, "path": path, "no": sn if len(sn) <= 3 else ""})
        for t in rt:
            for s in seq[t["trip_id"]]:
                so = stops.get(s)
                if not so:
                    continue
                pid = so.get("parent_station") or s
                p = stops.get(pid, so)
                o = stn.setdefault(pid, {"id": kind + ":" + pid, "ll": [round(float(p["stop_lat"]), 5), round(float(p["stop_lon"]), 5)],
                                         "en": re.sub(r"\s+(Metrolink )?Station$", "", p["stop_name"]).strip(), "zh": "", "ln": set()})
                o["ln"].add(idx)
    st = []
    for o in stn.values():
        o["ln"] = sorted(o["ln"])
        o["big"] = len(o["ln"]) >= (4 if kind == "sub" else 2)
        st.append(o)
    print("  %d 条线 · %d 站" % (len(lines), len(st)), flush=True)
    return {"k": kind, "n": name, "lines": lines, "st": st}


ZH = {
    "ny": {"Times Sq-42 St": "时代广场", "Grand Central-42 St": "中央车站", "34 St-Penn Station": "宾州车站", "34 St-Herald Sq": "先驱广场（梅西百货）", "Flushing-Main St": "法拉盛", "Canal St": "坚尼街（华埠）",
           "WTC Cortlandt": "世贸中心", "World Trade Center": "世贸中心", "Fulton St": "富尔顿街", "South Ferry": "南码头（斯塔滕岛渡轮）", "Whitehall St-South Ferry": "白厅街（渡轮）", "Wall St": "华尔街",
           "Brooklyn Bridge-City Hall": "布鲁克林大桥 · 市政厅", "Coney Island-Stillwell Av": "科尼岛", "161 St-Yankee Stadium": "洋基体育场", "Mets-Willets Point": "大都会球场 · 美网", "Jamaica Center-Parsons/Archer": "牙买加中心",
           "Sutphin Blvd-Archer Av-JFK Airport": "牙买加（换 JFK 机场快线）", "Howard Beach-JFK Airport": "霍华德海滩（换 JFK 机场快线）", "Jackson Hts-Roosevelt Av": "杰克逊高地（拉瓜迪亚机场巴士）", "8 Av": "八大道（布鲁克林华埠）",
           "125 St": "125 街（哈莱姆）", "59 St-Columbus Circle": "哥伦布圆环（中央公园）", "Lexington Av/59 St": "列克星敦大道 / 59 街", "14 St-Union Sq": "联合广场", "W 4 St-Wash Sq": "华盛顿广场",
           "High St": "高街（布鲁克林大桥公园）", "York St": "约克街（DUMBO）", "Bedford Av": "贝德福德大道（威廉斯堡）", "Atlantic Av-Barclays Ctr": "大西洋大道 · 巴克莱中心", "Roosevelt Island": "罗斯福岛"},
    "la": {"Union Station": "联合车站", "L.A. Union": "联合车站", "Los Angeles Union Station": "联合车站", "Chinatown": "唐人街", "Little Tokyo/Arts District": "小东京 · 艺术区", "Historic Broadway": "百老汇历史区",
           "Grand Av Arts/Bunker Hill": "大道艺术区 · 邦克山（迪士尼音乐厅）", "7th St/Metro Center": "第七街 / 地铁中心", "Pershing Square": "潘兴广场", "Hollywood/Highland": "好莱坞 / 高地（星光大道）",
           "Hollywood/Vine": "好莱坞 / 藤街", "Universal City/Studio City": "环球影城", "North Hollywood": "北好莱坞", "Wilshire/Western": "韩国城", "Downtown Santa Monica": "圣莫尼卡市中心（码头）",
           "Expo Park/USC": "博览会公园 · 南加大", "Downtown Long Beach": "长滩市中心", "Memorial Park": "帕萨迪纳老城", "Del Mar": "帕萨迪纳 Del Mar", "Arcadia": "阿卡迪亚", "APU/Citrus College": "阿祖萨",
           "Pomona North": "波莫纳北站", "Upland": "Upland（家门口）", "Montclair": "蒙特克莱尔", "Claremont": "克莱蒙特", "Rancho Cucamonga": "兰乔库卡蒙格", "LAX/Metro Transit Center": "LAX 机场换乘中心",
           "Culver City": "卡尔弗城", "Westwood/Rancho Park": "西木", "Fullerton": "富勒顿", "Anaheim - ARTIC": "阿纳海姆（迪士尼附近）", "Irvine": "欧文", "Burbank - Downtown": "伯班克市中心"},
}


def main():
    which = sys.argv[1:] or list(CITIES)
    for city in which:
        cfg, out = CITIES[city], os.path.join(ROOT, city, "transit.json")
        old = {}
        try:
            old = {L["k"]: L for L in json.load(open(out, encoding="utf-8"))["layers"]}
        except Exception:
            pass
        layers = []
        for kind, name, kws, name_kw, fb, types in cfg["feeds"]:
            got = None
            for url in catalog(kws, name_kw) + fb:
                try:
                    got = parse(kind, name, url, types)
                    if got["lines"]:
                        break
                except Exception as e:
                    print("  ✗", url[:90], e, flush=True)
                    got = None
            if not got and kind in old:
                print("  %s：用上一版" % kind)
                got = old[kind]
            if got:
                for s in got["st"]:
                    s["zh"] = s.get("zh") or ZH.get(city, {}).get(s["en"], "")
                layers.append(got)
        layers.append({"k": "tips", "n": "💡 用心提示", "lines": [], "st": [], "tips": [{"ll": [a, b], "e": e, "t": t, "d": d, "w": w} for a, b, e, t, d, w in TIPS[city]]})
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"note": "线路走向和车站来自官方公开 GTFS", "layers": layers}, f, ensure_ascii=False, separators=(",", ":"))
        print("%s/transit.json：" % city + " · ".join("%s %d 线 %d 站" % (L["k"], len(L["lines"]), len(L["st"])) for L in layers) + " · %d KB" % (os.path.getsize(out) // 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
