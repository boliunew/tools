"""Build deals/data/flyers.json + deals/data/meta.json for deals.html (打折雷达).

Sources (all public, fetched twice a day by GitHub Actions):
  * Flipp weekly-ad data for ZIP 91786 — every store flyer near Upland (Food 4 Less, Walmart, Stater Bros, ALDI, Target, Costco …),
    including next week's ads that are already published. Each flyer is cached by id, so an unchanged week costs one request.
  * Slickdeals RSS (front page, popular, store searches) — Amazon / Walmart online deals
  * camelcamelcamel "top price drops" RSS — Amazon price drops
  * DealNews RSS — deals that say "at Amazon" / "at Walmart"
Every source is optional: if one fails, the rest still publish (errors land in "notes").
"""
import datetime as dt
import hashlib
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "deals", "data")
ZIP = "91786"  # Upland, CA
UA = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Mobile Safari/537.36"
KEEP_ONLINE_H = 72   # keep online deals this long across runs
UPCOMING_DAYS = 8    # include flyers that start within this many days ("下周预告")
V = 4                # bump to re-parse cached flyers after changing the rules below

GROUPS = [  # key, zh, emoji — store groups for the page
    ("grocery", "超市", "🥬"), ("general", "综合百货", "🏬"), ("pharmacy", "药房美妆", "💊"), ("electronics", "电子办公", "🔌"),
    ("home", "家居五金", "🔨"), ("fashion", "服饰", "👗"), ("sports", "运动户外", "⚽"), ("pets", "宠物", "🐶"), ("craft", "手工", "🎨"),
    ("online", "网上", "📦"),
]
FLIPP_GROUP = {"Groceries": "grocery", "General Merchandise": "general", "Pharmacy": "pharmacy", "Electronics": "electronics",
               "Home & Garden": "home", "Fashion": "fashion", "Sporting Goods": "sports", "Pets": "pets", "Office": "electronics",
               "Automotive": "home", "Baby & Kids": "general", "Specialty": "general"}
# store overrides: id, groups, brand colour, product-search url ({q}), weekly-ad page
STORES = {
    "Food 4 Less": ("f4l", ["grocery"], "#C8102E", "https://www.food4less.com/search?query={q}", "https://www.food4less.com/weeklyad"),
    "Walmart": ("walmart", ["grocery", "general"], "#0071DC", "https://www.walmart.com/search?q={q}", "https://www.walmart.com/shop/deals"),
    "Target": ("target", ["grocery", "general"], "#CC0000", "https://www.target.com/s?searchTerm={q}", "https://www.target.com/weekly-ad"),
    "Costco": ("costco", ["grocery", "general"], "#E31837", "https://www.costco.com/CatalogSearch?keyword={q}", "https://www.costco.com/online-offers.html"),
    "Ralphs": ("ralphs", ["grocery"], "#0F4C9E", "https://www.ralphs.com/search?query={q}", "https://www.ralphs.com/weeklyad"),
    "Vons": ("vons", ["grocery"], "#E21A2C", "https://www.vons.com/shop/search-results.html?q={q}", "https://www.vons.com/weeklyad"),
    "Albertsons": ("albertsons", ["grocery"], "#0072CE", "https://www.albertsons.com/shop/search-results.html?q={q}", "https://www.albertsons.com/weeklyad"),
    "Stater Bros. Markets": ("stater", ["grocery"], "#D52B1E", None, None),
    "ALDI": ("aldi", ["grocery"], "#00005F", None, None),
    "Smart & Final": ("smartfinal", ["grocery"], "#E2231A", None, None),
    "Sprouts Farmers Market": ("sprouts", ["grocery"], "#5B8E3E", None, None),
    "Cardenas Markets": ("cardenas", ["grocery"], "#D7262F", None, None),
    "Vallarta Supermarkets": ("vallarta", ["grocery"], "#E30613", None, None),
    "Superior Grocers": ("superior", ["grocery"], "#E2001A", None, None),
    "El Super": ("elsuper", ["grocery"], "#E30613", None, None),
    "Grocery Outlet": ("groceryoutlet", ["grocery"], "#2E7D32", None, None),
    "Super King Markets": ("superking", ["grocery"], "#C62828", None, None),
    "Family Dollar": ("familydollar", ["general"], "#F26722", None, None),
    "Dollar General": ("dollargeneral", ["general"], "#FFC220", None, None),
    "Five Below": ("fivebelow", ["general"], "#00A0DF", None, None),
    "Kohl's": ("kohls", ["fashion", "general"], "#7B2B8E", "https://www.kohls.com/search.jsp?search={q}", None),
    "CVS Pharmacy": ("cvs", ["pharmacy"], "#CC0000", "https://www.cvs.com/search?searchTerm={q}", "https://www.cvs.com/weeklyad"),
    "Walgreens": ("walgreens", ["pharmacy"], "#E31837", "https://www.walgreens.com/search/results.jsp?Ntt={q}", None),
    "ULTA": ("ulta", ["pharmacy"], "#F26B3A", "https://www.ulta.com/search?search={q}", None),
    "Bath & Body Works": ("bbw", ["pharmacy"], "#1B2A4A", None, None),
    "Best Buy": ("bestbuy", ["electronics"], "#0046BE", "https://www.bestbuy.com/site/searchpage.jsp?st={q}", None),
    "GameStop": ("gamestop", ["electronics"], "#E4002B", None, None),
    "Office Depot OfficeMax": ("officedepot", ["electronics"], "#CC0000", None, None),
    "Home Depot": ("homedepot", ["home"], "#F96302", "https://www.homedepot.com/s/{q}", None),
    "Lowe's": ("lowes", ["home"], "#004990", "https://www.lowes.com/search?searchTerm={q}", None),
    "Ace Hardware": ("ace", ["home"], "#D40029", None, None),
    "Harbor Freight Tools": ("harborfreight", ["home"], "#C8102E", None, None),
    "Tractor Supply Company": ("tractor", ["home", "pets"], "#BD1E2D", None, None),
    "Michaels USA": ("michaels", ["craft"], "#D52B1E", None, None),
    "Hobby Lobby": ("hobbylobby", ["craft"], "#F58025", None, None),
    "PetSmart": ("petsmart", ["pets"], "#E2231A", None, None),
    "Dick's Sporting Goods": ("dicks", ["sports"], "#006B54", None, None),
    "Cabela's": ("cabelas", ["sports"], "#4A5D23", None, None),
}
ONLINE_META = {"amazon": {"name": "Amazon", "grp": ["online"], "color": "#FF9900", "wk": "https://www.amazon.com/deals"}}
notes = []


