import json, re, sys, requests
sys.path.insert(0, ".")
import scan
out = {}
db = json.load(open("data/db.json"))
# 1) Marktplaats : recherche brute + 4 fiches (pro 'a' et particulier 'm', BTW et marge)
r = scan.get(scan.MP_SEARCH, params=scan.mp_params("golf", 157, 0), headers={"Accept": "application/json", "Referer": "https://www.marktplaats.nl/"})
L = r.json().get("listings", [])
out["mp_ids_prefix"] = {p: sum(1 for x in L if str(x.get("itemId","")).startswith(p)) for p in "am"}
out["mp_search_keys"] = sorted({k for x in L for k in x})
out["mp_seller_samples"] = [x.get("sellerInformation") for x in L[:5]]
out["mp_search_sample_a"] = next((x for x in L if str(x.get("itemId","")).startswith("a")), None)
picks = [x["itemId"] for x in L if str(x.get("itemId","")).startswith("a")][:2] + [x["itemId"] for x in L if str(x.get("itemId","")).startswith("m")][:2]
out["mp_vip"] = {}
for iid in picks:
    v = scan.get(scan.MP_VIP.format(iid), method="POST", headers={"ecg-locale": "nl-NL", "Content-Type": "application/json", "Accept": "application/json"})
    try:
        j = v.json()
        core = j.get("adCore", {})
        out["mp_vip"][iid] = {"top_keys": list(j), "core_keys": list(core), "seller": j.get("sellerInformation"),
                              "carAttributes": core.get("carAttributes"), "price": core.get("price"),
                              "desc_btw": re.findall(r".{0,60}(?:btw|marge|BTW|Marge).{0,60}", str(core.get("description","")))[:6]}
    except Exception as e:
        out["mp_vip"][iid] = repr(e)
# 2) AutoScout24 : 3 fiches détail
as_items = [c for c in db.values() if c["source"] == "AutoScout24"][:3]
out["as"] = {}
for c in as_items:
    h = scan.get(c["url"], headers={"Accept": "text/html"})
    d = scan.next_data(h.text) if h is not None else None
    if not d:
        out["as"][c["url"]] = f"no next data, status {getattr(h,'status_code',None)}"; continue
    pp = d.get("props", {}).get("pageProps", {})
    keys = set()
    def walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                p = path + "." + k
                if re.search(r"vat|tax|btw|deduct|price|seller|equip|transmission|gear|description", k, re.I):
                    keys.add((p, str(v)[:120]))
                walk(v, p)
        elif isinstance(o, list):
            for v in o[:3]: walk(v, path + "[]")
    walk(pp)
    out["as"][c["url"]] = {"pp_keys": list(pp), "matches": sorted(keys)[:80]}
json.dump(out, open("probe.json", "w"), ensure_ascii=False, indent=1)
print("ok")
