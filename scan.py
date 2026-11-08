#!/usr/bin/env python3
"""
Auto-alerte NL : Golf 7.5 R-Line / Audi A3 8V2 S line
- automatique, toit ouvrant, intérieur R-Line / S line, TVA récupérable (BTW verrekenbaar)
- sources : Marktplaats.nl + AutoScout24.nl
- base complète dans docs/listings.json (+ CSV) affichée par docs/index.html (GitHub Pages)
- notification WhatsApp (CallMeBot) à chaque nouvelle annonce qui correspond

Usage :  python scan.py            (scan normal)
         python scan.py --full     (force un balayage complet)
         python scan.py --dry-run  (n'envoie aucun WhatsApp)
"""
from __future__ import annotations

import csv
import json
import os
import random
import re
import statistics
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
DATA = ROOT / "data"
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8"})

NOW = datetime.now(timezone.utc)
NOW_ISO = NOW.isoformat(timespec="seconds")


def log(*a):
    print(f"[{datetime.now().strftime('%H:%M:%S')}]", *a, flush=True)


def pause():
    lo, hi = CONFIG.get("request_delay_sec", [1.5, 3.5])
    time.sleep(random.uniform(lo, hi))


def get(url, *, params=None, headers=None, method="GET", tries=3):
    for attempt in range(tries):
        try:
            r = SESSION.request(method, url, params=params, headers=headers, timeout=30)
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(5 * (attempt + 1))
                continue
            return r
        except requests.RequestException as e:
            log("  réseau:", e)
            time.sleep(5 * (attempt + 1))
    return None


