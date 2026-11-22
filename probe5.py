import json, re, sys, statistics as st
sys.path.insert(0, ".")
import scan
scan.CONFIG["models"]["polo6"]["budget"] = 60000          # pas de plafond pour cette étude
rows = []
for site in scan.MP_SITES:
    res, ok = scan.mp_search(10, site) if False else ([], True)
# requêtes Polo seulement
scan.MP_QUERIES = [("polo", "polo", 157)]
scan.AS_QUERIES = [("polo", "/lst/volkswagen/polo")]
for site in scan.MP_SITES:
    r, ok = scan.mp_search(10, site); rows += r
for site in scan.AS_SITES:
    r, ok = scan.as_search(10, site); rows += r
seen = {}
for c in rows:
    seen[c["uid"]] = c
cands = []
for c in seen.values():
    t = c["title"] + " " + (c.get("text") or "")
    trans = c.get("transmission") or ""
    auto = bool(scan.AUTO_FIELD.search(trans)) if trans else bool(scan.AUTO.search(t))
    if not auto or not scan.ROOF.search(t) or not c.get("price") or c["price"] < 3000: continue
    if scan.MODELS["polo6"]["exclude"].search(c["title"]): continue
    if not c.get("year") or c["year"] < 2017: continue
    cands.append(c)
print("Polo 6 DSG + toit (titre/résumé), toutes années, sans plafond:", len(cands))
by = {}
for c in cands: by.setdefault(c["year"], []).append(c["price"])
for y in sorted(by): print(" ", y, "n=", len(by[y]), "min", min(by[y]), "médiane", int(st.median(by[y])))
for c in sorted(cands, key=lambda c: c["price"])[:12]:
    print(f"   {c['price']:>6} {c.get('km') or 0:>7} {c['year']} {c.get('country')} {c['source']:<14} {c['title'][:60]}")
