#!/usr/bin/env python3
"""
🌍 国际局势 · 分大洲  →  news/data/world.json（news.html 的「国际局势」标签用）

每个大洲用几家英文国际媒体的「地区频道」RSS（BBC 欧洲 / 亚洲 / 美加 / 拉美 / 澳洲、卫报、法国24、德国之声、
半岛电视台、CNA、日本时报、ABC 澳洲、新西兰 RNZ……），把讲同一件事的聚成一组，被越多家报道的排越前；
标题和摘要机翻成中文（和「今日大事」共用 today.py 的聚类和翻译），并标出涉及的国家，统计每个洲的「热点国家」。
只存标题、摘要、链接。任何一个源失败只跳过它，状态记在 "sources"。
"""
import datetime as dt
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from today import fetch_feed, cluster, translate  # noqa: E402

OUT = os.path.join(HERE, "data", "world.json")
KEEP_HOURS = 48
PER_REGION = 15

REGIONS = [
    ("eu", "欧洲", "🇪🇺", [
        ("BBC", "https://feeds.bbci.co.uk/news/world/europe/rss.xml"),
        ("卫报", "https://www.theguardian.com/world/europe-news/rss"),
        ("法国24", "https://www.france24.com/en/europe/rss"),
        ("德国之声", "https://rss.dw.com/rdf/rss-en-eu"),
        ("Euronews", "https://www.euronews.com/rss?level=theme&name=news"),
        ("Politico 欧洲", "https://www.politico.eu/feed/"),
        ("Sky News", "https://feeds.skynews.com/feeds/rss/world.xml"),
    ]),
    ("asia", "亚洲", "🌏", [
        ("BBC", "https://feeds.bbci.co.uk/news/world/asia/rss.xml"),
        ("卫报", "https://www.theguardian.com/world/asia-pacific/rss"),
        ("法国24", "https://www.france24.com/en/asia-pacific/rss"),
        ("德国之声", "https://rss.dw.com/rdf/rss-en-asia"),
        ("CNA", "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6511"),
        ("日本时报", "https://www.japantimes.co.jp/feed/"),
        ("南华早报", "https://www.scmp.com/rss/91/feed"),
        ("The Diplomat", "https://thediplomat.com/feed/"),
    ]),
    ("am", "美洲", "🌎", [
        ("BBC 美加", "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml"),
        ("BBC 拉美", "https://feeds.bbci.co.uk/news/world/latin_america/rss.xml"),
        ("卫报", "https://www.theguardian.com/world/americas/rss"),
        ("卫报美国", "https://www.theguardian.com/us-news/rss"),
        ("法国24", "https://www.france24.com/en/americas/rss"),
        ("NPR", "https://feeds.npr.org/1004/rss.xml"),
        ("CBC", "https://www.cbc.ca/webfeed/rss/rss-world"),
        ("CBC 加拿大", "https://www.cbc.ca/webfeed/rss/rss-canada"),
        ("MercoPress", "https://en.mercopress.com/rss/"),
    ]),
    ("oc", "澳洲", "🦘", [
        ("BBC", "https://feeds.bbci.co.uk/news/world/australia/rss.xml"),
        ("卫报澳洲", "https://www.theguardian.com/australia-news/rss"),
        ("ABC 澳洲", "https://www.abc.net.au/news/feed/51120/rss.xml"),
        ("SBS", "https://www.sbs.com.au/news/feed"),
        ("RNZ 新西兰", "https://www.rnz.co.nz/rss/national.xml"),
        ("RNZ 太平洋", "https://www.rnz.co.nz/rss/pacific.xml"),
    ]),
    ("mea", "中东 · 非洲", "🌍", [
        ("BBC 中东", "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml"),
        ("BBC 非洲", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"),
        ("半岛电视台", "https://www.aljazeera.com/xml/rss/all.xml"),
        ("法国24", "https://www.france24.com/en/middle-east/rss"),
        ("法国24 非洲", "https://www.france24.com/en/africa/rss"),
        ("卫报中东", "https://www.theguardian.com/world/middleeast/rss"),
        ("卫报非洲", "https://www.theguardian.com/world/africa/rss"),
    ]),
]

# 国家：英文关键词（正则）→ 国旗、中文名、所属大洲。按标题+摘要匹配，用来标注和统计热点。
C = [
    # 欧洲
    ("eu", "🇺🇦", "乌克兰", r"Ukrain\w*|Kyiv|Kiev|Zelensky\w*|Kharkiv|Odesa|Donbas"), ("eu", "🇷🇺", "俄罗斯", r"Russia\w*|Kremlin|Moscow|Putin"),
    ("eu", "🇬🇧", "英国", r"\bUK\b|Britain|British|England|Scotland|Wales|London|Starmer|Westminster|Northern Ireland"),
    ("eu", "🇫🇷", "法国", r"France|French|Paris|Macron"), ("eu", "🇩🇪", "德国", r"German\w*|Berlin|Merz\b|Bundestag"),
    ("eu", "🇮🇹", "意大利", r"Ital\w*|Rome\b|Meloni"), ("eu", "🇪🇸", "西班牙", r"Spain|Spanish|Madrid|S[aá]nchez|Catalan\w*"),
    ("eu", "🇵🇱", "波兰", r"Poland|Polish|Warsaw|Tusk\b"), ("eu", "🇳🇱", "荷兰", r"Netherlands|Dutch|Amsterdam|The Hague"),
    ("eu", "🇧🇪", "比利时", r"Belgi\w*|Brussels"), ("eu", "🇪🇺", "欧盟", r"\bEU\b|European Union|European Commission|von der Leyen|Eurozone"),
    ("eu", "🛡️", "北约", r"\bNato\b|\bNATO\b"), ("eu", "🇭🇺", "匈牙利", r"Hungar\w*|Budapest|Orb[aá]n"),
    ("eu", "🇷🇴", "罗马尼亚", r"Romania\w*|Bucharest"), ("eu", "🇲🇩", "摩尔多瓦", r"Moldova\w*"), ("eu", "🇧🇾", "白俄罗斯", r"Belarus\w*|Lukashenko|Minsk"),
    ("eu", "🇬🇪", "格鲁吉亚", r"Tbilisi|Georgian Dream|Kobakhidze"), ("eu", "🇷🇸", "塞尔维亚", r"Serbia\w*|Belgrade"), ("eu", "🇬🇷", "希腊", r"Greece|Greek|Athens"), ("eu", "🇦🇱", "西巴尔干", r"Albania\w*|Tirana|Kosovo\w*|Bosnia\w*|Sarajevo|Montenegr\w*|North Macedonia\w*"),
    ("eu", "🇵🇹", "葡萄牙", r"Portug\w*|Lisbon"), ("eu", "🇮🇪", "爱尔兰", r"Ireland|Irish|Dublin"), ("eu", "🇸🇪", "瑞典", r"Swed\w*|Stockholm"),
    ("eu", "🇳🇴", "挪威", r"Norw\w*|Oslo"), ("eu", "🇫🇮", "芬兰", r"Finland|Finnish|Helsinki"), ("eu", "🇩🇰", "丹麦", r"Denmark|Danish|Copenhagen|Greenland"),
    ("eu", "🇨🇭", "瑞士", r"Switzerland|Swiss|Geneva|Zurich"), ("eu", "🇦🇹", "奥地利", r"Austria\w*|Vienna"), ("eu", "🇨🇿", "捷克", r"Czech|Prague"),
    ("eu", "🇸🇰", "斯洛伐克", r"Slovakia\w*|Fico\b"), ("eu", "🇧🇬", "保加利亚", r"Bulgaria\w*"), ("eu", "🇭🇷", "克罗地亚", r"Croatia\w*"),
    ("eu", "🇱🇹", "波罗的海三国", r"Lithuania\w*|Latvia\w*|Estonia\w*|Baltic"), ("eu", "🇹🇷", "土耳其", r"Turkey|Turkish|T[uü]rkiye|Erdo[gğ]an|Istanbul|Ankara"),
    ("eu", "🇦🇲", "亚美尼亚", r"Armenia\w*"), ("eu", "🇦🇿", "阿塞拜疆", r"Azerbaijan\w*|Baku"), ("eu", "🇻🇦", "梵蒂冈", r"Vatican|Pope\b"),
    # 亚洲
    ("asia", "🇨🇳", "中国", r"China|Chinese|Beijing|Xi Jinping|\bXi\b|Shanghai|Shenzhen|Guangzhou|Hong Kong|Macau|Tibet\w*|Xinjiang"),
    ("asia", "🇹🇼", "台湾", r"Taiwan\w*|Taipei|Lai Ching-te"), ("asia", "🇯🇵", "日本", r"Japan\w*|Tokyo|Osaka|Takaichi|Ishiba"),
    ("asia", "🇰🇷", "韩国", r"South Korea\w*|Seoul|\bLee Jae[- ]myung"), ("asia", "🇰🇵", "朝鲜", r"North Korea\w*|Pyongyang|Kim Jong"),
    ("asia", "🇮🇳", "印度", r"India\b|Indian\b|Delhi|Mumbai|Modi\b|Kashmir"), ("asia", "🇵🇰", "巴基斯坦", r"Pakistan\w*|Islamabad|Karachi|Lahore"),
    ("asia", "🇧🇩", "孟加拉", r"Bangladesh\w*|Dhaka"), ("asia", "🇦🇫", "阿富汗", r"Afghan\w*|Kabul|Taliban"), ("asia", "🇳🇵", "尼泊尔", r"Nepal\w*|Kathmandu"),
    ("asia", "🇱🇰", "斯里兰卡", r"Sri Lanka\w*|Colombo"), ("asia", "🇲🇲", "缅甸", r"Myanmar|Burm\w*|Yangon"), ("asia", "🇹🇭", "泰国", r"Thai\w*|Bangkok"),
    ("asia", "🇻🇳", "越南", r"Vietnam\w*|Hanoi|Ho Chi Minh"), ("asia", "🇰🇭", "柬埔寨", r"Cambodia\w*|Phnom Penh"), ("asia", "🇱🇦", "老挝", r"Laos\b"),
    ("asia", "🇵🇭", "菲律宾", r"Philippin\w*|Filipino|Manila|Marcos"), ("asia", "🇮🇩", "印尼", r"Indonesia\w*|Jakarta|Prabowo|Bali\b"),
    ("asia", "🇲🇾", "马来西亚", r"Malaysia\w*|Kuala Lumpur|Anwar"), ("asia", "🇸🇬", "新加坡", r"Singapor\w*"),
    ("asia", "🇲🇳", "蒙古", r"Mongolia\w*|Ulaanbaatar"), ("asia", "🇰🇿", "中亚", r"Kazakh\w*|Uzbek\w*|Kyrgyz\w*|Tajik\w*|Turkmen\w*"),
    ("asia", "🌊", "南海", r"South China Sea|Scarborough|Spratly|Second Thomas"),
    # 美洲
    ("am", "🇺🇸", "美国", r"\bUS\b|U\.S\.|United States|(?<!Latin )(?<!South )(?<!Central )(?<!North )America\b|(?<!Latin )(?<!South )(?<!Central )American\b|Washington|White House|Trump|Congress|Senate|Pentagon|Biden|Vance\b|Rubio\b"),
    ("am", "🇨🇦", "加拿大", r"Canad\w*|Ottawa|Toronto|Vancouver|Montreal|Carney\b|Quebec|Alberta"), ("am", "🇲🇽", "墨西哥", r"Mexic\w*|Sheinbaum"),
    ("am", "🇧🇷", "巴西", r"Brazil\w*|Lula\b|S[aã]o Paulo|Rio de Janeiro|Bolsonaro|Amazon rainforest"), ("am", "🇦🇷", "阿根廷", r"Argentin\w*|Buenos Aires|Milei"),
    ("am", "🇻🇪", "委内瑞拉", r"Venezuel\w*|Caracas|Maduro"), ("am", "🇨🇴", "哥伦比亚", r"Colombia\w*|Bogot[aá]|Petro\b"), ("am", "🇨🇱", "智利", r"Chile\b|Chilean|Santiago"),
    ("am", "🇵🇪", "秘鲁", r"Peru\b|Peruvian|Lima\b"), ("am", "🇪🇨", "厄瓜多尔", r"Ecuador\w*|Quito"), ("am", "🇧🇴", "玻利维亚", r"Bolivia\w*"),
    ("am", "🇨🇺", "古巴", r"Cuba\w*|Havana"), ("am", "🇭🇹", "海地", r"Haiti\w*|Port-au-Prince"), ("am", "🇵🇦", "巴拿马", r"Panama\w*"),
    ("am", "🇬🇹", "中美洲", r"Guatemal\w*|Hondura\w*|El Salvador|Salvador\w*|Bukele|Nicaragu\w*|Costa Ric\w*"), ("am", "🇩🇴", "加勒比", r"Dominican|Jamaica\w*|Puerto Ric\w*|Caribbean|Trinidad"),
    ("am", "🇺🇾", "乌拉圭", r"Urugua\w*"), ("am", "🇵🇾", "巴拉圭", r"Paragua\w*"), ("am", "🇫🇰", "马岛", r"Falkland\w*"),
    # 澳洲 · 大洋洲
    ("oc", "🇦🇺", "澳大利亚", r"Australia\w*|Canberra|Sydney|Melbourne|Brisbane|Perth|Adelaide|Albanese|Queensland|Victoria\b|New South Wales|Tasmania"),
    ("oc", "🇳🇿", "新西兰", r"New Zealand|Wellington|Auckland|Christchurch|Luxon\b|M[aā]ori"), ("oc", "🇵🇬", "巴布亚新几内亚", r"Papua New Guinea|\bPNG\b|Port Moresby|Bougainville"),
    ("oc", "🇫🇯", "斐济", r"\bFiji\w*"), ("oc", "🇸🇧", "所罗门群岛", r"Solomon Islands"), ("oc", "🇼🇸", "太平洋岛国", r"Samoa\w*|Tonga\w*|Vanuatu|Kiribati|Tuvalu|Nauru|Palau|Cook Islands|New Caledonia|Pacific Islands"),
    # 中东 · 非洲
    ("mea", "🇮🇱", "以色列", r"Israel\w*|Netanyahu|Jerusalem|Tel Aviv|\bIDF\b"), ("mea", "🇵🇸", "巴勒斯坦", r"Palestin\w*|Gaza\w*|West Bank|Hamas"),
    ("mea", "🇮🇷", "伊朗", r"\bIran\w*|Tehran|Khamenei"), ("mea", "🇱🇧", "黎巴嫩", r"Leban\w*|Beirut|Hezbollah"), ("mea", "🇸🇾", "叙利亚", r"Syria\w*|Damascus"),
    ("mea", "🇮🇶", "伊拉克", r"\bIraq\w*|Baghdad|Kurdist\w*"), ("mea", "🇸🇦", "沙特", r"Saudi\w*|Riyadh"), ("mea", "🇾🇪", "也门", r"Yemen\w*|Houthi\w*|Sanaa"),
    ("mea", "🇶🇦", "海湾国家", r"Qatar\w*|Doha|\bUAE\b|Emirat\w*|Dubai|Abu Dhabi|Kuwait\w*|Bahrain\w*|\bOman\w*"), ("mea", "🇯🇴", "约旦", r"Jordan\b|Jordanian|Amman"),
    ("mea", "🇪🇬", "埃及", r"Egypt\w*|Cairo"), ("mea", "🇸🇩", "苏丹", r"\bSudan\w*|Khartoum|Darfur|\bRSF\b"), ("mea", "🇸🇸", "南苏丹", r"South Sudan\w*"),
    ("mea", "🇱🇾", "利比亚", r"Libya\w*|Tripoli"), ("mea", "🇹🇳", "北非", r"Tunisia\w*|Algeria\w*|Morocc\w*"), ("mea", "🇪🇹", "埃塞俄比亚", r"Ethiopia\w*|Addis Ababa|Tigray"),
    ("mea", "🇸🇴", "索马里", r"Somali\w*|Mogadishu"), ("mea", "🇰🇪", "肯尼亚", r"Kenya\w*|Nairobi"), ("mea", "🇳🇬", "尼日利亚", r"Nigeria\w*|Lagos|Abuja"),
    ("mea", "🇿🇦", "南非", r"South Africa\w*|Johannesburg|Cape Town|Pretoria|Ramaphosa"), ("mea", "🇨🇩", "刚果（金）", r"\bCongo\w*|\bDRC\b|Kinshasa|Goma|\bM23\b"),
    ("mea", "🇷🇼", "卢旺达", r"Rwanda\w*|Kigali"), ("mea", "🇲🇱", "萨赫勒", r"\bMali\b|Malian|Burkina Faso|\bNiger\b|Sahel|Chad\b"),
    ("mea", "🇺🇬", "东非", r"Uganda\w*|Tanzania\w*|Mozambi\w*"), ("mea", "🇿🇼", "南部非洲", r"Zimbabwe\w*|Zambia\w*|Malawi\w*|Angola\w*|Namibia\w*|Botswana\w*|Madagascar"),
    ("mea", "🇬🇭", "西非", r"Ghana\w*|Senegal\w*|Ivory Coast|C[oô]te d'Ivoire|Cameroon\w*|(?<!New )Guinea\b|Sierra Leone|Liberia\w*"),
]
CRX = [(reg, flag, zh, re.compile(r"\b(?:" + rx + r")")) for reg, flag, zh, rx in C]
SKIP = re.compile(r"^(Watch|Video|Live|Listen|In pictures|Quiz|Podcast|Newsletter|The week in|Morning mail|Crossword|Latest news bulletin|News bulletin)\b\s*[:：]?", re.I)


# 局势影响：按英文标题+摘要里的关键词判断这件事「可能影响」到哪一块，配上传导路径的说明。
# 只是关键词规则，不是逐条分析；页面上写明「可能影响」。顺序就是优先级，每条最多标 3 个。
IMPACTS = [
    ("oil", "🛢️", "油价 · 能源", r"\boil\b|crude|OPEC|Hormuz|petrol|gasoline|diesel|\bLNG\b|natural gas|gas pipeline|refiner\w*|energy (?:price|crisis|supply|infrastructure)|power plants?|Aramco",
     "产油国动荡、OPEC 决定、能源设施遇袭会让国际油价波动，几周内传到加州油价、柴油价和运输成本。"),
    ("ship", "🚢", "航运 · 港口物流", r"shipping|\bports?\b|container|freight|cargo|Red Sea|Suez|Panama Canal|Strait of|Houthi\w* (?:attack|strike|missile)\w* on ships?|supply chain|dockworkers?|longshore\w*|vessel|tanker|logistic\w*",
     "航线受阻、港口罢工、运费上涨会改变到港时间和货量，最后体现在洛杉矶/长滩港的柜量和 IE 仓库的忙闲。"),
    ("trade", "🧾", "关税 · 贸易", r"tariff\w*|trade (?:war|deal|talks|deficit|surplus|agreement|tensions?)|sanction\w*|export controls?|export ban|import (?:ban|duties)|\bWTO\b|customs dut\w*|exports?\b|imports?\b",
     "关税、制裁和贸易谈判改变进口成本：商品涨价、进口商提前抢运或砍单，港口货量会跟着大起大落。"),
    ("chip", "💾", "科技 · 芯片", r"semiconductor\w*|\bchips?\b|chipmak\w*|TSMC|Nvidia|rare earths?|artificial intelligence|\bAI\b|5G|Huawei",
     "芯片、稀土和 AI 是科技公司的命脉，出口管制、台海和供应消息常让科技股大幅波动，也影响电子产品价格。"),
    ("market", "📈", "股市 · 利率 · 汇率", r"stock\w*|share prices?|(?:stock|financial|bond|oil) markets?|markets? (?:fell|fall|rose|rise|tumbl|rall|slump|plung)\w*|Wall Street|interest rates?|central bank|Federal Reserve|\bFed\b|inflation|\bGDP\b|recession|bond\w*|currenc\w*|\byen\b|\byuan\b|\beuro\b|economy|economic growth|(?:national|sovereign|government) debt|debt crisis",
     "经济数据和央行决定牵动美股、利率和汇率：持仓、房贷车贷利率、换汇和回国汇款都会受影响。"),
    ("food", "🌾", "粮食 · 物价", r"wheat|grain|\bcorn\b|rice prices?|food (?:prices?|security|shortage|aid|insecurity)|famine|hunger|drought|harvest|fertili[sz]er|cocoa|coffee prices?|Black Sea",
     "产粮区的战争、干旱和出口限制会推高粮价，慢慢传到超市的面包、肉、咖啡和巧克力价格。"),
    ("sec", "⚔️", "冲突 · 安全", r"\bwar\b|missile\w*|air ?strikes?|drone (?:attack|strike)s?|invasion|troops|nuclear|ceasefire|truce|bombing|shelling|offensive|military|militants?|insurgen\w*|coup",
     "冲突升级或停火是油价、黄金、美元和军工股的风向标，也决定当地人道局势和周边国家的安全。"),
    ("cn", "🤝", "中美关系", r"(?:China|Chinese|Beijing|Xi)\b[^.]{0,80}\b(?:US|U\.S\.|Washington|Trump|American)|(?:US|U\.S\.|Washington|Trump|American)\b[^.]{0,80}\b(?:China|Chinese|Beijing|Xi)\b",
     "中美关系牵动关税、科技管制、签证留学、航班和两地往来，也是港口货量的大变量。"),
    ("travel", "✈️", "出行 · 旅行", r"flights? (?:cancel|delay|divert|suspend|ground)\w*|airlines?|airports?|airspace|travel (?:advisory|warning|ban|chaos|disruption)s?|tourists?|tourism|visas?\b|passports?|border (?:closure|crossing)|evacuat\w*|strikes? (?:by|at) (?:rail|train|airport|transport)",
     "航班取消、空域关闭、签证政策、罢工和疏散会打乱行程，计划出门前先看一眼。"),
    ("nature", "🌪️", "天灾 · 气候", r"earthquake|typhoon|hurricane|cyclone|floods?\b|flooding|wildfires?|bushfires?|heatwave|tsunami|volcan\w*|landslide|tropical storm|winter storm|storms? (?:hit|lash|batter|slam)\w*|climate change",
     "天灾会打断当地生产和运输，严重时波及全球供应链、保险和农产品价格。"),
    ("us", "🇺🇸", "美国政策 · 生活", r"White House|Congress|Senate|Supreme Court|federal|Trump administration|executive order|immigration|deportation|government shutdown|California|Los Angeles",
     "联邦政策、法院判决、移民和政府停摆这些事，会直接影响在美国工作、报税、出行和办事。"),
]
IRX = [(k, e, n, re.compile(r"(?:" + rx + r")", re.I if k in ("ship", "food", "nature", "travel", "sec") else 0), why) for k, e, n, rx, why in IMPACTS]


def impacts(text, cs=()):
    out = []
    for k, e, n, rx, why in IRX:
        if k == "us" and "美国" not in cs:      # 美国政策：必须是讲美国的事（巴西也有联邦法院）
            continue
        if rx.search(text):
            out.append(k)
    return out[:3]


def countries(text):
    out = []
    for reg, flag, zh, rx in CRX:
        if rx.search(text) and zh not in [x[1] for x in out]:
            out.append([flag, zh, reg])
    return out


def archive(regions, now):
    """把这次的报道追加到按月存档 news/data/archive/YYYY-MM.json（思考本的「事件追踪」时间线用）。
    同一条（按原文链接）只存一次，后来报道的媒体变多了就更新家数。只存标题、链接、来源、时间、国家和影响标签。"""
    adir = os.path.join(HERE, "data", "archive")
    os.makedirs(adir, exist_ok=True)
    path = os.path.join(adir, now.strftime("%Y-%m") + ".json")
    try:
        with open(path, encoding="utf-8") as f:
            items = json.load(f)["items"]
    except Exception:
        items = []
    idx = {it["l"].split("?")[0]: it for it in items}
    added = 0
    for r in regions:
        if r.get("stale"):
            continue
        for g in r["stories"]:
            key = (g.get("link") or "").split("?")[0]
            if not key:
                continue
            if key in idx:
                old = idx[key]
                old["n"] = max(old.get("n", 1), g.get("n", 1))
                continue
            it = {"d": g.get("time") or now.strftime("%Y-%m-%dT%H:%M:%SZ"), "t": g.get("title", ""), "e": g.get("en", ""), "l": g.get("link", ""),
                  "s": g.get("source", ""), "n": g.get("n", 1), "c": [c[1] for c in g.get("c", [])], "i": g.get("imp", []), "r": r["k"]}
            items.append(it)
            idx[key] = it
            added += 1
    items.sort(key=lambda x: x["d"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"month": now.strftime("%Y-%m"), "items": items}, f, ensure_ascii=False, separators=(",", ":"))
    print("存档 %s：新增 %d 条，共 %d 条" % (os.path.basename(path), added, len(items)))


def main():
    now = dt.datetime.now(dt.timezone.utc)
    prev = {}
    if os.path.exists(OUT):
        try:
            with open(OUT, encoding="utf-8") as f:
                prev = json.load(f)
        except Exception:
            prev = {}
    tcache = prev.get("tcache", {})
    prev_regions = {r["k"]: r for r in prev.get("regions", [])}
    jobs = [(k, name, url) for k, _, _, feeds in REGIONS for name, url in feeds]
    with ThreadPoolExecutor(10) as ex:
        res = list(ex.map(lambda j: (j[0],) + fetch_feed(j[1], j[2]), jobs))
    status, items = [], {k: [] for k, _, _, _ in REGIONS}
    seen = {k: set() for k in items}
    for k, name, url, its, err in res:
        status.append({"region": k, "source": name, "url": url, "ok": err is None and bool(its), "n": len(its), "err": err})
        for it in its:
            key = it["link"].split("?")[0]
            if key in seen[k] or SKIP.match(it["title"]):
                continue
            if it["time"] and now - it["time"] > dt.timedelta(hours=KEEP_HOURS):
                continue
            seen[k].add(key)
            items[k].append(it)

    regions = []
    for k, zh, emo, feeds in REGIONS:
        its = items[k]
        # Sky、半岛、日本时报、CBC 国际、NPR 国际这类综合源不分地区：只留提到本洲国家的
        own = [c for c in C if c[0] == k]
        its = [it for it in its if it["source"] not in ("Sky News", "半岛电视台", "日本时报", "CBC", "NPR") or
               any(re.search(r"\b(?:" + rx + ")", it["title"] + " " + it["summary"]) for _, _, _, rx in own)]
        groups = cluster(its)[:PER_REGION] if its else []
        hot = {}
        for g in groups:
            g["en"], g["en_summary"] = g["title"], g["summary"]
            text = g["en"] + " " + g["en_summary"] + " " + " ".join(o["title"] for o in g.get("others", []))
            g["c"] = countries(text)[:4]
            g["imp"] = impacts(text, [x[1] for x in g["c"]])
            for flag, cz, reg in g["c"]:
                w = hot.setdefault(cz, [flag, cz, reg, 0])
                w[3] += g["n"]
            g["title"] = translate(g["en"], tcache) or g["en"]
            g["summary"] = translate(g["en_summary"], tcache) if g["en_summary"] else ""
            g["zh"] = g["title"] != g["en"]
        # 热点国家：本洲的排前面
        hot = sorted(hot.values(), key=lambda x: (x[2] == k, x[3]), reverse=True)[:10]
        r = {"k": k, "n": zh, "e": emo, "stories": groups, "hot": hot, "count": len(its),
             "ok": sum(1 for s in status if s["region"] == k and s["ok"]), "feeds": len(feeds)}
        if not groups and k in prev_regions:
            r = dict(prev_regions[k], stale=True)
        regions.append(r)

    archive(regions, now)
    keep = set()
    for r in regions:
        for g in r["stories"]:
            keep.add(g.get("en", ""))
            keep.add(g.get("en_summary", ""))
    tcache = {a: b for a, b in tcache.items() if a in keep}
    imp = {k: {"k": k, "e": e, "n": n, "why": why, "count": 0} for k, e, n, rx, why in IRX}
    for r in regions:
        for g in r["stories"]:
            for k in g.get("imp") or []:
                imp[k]["count"] += 1
    out = {"generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "regions": regions, "impacts": [imp[k] for k, *_ in IMPACTS], "sources": status, "tcache": tcache}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    for r in regions:
        print("%s %s：%d 条 → %d 组 · 源 %d/%d · 热点 %s%s" % (r["e"], r["n"], r.get("count", 0), len(r["stories"]), r.get("ok", 0), r.get("feeds", 0),
                                                       " ".join(h[1] for h in r["hot"][:5]), "（用上次的）" if r.get("stale") else ""))
    bad = ["%s/%s(%s)" % (s["region"], s["source"], s["err"] or "空") for s in status if not s["ok"]]
    if bad:
        print("FAILED:", "; ".join(bad))


if __name__ == "__main__":
    main()
