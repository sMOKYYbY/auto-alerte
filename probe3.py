import json, sys
sys.path.insert(0, ".")
import scan
scan.CONFIG["max_price_ht"] = 22000
db = json.load(open("data/db.json"))
for uid in json.load(open("probe_ids.json")):
    c = db[uid]
    if c["source"] == "Marktplaats":
        txt, flag = scan.mp_detail(c), None
    else:
        txt, flag = scan.as_detail(c)
    c["text"] = (c.get("text", "") + "\n" + (txt or ""))
    c["vat_flag"] = flag
    scan.evaluate(c)
    print("ROW", json.dumps({"p": c.get("price_ht"), "ttc": c.get("price"), "km": c.get("km"), "y": c.get("year"), "m": c["model"],
                             "st": c["status"], "tva": c["checks"].get("tva"), "int": c["checks"].get("interieur"),
                             "seller": c.get("seller_type"), "why": c.get("reasons"), "t": c["title"][:60], "u": c["url"]}, ensure_ascii=False))
    scan.pause()
