#!/usr/bin/env python3
"""圣何塞（硅谷）实景交通图 → sj/transit.json（sj.html 用）

· VTA 轻轨（蓝 / 绿 / 橙线）、Caltrain、几条主要 VTA 巴士：从官方公开发布的 GTFS 时刻表里取真实走向和车站
  （通过 Mobility Database 公开目录找下载地址）。拿不到时沿用上一版 sj/transit.json 里的线路。
· BART：沿用 build_sf_transit.py 里的全部 50 站（实时到站要用）。
· 💡 用心提示：下面 TIPS 手写。
只用标准库。  python3 scripts/build_sj_transit.py   （加 --offline 不联网，只更新提示）
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_sf_transit import BS, BL, st  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "sj", "transit.json")
UA = "boliunew-tools-sj/1.0 (https://github.com/boliunew/tools)"
CATALOG = "https://share.mobilitydata.org/catalogs-csv"
FEEDS = [  # (layer key, catalog keywords, fallback urls)
    ("vta", ["santa clara valley transportation", "vta"], ["https://gtfs.vta.org/gtfs_vta.zip"]),
    ("caltrain", ["caltrain"], ["https://data.trilliumtransit.com/gtfs/caltrain-ca-us/caltrain-ca-us.zip"]),
]
BUS_KEEP = ["500", "522", "523", "568", "60", "22", "23"]
BUS_ZH = {"500": "Diridon 站 ⇄ Berryessa BART（快线）", "522": "Rapid 522：Palo Alto ⇄ Eastridge（El Camino · Alum Rock 快线）",
          "523": "Rapid 523：Lockheed Martin ⇄ Berryessa BART（De Anza 学院 · Sunnyvale）", "568": "Rapid 568：Gilroy ⇄ Diridon 站",
          "60": "60 路：Winchester ⇄ Milpitas BART（经过 SJC 机场 · Santa Clara Caltrain）", "22": "22 路：Palo Alto ⇄ Eastridge（El Camino 慢车）",
          "23": "23 路：De Anza 学院 ⇄ Alum Rock（Stevens Creek 大道）"}
ZH = {  # (layer, cleaned english name) → 中文
    "vta": {"Diridon": "迪里登车站 · 换乘 Caltrain / Amtrak · SAP 中心", "Convention Center": "会展中心", "San Antonio": "市中心 · San Antonio St",
            "Santa Clara": "市中心 · Santa Clara St", "Saint James": "圣詹姆斯公园", "Japantown/Ayer": "日本町", "Civic Center": "市政中心",
            "Children's Discovery Museum": "儿童探索博物馆", "San Fernando": "市中心 · San Fernando", "Baypointe": "Baypointe（蓝线北端）",
            "Great Mall": "大商场 Great Mall", "Milpitas": "米尔皮塔斯 · 换乘 BART", "Tasman": "Tasman", "Great America": "大美洲乐园 · 李维斯球场",
            "Mountain View": "山景城 · 换乘 Caltrain", "Alum Rock": "Alum Rock（橙线东端）", "Winchester": "Winchester（绿线西端）",
            "Santa Teresa": "Santa Teresa（蓝线南端）", "Old Ironsides": "Old Ironsides（绿线北端）", "Tamien": "Tamien · 换乘 Caltrain",
            "Campbell": "坎贝尔市中心", "Metro/Airport": "Metro/Airport · 转车去 SJC 机场", "Berryessa": "Berryessa", "Lockheed Martin": "洛克希德·马丁",
            "Cisco": "思科", "Hamilton": "Hamilton"},
    "caltrain": {"San Francisco": "旧金山 4th & King · 甲骨文球场", "22nd Street": "旧金山 22 街", "Bayshore": "Bayshore", "South San Francisco": "南旧金山",
                 "San Bruno": "圣布鲁诺", "Millbrae": "密尔布雷 · 换乘 BART 去 SFO", "Burlingame": "伯灵格姆", "San Mateo": "圣马特奥", "Hayward Park": "Hayward Park",
                 "Hillsdale": "Hillsdale", "Belmont": "贝尔蒙特", "San Carlos": "圣卡洛斯", "Redwood City": "红木城", "Menlo Park": "门洛帕克",
                 "Palo Alto": "帕罗奥图 · 斯坦福", "Stanford": "斯坦福球场（赛事日）", "California Avenue": "帕罗奥图 California Ave", "San Antonio": "山景城 San Antonio",
                 "Mountain View": "山景城 · 换乘 VTA 轻轨", "Sunnyvale": "森尼韦尔", "Lawrence": "Lawrence", "Santa Clara": "圣克拉拉 · 去 SJC 机场换 60 路",
                 "College Park": "College Park", "San Jose Diridon": "圣何塞迪里登车站", "Tamien": "Tamien · 换乘 VTA 轻轨", "Capitol": "Capitol",
                 "Blossom Hill": "Blossom Hill", "Morgan Hill": "摩根山", "San Martin": "圣马丁", "Gilroy": "吉尔罗伊（大蒜之都）"},
}

# ---------------------------------------------------------------- 💡 用心提示 (lat, lon, emoji, 标题, 内容, 警告?)
TIPS = [
    # 到达和换乘
    (37.3297, -121.9026, "🚉", "迪里登车站：南湾的总站", "Caltrain（去旧金山）、ACE（去斯托克顿）、Amtrak（Capitol Corridor 去萨克拉门托，Coast Starlight 南下洛杉矶）、VTA 轻轨和巴士都在这里。1935 年的老车站大厅值得进去看一眼。", 0),
    (37.3640, -121.9290, "✈️", "SJC 机场：离市中心只有十分钟", "机场就在城市中间，打车到市中心很便宜。公交：VTA 60 路连到 Santa Clara Caltrain 站和 Milpitas BART，用 Clipper 卡上车。", 0),
    (37.3684, -121.8746, "🚇", "BART 最南端：Berryessa", "坐 BART 能从这里一路到旧金山和奥克兰（大约一个半小时）。去市中心换 VTA 500 路快线，或者干脆打车。", 0),
    (37.4103, -121.8913, "🔁", "Milpitas：BART 换轻轨", "BART 和 VTA 橙线 / 绿线在这里一个天桥连起来，旁边就是 Great Mall 大商场。", 0),
    (37.3390, -121.8930, "🚋", "轻轨在市中心像散步", "VTA 轻轨在 First / Second St 和街上的车混行，市中心这一段走路都差不多快。出了市区才跑得快。车票用 Clipper 或 Transit App，2 小时内换乘免费。", 0),
    (37.3940, -122.0763, "🚆", "Caltrain 去旧金山", "2024 年起 Caltrain 换成了电气化列车，更快更安静。圣何塞到旧金山 4th & King：快车大约一小时，慢车一个半小时。周末班次少，提前查好。", 0),
    # 市中心
    (37.3327, -121.8894, "🎄", "César Chávez 广场", "市中心的大草坪。11 月底到 1 月初有「Christmas in the Park」，满广场圣诞树，免费；旁边还有露天溜冰场。", 0),
    (37.3365, -121.8912, "💡", "1881 年的电灯塔就立在这里", "Market St 和 Santa Clara St 路口曾经立着一座 237 英尺高的电灯塔，想用一座塔把整个市中心照亮。相传埃菲尔看过它的设计，但没有证据。1915 年被风暴吹倒。History Park 里有一座一半大小的复制品。", 0),
    (37.3363, -121.8942, "🍢", "San Pedro Square Market", "老砖楼里的美食集市，几十家小摊，室外有座位和现场音乐。SAP 中心看球前后人很多。", 0),
    (37.3315, -121.8901, "🔬", "The Tech 科技互动博物馆", "能自己动手设计机器人、测试地震抗震的科学馆，还有圆顶 IMAX 影院。小孩和大人都玩得开心。", 0),
    (37.3355, -121.8850, "📚", "King 图书馆：大学和城市共用", "全美第一座由大学（圣何塞州立大学）和城市合建、共用的大型图书馆，八层楼，任何人都能进，有干净厕所和充电。", 0),
    (37.3352, -121.8815, "✊", "1968 年奥运的拳头", "圣何塞州立大学校园里有 Tommie Smith 和 John Carlos 的雕像，两人都是这所学校的学生，1968 年墨西哥城奥运领奖台上举拳抗议种族歧视。", 0),
    (37.3368, -121.8900, "🛬", "市中心的楼为什么不高", "飞机进出 SJC 就从市中心头顶飞过，所以楼高受限，市中心没有旧金山那种摩天楼。在 St. James 公园抬头看飞机，非常低。", 0),
    (37.3327, -121.9010, "🦈", "SAP 中心：鲨鱼队的「鱼缸」", "NHL 圣何塞鲨鱼队的主场，球迷叫它「the Shark Tank」。球员入场时从一个巨大的鲨鱼头里滑出来。散场时轻轨和停车场都很挤，可以走去 San Pedro Square 吃个夜宵再走。", 0),
    (37.3313, -121.8869, "🍝", "Original Joe's", "1956 年开在市中心的老牌意大利馆子，服务生穿燕尾服，开放式厨房，分量很大。", 0),
    # 街区
    (37.3486, -121.8946, "🏯", "日本町", "全美只剩三个历史日本町（另两个在旧金山和洛杉矶），这是其中之一。周日早上 Jackson St 有农夫市场；Shuei-Do 手工和果子；日裔美国人博物馆讲二战拘留营的历史。", 0),
    (37.3489, -121.8932, "🏮", "这里曾经是唐人街", "1887 年圣何塞市中心的唐人街被人纵火烧光。德国移民 John Heinlen 顶着压力把自己的地租给华人，在这一带建起了「Heinlenville」唐人街，和日本町毗邻共存了几十年。", 0),
    (37.3329, -121.8514, "🍜", "越南城：Story Road", "圣何塞常被说成越南以外越南人最多的城市。Story Rd 和 Tully Rd 一带是越南商场、河粉、法棍三明治（bánh mì）、甜汤（chè）。Lee's Sandwiches 就是从圣何塞起家的。", 0),
    (37.3201, -121.8279, "🧧", "Lion Plaza 越南广场", "Tully Rd 和 King Rd 路口，越南超市、面包店、咖啡。农历新年（Tết）前后最热闹。", 0),
    (37.3534, -121.8558, "🌮", "东区：墨西哥裔社区", "Alum Rock Ave 一带是墨西哥裔老社区，塔可车、面包房（panadería）、水果冰（paletas）。凯撒·查维斯年轻时就住在东区的「Sal Si Puedes」街区，在这里学会了组织工人。", 0),
    (37.3043, -121.8999, "🌳", "Willow Glen", "Lincoln Ave 两边是林荫、小店和咖啡馆，像个小镇。周边老平房很漂亮，节日时家家户户挂灯。", 0),
    (37.3209, -121.9478, "🛍️", "Santana Row + Valley Fair", "露天的欧式购物街，晚上很热闹；对面 Westfield Valley Fair 是湾区最大的商场之一。停车场注意车里别留东西。", 0),
    # 景点
    (37.3184, -121.9511, "🏚️", "温彻斯特神秘屋", "温彻斯特步枪继承人 Sarah Winchester 的大宅，修了几十年，约 160 个房间，有通向天花板的楼梯、开向墙壁的门。只能跟导览进，周末和万圣节前后提前网上买票。", 0),
    (37.3336, -121.9234, "🏺", "玫瑰十字会埃及博物馆", "西北美洲（北美西部）展出古埃及文物最多的博物馆，有真的木乃伊，还能走进仿造的古墓。外面的院子像个小埃及。", 0),
    (37.3317, -121.9284, "🌹", "市立玫瑰园", "免费，几千株玫瑰，4–5 月开得最盛。离埃及博物馆走路几分钟，可以一起逛。", 0),
    (37.3197, -121.8563, "🗼", "History Park：老圣何塞", "把老房子、老电车、老邮局搬来拼成一条老街，还有那座电灯塔的一半大小复制品。旁边 Kelley Park 里有日本友好花园（免费，锦鲤池）和 Happy Hollow 小动物园。", 0),
    (37.3966, -121.8001, "♨️", "Alum Rock 公园", "1872 年建，加州最古老的市立公园。峡谷里有当年温泉疗养地留下的石头小屋。夏天中午很热，早上去，带足水。", 0),
    (37.3414, -121.6429, "🔭", "利克天文台", "汉密尔顿山顶，1888 年建成，是世界上第一座山顶永久天文台；出钱的富商 James Lick 就葬在大望远镜下面。山路弯道非常多，容易晕车。开放日有限，夏天有夜间观星活动，先查官网。", 0),
    (37.4033, -121.9694, "🏈", "李维斯球场", "旧金山 49 人队其实在圣克拉拉打主场。办过 2016 年和 2026 年超级碗，也是 2026 年世界杯赛场。比赛日坐轻轨去，开车堵到怀疑人生。", 0),
    (37.3979, -121.9745, "🎢", "大美洲乐园", "球场旁边的游乐园，土地已经卖掉，以后会关闭。想去的话趁早。", 0),
    (37.3489, -121.9409, "⛪", "圣克拉拉教堂", "圣克拉拉大学校园中间的西班牙教堂，加州 21 座传教站之一（1777 年创立，现在这座是重建的）。校园漂亮，免费参观。", 0),
    (37.3513, -121.9250, "⚽", "地震队主场", "MLS 圣何塞地震队（San Jose Earthquakes），名字来自湾区最出名的「特产」。", 0),
    (37.1745, -121.8277, "⛏️", "新阿尔马登水银矿", "加州第一个矿（1845 年），挖的是提炼黄金要用的水银，淘金热靠它。现在是县立公园，有矿工小镇博物馆和徒步道。不要喝溪水、不要捡矿石：老矿区有汞污染。", 0),
    (37.4278, -121.9810, "🦩", "Alviso：湾边盐田", "南湾尽头的老码头小镇，周围是彩色盐田（坐飞机能看到红、橙、绿色的池子）和野生动物保护区，看鸟很好。", 0),
    # 硅谷
    (37.3327, -122.0053, "🍎", "Apple Park 访客中心", "苹果总部对面的访客中心，免费。有屋顶露台，能远远看到那个「飞碟」大楼；店里有用 AR 看的总部模型，还有只在这里卖的纪念 T 恤。总部本身不对外开放。", 0),
    (37.4143, -122.0775, "💾", "计算机历史博物馆", "山景城，从算盘到 AI。能看到能运转的巴贝奇差分机、谷歌第一台服务器机架、早期苹果电脑。", 0),
    (37.4275, -122.1697, "🎓", "斯坦福大学", "免费逛。主四方院和纪念教堂很漂亮；Cantor 美术馆免费，户外有罗丹的雕塑园；胡佛塔可以上去看风景（收少量门票）。校内停车要付费。", 0),
    (37.4430, -122.1550, "🏠", "HP 车库：「硅谷诞生地」", "367 Addison Ave，1939 年惠普在这间车库里成立，现在是加州历史地标。这是私人住宅，只能在路边看看拍照，别进院子。", 0),
    (37.3530, -121.9850, "🍖", "El Camino 上的韩国城", "圣克拉拉 El Camino Real 一段是韩国烤肉、豆腐汤、韩国超市扎堆的地方，晚上营业到很晚。", 0),
    (37.4157, -121.8978, "🧋", "Milpitas：亚洲美食集中地", "Great Mall 附近和几个亚洲广场里有 99 大华超市、台湾、港式、川菜、越南菜，奶茶店一家接一家。", 0),
    (37.3233, -121.9289, "🧆", "Falafel's Drive-In", "1966 年开到现在的路边小店，招牌是沙拉三明治配香蕉奶昔，上过美食节目，排队也快。", 0),
    # 山野和周边
    (37.3317, -122.0876, "🥾", "Rancho San Antonio", "硅谷人最爱的徒步地，能看到鹿和山上的老农场。周末早上 8 点前停车场就满了。", 0),
    (37.5126, -121.8806, "🌅", "Mission Peak 看日出", "弗里蒙特的山顶，顶上有根「Mission Peak 柱子」，大家排队站上去拍照。上山一路没有树荫，带足水，夏天别中午爬。", 0),
    (37.2565, -122.0447, "🎋", "箱根花园 Hakone Gardens", "萨拉托加山坡上的日式庭园，1915 年建，号称西半球最老的日式住宅庭园之一。", 0),
    (37.2266, -121.9822, "☕", "Los Gatos 小镇", "山脚下的小镇，老街咖啡馆、餐厅，Los Gatos Creek Trail 适合散步骑车。", 0),
    (37.1700, -121.9850, "⚠️", "17 号公路：别赶时间", "去圣克鲁兹必经的山路，急弯多、车速快、事故多，夏天周末去海边的车能堵一路。别跟车太近，下雨天特别小心。", 1),
    (36.9643, -122.0177, "🎡", "圣克鲁兹海滨乐园", "离圣何塞大约 45 分钟车程。1907 年开的海边游乐场，1924 年的木头过山车「Giant Dipper」还在跑；码头上看海狮，West Cliff Drive 看冲浪。", 0),
    # 安全提醒
    (37.3380, -121.8960, "⚠️", "市中心深夜", "市中心白天和看球的晚上都很正常；深夜人少的时候，Guadalupe 河边步道和一些空荡的街区不要一个人逛。", 1),
    (37.3000, -121.8700, "🔥", "夏天热、秋天有烟", "南湾比旧金山热得多，夏天常过 90°F。秋天山火季偶尔有烟，出门前看一下空气质量（AirNow）。", 1),
]


def get(url, tries=3, timeout=180):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            if i == tries - 1:
                raise
            print("  retry", url[:90], e, flush=True)
            time.sleep(5 * (i + 1))


def catalog_urls(kws):
    try:
        raw = get(CATALOG).decode("utf-8-sig", "replace")
    except Exception as e:
        print("  目录拿不到：", e)
        return []
    out = []
    for r in csv.DictReader(io.StringIO(raw)):
        if (r.get("data_type") or "").lower() != "gtfs" or (r.get("status") or "").lower() in ("deprecated", "inactive"):
            continue
        if (r.get("urls.authentication_type") or "0") not in ("0", ""):
            continue
        prov = (r.get("provider") or "").lower()
        sub = (r.get("location.subdivision_name") or "").lower()
        if any(k in prov for k in kws) and ("california" in sub or not sub):
            for u in (r.get("urls.direct_download"), r.get("urls.latest")):
                if u and u not in out:
                    out.append(u)
    return out


def read(z, name):
    try:
        with z.open(name) as f:
            return list(csv.DictReader(io.TextIOWrapper(f, "utf-8-sig")))
    except KeyError:
        return []


def zh_of(kind, name):
    return ZH.get(kind, {}).get(name, "")


def clean(n):
    n = re.sub(r"\s*\((north|south|east|west)bound\)|\s+(north|south|east|west)bound|\s*\(\d+\)|\s+station$|\s+caltrain$", "", n, flags=re.I)
    n = n.replace(" Light Rail", "").strip()
    return re.sub(r"\s+(station|caltrain)$", "", n, flags=re.I).strip()


def parse(kind, url):
    print("%s ← %s" % (kind, url), flush=True)
    z = zipfile.ZipFile(io.BytesIO(get(url)))
    routes = {r["route_id"]: r for r in read(z, "routes.txt")}
    want = {}
    for rid, r in routes.items():
        t = (r.get("route_type") or "").strip()
        sn = (r.get("route_short_name") or "").strip()
        if kind == "caltrain" and t == "2":
            want[rid] = "caltrain"
        elif kind == "vta" and t == "0" and not re.search(r"event|special", (r.get("route_long_name") or "") + sn, re.I):
            want[rid] = "vta"
        elif kind == "vta" and t == "3" and re.sub(r"\D", "", sn) in BUS_KEEP:
            want[rid] = "vbus"
    if not want:
        raise RuntimeError("没有需要的线路")
    trips = [t for t in read(z, "trips.txt") if t["route_id"] in want]
    tid = {t["trip_id"]: t for t in trips}
    cnt = {}
    first_stops = {}
    with z.open("stop_times.txt") as f:
        for r in csv.DictReader(io.TextIOWrapper(f, "utf-8-sig")):
            if r["trip_id"] in tid:
                cnt.setdefault(r["trip_id"], []).append((int(r["stop_sequence"]), r["stop_id"]))
    stops = {s["stop_id"]: s for s in read(z, "stops.txt")}
    shp = {}
    for r in read(z, "shapes.txt"):
        shp.setdefault(r["shape_id"], []).append((int(r["shape_pt_sequence"]), float(r["shape_pt_lat"]), float(r["shape_pt_lon"])))
    lines, stns = {"vta": [], "caltrain": [], "vbus": []}, {}
    for rid, kd in want.items():
        r = routes[rid]
        rt = [t for t in trips if t["route_id"] == rid and t["trip_id"] in cnt]
        if not rt:
            continue
        best = max(rt, key=lambda t: (len(cnt[t["trip_id"]]), len(shp.get(t.get("shape_id"), []))))
        seq = [s for _, s in sorted(cnt[best["trip_id"]])]
        pts = sorted(shp.get(best.get("shape_id"), []))
        if pts:
            step = max(1, len(pts) // 260)
            path = [[round(a, 5), round(b, 5)] for _, a, b in pts[::step]] + [[round(pts[-1][1], 5), round(pts[-1][2], 5)]]
        else:
            path = [[round(float(stops[s]["stop_lat"]), 5), round(float(stops[s]["stop_lon"]), 5)] for s in seq if s in stops]
        sn = re.sub(r"\D", "", (r.get("route_short_name") or "")) if kd == "vbus" else (r.get("route_short_name") or "").strip()
        ln_ = (r.get("route_long_name") or "").strip()
        col = r.get("route_color") or ""
        col = "#" + col if len(col) == 6 and col.upper() not in ("FFFFFF", "000000") else {"caltrain": "#E31837", "vta": "#0072CE", "vbus": "#6B7480"}[kd]
        idx = len(lines[kd])
        if kd == "vbus":
            lines[kd].append({"n": "%s 路" % sn, "c": col, "d": BUS_ZH.get(sn, ln_), "no": sn, "path": path})
            continue
        nm = ln_ or sn
        if kd == "vta":
            nm = (sn + " " + ln_).strip() if sn and sn.lower() not in ln_.lower() else nm
        lines[kd].append({"n": nm, "c": col, "path": path})
        if kd == "vta":
            m = re.match(r"(Blue|Green|Orange)\s+Line\s+(.+?)\s+-\s+(.+)$", nm, re.I)
            if m:
                lines[kd][-1]["n"] = "%s线 %s ⇄ %s" % ({"blue": "蓝", "green": "绿", "orange": "橙"}[m.group(1).lower()], m.group(2), m.group(3))
        if kd == "caltrain":
            idx = 0  # Caltrain 只画一条（几种停站模式走同一条轨道），车站合并
        all_stops = set()
        for t in rt:
            for _, s in cnt[t["trip_id"]]:
                all_stops.add(s)
        for s in all_stops:
            if s not in stops:
                continue
            so = stops[s]
            par = so.get("parent_station") or ""
            nm2 = clean(stops[par]["stop_name"] if par in stops else so.get("stop_name", s))
            if "NOT A PUBLIC" in nm2.upper():
                continue
            key = kd + ":" + nm2.lower()
            o = stns.setdefault(key, {"k": kd, "en": nm2, "pts": [], "ln": set()})
            o["pts"].append((float(so["stop_lat"]), float(so["stop_lon"])))
            o["ln"].add(idx)
    if kind == "caltrain" and lines["caltrain"]:
        lc = max(lines["caltrain"], key=lambda x: len(x["path"]))
        lines["caltrain"] = [dict(lc, n="Caltrain 旧金山 ⇄ 圣何塞 ⇄ 吉尔罗伊", c="#E31837")]
    out_st = {"vta": [], "caltrain": []}
    big = re.compile(r"diridon|convention|santa clara|baypointe|milpitas|mountain view|alum rock|winchester|santa teresa|great america|levi|san francisco|palo alto|millbrae|tamien|gilroy|redwood city|sunnyvale|japantown", re.I)
    for key, o in stns.items():
        la = sum(p[0] for p in o["pts"]) / len(o["pts"])
        lo = sum(p[1] for p in o["pts"]) / len(o["pts"])
        out_st[o["k"]].append({"id": key, "ll": [round(la, 5), round(lo, 5)], "en": o["en"], "zh": zh_of(o["k"], o["en"]), "big": bool(big.search(o["en"])), "ln": sorted(o["ln"])})
    print("  轻轨 %d 条 / Caltrain %d / 巴士 %d · 车站 %d" % (len(lines["vta"]), len(lines["caltrain"]), len(lines["vbus"]), len(stns)), flush=True)
    return lines, out_st


def main():
    offline = "--offline" in sys.argv
    old = {}
    if os.path.exists(OUT):
        try:
            old = {L["k"]: L for L in json.load(open(OUT, encoding="utf-8"))["layers"]}
        except Exception:
            old = {}
    got = {}
    if not offline:
        for kind, kws, fb in FEEDS:
            for url in catalog_urls(kws) + fb:
                try:
                    lines, sts = parse(kind, url)
                    if kind == "vta" and not lines["vta"]:
                        continue
                    if kind == "caltrain" and not lines["caltrain"]:
                        continue
                    for k in ("vta", "caltrain", "vbus"):
                        if lines[k]:
                            got[k] = (lines[k], sts.get(k, []))
                    break
                except Exception as e:
                    print("  ✗", url[:90], e, flush=True)
    names = {"vta": "VTA 轻轨", "caltrain": "Caltrain", "vbus": "VTA 主要巴士"}
    layers = []
    for k in ("vta", "caltrain", "vbus"):
        if k in got:
            layers.append({"k": k, "n": names[k], "lines": got[k][0], "st": got[k][1]})
        elif k in old:
            print("  %s：用上一版的线路" % k)
            layers.append(old[k])
        else:
            layers.append({"k": k, "n": names[k], "lines": [], "st": []})
    big = {"BERY", "MLPT", "WARM", "FRMT", "EMBR", "POWL", "MONT", "SFIA", "MLBR", "12TH", "19TH", "COLS", "BAYF", "DALY", "RICH", "ANTC", "DUBL"}
    layers.append({"k": "bart", "n": "BART", "lines": [{"n": n, "c": c, "st": seq} for n, c, seq in BL],
                   "st": [dict(st(BS, k), big=k in big) for k in BS]})
    layers.append({"k": "tips", "n": "用心提示", "lines": [], "st": [], "tips": [{"ll": [a, b], "e": e, "t": t, "d": d, "w": w} for a, b, e, t, d, w in TIPS]})
    out = {"note": "VTA 轻轨、Caltrain、巴士线路来自官方 GTFS；BART 车站间按直线连接。", "layers": layers}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("sj/transit.json：" + " · ".join("%s %d 线 %d 站" % (L["k"], len(L["lines"]), len(L["st"])) for L in layers) + " · 提示 %d · %d KB" % (len(TIPS), os.path.getsize(OUT) // 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
