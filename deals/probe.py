"""One-off probe: which deal sources answer from GitHub Actions, and what do they look like."""
import json, re, time, urllib.request

UA = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Mobile Safari/537.36"
ZIP = "91786"
out = {}


def get(url, n=1800):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, text/xml, */*"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            b = r.read()
            return {"status": r.status, "type": r.headers.get("Content-Type"), "len": len(b), "head": b[:n].decode("utf-8", "replace")}, b
    except Exception as e:  # noqa: BLE001
        code = getattr(e, "code", None)
        return {"error": str(e)[:200], "status": code}, b""


URLS = {
    "flipp_flyers": f"https://backflipp.wishabi.com/flipp/flyers?locale=en-us&postal_code={ZIP}",
    "flipp_ng_data": f"https://flyers-ng.flippback.com/api/flipp/data?locale=en-us&postal_code={ZIP}&sid=8243957120",
    "flipp_search_f4l": f"https://backflipp.wishabi.com/flipp/items/search?locale=en-us&postal_code={ZIP}&q=food%204%20less",
    "flipp_search_chicken": f"https://backflipp.wishabi.com/flipp/items/search?locale=en-us&postal_code={ZIP}&q=chicken",
    "sd_frontpage": "https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&rss=1",
    "sd_pop": "https://slickdeals.net/newsearch.php?mode=popdeals&searcharea=deals&searchin=first&rss=1",
    "sd_walmart": "https://slickdeals.net/newsearch.php?q=walmart&searcharea=deals&searchin=first&rss=1",
    "sd_amazon": "https://slickdeals.net/newsearch.php?q=amazon&searcharea=deals&searchin=first&rss=1",
    "camel_drops": "https://camelcamelcamel.com/top_drops/feed",
    "dealnews": "https://www.dealnews.com/?rss=1",
}
bodies = {}
for k, u in URLS.items():
    out[k], bodies[k] = get(u)
    out[k]["url"] = u
    time.sleep(1)

# follow-up: find flyer ids (Food 4 Less, Walmart, …) and try the item endpoints
import traceback
flyers = []
try:
  _follow = True
  for k in ("flipp_ng_data", "flipp_flyers"):
      try:
          d = json.loads(bodies[k])
          fl = d.get("flyers") if isinstance(d, dict) else d
          if fl:
              flyers = fl
              out["flyer_source"] = k
              break
      except Exception:  # noqa: BLE001
          pass
  out["merchants"] = [{kk: f.get(kk) for kk in ("id", "merchant", "merchant_name", "name", "valid_from", "valid_to", "categories", "categories_csv", "merchant_id")} for f in flyers][:80]
  want = [f for f in flyers if re.search(r"food ?4 ?less|walmart", json.dumps(f), re.I)][:3]
  for f in want:
      fid = f.get("id")
      for k, u in {
          f"items_ng_{fid}": f"https://flyers-ng.flippback.com/api/flipp/flyers/{fid}/flyer_items?locale=en-us&sid=8243957120",
          f"items_back_{fid}": f"https://backflipp.wishabi.com/flipp/flyers/{fid}?locale=en-us",
      }.items():
          out[k], _ = get(u, 3000)
          out[k]["url"] = u
          time.sleep(1)

except Exception:  # noqa: BLE001
  out["follow_error"] = traceback.format_exc()[-1500:]
  try:
    out["flyers_type"] = str(type(flyers)) + " " + json.dumps(flyers)[:1500]
  except Exception:  # noqa: BLE001
    pass

import os
os.makedirs("deals/data", exist_ok=True)
json.dump(out, open("deals/data/probe.json", "w"), ensure_ascii=False, indent=1)
print("done")
