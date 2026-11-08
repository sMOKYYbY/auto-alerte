import json, sys
sys.path.insert(0, ".")
import scan
db = json.load(open("data/db.json"))
as_ids = {c["id"] for c in db.values() if c["source"] == "AutoScout24"}
for model, path in [("golf", "/aanbod/volkswagen/golf"), ("a3", "/aanbod/audi/a3")]:
    for params in [scan.as_params(1), {**scan.as_params(1), "fregfrom": None}]:
        p = {k: v for k, v in params.items() if v is not None}
        r = scan.get("https://www.autotrack.nl" + path, params=p, headers={"Accept": "text/html"})
        d = scan.next_data(r.text) if r is not None else None
        if not d:
            print(model, "no data", getattr(r, "status_code", None)); continue
        pp = d["props"]["pageProps"]
        L = pp.get("listings", [])
        ids = [x["id"] for x in L]
        print(model, r.url[:160])
        print("   numberOfResults", pp.get("numberOfResults"), "page", len(L), "overlap with AS24 db:", sum(i in as_ids for i in ids))
        for x in L[:4]:
            t = x.get("tracking", {})
            print("   ", x["id"], x.get("url"), t.get("price"), t.get("mileage"), t.get("firstRegistration"),
                  (x.get("vehicle") or {}).get("modelVersionInput"), "| seller:", (x.get("seller") or {}).get("type"),
                  "| price:", json.dumps(x.get("price"))[:150])
        break
