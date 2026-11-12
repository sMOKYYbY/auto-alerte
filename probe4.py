import json, re, sys
sys.path.insert(0, ".")
import scan
H = {"Accept": "application/json, text/plain, */*", "Referer": "https://www.2dehands.be/"}
p = scan.mp_params("golf", 157, 0, years=(2004, 2013))
r = scan.get("https://www.2dehands.be/lrp/api/search", params=p, headers=H)
print("2D search", r.status_code if r is not None else None)
d = r.json(); L = d.get("listings", [])
print("2D total", d.get("totalResultCount"), "page", len(L))
for x in L[:3]:
    print("  ", x.get("itemId"), x.get("title"), x.get("priceInfo"), x.get("vipUrl"), (x.get("location") or {}).get("cityName"),
          [(a.get("key"), a.get("value")) for a in (x.get("extendedAttributes") or [])][:8])
if L:
    iid = L[0]["itemId"]
    v = scan.get(f"https://app.2dehands.be/app/vip/v4/item/{iid}", method="POST",
                 headers={"ecg-locale": "nl-BE", "Content-Type": "application/json", "Accept": "application/json"})
    print("2D vip", v.status_code if v is not None else None)
    try:
        j = v.json(); core = j.get("adCore", {})
        print("  seller", j.get("sellerInformation", {}).get("type"), "| desc", str(core.get("description"))[:200].replace("\n", " "))
        print("  btw:", re.findall(r".{0,40}(?:btw|BTW|tva|TVA|marge|Marge).{0,60}", json.dumps(core, ensure_ascii=False))[:4])
    except Exception as e:
        print("  vip err", e, v.text[:200])
for base in ["https://www.autoscout24.be/nl/lst/volkswagen/golf", "https://www.autoscout24.be/lst/volkswagen/golf", "https://www.autoscout24.be/fr/lst/volkswagen/golf"]:
    prm = scan.as_params(1, years=(2004, 2013)); prm["cy"] = "B"
    r = scan.get(base, params=prm, headers={"Accept": "text/html"})
    nd = scan.next_data(r.text) if r is not None else None
    n = scan.as_listing_nodes(nd) if nd else []
    print("AS.be", base, r.status_code if r is not None else None, "final", r.url[:90] if r is not None else "", "nodes", len(n),
          "total", scan.values_for_keys(nd, ["numberOfResults"])[:1] if nd else None)
    if n:
        c = scan.as_parse(n[0], "golf"); print("   ", c["title"], c["price"], c["km"], c["year"], c["url"][:90]); break