def to_int(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    d = re.sub(r"[^\d]", "", str(v))
    return int(d) if d else None


def find_all(obj, pred, out=None):
    """Parcourt récursivement un JSON et renvoie les noeuds qui satisfont pred."""
    if out is None:
        out = []
    if pred(obj):
        out.append(obj)
    if isinstance(obj, dict):
        for v in obj.values():
            find_all(v, pred, out)
    elif isinstance(obj, list):
        for v in obj:
            find_all(v, pred, out)
    return out


def values_for_keys(obj, keys):
    """Toutes les valeurs dont la clé (insensible à la casse) est dans keys."""
    keys = {k.lower() for k in keys}
    out = []
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k.lower() in keys:
                    out.append(v)
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(obj)
    return out


def strip_html(s: str) -> str:
    s = re.sub(r"<br\s*/?>|</p>|</li>", "\n", s, flags=re.I)
    return re.sub(r"<[^>]+>", " ", s)


# --------------------------------------------------------------------------
# Règles de correspondance
# --------------------------------------------------------------------------
RX = lambda p: re.compile(p, re.I)

ROOF = RX(r"panorama(?![\s-]*(?:camera|view|beeld|monitor))|\bpano\b|panodak|schuif[\s/-]*(?:kantel)?[\s-]*dak|schuifdak|kanteldak|"
          r"open\s*dak|glazen\s*(?:schuif)?dak|zonnedak|sunroof|toit ouvrant|schiebedach")
AUTO = RX(r"\bdsg\b|s[\s-]?tronic|\bautomaat\b|\bautomatic\b|\bautomatique\b|tiptronic|\baut\b")
AUTO_FIELD = RX(r"autom|dsg|tronic")
MANUAL = RX(r"handgeschakeld|\bhandbak\b|manual|manuel")

VAT_YES = RX(r"btw[^\n.]{0,40}verrekenbaar|verrekenbaar[^\n.]{0,20}btw|btw[\s-]*auto\b|"
             r"excl\.?\s*btw|ex\.?\s*btw|btw\s*/\s*marge\s*:?\s*btw\b|btw\s*:\s*verrekenbaar|"
             r"vat\s*deductible|tva\s*r[ée]cup[ée]rable")
VAT_NO = RX(r"btw\s*/\s*marge\s*:?\s*marge|\bmargeauto\b|marge\s*auto|btw\s*niet\s*(?:verrekenbaar|aftrekbaar)|"
            r"niet\s*btw[\s-]*verrekenbaar|\(marge\)|prijs\s*is\s*marge|marge[\s-]*regeling")
VAT_FIELD = RX(r"btw\s*/\s*marge\s*:?\s*([^\n]{1,60})")
EXCL_PRICE = [
    RX(r"(?:prijs\s*)?excl\.?\s*btw\s*[:\-]?\s*€?\s*([\d.]{4,7})"),
    RX(r"€\s*([\d.]{4,7}),?-?\s*(?:excl\.?|ex\.?)\s*btw"),
    RX(r"([\d.]{4,7}),?-?\s*(?:euro\s*)?excl\.?\s*btw"),
]

MODELS = {
    "golf": {
        "label": "VW Golf 7.5 R-Line",
        "is_model": RX(r"\bgolf\b"),
        "exclude": RX(r"sportsvan|golf\s*plus|alltrack|\bgti\b|\bgtd\b|\bgte\b|e[\s-]?golf|"
                      r"golf\s+r(?![\s-]*line)\b|\betsi\b|golf\s*8\b|golf\s*viii|\bmk\s*8\b"),
        "variant": RX(r"variant|break|estate"),
        "trim": RX(r"r[\s-]?line|business\s*r\b|\bhighline\s*r\b"),
        "interior_yes": RX(
            r"r[\s-]?line\s*(?:interieur|interior|int\.|binnen)|"
            r"(?:in[\s-]*(?:en|&|/|\+)\s*ex|interieur\s*(?:en|&|/|\+)\s*exterieur|binnen\s*en\s*buiten)[^\n]{0,15}r[\s-]?line|"
            r"r[\s-]?line[^\n]{0,15}(?:in[\s-]*(?:en|&|/|\+)\s*ex|interieur\s*(?:en|&|/|\+)\s*exterieur|binnen\s*en\s*buiten)|"
            r"\b3\s*x\s*r[\s-]?line|r[\s-]?line\s*(?:sport)?\s*pakket[^\n]{0,30}interieur|"
            r"sportstoelen\s*(?:\"|')?r[\s-]?line|r[\s-]?line[\s-]*(?:sport)?(?:stoelen|zetels|kuipstoelen|bekleding|seats)|"
            r"stoelbekleding[^\n]{0,20}r[\s-]?line|r[\s-]?line\s*alcantara"),
        "interior_ext_only": RX(r"r[\s-]?line\s*(?:exterieur|exterior|ext\.|buiten|styling|look)"),
        "gen_sure": RX(r"\b7\.5\b|\bvii\.?5\b|1\.5\s*tsi|active\s*info\s*display|digital(?:e)?\s*cockpit|virtual|"
                       r"discover\s*pro|composition\s*media"),
        "gen_wrong": RX(r"\betsi\b|golf\s*8\b|golf\s*viii|\bmk\s*8\b"),
    },
    "a3": {
        "label": "Audi A3 8V2 S line",
        "is_model": RX(r"\ba3\b"),
        "exclude": RX(r"\bs3\b|\brs\s?3\b|cabrio|\b8y\b|\be[\s-]?tron\s*40\b|\b40\s*tfsi\s*e\b|\b45\s*tfsi\s*e\b"),
        "variant": RX(r"$^"),
        "trim": RX(r"s[\s-]?line|pro\s*line\s*s\b|sport\s*s\b"),
        "interior_yes": RX(
            r"s[\s-]?line\s*(?:interieur|interior|int\.|binnen)|"
            r"(?:in[\s-]*(?:en|&|/|\+)\s*ex|interieur\s*(?:en|&|/|\+)\s*exterieur|binnen\s*en\s*buiten)[^\n]{0,15}s[\s-]?line|"
            r"s[\s-]?line[^\n]{0,15}(?:in[\s-]*(?:en|&|/|\+)\s*ex|interieur\s*(?:en|&|/|\+)\s*exterieur|binnen\s*en\s*buiten)|"
            r"\b3\s*x\s*s[\s-]?line|s[\s-]?line\s*sport\s*pa(?:kket|ckage)|sportpakket\s*s[\s-]?line|"
            r"sportstoelen\s*(?:\"|')?s[\s-]?line|s[\s-]?line[\s-]*(?:sport)?(?:stoelen|zetels|kuipstoelen|bekleding|seats)|"
            r"stoelbekleding[^\n]{0,20}s[\s-]?line|s[\s-]?line\s*(?:alcantara|leder|leer)"),
        "interior_ext_only": RX(r"s[\s-]?line\s*(?:exterieur|exterior|ext\.|buiten|styling|look)"),
        "gen_sure": RX(r"\b8v\b|\b8v2\b|facelift|virtual\s*cockpit|\b35\s*tfsi\b|\b30\s*tfsi\b|1\.5\s*tfsi|1\.0\s*tfsi|"
                       r"\b30\s*tdi\b|\b35\s*tdi\b"),
        "gen_wrong": RX(r"\b8y\b"),
    },
}


def detect_model(title: str):
    t = title.lower()
    for key, m in MODELS.items():
        if m["is_model"].search(t):
            return key
    return None


def evaluate(c: dict) -> dict:
    """Ajoute à c : checks, status ('match' | 'a_verifier' | 'rejete'), reasons, price_ht."""
    title = c.get("title", "")
    model = c.get("model") or detect_model(title)
    if model and not MODELS[model]["is_model"].search(title):
        model = None
    c["model"] = model or c.get("model")
    blob = "\n".join([title, c.get("text", "")])
    reasons, warn = [], []

    if not model:
        c.update(status="rejete", reasons=["modèle"], checks={})
        return c
    m = MODELS[model]

    # Prix HT
    price = c.get("price")
    price_ht = None
    for rx in EXCL_PRICE:
        mm = rx.search(blob)
        if mm:
            v = to_int(mm.group(1))
            if v and 2000 < v < 100000 and (not price or v <= price):
                price_ht = v
                break
    if price_ht is None and price:
        price_ht = round(price / (1 + CONFIG["vat_rate"]))
    c["price_ht"] = price_ht

    checks = {}
    # Génération / modèle exact
    if m["exclude"].search(title) or m["gen_wrong"].search(blob):
        reasons.append("autre version/génération")
    if model == "golf" and not CONFIG.get("include_variant", True) and m["variant"].search(title):
        reasons.append("Variant exclue")
    year = c.get("year")
    if year is None:
        warn.append("année inconnue")
    elif year < CONFIG["year_min"] or year > CONFIG["year_max"]:
        reasons.append(f"année {year}")
    else:
        gen_ok = bool(m["gen_sure"].search(blob))
        edge = (model == "golf" and year == 2017) or year == 2020
        if edge and not gen_ok:
            warn.append("vérifier génération (restylée ?)")
    checks["generation"] = "non" if "autre version/génération" in reasons else "ok"

    # Km
    km = c.get("km")
    if km is None:
        warn.append("km inconnu")
    elif km > CONFIG["max_km"]:
        reasons.append(f"{km:,} km".replace(",", "."))

    # Prix
    if not price_ht:
        reasons.append("prix inconnu")
    elif (c.get("price") or 0) < 3000:
        reasons.append("prix anormal (pièces/jantes ?)")
    elif price_ht > CONFIG["max_price_ht"]:
        reasons.append(f"{price_ht:,} € HT".replace(",", "."))

    # Boîte auto
    trans = (c.get("transmission") or "").lower()
    if trans:
        is_auto = bool(AUTO_FIELD.search(trans)) and not MANUAL.search(trans)
    else:
        is_auto = bool(AUTO.search(blob)) and not MANUAL.search(title)
    checks["auto"] = "oui" if is_auto else "non"
    if not is_auto:
        reasons.append("pas automatique")

    # Toit ouvrant
    roof = bool(ROOF.search(blob))
    checks["toit"] = "oui" if roof else "non"
    if not roof:
        reasons.append("pas de toit ouvrant")

    # Intérieur R-Line / S line
    if m["interior_yes"].search(blob):
        checks["interieur"] = "confirmé"
    elif m["trim"].search(blob):
        if m["interior_ext_only"].search(blob):
            checks["interieur"] = "extérieur seul ?"
            warn.append("intérieur à confirmer")
        else:
            checks["interieur"] = "probable"
            if not CONFIG.get("interior_probable_ok"):
                warn.append("intérieur à confirmer")
    else:
        checks["interieur"] = "non"
        reasons.append("pas R-Line/S line")

    # TVA
    vat_flag = c.get("vat_flag")  # bool structuré de la source, sinon None
    if vat_flag is None:
        fm = VAT_FIELD.search(blob)
        if fm:
            val = fm.group(1).lower()
            if re.search(r"niet|marge", val):
                vat_flag = False
            elif re.search(r"btw|verrekenbaar|aftrekbaar|ja\b", val):
                vat_flag = True
    if c.get("seller_type") == "particulier":
        checks["tva"] = "particulier"
        reasons.append("vendeur particulier (pas de TVA)")
    elif vat_flag is True or (vat_flag is None and VAT_YES.search(blob) and not VAT_NO.search(blob)):
        checks["tva"] = "récupérable"
    elif vat_flag is False or VAT_NO.search(blob):
        checks["tva"] = "marge"
        reasons.append("TVA non récupérable (marge)")
    else:
        checks["tva"] = "non indiqué"
        warn.append("TVA à confirmer")

    c["checks"] = checks
    c["reasons"] = reasons
    c["warnings"] = warn
    if reasons:
        c["status"] = "rejete"
    elif warn:
        c["status"] = "a_verifier"
    else:
        c["status"] = "match"
    return c


# --------------------------------------------------------------------------
# Source 1 : Marktplaats (API JSON du site)
# --------------------------------------------------------------------------
MP_SEARCH = "https://www.marktplaats.nl/lrp/api/search"
MP_VIP = "https://app.marktplaats.nl/app/vip/v4/item/{}"
MP_QUERIES = [("golf", "golf", 157), ("a3", "a3", 93)]  # (modèle, requête, l2CategoryId)


def mp_params(query, l2, offset, limit=100):
    max_incl = int(CONFIG["max_price_ht"] * (1 + CONFIG["vat_rate"]) * 1.02)
    return [
        ("query", query), ("limit", str(limit)), ("offset", str(offset)),
        ("searchInTitleAndDescription", "true"), ("viewOptions", "list-view"),
        ("sortBy", "SORT_INDEX"), ("sortOrder", "DECREASING"),
        ("l1CategoryId", "91"), ("l2CategoryIds[]", str(l2)),
        ("attributeRanges[]", f"constructionYear:{CONFIG['year_min']}:{CONFIG['year_max']}"),
        ("attributeRanges[]", f"mileage::{CONFIG['max_km']}"),
        ("attributeRanges[]", f"PriceCents::{max_incl * 100}"),
    ]


def mp_attrs(raw):
    out = {}
    for a in (raw.get("attributes") or []) + (raw.get("extendedAttributes") or []):
        if isinstance(a, dict) and a.get("key"):
            v = a.get("value")
            if v is None and a.get("values"):
                v = ", ".join(map(str, a["values"]))
            out.setdefault(a["key"], v)
    return out


def mp_parse(raw, model):
    item_id = str(raw.get("itemId", ""))
    if not item_id:
        return None
    attrs = mp_attrs(raw)
    pi = raw.get("priceInfo") or {}
    cents = pi.get("priceCents") or 0
    vip = raw.get("vipUrl")
    trans = attrs.get("transmission") or attrs.get("transmissionType") or ""
    return {
        "uid": f"mp:{item_id}", "source": "Marktplaats", "id": item_id, "model": model,
        "title": str(raw.get("title", "")),
        "url": f"https://www.marktplaats.nl{vip}" if vip else f"https://link.marktplaats.nl/{item_id}",
        "price": cents // 100 if cents else None,
        "km": to_int(attrs.get("mileage")),
        "year": to_int(attrs.get("constructionYear")),
        "transmission": str(trans),
        "city": (raw.get("location") or {}).get("cityName"),
        "seller": (raw.get("sellerInformation") or {}).get("sellerName"),
        "text": " ".join(str(x) for x in [raw.get("categorySpecificDescription") or raw.get("description") or "",
                                          json.dumps(attrs, ensure_ascii=False)]),
        "image": ("https:" + raw["imageUrls"][0]) if raw.get("imageUrls") and str(raw["imageUrls"][0]).startswith("//") else None,
    }


def mp_search(pages):
    results, ok = [], True
    for model, query, l2 in MP_QUERIES:
        for page in range(pages):
            r = get(MP_SEARCH, params=mp_params(query, l2, page * 100),
                    headers={"Accept": "application/json, text/plain, */*",
                             "Referer": "https://www.marktplaats.nl/", "Sec-Fetch-Mode": "cors",
                             "Sec-Fetch-Site": "same-origin"})
            if r is None or r.status_code != 200:
                log(f"  Marktplaats {query} p{page}: HTTP {getattr(r, 'status_code', 'ERR')}")
                ok = False
                break
            try:
                data = r.json()
            except ValueError:
                log("  Marktplaats: réponse non JSON"); ok = False; break
            items = data.get("listings") or []
            for raw in items:
                p = mp_parse(raw, model)
                if p:
                    results.append(p)
            log(f"  Marktplaats {query} p{page}: {len(items)} annonces (total site {data.get('totalResultCount')})")
            if len(items) < 100:
                break
            pause()
    return results, ok


def mp_detail(c):
    r = get(MP_VIP.format(c["id"]), method="POST",
            headers={"ecg-locale": "nl-NL", "Content-Type": "application/json",
                     "Accept": "application/json"})
    if r is not None and r.status_code == 200:
        try:
            j = r.json()
            core = j.get("adCore") or {}
            parts = [strip_html(str(core.get("description") or ""))]
            for grp in core.get("carAttributes") or []:
                parts.append(json.dumps(grp, ensure_ascii=False))
            parts.append(json.dumps(core.get("attributes") or [], ensure_ascii=False))
            stype = str((j.get("sellerInformation") or {}).get("type") or "").upper()
            c["seller_type"] = "pro" if stype == "TRADER" else ("particulier" if stype else None)
            return "\n".join(parts)
        except ValueError:
            pass
    # repli : page HTML de l'annonce
    r = get(c["url"], headers={"Accept": "text/html"})
    if r is not None and r.status_code == 200:
        m = re.search(r'<div[^>]+(?:Description|description)[^>]*>(.*?)</div>\s*</div>', r.text, re.S)
        return strip_html(m.group(1) if m else r.text)[:20000]
    return None


# --------------------------------------------------------------------------
# Source 2 : AutoScout24.nl (JSON __NEXT_DATA__ des pages)
# --------------------------------------------------------------------------
AS_BASE = "https://www.autoscout24.nl"
AS_QUERIES = [("golf", "/lst/volkswagen/golf"), ("a3", "/lst/audi/a3")]
NEXT_RX = re.compile(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def as_params(page):
    max_incl = int(CONFIG["max_price_ht"] * (1 + CONFIG["vat_rate"]) * 1.02)
    return {"atype": "C", "cy": "NL", "ustate": "N,U", "damaged_listing": "exclude",
            "fregfrom": CONFIG["year_min"], "fregto": CONFIG["year_max"],
            "kmto": CONFIG["max_km"], "priceto": max_incl, "gear": "A",
            "sort": "age", "desc": "1", "page": page}


def next_data(html):
    m = NEXT_RX.search(html or "")
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


def as_listing_nodes(data):
    """Repère la liste d'annonces dans __NEXT_DATA__ sans dépendre d'un chemin fixe."""
    pp = (data.get("props") or {}).get("pageProps") or {}
    if isinstance(pp.get("listings"), list):
        return pp["listings"]
    lists = find_all(data, lambda o: isinstance(o, list) and o and isinstance(o[0], dict)
                     and "id" in o[0] and ("price" in o[0] or "tracking" in o[0]) and "url" in o[0])
    return max(lists, key=len) if lists else []


def as_parse(node, model):
    lid = str(node.get("id") or "")
    if not lid:
        return None
    veh = node.get("vehicle") or {}
    trk = node.get("tracking") or {}
    pr = node.get("price") or {}
    title = " ".join(str(x) for x in [veh.get("make"), veh.get("model"),
                                      veh.get("modelVersionInput") or veh.get("variant") or veh.get("subtitle")] if x)
    price = to_int(trk.get("price")) or to_int(pr.get("priceFormatted") if isinstance(pr, dict) else pr)
    km = to_int(trk.get("mileage")) or to_int(veh.get("mileageInKm"))
    fr = str(trk.get("firstRegistration") or node.get("firstRegistration") or "")
    ym = re.search(r"(19|20)\d{2}", fr)
    details = " | ".join(str(d.get("data")) for d in node.get("vehicleDetails") or [] if isinstance(d, dict))
    url = node.get("url") or ""
    loc = node.get("location") or {}
    img = (node.get("images") or [None])[0]
    return {
        "uid": f"as:{lid}", "source": "AutoScout24", "id": lid, "model": model,
        "title": title or str(node.get("title") or ""),
        "url": url if url.startswith("http") else AS_BASE + url,
        "price": price, "km": km,
        "year": int(ym.group(0)) if ym else None, "first_reg": fr or None,
        "transmission": str(veh.get("transmission") or ""),
        "city": loc.get("city"),
        "seller": (node.get("seller") or {}).get("companyName"),
        "text": details,
        "image": img if isinstance(img, str) else None,
    }


def as_search(pages):
    results, ok = [], True
    for model, path in AS_QUERIES:
        for page in range(1, pages + 1):
            r = get(AS_BASE + path, params=as_params(page), headers={"Accept": "text/html"})
            if r is None or r.status_code != 200:
                log(f"  AutoScout24 {model} p{page}: HTTP {getattr(r, 'status_code', 'ERR')}")
                ok = False
                break
            data = next_data(r.text)
            if not data:
                log("  AutoScout24: __NEXT_DATA__ introuvable (page bloquée ?)"); ok = False; break
            nodes = as_listing_nodes(data)
            for n in nodes:
                p = as_parse(n, model)
                if p:
                    results.append(p)
            total = values_for_keys(data, ["numberOfResults", "totalResults"])
            log(f"  AutoScout24 {model} p{page}: {len(nodes)} annonces (total site {total[:1]})")
            if len(nodes) < 15:
                break
            pause()
    return results, ok


def as_detail(c):
    r = get(c["url"], headers={"Accept": "text/html"})
    if r is None or r.status_code != 200:
        return None, None
    data = next_data(r.text)
    if not data:
        return strip_html(r.text)[:20000], None
    pp = (data.get("props") or {}).get("pageProps") or {}
    det = pp.get("listingDetails") or pp
    descs = [v for v in values_for_keys(det, ["description"]) if isinstance(v, str)]
    parts = [strip_html(max(descs, key=len))] if descs else []
    for eq in values_for_keys(det, ["equipment"]):
        parts.append(json.dumps(eq, ensure_ascii=False))
    for v in values_for_keys(det, ["modelVersionInput", "transmission", "transmissionType", "gearbox"]):
        parts.append(str(v))
    flags = [v for v in values_for_keys(det, ["taxDeductible", "vatDeductible", "isVatDeductible"])
             if isinstance(v, bool)]
    vat_flag = True if True in flags else (False if flags else None)
    seller = det.get("seller") or {}
    if isinstance(seller.get("isDealer"), bool):
        c["seller_type"] = "pro" if seller["isDealer"] else "particulier"
    return "\n".join(parts), vat_flag


# --------------------------------------------------------------------------
# Base, état, déduplication, score "bonne affaire"
# --------------------------------------------------------------------------
def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return default


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def dedup_key(c):
    if not (c.get("km") and c.get("price")):
        return None
    return f"{c.get('model')}|{c.get('year')}|{round(c['km'] / 1000)}|{round(c['price'] / 250)}"


def add_deal_scores(db):
    """Écart du prix HT vs médiane des annonces comparables (même modèle et année)."""
    groups = {}
    for c in db.values():
        if c.get("price_ht") and c.get("year") and c.get("checks", {}).get("generation") == "ok" \
                and not c.get("gone"):
            groups.setdefault((c["model"], c["year"]), []).append(c["price_ht"])
    for c in db.values():
        g = groups.get((c.get("model"), c.get("year")), [])
        if len(g) >= 4 and c.get("price_ht"):
            med = statistics.median(g)
            c["deal_pct"] = round((c["price_ht"] - med) / med * 100)
        else:
            c["deal_pct"] = None


# --------------------------------------------------------------------------
# WhatsApp (CallMeBot)
# --------------------------------------------------------------------------
def _send(name, fn):
    for attempt in range(3):
        try:
            r = fn()
            if 200 <= r.status_code < 300:
                return True
            log(f"  {name} HTTP", r.status_code, r.text[:200])
        except requests.RequestException as e:
            log(f"  {name}:", e)
        time.sleep(10)
    return False


def whatsapp(text, dry=False):
    """Envoie sur chaque canal configuré (secrets GitHub) : Green-API, CallMeBot, Telegram."""
    E = os.environ.get
    channels = []
    # 1) Green-API (WhatsApp via un compte lié par QR code) — plan Developer gratuit
    if E("GREENAPI_ID") and E("GREENAPI_TOKEN") and E("WHATSAPP_TO"):
        base = (E("GREENAPI_URL") or "https://api.greenapi.com").rstrip("/")
        chat = re.sub(r"\D", "", E("WHATSAPP_TO")) + "@c.us"
        url = f"{base}/waInstance{E('GREENAPI_ID')}/sendMessage/{E('GREENAPI_TOKEN')}"
        channels.append(("Green-API", lambda u=url: requests.post(u, json={"chatId": chat, "message": text}, timeout=30)))
    # 2) CallMeBot (si un créneau se libère)
    if E("CALLMEBOT_PHONE") and E("CALLMEBOT_APIKEY"):
        url = ("https://api.callmebot.com/whatsapp.php?phone=" + urllib.parse.quote(E("CALLMEBOT_PHONE")) +
               "&text=" + urllib.parse.quote(text) + "&apikey=" + urllib.parse.quote(E("CALLMEBOT_APIKEY")))
        channels.append(("CallMeBot", lambda u=url: requests.get(u, timeout=30)))
    # 3) Telegram (bot gratuit, en secours)
    if E("TELEGRAM_TOKEN") and E("TELEGRAM_CHAT_ID"):
        url = f"https://api.telegram.org/bot{E('TELEGRAM_TOKEN')}/sendMessage"
        channels.append(("Telegram", lambda u=url: requests.post(u, data={"chat_id": E("TELEGRAM_CHAT_ID"), "text": text,
                                                                     "disable_web_page_preview": "false"}, timeout=30)))
    if dry or not channels:
        log("  [message non envoyé]", text.replace("\n", " | ")[:300])
        return False
    ok = False
    for name, fn in channels:
        ok = _send(name, fn) or ok
    time.sleep(4)  # ménage les limites de débit
    return ok


def fmt_eur(v):
    return f"{v:,}".replace(",", ".") if v else "?"


def notif_text(c, prefix):
    ck = c.get("checks", {})
    deal = c.get("deal_pct")
    deal_s = f" ({deal:+d}% vs marché)" if deal is not None else ""
    lines = [
        f"{prefix} {MODELS[c['model']]['label']}",
        c.get("title", "")[:90],
        f"💶 {fmt_eur(c.get('price_ht'))} € HT{deal_s} · {fmt_eur(c.get('price'))} € TTC",
        f"📅 {c.get('first_reg') or c.get('year')} · 🛣️ {fmt_eur(c.get('km'))} km",
        f"Toit {ck.get('toit')} · Auto {ck.get('auto')} · Intérieur {ck.get('interieur')} · TVA {ck.get('tva')}",
    ]
    if c.get("warnings"):
        lines.append("⚠️ " + ", ".join(c["warnings"]))
    lines.append(f"📍 {c.get('city') or ''} · {c['source']}")
    lines.append(c["url"])
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Exports
# --------------------------------------------------------------------------
CSV_COLS = ["status", "model", "title", "price_ht", "price", "deal_pct", "km", "year", "first_reg",
            "auto", "toit", "interieur", "tva", "warnings", "reasons", "city", "seller", "source",
            "first_seen", "last_seen", "gone", "url"]


def export(db, state):
    rows = sorted(db.values(), key=lambda c: ({"match": 0, "a_verifier": 1}.get(c.get("status"), 2),
                                             c.get("price_ht") or 10 ** 9))
    public = []
    for c in rows:
        d = {k: v for k, v in c.items() if k not in ("text",)}
        public.append(d)
    save(DOCS / "listings.json", {"updated": NOW_ISO, "config": {k: v for k, v in CONFIG.items() if not k.startswith("_")},
                                  "sources": state.get("source_status", {}), "listings": public})
    with open(DOCS / "listings.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(CSV_COLS)
        for c in rows:
            ck = c.get("checks", {})
            w.writerow([c.get("status"), c.get("model"), c.get("title"), c.get("price_ht"), c.get("price"),
                        c.get("deal_pct"), c.get("km"), c.get("year"), c.get("first_reg"),
                        ck.get("auto"), ck.get("toit"), ck.get("interieur"), ck.get("tva"),
                        ", ".join(c.get("warnings", [])), ", ".join(c.get("reasons", [])),
                        c.get("city"), c.get("seller"), c.get("source"),
                        c.get("first_seen"), c.get("last_seen"), c.get("gone", False), c.get("url")])


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    dry = "--dry-run" in sys.argv
    state = load(DATA / "state.json", {})
    db = load(DATA / "db.json", {})
    first_run = not state.get("bootstrapped")
    RULES_VERSION = 3
    if state.get("rules_version") != RULES_VERSION:
        for c in db.values():
            if c.get("status") in ("match", "a_verifier") or not c.get("detail_done"):
                c["detail_done"] = False
                c["needs_eval"] = True
        state["rules_version"] = RULES_VERSION

    last_full = state.get("last_full_sweep")
    hours_since = (NOW - datetime.fromisoformat(last_full)).total_seconds() / 3600 if last_full else 1e9
    full = "--full" in sys.argv or first_run or hours_since >= CONFIG["full_sweep_every_hours"]
    pages = 40 if full else CONFIG["pages_quick_scan"]
    log(f"Scan {'COMPLET' if full else 'rapide'} ({pages} pages max par recherche)")

    found, src_status = [], state.get("source_status", {})
    for name, fn in [("Marktplaats", mp_search), ("AutoScout24", as_search)]:
        try:
            res, ok = fn(pages)
        except Exception as e:  # une source cassée ne doit pas bloquer l'autre
            log(f"  {name} ERREUR:", repr(e)); res, ok = [], False
        st = src_status.setdefault(name, {"fails": 0})
        st.update(last_count=len(res), last_run=NOW_ISO, ok=ok and len(res) > 0)
        st["fails"] = 0 if st["ok"] else st.get("fails", 0) + 1
        found.extend(res)
    state["source_status"] = src_status

    # Fusion dans la base
    seen_now = set()
    for c in found:
        uid = c["uid"]
        seen_now.add(uid)
        old = db.get(uid)
        if old:
            if c.get("price") and old.get("price") and c["price"] != old["price"]:
                old.setdefault("price_history", []).append([NOW_ISO[:10], old["price"]])
                old["prev_price"] = old["price"]
                old["price"] = c["price"]
                old["needs_eval"] = True
            old.update(last_seen=NOW_ISO, gone=False)
            for k in ("title", "km", "city", "image"):
                if c.get(k):
                    old[k] = c[k]
        else:
            c.update(first_seen=NOW_ISO, last_seen=NOW_ISO, detail_done=False, needs_eval=True)
            db[uid] = c

    if full:
        for uid, c in db.items():
            if uid not in seen_now and c["source"] in [s for s, v in src_status.items() if v.get("ok")]:
                c["gone"] = True
        state["last_full_sweep"] = NOW_ISO

    # Pré-évaluation sans détail, puis détail pour les candidats plausibles
    budget = 450 if first_run else CONFIG["max_details_per_run"]
    queue = []
    for c in db.values():
        if c.get("gone") or not c.get("needs_eval"):
            continue
        evaluate(c)
        hard = [r for r in c["reasons"] if r.startswith(("année", "autre version", "Variant", "modèle"))
                or "km" in r or "€ HT" in r or (r == "pas automatique" and c.get("transmission"))]
        if not c["detail_done"] and not hard:
            queue.append(c)
        else:
            c["needs_eval"] = False
    def promise(c):
        t = (c.get("title", "") + " " + c.get("text", "")[:400]).lower()
        m = MODELS.get(c.get("model")) or MODELS["golf"]
        return (bool(m["trim"].search(t)) + bool(ROOF.search(t)), c.get("first_seen", ""))
    queue.sort(key=promise, reverse=True)
    log(f"Détails à lire : {len(queue)} (budget {budget} ce run)")
    for c in queue[:budget]:
        try:
            if c["source"] == "Marktplaats":
                txt, flag = mp_detail(c), None
            else:
                txt, flag = as_detail(c)
        except Exception as e:
            log("  détail ERREUR", c["uid"], repr(e)); txt, flag = None, None
        if txt:
            c["text"] = (c.get("text", "") + "\n" + txt)[:30000]
            c["vat_flag"] = flag
            c["detail_done"] = True
            c["needs_eval"] = False
            evaluate(c)
        pause()

    # Doublons inter-sites
    keys = {}
    for c in db.values():
        k = dedup_key(c)
        if k and not c.get("gone"):
            keys.setdefault(k, []).append(c)
    for group in keys.values():
        if len(group) > 1:
            srcs = sorted({g["source"] for g in group})
            for g in group:
                g["also_on"] = [s for s in srcs if s != g["source"]]
                g["dup_group"] = sorted(x["uid"] for x in group)

    add_deal_scores(db)

    # Notifications (pendant l'amorçage on remplit la base sans spammer)
    bootstrapping = first_run and len(queue) > budget
    notified = set(state.get("notified", []))
    msgs = []
    for c in db.values():
        if c.get("gone") or not c.get("detail_done"):
            continue
        st = c.get("status")
        group = c.get("dup_group") or [c["uid"]]
        if st in CONFIG["notify_statuses"] and not any(u in notified for u in group):
            notified.add(c["uid"])
            if not first_run:
                prefix = "✅ NOUVELLE ANNONCE" if st == "match" else "🟡 À VÉRIFIER"
                msgs.append(notif_text(c, prefix))
        elif (CONFIG.get("notify_price_drops") and st in CONFIG["notify_statuses"] and c["uid"] in notified
              and c.get("prev_price") and c["price"] < c["prev_price"] and not c.get("drop_notified") == c["price"]):
            msgs.append(notif_text(c, f"📉 BAISSE DE PRIX ({fmt_eur(c['prev_price'])} → {fmt_eur(c['price'])} € TTC)"))
            c["drop_notified"] = c["price"]

    if first_run and not bootstrapping:
        n_match = sum(1 for c in db.values() if c.get("status") == "match")
        n_check = sum(1 for c in db.values() if c.get("status") == "a_verifier")
        whatsapp(f"🚗 Alerte auto activée !\nBase initiale : {n_match} annonces OK, {n_check} à vérifier "
                 f"(sur {len(db)} analysées).\nTu recevras ici chaque nouvelle annonce.\n"
                 f"{CONFIG.get('dashboard_url') or ''}", dry)
        state["bootstrapped"] = True
    else:
        if len(msgs) > 6:
            whatsapp(f"🚗 {len(msgs)} nouvelles annonces — les 6 premières suivent. Base complète : "
                     f"{CONFIG.get('dashboard_url') or 'voir le tableau'}", dry)
            msgs = msgs[:6]
        for m in msgs:
            whatsapp(m, dry)

    # Alerte si une source est bloquée depuis longtemps
    for name, st in src_status.items():
        if st.get("fails") == 6:
            whatsapp(f"⚠️ Alerte auto : {name} ne répond plus depuis 6 scans (blocage possible). "
                     f"L'autre source continue.", dry)

    state["notified"] = sorted(notified)
    # Allège la base : texte complet seulement pour les annonces encore pertinentes
    for c in db.values():
        soft = [r for r in c.get("reasons", []) if not ("€ HT" in r)]
        if c.get("detail_done") and (soft or c.get("gone")):
            c["text"] = ""
        else:
            c["text"] = (c.get("text") or "")[:5000]
    state["last_run"] = NOW_ISO
    save(DATA / "db.json", db)
    save(DATA / "state.json", state)
    export(db, state)
    cnt = {s: sum(1 for c in db.values() if c.get("status") == s and not c.get("gone"))
           for s in ("match", "a_verifier", "rejete")}
    log(f"Terminé. Base : {len(db)} annonces — {cnt}. Messages : {len(msgs)}")


if __name__ == "__main__":
    main()
