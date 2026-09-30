"""Build the SubLingo English-Chinese dictionary shards from ECDICT (MIT, github.com/skywind3000/ECDICT).

Usage: python3 scripts/build_dict.py /path/to/ecdict.csv
Output: dict/en/<prefix>.json  — {word: [phonetic, zh, en, tags, oxford3000, collins, exchange] | "@lemma"}
"""
import csv, json, os, re, sys
from collections import defaultdict

csv.field_size_limit(10 ** 8)
src = sys.argv[1]
out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dict", "en")
os.makedirs(out_dir, exist_ok=True)
WORD = re.compile(r"^[A-Za-z][A-Za-z'\-]*$")

def keep(row):
    frq, bnc = int(row["frq"] or 0), int(row["bnc"] or 0)
    return row["oxford"] == "1" or row["tag"] or row["collins"] not in ("", "0") or 0 < frq <= 50000 or 0 < bnc <= 50000

def clean_zh(s):
    lines = [l.strip() for l in s.replace("\\n", "\n").split("\n") if l.strip()]
    main = [l for l in lines if not l.startswith("[")]
    other = [l for l in lines if l.startswith("[")]
    lines = (main[:5] or other[:2])
    return "\n".join(l[:120] for l in lines)

def clean_en(s):
    lines = [l.strip() for l in s.replace("\\n", "\n").split("\n") if l.strip()]
    return "\n".join(l[:140] for l in lines[:3])

entries, forms = {}, {}
with open(src, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        w = row["word"]
        if not WORD.match(w) or not row["translation"] or not keep(row):
            continue
        k = w.lower()
        if k in entries and w != k:
            continue  # prefer lowercase headword
        entries[k] = [row["phonetic"], clean_zh(row["translation"]), clean_en(row["definition"]), row["tag"],
                      1 if row["oxford"] == "1" else 0, int(row["collins"] or 0), row["exchange"]]
        for part in (row["exchange"] or "").split("/"):
            if ":" in part:
                typ, val = part.split(":", 1)
                if typ in "pdi3sr t" and val and WORD.match(val):
                    forms.setdefault(val.lower(), k)

for form, base in forms.items():
    if form not in entries and form != base:
        entries[form] = "@" + base

shards = defaultdict(dict)
for k, v in entries.items():
    p = re.sub(r"[^a-z]", "_", k[:2].ljust(2, "_"))
    shards[p][k] = v
total = 0
for p, d in shards.items():
    s = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    total += len(s.encode())
    with open(os.path.join(out_dir, p + ".json"), "w", encoding="utf-8") as f:
        f.write(s)
print(len(entries), "entries,", len(shards), "shards,", total // 1024, "KB")