def get(url, tries=2):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, application/rss+xml, text/xml, */*"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 + i * 3)
    raise last


def https(u):
    return re.sub(r"^http://", "https://", u or "")


def money(x):
    try:
        v = float(x)
        return int(v) if v == int(v) else round(v, 2)
    except (TypeError, ValueError):
        return None


def fmt(v):
    return ("%d" % v) if v == int(v) else ("%.2f" % v)


# ---------------------------------------------------------------- categories
CATS = [  # key, zh, emoji
    ("meat", "肉类", "🥩"), ("seafood", "海鲜", "🦐"), ("produce", "蔬菜水果", "🥬"), ("dairy", "奶蛋", "🥛"),
    ("bakery", "面包烘焙", "🍞"), ("frozen", "冷冻食品", "🧊"), ("pantry", "粮油调料", "🥫"), ("snacks", "零食糖果", "🍪"),
    ("drinks", "饮料酒水", "🥤"), ("household", "日用清洁", "🧻"), ("beauty", "个护健康", "🧴"), ("baby", "母婴", "👶"),
    ("pet", "宠物", "🐶"), ("electronics", "电子数码", "📱"), ("home", "家居厨房", "🛋️"), ("clothing", "服饰鞋包", "👕"),
    ("toys", "玩具游戏", "🧸"), ("media", "图书影音", "📚"), ("outdoor", "工具户外汽车", "🛠️"), ("other", "其他", "📦"),
]
RULES = [  # order matters: the first match wins
    ("media", r"\b(e-?book|kindle edition|hardcover|paperback|audiobook|blu-?ray|4k uhd|dvd|vinyl|lp|cd|album|soundtrack|novel|workbook|storybook|bible|comic|manga|movie collection|season one|season \d|french edition|edition\)|recordings|magazine)\b"),
    ("pet", r"\b(dog|dogs|puppy|cats?|cat food|cat litter|cat treats|kitten|kitty|litter|pet|pets|purina|pedigree|friskies|meow mix|iams|blue buffalo|milk-bone|greenies|fancy feast|temptations)\b"),
    ("baby", r"\b(diaper|diapers|pampers|huggies|luvs|baby|babies|infant|toddler|enfamil|similac|gerber|pacifier|stroller|car seat)\b"),
    ("electronics", r"\b(carplay|android auto|dash ?cam|power station|docking station|pc case|ssd|apple (?:airpods|watch|ipad|iphone|macbook|tv|pencil)|tv|tvs|television|oled|qled|laptop|laptops|chromebook|macbook|tablet|ipad|iphone|android phone|smartphone|phone|headphones|earbuds|airpods|speaker|speakers|soundbar|monitor|camera|smart ?watch|apple watch|charger|charging|usb|cable|ssd|hard drive|microsd|router|wi-?fi|gaming|playstation|ps5|xbox|nintendo|switch 2|printer|kindle|echo|alexa|fire tv|roku|streaming|bluetooth|projector|gpu|graphics card|keyboard|mouse|power bank|batteries|drone|dash cam|electronics)\b"),
    ("drinks", r"\b(soda|sodas|coca-cola|coke|pepsi|sprite|dr\.? pepper|squirt|7up|7-up|fanta|jarritos|water|waters|juice|juices|tea|teas|coffee|k-cup|k-cups|gatorade|powerade|energy drink|monster energy|red bull|beer|beers|wine|wines|vodka|tequila|whiskey|whisky|rum|seltzer|lemonade|kombucha|drink|drinks|beverage|beverages|horchata|agua fresca|bodyarmor|celsius|smoothie)\b"),
    ("snacks", r"\b(nutter butter|chips|doritos|cheetos|lay'?s|ruffles|pringles|takis|tostitos|fritos|cookies|cookie|oreo|crackers|cheez-it|goldfish|candy|candies|chocolate|chocolates|gum|snack|snacks|popcorn|pretzels|nuts|almonds|peanuts|pistachios|trail mix|granola bars?|fruit snacks|jerky|gummies|gummy|m&m'?s|snickers|reese'?s|kit ?kat|skittles|halloween candy)\b"),
    ("frozen", r"\b(frozen|ice cream|popsicles?|ice pops?|hot pockets|burritos|chimichangas|taquitos|nuggets|waffles|tv dinners?|el monterey|totino'?s|digiorno|red baron|stouffer'?s|banquet|lean cuisine|marie callender'?s|eggo|pizza rolls|frozen pizza|pot pies?)\b"),
    ("bakery", r"\b(bread|breads|bagels?|buns|rolls|tortillas?|muffins?|donuts?|doughnuts?|cakes?|pies?|croissants?|pan dulce|conchas|bolillos?|bakery|hawaiian rolls|english muffins)\b"),
    ("dairy", r"\b(milk|cheese|cheeses|yogurt|yoghurt|(?<!peanut )butter|eggs|egg|sour cream|cream cheese|creamer|creamers|cottage cheese|half & half|half and half|crema|queso|whipped cream|margarine)\b"),
    ("seafood", r"\b(shrimp|salmon|tilapia|cod|crab|crabs|lobster|swai|catfish|mussels|clams|scallops|oysters|seafood|fish fillets?|fresh fish|mojarra|pollock)\b"),
    ("meat", r"\b(chicken|beef|pork|steak|steaks|ground|turkey|ham|bacon|sausage|sausages|hot dogs?|franks|ribs|roast|chops|carne|carne asada|chorizo|lamb|wings|thighs|drumsticks|breasts?|tri-tip|tri tip|brisket|deli meat|lunch ?meat|salami|bologna|meat|meats|ribeye|sirloin|fajita|al pastor|tenderloin|loin|carnitas|patties)\b"),
    ("produce", r"\b(apples?|bananas?|oranges?|grapes|berries|strawberries|blueberries|raspberries|blackberries|avocados?|tomatoes|tomato|potatoes|potato|onions?|lettuce|cabbage|carrots?|sweet corn|corn on the cob|peppers|bell peppers?|cucumbers?|squash|zucchini|melons?|watermelons?|cantaloupes?|honeydew|pineapples?|mangos?|mangoes|peaches|pears?|plums?|lemons?|limes?|cilantro|celery|broccoli|cauliflower|spinach|kale|garlic|ginger|jicama|tomatillos?|papayas?|grapefruit|mandarins?|tangerines?|clementines?|kiwis?|cherries|salad|salads|mushrooms?|asparagus|green beans|yams?|sweet potatoes|jalape[nñ]os?|chiles?|produce|fruit|fruits|vegetables?|nectarines|pomegranates?|persimmons?|pumpkins?)\b"),
    ("pantry", r"\b(rice|beans|pasta|spaghetti|noodles|ramen|ramyun|cereal|oatmeal|oats|flour|sugar|cooking oil|olive oil|sauce|salsa|soups?|broth|spices|seasoning|ketchup|mayo|mayonnaise|mustard|peanut butter|jelly|jam|honey|syrup|tuna|vinegar|masa|maseca|pancake|waffle mix|baking mix|cake mix|grocery|groceries|canned)\b"),
    ("household", r"\b(disposable|steam pans?|party cups|paper bowls|paper plates|paper towels?|bath tissue|toilet paper|facial tissue|tissues?|napkins|detergent|tide|gain|bleach|clorox|cleaner|cleaners|cleaning|trash bags?|garbage bags?|aluminum foil|foil|plastic wrap|ziploc|storage bags|dish soap|dawn|cascade|finish|fabric softener|downy|dryer sheets|sponges?|lysol|air fresheners?|febreze|pine-sol|swiffer|charmin|bounty|scott|cottonelle|kleenex|plates|cups|utensils)\b"),
    ("beauty", r"\b(shampoo|conditioner|soap|body wash|deodorant|antiperspirant|toothpaste|toothbrush|mouthwash|floss|razors?|shave|lotion|makeup|cosmetics?|mascara|lipstick|vitamins?|supplements?|medicine|pain relief|tylenol|advil|motrin|aleve|allergy|cold & flu|cough|first aid|bandages|hair|skin ?care|sunscreen|feminine|tampons|pads|perfume|cologne|fragrance|nail|serum|moisturizer|cleanser|colgate|crest|dove|olay|neutrogena|cerave|gillette|pharmacy|health)\b"),
    ("toys", r"\b(the game|card game|catan|toy|toys|lego|barbie|hot wheels|dolls?|puzzles?|board games?|nerf|play-doh|plush|action figures?|kids'? games?|pok[eé]mon cards)\b"),
    ("clothing", r"\b(shirts?|t-shirts?|tees?|pants|jeans|dress|dresses|shoes|sneakers|boots|sandals|slippers|jackets?|coats?|socks|underwear|bras?|hoodies?|sweaters?|sweatshirts?|leggings|shorts|backpacks?|handbags?|purses?|wallets?|apparel|clothing|fashion|pajamas|uniforms?|scrubs|hats?|caps|sunglasses|jewelry|necklace|earrings|watch|watches|luggage|suitcase|crossbody|sweatpants|joggers|base layer|thermal)\b"),
    ("home", r"\b(mattress|mattresses|sofa|couch|recliner|chairs?|tables?|desks?|bed frames?|beds|bedding|sheets|comforters?|pillows?|towels?|rugs?|curtains|lamps?|vacuums?|robot vacuum|air fryers?|blenders?|cookware|frying pans?|skillets?|pots|knives|knife|kitchen|furniture|storage|shelves|shelf|decor|candles?|microwaves?|coffee makers?|keurig|instant pot|toaster|mixer|dinnerware|space heater|fans?|air purifier|humidifier|dehumidifier|home|griddle|multi-cooker|slow cooker|pressure cooker|night light|led lights?|smart lock|doorbell|halloween|christmas|decorations?|shopping cart|jug|tumbler|water bottle|stanley|inflatable)\b"),
    ("outdoor", r"\b(tools?|drill|drills|saw|wrench|ladder|grills?|garden|gardening|lawn|mower|trimmer|leaf blower|camping|tent|bikes?|bicycles?|e-bike|scooter|fitness|treadmill|dumbbells?|kettlebell|yoga|golf|car|cars|auto|automotive|tires?|motor oil|wipers?|hose|patio|cooler|fishing|hunting|generator|pressure washer|dewalt|milwaukee|ryobi|craftsman|irrigation|u-bolts?|bolts|screws|curl bar|barbell|weights|bench press)\b"),
]
RULES = [(k, re.compile(p, re.I)) for k, p in RULES]
L1MAP = {
    "Animals & Pet Supplies": "pet", "Baby & Toddler": "baby", "Electronics": "electronics", "Apparel & Accessories": "clothing",
    "Toys & Games": "toys", "Health & Beauty": "beauty", "Furniture": "home", "Hardware": "outdoor", "Sporting Goods": "outdoor",
    "Vehicles & Parts": "outdoor", "Luggage & Bags": "clothing", "Office Supplies": "other", "Media": "other", "Arts & Entertainment": "other",
}
FOOD = {"meat", "seafood", "produce", "dairy", "bakery", "frozen", "pantry", "snacks", "drinks"}


def classify(name, l1=None, l2=None, grocery=False):
    if l1 == "Home & Garden":
        cat = {"Household Supplies": "household", "Kitchen & Dining": "home", "Lawn & Garden": "outdoor"}.get(l2 or "", None)
        if cat:
            return cat
    if l1 in L1MAP:
        return L1MAP[l1]
    if l1 == "Food, Beverages & Tobacco" and l2 == "Beverages":
        return "drinks"
    is_food = l1 == "Food, Beverages & Tobacco"
    for k, rx in RULES:
        if is_food and k not in FOOD:
            continue
        if rx.search(name):
            return k
    if is_food or grocery:
        return "pantry" if is_food else "other"
    return "other"


# ---------------------------------------------------------------- Chinese hints for groceries
GLOSS = [
    (r"chicken breasts?", "鸡胸肉"), (r"chicken thighs?", "鸡腿肉"), (r"drumsticks", "鸡腿"), (r"chicken wings|wings", "鸡翅"), (r"whole chicken|fryer", "整鸡"), (r"chicken", "鸡肉"),
    (r"ground beef", "牛肉馅"), (r"tri-tip|tri tip", "三角尖牛肉"), (r"ribeye|sirloin|steaks?", "牛排"), (r"carne asada", "烤牛肉片"), (r"beef", "牛肉"),
    (r"pork ribs|spare ribs|ribs", "排骨"), (r"pork chops", "猪排"), (r"pork shoulder|pork butt", "猪肩肉"), (r"pork", "猪肉"), (r"bacon", "培根"), (r"chorizo", "墨西哥香肠"),
    (r"sausages?", "香肠"), (r"hot dogs?|franks", "热狗肠"), (r"\bham\b", "火腿"), (r"turkey", "火鸡"), (r"shrimp", "虾"), (r"salmon", "三文鱼"), (r"tilapia", "罗非鱼"),
    (r"\beggs?\b", "鸡蛋"), (r"\bmilk\b", "牛奶"), (r"cheese", "奶酪"), (r"yogurt", "酸奶"), (r"butter", "黄油"), (r"sour cream|crema", "酸奶油"), (r"creamer", "咖啡奶精"),
    (r"tortilla chips", "玉米片"), (r"corn tortillas", "玉米饼"), (r"flour tortillas", "面饼"), (r"tortillas?", "玉米饼/面饼"), (r"bread", "面包"), (r"\brice\b", "大米"), (r"beans", "豆子"), (r"cereal", "麦片"), (r"pasta|spaghetti", "意面"), (r"ramen|noodles", "面条"),
    (r"\boil\b", "食用油"), (r"sugar", "糖"), (r"flour", "面粉"), (r"avocados?", "牛油果"), (r"tomatoes|tomato", "西红柿"), (r"potatoes|potato", "土豆"), (r"onions?", "洋葱"),
    (r"bananas?", "香蕉"), (r"apples?", "苹果"), (r"oranges?|mandarins?|clementines?", "橙子/橘子"), (r"grapes", "葡萄"), (r"strawberries", "草莓"), (r"blueberries", "蓝莓"),
    (r"watermelons?", "西瓜"), (r"cantaloupes?", "哈密瓜"), (r"pineapples?", "菠萝"), (r"mangos?|mangoes", "芒果"), (r"lemons?", "柠檬"), (r"limes?", "青柠"), (r"sweet corn|corn", "玉米"),
    (r"lettuce", "生菜"), (r"cabbage", "卷心菜"), (r"carrots?", "胡萝卜"), (r"broccoli", "西兰花"), (r"cucumbers?", "黄瓜"), (r"bell peppers?", "甜椒"), (r"jalape[nñ]os?|chiles?", "辣椒"),
    (r"zucchini|squash", "西葫芦"), (r"mushrooms?", "蘑菇"), (r"cilantro", "香菜"), (r"garlic", "大蒜"), (r"ice cream", "冰淇淋"), (r"pizza", "披萨"), (r"chips", "薯片"),
    (r"cookies", "饼干"), (r"soda|coca-cola|pepsi|sprite|squirt|dr\.? pepper|7up|fanta|jarritos", "汽水"), (r"\bwater\b", "饮用水"), (r"juice", "果汁"), (r"coffee", "咖啡"), (r"beer", "啤酒"),
    (r"bath tissue|toilet paper", "卫生纸"), (r"paper towels?", "厨房纸巾"), (r"detergent", "洗衣液"), (r"diapers", "尿布"), (r"dog food", "狗粮"), (r"cat food", "猫粮"),
]
GLOSS = [(re.compile(r"\b(" + p + r")\b" if not p.startswith("\\b") else p, re.I), z) for p, z in GLOSS]


def gloss(name, cat):
    if cat not in FOOD and cat not in ("household", "baby", "pet"):
        return ""
    out, rest = [], name
    for rx, z in GLOSS:
        if rx.search(rest):
            rest = rx.sub(" ", rest)
            if z not in out:
                out.append(z)
        if len(out) >= 2:
            break
    return "、".join(out)


# ---------------------------------------------------------------- sale text → Chinese
def story_zh(s):
    if not s:
        return ""
    t = re.sub(r"\s+", " ", s).strip()
    rules = [
        (r"buy (\d+),? get (\d+)(?: of equal or lesser value)? free", lambda m: "买%s送%s" % (m.group(1), m.group(2))),
        (r"buy (\d+),? get (\d+) (\d+)% off", lambda m: ("第二件%s折" % fmt(10 - int(m.group(3)) / 10.0)) if m.group(1) == m.group(2) == "1" else "买%s件，再买%s件打%s折" % (m.group(1), m.group(2), fmt(10 - int(m.group(3)) / 10.0))),
        (r"buy one,? get one free|bogo free|b1g1 free", lambda m: "买一送一"),
        (r"buy one,? get one (\d+)% off|bogo (\d+)% off", lambda m: "第二件%s折" % fmt(10 - int(m.group(1) or m.group(2)) / 10.0)),
        (r"save \$(\d+(?:\.\d+)?)", lambda m: "省 $%s" % m.group(1)),
        (r"(\d+)% off", lambda m: "%s折" % fmt(10 - int(m.group(1)) / 10.0)),
        (r"digital coupon", lambda m: "需领电子券"),
        (r"with card", lambda m: "需会员卡"),
        (r"must buy (\d+)", lambda m: "需买%s件" % m.group(1)),
        (r"limit (\d+)", lambda m: "限购%s件" % m.group(1)),
        (r"rollback", lambda m: "Rollback 降价"),
        (r"clearance", lambda m: "清仓"),
        (r"mix (?:&|and) match", lambda m: "可混搭"),
    ]
    out, deal = [], False
    for n, (p, f) in enumerate(rules):
        if n == 5 and deal:  # plain "% off" only when no buy-x-get-y rule matched
            continue
        m = re.search(p, t, re.I)
        if m:
            if n < 4:
                if deal:
                    continue
                deal = True
            z = f(m)
            if z not in out:
                out.append(z)
    return "，".join(out)


# ---------------------------------------------------------------- weekly ads (Flipp)
def slug(name):
    return re.sub(r"[^a-z0-9]+", "", name.lower())[:16] or "store"


def store_of(merchant, flyer_cats):
    merchant = merchant.strip()
    if merchant in STORES:
        sid, grp, color, q, wk = STORES[merchant]
    else:
        grp = []
        for c in flyer_cats:
            g = FLIPP_GROUP.get(c)
            if g and g not in grp:
                grp.append(g)
        sid, color, q, wk = slug(merchant), None, None, None
        grp = grp or ["general"]
    return {"id": sid, "name": merchant, "grp": grp, "color": color, "q": q, "wk": wk}


def parse_flyer(store, flyer, raw_items, rich):
    grocery = "grocery" in store["grp"]
    items, seen, got_rich = [], set(), 0
    for it in raw_items:
        if it.get("display_type") != 1 or not it.get("name"):
            continue
        name = re.sub(r"\s+", " ", html.unescape(it["name"])).strip()
        if re.match(r"^\d{5,}-", name) or len(name) < 3:  # internal banner ids
            continue
        r = rich.get(it.get("id")) or {}
        if r:
            got_rich += 1
        price = money(r.get("current_price")) if r else None
        if price is None:
            price = money(it.get("price"))
        pre, post = (r.get("pre_price_text") or "").strip(), (r.get("post_price_text") or "").strip()
        flags, unit = [], ""
        if re.search(r"digital coupon", post, re.I):
            flags.append("需领电子券")
        if re.search(r"with card|member", post, re.I):
            flags.append("会员价")
        mb = re.search(r"when you buy (\d+)", post, re.I)
        if mb:
            flags.append("买%s件才是此价" % mb.group(1))
        mu = re.search(r"(?:^|\s|/)(ea|lb|lbs|oz|ct|pk)\b", post, re.I)
        if mu:
            unit = {"ea": "/个", "lb": "/磅", "lbs": "/磅", "oz": "/盎司", "ct": "/个", "pk": "/包"}[mu.group(1).lower()]
        pt = ""
        if price is not None and price > 0:
            pt = (pre if re.fullmatch(r"\d+/", pre or "") else "") + "$" + fmt(price) + unit
        elif price == 0:
            price = None
        story = (r.get("sale_story") or "").strip()
        if re.fullmatch(r"final (?:cost|price)", story, re.I):
            story = ""
        if not pt and not story:
            continue
        was = money(r.get("original_price"))
        off = it.get("discount") or (round((1 - price / was) * 100) if (price and was and was > price) else None)
        key = (name.lower(), pt)
        if key in seen:
            continue
        seen.add(key)
        c = classify(name, r.get("_L1"), r.get("_L2"), grocery=grocery)
        img = https(r.get("clean_image_url") or it.get("cutout_image_url"))
        m = re.match(r"https://f\.wishabi\.net/page_items/(\d+/\d+)/extra_large\.jpg$", img)
        x = {"n": name, "b": (it.get("brand") or "").split("|")[0].strip(), "p": price, "pt": pt, "was": was, "off": off,
             "st": story, "stz": "，".join([z for z in [story_zh(story)] + flags if z]), "c": c, "zh": gloss(name, c),
             "im": m.group(1) if m else img, "id": "fl%s" % it["id"]}
        if not r and pre == "" and price is not None:
            x["pq"] = 1  # price from the flyer only — may be "2 for" etc.; the page says "约"
        items.append({k: v for k, v in x.items() if v not in (None, "", 0) or k == "p"})
    return items, got_rich


def weekly_ads():
    now = dt.datetime.now(dt.timezone.utc)
    cache_path = os.path.join(DATA, "flyers.json")
    try:
        cache = json.load(open(cache_path, encoding="utf-8"))
        if cache.get("v") != V:
            cache = {"flyers": {}}
    except Exception:  # noqa: BLE001
        cache = {"flyers": {}}
    d = json.loads(get(f"https://flyers-ng.flippback.com/api/flipp/data?locale=en-us&postal_code={ZIP}&sid=8243957120"))
    want, by_merchant = {}, {}
    for f in d.get("flyers", []):
        try:
            vf = dt.datetime.fromisoformat(f["valid_from"]); vt = dt.datetime.fromisoformat(f["valid_to"])
        except Exception:  # noqa: BLE001
            continue
        if vt < now or vf > now + dt.timedelta(days=UPCOMING_DAYS):
            continue
        merchant = (f.get("merchant") or "").strip()
        if not merchant:
            continue
        cats = [c for c in (f.get("categories") or []) if c != "All Flyers"]
        st = store_of(merchant, cats)
        meta = {"s": st["id"], "name": (f.get("name") or "").strip(), "from": f["valid_from"][:10], "to": f["valid_to"][:10],
                "up": 1 if vf > now + dt.timedelta(hours=12) else 0}
        want[str(f["id"])] = meta
        by_merchant.setdefault(merchant, {"store": st, "logo": https(f.get("merchant_logo") or ""), "fids": []})["fids"].append(str(f["id"]))
    out, stats = {}, {}
    for merchant, m in by_merchant.items():
        todo = [fid for fid in m["fids"] if fid not in cache["flyers"]]
        rich = {}
        if todo:
            try:
                sres = json.loads(get(f"https://backflipp.wishabi.com/flipp/items/search?locale=en-us&postal_code={ZIP}&q={urllib.parse.quote(merchant)}"))
                for it in sres.get("items", []):
                    if (it.get("merchant_name") or "").strip().lower() == merchant.lower():
                        rich[it.get("flyer_item_id") or it.get("id")] = it
            except Exception as e:  # noqa: BLE001
                notes.append(f"{merchant} search: {str(e)[:80]}")
            time.sleep(1)
        for fid in m["fids"]:
            if fid in cache["flyers"]:
                out[fid] = dict(cache["flyers"][fid], **want[fid])
                continue
            try:
                raw = json.loads(get(f"https://backflipp.wishabi.com/flipp/flyers/{fid}?locale=en-us")).get("items", [])
            except Exception as e:  # noqa: BLE001
                notes.append(f"{merchant} flyer {fid}: {str(e)[:80]}")
                continue
            items, got = parse_flyer(m["store"], want[fid], raw, rich)
            stats[merchant + " · " + want[fid]["name"]] = "%d items, %d with full details" % (len(items), got)
            out[fid] = dict(want[fid], items=items)
            time.sleep(1)
    stores = {}
    for merchant, m in by_merchant.items():
        st = dict(m["store"])
        if m["logo"]:
            st["logo"] = m["logo"]
        st["n"] = sum(len(out[f]["items"]) for f in m["fids"] if f in out)
        if st["n"]:
            stores[st["id"]] = {k: v for k, v in st.items() if v not in (None, "", [])}
    out = {f: v for f, v in out.items() if v.get("items")}
    return out, stores, stats


# ---------------------------------------------------------------- RSS helpers
def rss_items(xml):
    return re.findall(r"<item\b.*?</item>", xml, re.S)


def tag(it, name):
    m = re.search(r"<%s\b[^>]*>(.*?)</%s>" % (re.escape(name), re.escape(name)), it, re.S)
    if not m:
        return ""
    v = m.group(1).strip()
    m2 = re.match(r"<!\[CDATA\[(.*)\]\]>$", v, re.S)
    return m2.group(1) if m2 else html.unescape(v)


def clean_text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def pub_iso(s):
    for f in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            d = dt.datetime.strptime(s.replace("PDT", "-0700").replace("PST", "-0800").replace("UTC", "+0000").replace("GMT", "+0000").strip(), f)
            return d.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:  # noqa: BLE001
            pass
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def first_price(t):
    m = re.search(r"\$\s?(\d{1,5}(?:,\d{3})*(?:\.\d{2})?)", t)
    return money(m.group(1).replace(",", "")) if m else None


def pct(t):
    m = re.search(r"(\d{1,2})%\s*off", t, re.I)
    return int(m.group(1)) if m else None


def sid_of(link, pat, pre, title):
    m = re.search(pat, link or "")
    return pre + (m.group(1) if m else hashlib.md5(title.encode("utf-8")).hexdigest()[:10])


FLAGS = [
    (r"\bS&?S\b|\bSnS\b|subscribe (?:&|and) save|sub\. ?& ?save", "订阅省"), (r"\bAC\b|apply coupon|clip coupon|w/ coupon|\bcoupon\b", "点券"),
    (r"\bprime members?\b|\[prime\]|w/ prime|prime day", "Prime 会员"), (r"select accounts", "部分账号"), (r"walmart\+", "Walmart+"),
    (r"free (?:shipping|s&h)", "包邮"), (r"new woot!? customers", "Woot 新客"), (r"\bYMMV\b", "因人而异"),
]
FLAGS = [(re.compile(p, re.I), z) for p, z in FLAGS]


def tidy(title):
    """'[SnS, AC] $9.35 | 10-Pack Nutter Butter at Amazon' → ('10-Pack Nutter Butter', ['订阅省', '点券'])"""
    flags = []
    for rx, z in FLAGS:
        if rx.search(title) and z not in flags:
            flags.append(z)
    t = title
    t = re.sub(r"^(?:\[[^\]]*\]\s*)+", "", t)
    t = re.sub(r"^(?:Amazon|Walmart)\s*[~:-]\s*", "", t, flags=re.I)
    t = re.sub(r"^(?:Prime Members|Select Accounts|New Woot!? Customers|Walmart\+ Members)\s*:\s*", "", t, flags=re.I)
    t = re.sub(r"^~?\$[\d,.]+\*?\s*[|:]\s*", "", t)
    t = re.sub(r"\s*(?:@|at)\s+(?:Amazon|Walmart|Woot!?)(?:\.com)?\b.*$", "", t, flags=re.I)
    t = re.sub(r"\s*Walmart\.com\s*$", "", t, flags=re.I)
    t = re.sub(r"\s*\+\s*Free (?:Shipping|S&H).*$", "", t, flags=re.I)
    t = re.sub(r"\s+for\s+\$[\d,.]+.*$", "", t)  # DealNews: 'X for $89 + free shipping'
    t = re.sub(r"\s*~?\$[\d,.]+\*?(?:\s*(?:w/|after\b|with\b).*)?$", "", t)  # trailing price
    t = re.sub(r"\s+", " ", t).strip(" -|~:")
    return (t or title), flags


def slickdeals(url, label):
    out = []
    for it in rss_items(get(url)):
        title = clean_text(tag(it, "title"))
        body = tag(it, "content:encoded") or tag(it, "description")
        slug = re.search(r'data-store-slug="([a-z0-9-]+)"', body)
        exitw = re.search(r'data-product-exitWebsite="([^"]+)"', body)
        store = (slug.group(1) if slug else "") + " " + (exitw.group(1) if exitw else "")
        low = (title + " " + store).lower()
        s = "amazon" if re.search(r"\bamazon\b|amazon\.com|\bwoot\b", store) or re.search(r"\bat amazon\b|\bamazon\b", title.lower()) else \
            "walmart" if re.search(r"\bwalmart\b", low) else None
        if not s:
            continue
        img = re.search(r'<img[^>]+src="([^"]+)"', body)
        score = re.search(r"Thumb Score:\s*([+-]?\d+)", body)
        p = first_price(title)
        name, fl = tidy(title)
        out.append({"s": s, "src": "sd", "n": name, "full": title, "fl": fl, "p": p, "pt": ("$" + fmt(p)) if p is not None else "", "off": pct(title),
                    "c": classify(title), "img": https(img.group(1)) if img else "", "u": tag(it, "link").split("?utm_")[0],
                    "t": pub_iso(tag(it, "pubDate")), "score": int(score.group(1)) if score else 0, "via": "Slickdeals", "tag": label,
                    "id": sid_of(tag(it, "link"), r"/f/(\d+)", "sd", title)})
    return out


def camel():
    out = []
    for it in rss_items(get("https://camelcamelcamel.com/top_drops/feed")):
        title = clean_text(tag(it, "title"))
        m = re.search(r"^(.*?) - down ([\d.]+)% \(\$([\d,.]+)\) to \$([\d,.]+) from \$([\d,.]+)", title)
        if not m:
            continue
        name = m.group(1).strip()
        p, was = money(m.group(4).replace(",", "")), money(m.group(5).replace(",", ""))
        out.append({"s": "amazon", "src": "camel", "n": name, "p": p, "pt": "$" + fmt(p), "was": was, "off": round(float(m.group(2))),
                    "c": classify(name), "zh": "", "img": "", "u": tag(it, "link"), "t": pub_iso(tag(it, "pubDate")),
                    "via": "camelcamelcamel", "tag": "降价榜", "id": "cc" + tag(it, "link").rstrip("/").split("/")[-1]})
    return out


def dealnews():
    out = []
    for it in rss_items(get("https://www.dealnews.com/?rss=1")):
        title = clean_text(tag(it, "title"))
        body = tag(it, "description")
        txt = clean_text(body)
        m = re.search(r"(?:Buy|Shop) Now at ([^.<]+?)(?:\s*$|\.|\s{2})", txt)
        where = (m.group(1) if m else "").lower()
        s = "amazon" if "amazon" in where or "woot" in where else "walmart" if "walmart" in where else None
        if not s:
            continue
        img = re.search(r"<img[^>]+src='([^']+)'", body) or re.search(r'<img[^>]+src="([^"]+)"', body)
        p = first_price(title)
        name, fl = tidy(title)
        out.append({"s": s, "src": "dn", "n": name, "full": title, "fl": fl, "p": p, "pt": ("$" + fmt(p)) if p is not None else "", "off": pct(title) or pct(txt),
                    "c": classify(title), "img": https(img.group(1)) if img else "", "u": tag(it, "link").split("?iref")[0],
                    "t": pub_iso(tag(it, "pubDate")), "via": "DealNews", "tag": "精选", "sum": txt[:220],
                    "id": sid_of(tag(it, "link"), r"/(\d+)\.html", "dn", title)})
    return out


# ---------------------------------------------------------------- main
def dump(path, doc):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    os.replace(tmp, path)


def main():
    now = dt.datetime.now(dt.timezone.utc)
    os.makedirs(DATA, exist_ok=True)
    flyers, stores, stats = {}, {}, {}
    try:
        flyers, stores, stats = weekly_ads()
    except Exception as e:  # noqa: BLE001
        notes.append(f"flipp: {str(e)[:120]}")
        try:  # keep last week's data rather than publishing nothing
            old = json.load(open(os.path.join(DATA, "flyers.json"), encoding="utf-8"))
            flyers = {k: v for k, v in old.get("flyers", {}).items() if v.get("to", "") >= now.strftime("%Y-%m-%d")}
            stores = json.load(open(os.path.join(DATA, "meta.json"), encoding="utf-8")).get("stores", {})
        except Exception:  # noqa: BLE001
            pass

    online = []
    for label, url in [
        ("热门", "https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&rss=1"),
        ("热门", "https://slickdeals.net/newsearch.php?mode=popdeals&searcharea=deals&searchin=first&rss=1"),
        ("搜索", "https://slickdeals.net/newsearch.php?q=amazon&searcharea=deals&searchin=first&rss=1"),
        ("搜索", "https://slickdeals.net/newsearch.php?q=walmart&searcharea=deals&searchin=first&rss=1"),
    ]:
        try:
            online += slickdeals(url, label)
        except Exception as e:  # noqa: BLE001
            notes.append(f"slickdeals: {str(e)[:80]}")
        time.sleep(1)
    for fn in (camel, dealnews):
        try:
            online += fn()
        except Exception as e:  # noqa: BLE001
            notes.append(f"{fn.__name__}: {str(e)[:80]}")
    try:  # keep recent online deals from the previous run
        old = json.load(open(os.path.join(DATA, "meta.json"), encoding="utf-8"))
        cutoff = (now - dt.timedelta(hours=KEEP_ONLINE_H)).strftime("%Y-%m-%dT%H:%M:%SZ")
        online += [x for x in old.get("online", []) if x.get("t", "") >= cutoff]
    except Exception:  # noqa: BLE001
        pass
    seen, merged = set(), []
    for x in online:
        k2 = re.sub(r"\W+", "", x["n"].lower())[:60]
        if x.get("id") in seen or k2 in seen:
            continue
        seen.add(x.get("id")); seen.add(k2)
        merged.append({k: v for k, v in x.items() if v not in (None, "", 0, []) or k == "p"})
    merged.sort(key=lambda x: x.get("t", ""), reverse=True)

    for sid, meta in ONLINE_META.items():
        n = sum(1 for x in merged if x["s"] == sid)
        if n:
            stores[sid] = dict(meta, id=sid, n=n)
    if "walmart" in stores:
        stores["walmart"]["n"] += sum(1 for x in merged if x["s"] == "walmart")
    elif any(x["s"] == "walmart" for x in merged):
        sid, grp, color, q, wk = STORES["Walmart"]
        stores["walmart"] = {"id": "walmart", "name": "Walmart", "grp": grp, "color": color, "q": q, "wk": wk,
                             "n": sum(1 for x in merged if x["s"] == "walmart")}

    dump(os.path.join(DATA, "flyers.json"), {"v": V, "zip": ZIP, "flyers": flyers})
    dump(os.path.join(DATA, "meta.json"), {
        "updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "zip": ZIP, "stores": stores, "online": merged,
        "groups": [{"k": k, "zh": z, "e": e} for k, z, e in GROUPS], "cats": [{"k": k, "zh": z, "e": e} for k, z, e in CATS],
        "notes": notes, "stats": stats,
    })
    old_latest = os.path.join(DATA, "latest.json")
    if os.path.exists(old_latest):
        os.remove(old_latest)
    nfl = sum(len(v["items"]) for v in flyers.values())
    print("flyers:", len(flyers), "stores:", len(stores), "flyer items:", nfl, "online:", len(merged))
    print("notes:", notes)
    for k, v in sorted(stats.items()):
        print("  ", k, "→", v)
    for fn in ("flyers.json", "meta.json"):
        print(fn, os.path.getsize(os.path.join(DATA, fn)) // 1024, "KB")


if __name__ == "__main__":
    main()
