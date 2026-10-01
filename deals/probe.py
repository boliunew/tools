"""Probe 2: full field samples for flyer items and feed items."""
import json, os, re, time, urllib.request

UA = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Mobile Safari/537.36"
out = {}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return "ERR " + str(e)


try:
    s = json.loads(get("https://backflipp.wishabi.com/flipp/items/search?locale=en-us&postal_code=91786&q=food%204%20less"))
    out["search_keys"] = list(s.keys())
    out["search_items_n"] = len(s.get("items", []))
    out["search_items"] = s.get("items", [])[:4]
    out["search_facets"] = s.get("facets")
    out["search_merchants"] = s.get("merchants", [])[:3]
except Exception as e:  # noqa: BLE001
    out["search_err"] = str(e)
for fid in (8157097, 8168650):
    try:
        d = json.loads(get(f"https://backflipp.wishabi.com/flipp/flyers/{fid}?locale=en-us"))
        its = d.get("items", [])
        out[f"flyer_{fid}_keys"] = list(d.keys())
        out[f"flyer_{fid}_n"] = len(its)
        out[f"flyer_{fid}_types"] = {str(t): sum(1 for i in its if i.get("display_type") == t) for t in set(i.get("display_type") for i in its)}
        out[f"flyer_{fid}_items"] = [i for i in its if i.get("display_type") == 1][:5]
        out[f"flyer_{fid}_meta"] = {k: v for k, v in d.items() if k != "items" and not isinstance(v, (list, dict))}
    except Exception as e:  # noqa: BLE001
        out[f"flyer_{fid}_err"] = str(e)
    time.sleep(1)
for k, u in {"sd": "https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&rss=1",
             "camel": "https://camelcamelcamel.com/top_drops/feed",
             "dealnews": "https://www.dealnews.com/?rss=1"}.items():
    x = get(u)
    items = re.findall(r"<item>.*?</item>", x, re.S)
    out[k + "_n"] = len(items)
    out[k + "_items"] = [i[:2500] for i in items[:3]]
    time.sleep(1)
os.makedirs("deals/data", exist_ok=True)
json.dump(out, open("deals/data/probe.json", "w"), ensure_ascii=False, indent=1)
print("done")
