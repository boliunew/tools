"""Build deals/data/latest.json for deals.html (打折雷达).

Sources (all public, fetched twice a day by GitHub Actions):
  * Flipp weekly-ad data for ZIP 91786 — Food 4 Less weekly ad and Walmart's own weekly flyer
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
OUT = os.path.join(ROOT, "deals", "data", "latest.json")
ZIP = "91786"  # Upland, CA
UA = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Mobile Safari/537.36"
KEEP_ONLINE_H = 72  # keep online deals this long across runs

# weekly-ad stores: id, Flipp merchant name, flyer-name filter (None = any), link template for "look it up"
FLYER_STORES = [
    ("f4l", "Food 4 Less", None, "https://www.food4less.com/search?query={q}"),
    ("walmart", "Walmart", None, "https://www.walmart.com/search?q={q}"),
]
STORE_META = {
    "f4l": {"name": "Food 4 Less", "icon": "🛒", "color": "#C8102E"},
    "walmart": {"name": "Walmart", "icon": "🟦", "color": "#0071DC"},
    "amazon": {"name": "Amazon", "icon": "📦", "color": "#FF9900"},
}
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
    ("electronics", r"\b(power station|docking station|pc case|ssd|apple (?:airpods|watch|ipad|iphone|macbook|tv|pencil)|tv|tvs|television|oled|qled|laptop|laptops|chromebook|macbook|tablet|ipad|iphone|android phone|smartphone|phone|headphones|earbuds|airpods|speaker|speakers|soundbar|monitor|camera|smart ?watch|apple watch|charger|charging|usb|cable|ssd|hard drive|microsd|router|wi-?fi|gaming|playstation|ps5|xbox|nintendo|switch 2|printer|kindle|echo|alexa|fire tv|roku|streaming|bluetooth|projector|gpu|graphics card|keyboard|mouse|power bank|batteries|drone|dash cam|electronics)\b"),
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
def flipp_flyers():
    d = json.loads(get(f"https://flyers-ng.flippback.com/api/flipp/data?locale=en-us&postal_code={ZIP}&sid=8243957120"))
    return d.get("flyers", [])


def flyer_items(store_id, merchant, name_filter, link_tpl, flyers):
    now = dt.datetime.now(dt.timezone.utc)
    mine = [f for f in flyers if (f.get("merchant") or "").strip().lower() == merchant.lower()
            and (not name_filter or re.search(name_filter, f.get("name") or "", re.I))]
    live = []
    for f in mine:
        try:
            vf = dt.datetime.fromisoformat(f["valid_from"]); vt = dt.datetime.fromisoformat(f["valid_to"])
        except Exception:  # noqa: BLE001
            continue
        if vf <= now + dt.timedelta(days=1) and vt >= now:
            live.append(f)
    if not live:
        notes.append(f"{merchant}: no current flyer")
        return [], []
    # rich fields (sale text, categories) come from item search; discount % from the flyer itself
    rich = {}
    try:
        s = json.loads(get(f"https://backflipp.wishabi.com/flipp/items/search?locale=en-us&postal_code={ZIP}&q={urllib.parse.quote(merchant)}"))
        for it in s.get("items", []):
            rich[it.get("flyer_item_id") or it.get("id")] = it
    except Exception as e:  # noqa: BLE001
        notes.append(f"{merchant} search: {e}")
    items, metas = [], []
    for f in live:
        try:
            d = json.loads(get(f"https://backflipp.wishabi.com/flipp/flyers/{f['id']}?locale=en-us"))
        except Exception as e:  # noqa: BLE001
            notes.append(f"{merchant} flyer {f['id']}: {e}")
            continue
        metas.append({"id": f["id"], "name": f.get("name"), "from": f["valid_from"][:10], "to": f["valid_to"][:10]})
        for it in d.get("items", []):
            if it.get("display_type") != 1 or not it.get("name"):
                continue
            r = rich.get(it.get("id"), {})
            name = re.sub(r"\s+", " ", html.unescape(it["name"])).strip()
            if re.match(r"^\d{5,}-", name):  # internal banner ids
                continue
            price = money(r.get("current_price")) if r else None
            if price is None:
                price = money(it.get("price"))
            pre, post = (r.get("pre_price_text") or "").strip(), (r.get("post_price_text") or "").strip()
            flags, unit = [], ""
            if re.search(r"digital coupon", post, re.I):
                flags.append("需领电子券")
            if re.search(r"with card", post, re.I):
                flags.append("会员卡价")
            mb = re.search(r"when you buy (\d+)", post, re.I)
            if mb:
                flags.append("买%s件才是此价" % mb.group(1))
            mu = re.search(r"(?:^|\s|/)(ea|lb|oz|ct|pk)\b", post, re.I)
            if mu:
                unit = {"ea": "/个", "lb": "/磅", "oz": "/盎司", "ct": "/个", "pk": "/包"}[mu.group(1).lower()]
            pt = ""
            if price is not None:
                pt = (pre if pre else "") + "$" + fmt(price) + unit
            story = (r.get("sale_story") or "").strip()
            if re.fullmatch(r"final cost", story, re.I):
                story = ""
            was = money(r.get("original_price"))
            off = it.get("discount") or (round((1 - price / was) * 100) if (price and was and was > price) else None)
            items.append({
                "s": store_id, "src": "flyer", "n": name, "b": (it.get("brand") or "").split("|")[0].strip(),
                "p": price, "pt": pt, "was": was, "off": off, "st": story, "stz": "，".join([z for z in [story_zh(story)] + flags if z]),
                "c": classify(name, r.get("_L1"), r.get("_L2"), grocery=(store_id == "f4l")), "zh": "",
                "img": https(r.get("clean_image_url") or it.get("cutout_image_url")),
                "u": link_tpl.format(q=urllib.parse.quote_plus(name)), "to": f["valid_to"][:10], "id": "fl%s" % it["id"],
            })
        time.sleep(1)
    for x in items:
        x["zh"] = gloss(x["n"], x["c"])
    return items, metas


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
    t = re.sub(r"\s*~?\$[\d,.]+\*?(?:\s*(?:w/|after|with)\b.*)?$", "", t)  # trailing price
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
def main():
    now = dt.datetime.now(dt.timezone.utc)
    items, flyers_meta = [], {}
    try:
        fl = flipp_flyers()
        for sid, merchant, nf, link in FLYER_STORES:
            try:
                its, metas = flyer_items(sid, merchant, nf, link, fl)
                items += its
                flyers_meta[sid] = metas
            except Exception as e:  # noqa: BLE001
                notes.append(f"{merchant}: {e}")
    except Exception as e:  # noqa: BLE001
        notes.append(f"flipp: {e}")

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
            notes.append(f"slickdeals {url[-60:]}: {e}")
        time.sleep(1)
    for fn in (camel, dealnews):
        try:
            online += fn()
        except Exception as e:  # noqa: BLE001
            notes.append(f"{fn.__name__}: {e}")

    # keep recent online deals from the previous run
    try:
        old = json.load(open(OUT, encoding="utf-8"))
        cutoff = (now - dt.timedelta(hours=KEEP_ONLINE_H)).strftime("%Y-%m-%dT%H:%M:%SZ")
        online += [x for x in old.get("items", []) if x.get("src") in ("sd", "camel", "dn") and x.get("t", "") >= cutoff]
    except Exception:  # noqa: BLE001
        pass
    seen, merged = set(), []
    for x in online:
        k = x["id"] if x.get("id") else re.sub(r"\W+", "", x["n"].lower())[:60]
        k2 = re.sub(r"\W+", "", x["n"].lower())[:60]
        if k in seen or k2 in seen:
            continue
        seen.add(k); seen.add(k2)
        merged.append(x)
    items += merged

    for x in items:
        for k in [k for k, v in x.items() if v in (None, "", 0) and k not in ("p",)]:
            del x[k]
    counts = {}
    for x in items:
        counts.setdefault(x["s"], {}).setdefault(x["c"], 0)
        counts[x["s"]][x["c"]] += 1
    doc = {
        "updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "zip": ZIP, "stores": STORE_META, "flyers": flyers_meta,
        "cats": [{"k": k, "zh": z, "e": e} for k, z, e in CATS], "items": items, "counts": counts, "notes": notes,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    by = {}
    for x in items:
        by[x["s"] + "/" + x.get("src", "")] = by.get(x["s"] + "/" + x.get("src", ""), 0) + 1
    print("deals:", by, "notes:", notes, os.path.getsize(OUT) // 1024, "KB")


if __name__ == "__main__":
    main()
