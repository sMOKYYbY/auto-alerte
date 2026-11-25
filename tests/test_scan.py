"""Tests hors-ligne : python -m pytest -q  (aucun accès réseau)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scan  # noqa: E402

# Les tests de règles portent sur tous les modèles avec leurs réglages par défaut ;
# la configuration réelle (config.json) est testée à part, en bas du fichier.
REAL_MODELS = scan.CONFIG.get("models") or {}
scan.CONFIG["models"] = {}


def base(**kw):
    c = {"uid": "t:1", "source": "Test", "id": "1", "url": "https://x", "price": 8500,
         "km": 150000, "year": 2011, "transmission": "", "text": "", "family": "golf", "detail_done": True}
    c.update(kw)
    return c


# --- Golf 6 essence ----------------------------------------------------------
def test_golf6_petrol_dsg_roof_marge_is_match():
    c = scan.evaluate(base(title="Volkswagen Golf 1.4 TSI Highline DSG Schuifdak",
                           text="BTW/marge: Marge, de BTW is niet aftrekbaar"))
    assert c["model"] == "golf6" and c["status"] == "match", c
    assert c["cost"] == 8500          # marge : le prix affiché est le prix final


def test_golf6_diesel_rejected():
    c = scan.evaluate(base(title="Volkswagen Golf 1.6 TDI Highline DSG Schuifdak", text="BTW/marge: Marge"))
    assert c["status"] == "rejete" and "diesel" in c["reasons"]
    c = scan.evaluate(base(title="Volkswagen Golf 2.0 GTD DSG pano", text="Marge"))
    assert c["status"] == "rejete"


def test_golf6_budget_depends_on_vat():
    # 10 500 TTC = 8 678 HT : OK si TVA récupérable, refusé si marge
    ok = scan.evaluate(base(title="Golf 1.4 TSI DSG schuifdak", price=10500,
                            text="BTW/marge: BTW verrekenbaar voor ondernemers"))
    assert ok["status"] == "match" and ok["cost"] == round(10500 / 1.21)
    ko = scan.evaluate(base(title="Golf 1.4 TSI DSG schuifdak", price=10500, text="BTW/marge: Marge"))
    assert ko["status"] == "rejete" and any(r.startswith("budget") for r in ko["reasons"])
    priv = scan.evaluate(base(title="Golf 1.4 TSI DSG schuifdak", price=10500, seller_type="particulier"))
    assert priv["status"] == "rejete"
    unk = scan.evaluate(base(title="Golf 1.4 TSI DSG schuifdak", price=10500, text=""))
    assert unk["status"] == "a_verifier" and "dans le budget seulement si TVA récupérable" in unk["warnings"]


def test_golf6_needs_auto_and_roof():
    assert scan.evaluate(base(title="Golf 1.4 TSI Highline schuifdak", transmission="Handgeschakeld",
                              text="Marge"))["status"] == "rejete"
    assert scan.evaluate(base(title="Golf 1.4 TSI Highline DSG", text="Marge, panorama camera"))["status"] == "rejete"


def test_golf6_other_versions_excluded():
    for t in ["Volkswagen Golf Plus 1.4 TSI DSG schuifdak", "Volkswagen Golf Cabriolet 1.4 TSI DSG",
              "Volkswagen Golf 7 1.4 TSI DSG pano", "Volkswagen Golf Sportsvan 1.2 TSI DSG pano"]:
        assert scan.evaluate(base(title=t, text="Marge"))["status"] == "rejete", t


def test_golf6_edge_years_flagged():
    c = scan.evaluate(base(title="Volkswagen Golf 1.4 TSI DSG schuifdak", year=2013, text="Marge"))
    assert c["status"] == "a_verifier" and "vérifier génération" in c["warnings"]
    c = scan.evaluate(base(title="Volkswagen Golf 6 1.4 TSI DSG schuifdak", year=2013, text="Marge"))
    assert c["status"] == "match"


# --- Golf 5 GTI --------------------------------------------------------------
def test_golf5_gti():
    c = scan.evaluate(base(title="Volkswagen Golf 2.0 TFSI GTI DSG Schuifdak", year=2007, price=7500, text="Marge"))
    assert c["model"] == "golf5gti" and c["status"] == "match", c
    # Golf 5 non GTI : pas recherchée
    c = scan.evaluate(base(title="Volkswagen Golf 1.4 TSI Sportline DSG schuifdak", year=2007, text="Marge"))
    assert c["status"] == "rejete" and c["reasons"] == ["Golf 5 non GTI"]
    # GTI 2010 = Golf 6 GTI (essence) : acceptée comme Golf 6
    c = scan.evaluate(base(title="Volkswagen Golf 2.0 GTI DSG schuifdak", year=2010, text="Marge"))
    assert c["model"] == "golf6gti" and c["status"] == "match"


# --- Polo 6 -------------------------------------------------------------------
def test_polo6():
    c = scan.evaluate(base(family="polo", title="Volkswagen Polo 1.0 TSI Highline DSG Panoramadak", year=2019,
                           price=10800, text="BTW/marge: BTW verrekenbaar"))
    assert c["model"] == "polo6" and c["status"] == "match" and c["cost"] == round(10800 / 1.21)
    c = scan.evaluate(base(family="polo", title="Volkswagen Polo 1.2 TSI 6R DSG schuifdak", year=2016, text="Marge"))
    assert c["status"] == "rejete"
    c = scan.evaluate(base(family="polo", title="Volkswagen Polo 1.0 TSI DSG schuifdak", year=2017, text="Marge"))
    assert c["status"] == "a_verifier" and "vérifier génération" in c["warnings"]


# --- Généralités ---------------------------------------------------------------
def test_km_limit_and_junk_price():
    assert scan.evaluate(base(title="Golf 1.4 TSI DSG schuifdak", km=210000, text="Marge"))["status"] == "rejete"
    assert scan.evaluate(base(title="Golf 1.4 TSI DSG schuifdak", price=300, text="Marge"))["status"] == "rejete"


def test_mp_parse_fixture():
    raw = {"itemId": "m2426128902", "title": "Volkswagen Golf 1.4 TSI Highline DSG Schuifdak",
           "categorySpecificDescription": "DSG, BTW verrekenbaar",
           "priceInfo": {"priceCents": 995000, "priceType": "FIXED"},
           "location": {"cityName": "Utrecht"}, "vipUrl": "/v/auto-s/volkswagen/m2426128902-golf",
           "extendedAttributes": [{"key": "constructionYear", "value": "2011"},
                                  {"key": "mileage", "value": "128.968"},
                                  {"key": "transmission", "value": "Automaat"},
                                  {"key": "fuel", "value": "Benzine"}]}
    c = scan.mp_parse(raw, "golf")
    assert (c["price"], c["km"], c["year"], c["transmission"], c["fuel"]) == (9950, 128968, 2011, "Automaat", "Benzine")
    assert c["url"].startswith("https://www.marktplaats.nl/v/")
    assert scan.evaluate(c)["status"] in ("match", "a_verifier")


def test_as_parse_and_next_data():
    data = {"props": {"pageProps": {"listings": [{
        "id": "abc-123", "url": "/aanbod/volkswagen-polo-abc-123",
        "price": {"priceFormatted": "€ 9.950,-"},
        "vehicle": {"make": "Volkswagen", "model": "Polo", "modelVersionInput": "1.0 TSI Highline DSG Pano",
                    "transmission": "Automatisch", "fuel": "Benzine"},
        "tracking": {"firstRegistration": "05-2019", "mileage": "101000", "price": "9950"},
        "location": {"city": "Breda"}}], "numberOfResults": 1}}}
    html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'
    nodes = scan.as_listing_nodes(scan.next_data(html))
    c = scan.as_parse(nodes[0], "polo")
    assert (c["price"], c["km"], c["year"]) == (9950, 101000, 2019) and "Benzine" in c["fuel"]
    c = scan.evaluate(c)
    assert c["model"] == "polo6" and c["checks"]["auto"] == "oui" and c["checks"]["toit"] == "oui"


def test_btw_marge_field_and_private_seller():
    marge = scan.evaluate(base(title="Golf 1.4 TSI DSG pano", text="BTW/marge:  BTW niet verrekenbaar (marge)"))
    assert marge["checks"]["tva"] == "marge"
    btw = scan.evaluate(base(title="Golf 1.4 TSI DSG pano", text="BTW/Marge : BTW verrekenbaar voor ondernemers"))
    assert btw["checks"]["tva"] == "récupérable"
    priv = scan.evaluate(base(title="Golf 1.4 TSI DSG pano", seller_type="particulier", text="BTW verrekenbaar"))
    assert priv["checks"]["tva"] == "particulier" and priv["status"] == "match"   # TVA pas obligatoire


def test_new_search_archives_old_base(tmp_path, monkeypatch):
    monkeypatch.setattr(scan, "DATA", tmp_path / "data")
    monkeypatch.setattr(scan, "DOCS", tmp_path / "docs")
    monkeypatch.setattr(scan, "pause", lambda: None)
    sent = []
    monkeypatch.setattr(scan, "whatsapp", lambda t, dry=False: sent.append(t) or True)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "db.json").write_text(json.dumps({"mp:old": {"uid": "mp:old", "model": "a3"}}))
    (tmp_path / "data" / "state.json").write_text(json.dumps({"bootstrapped": True, "notified": ["mp:old"]}))
    monkeypatch.setattr(scan, "mp_search", lambda pages, site=None: ([], True))
    monkeypatch.setattr(scan, "as_search", lambda pages, site=None: ([], True))
    monkeypatch.setattr(scan.sys, "argv", ["scan.py"])
    scan.main()
    db = json.loads((tmp_path / "data" / "db.json").read_text())
    st = json.loads((tmp_path / "data" / "state.json").read_text())
    assert db == {} and st["search_id"] == scan.CONFIG["search_id"]
    assert (tmp_path / "data" / "archive" / "golf7-a3-db.json").exists()


def test_wiped_text_is_reread_before_reevaluation(tmp_path, monkeypatch):
    monkeypatch.setattr(scan, "DATA", tmp_path / "data")
    monkeypatch.setattr(scan, "DOCS", tmp_path / "docs")
    monkeypatch.setattr(scan, "pause", lambda: None)
    monkeypatch.setattr(scan, "whatsapp", lambda *a, **k: True)
    (tmp_path / "data").mkdir()
    old = {"uid": "mp:m1", "source": "Marktplaats", "id": "m1", "model": "golf", "family": "golf", "url": "https://x",
           "title": "Volkswagen Golf 1.4 TSI DSG schuifdak", "price": 8900, "km": 150000,
           "year": 2011, "transmission": "Automaat", "text": "", "detail_done": True, "needs_eval": False,
           "status": "rejete", "reasons": ["autre"], "checks": {}, "first_seen": "2026-11-08"}
    (tmp_path / "data" / "db.json").write_text(json.dumps({"mp:m1": old}))
    (tmp_path / "data" / "state.json").write_text(json.dumps({"bootstrapped": True, "rules_version": 7,
                                                             "search_id": scan.CONFIG["search_id"],
                                                             "last_full_sweep": scan.NOW_ISO}))
    new = dict(old, price=8500, text="")
    monkeypatch.setattr(scan, "mp_search", lambda pages, site=None: ([new] if site in (None, "Marktplaats") else [], True))
    monkeypatch.setattr(scan, "as_search", lambda pages, site=None: ([], True))
    monkeypatch.setattr(scan, "mp_detail", lambda c: "BTW/Marge: Marge, de BTW is niet aftrekbaar. Benzine")
    monkeypatch.setattr(scan.sys, "argv", ["scan.py"])
    scan.main()
    c = json.loads((tmp_path / "data" / "db.json").read_text())["mp:m1"]
    assert c["checks"]["tva"] == "marge" and c["detail_done"] is True


def test_broken_unicode_does_not_crash_save(tmp_path):
    scan.save(tmp_path / "x.json", {"t": "Golf \ud835 GTI"})
    assert "Golf" in (tmp_path / "x.json").read_text(encoding="utf-8")
    assert scan.clean_text("a\ud835b") == "a?b"


def test_project_and_tuned_cars_flagged():
    c = scan.evaluate(base(title="Volkswagen Golf GTI – Projectauto / Klusauto DSG schuifdak", year=2007, price=3000))
    assert c["status"] == "a_verifier" and "à réparer / projet ?" in c["warnings"]
    c = scan.evaluate(base(title="Volkswagen Golf 1.4 TSI Highline DSG schuifdak", text="Ketting hoorbaar, Marge"))
    assert "à réparer / projet ?" in c["warnings"]
    c = scan.evaluate(base(title="Volkswagen Golf 2.0 GTI STAGE 2 FULL OPTION 300+ PK DSG pano", year=2010, text="Marge"))
    assert "moteur modifié" in c["warnings"]


def test_2dehands_parse_and_french_wording():
    raw = {"itemId": "m2459721887", "title": "Golf 6 1.4 TSI*Boîte Automatique*Toit ouvrant*Prête à immat",
           "priceInfo": {"priceCents": 790000}, "vipUrl": "/v/auto-s/volkswagen/m2459721887-golf-6",
           "location": {"cityName": "Gosselies"},
           "extendedAttributes": [{"key": "constructionYear", "value": "2010"}, {"key": "mileage", "value": "150000"},
                                  {"key": "fuel", "value": "Benzine"}]}
    c = scan.mp_parse(raw, "golf", "2dehands")
    assert c["uid"] == "2d:m2459721887" and c["country"] == "BE" and c["url"].startswith("https://www.2dehands.be/v/")
    c["text"] += "\nVoiture vendue sous le régime de la marge."
    c["detail_done"] = True
    c = scan.evaluate(c)
    assert c["model"] == "golf6" and c["checks"]["auto"] == "oui" and c["checks"]["toit"] == "oui"
    assert c["checks"]["tva"] == "marge" and c["status"] == "match", c
    htva = scan.evaluate(base(title="VW Golf 1.4 TSI DSG toit panoramique", price=10500,
                              text="Prix : 8.678 € HTVA, TVA déductible"))
    assert htva["checks"]["tva"] == "récupérable" and htva["price_ht"] == 8678 and htva["status"] == "match"
    assert "à réparer / projet ?" in scan.evaluate(base(title="Golf 1.4 TSI DSG toit ouvrant",
                                                        text="Vendu pour marchand, problème boîte"))["warnings"]


def test_autoscout_be_url_host():
    node = {"id": "x1", "url": "/nl/aanbod/volkswagen-golf-x1", "vehicle": {"make": "Volkswagen", "model": "Golf"},
            "tracking": {"price": "8999", "mileage": "68496", "firstRegistration": "03-2009"}}
    c = scan.as_parse(node, "golf", "AutoScout24.be")
    assert c["url"] == "https://www.autoscout24.be/nl/aanbod/volkswagen-golf-x1" and c["uid"] == "asbe:x1"
    assert scan.as_params(1, years=(2004, 2013), cy="B")["cy"] == "B"


def test_new_source_is_bootstrapped_silently(tmp_path, monkeypatch):
    monkeypatch.setattr(scan, "DATA", tmp_path / "data")
    monkeypatch.setattr(scan, "DOCS", tmp_path / "docs")
    monkeypatch.setattr(scan, "pause", lambda: None)
    sent = []
    monkeypatch.setattr(scan, "whatsapp", lambda t, dry=False: sent.append(t) or True)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "db.json").write_text("{}")
    (tmp_path / "data" / "state.json").write_text(json.dumps({
        "bootstrapped": True, "search_id": scan.CONFIG["search_id"], "rules_version": 9,
        "models_bootstrapped": list(scan.MODELS),
        "last_full_sweep": scan.NOW_ISO,
        "source_status": {"Marktplaats": {"ok": True}, "AutoScout24": {"ok": True}}}))

    def be_item(i):
        return {"uid": f"2d:m{i}", "source": "2dehands", "country": "BE", "id": f"m{i}", "model": "golf",
                "family": "golf", "title": "VW Golf 1.4 TSI DSG toit ouvrant", "url": f"https://www.2dehands.be/v/m{i}",
                "price": 7500, "km": 150000, "year": 2011, "transmission": "Automaat", "fuel": "Benzine", "text": ""}
    items = [be_item(1), be_item(2)]
    monkeypatch.setattr(scan, "mp_search", lambda pages, site=None: (items if site == "2dehands" else [], True))
    monkeypatch.setattr(scan, "as_search", lambda pages, site=None: ([], True))
    monkeypatch.setattr(scan, "mp_detail", lambda c: "régime de la marge")
    monkeypatch.setattr(scan.sys, "argv", ["scan.py"])
    scan.main()
    assert len(sent) == 1 and "2dehands ajouté : 2 annonces OK" in sent[0]      # récap, pas 2 alertes
    sent.clear()
    items.append(dict(be_item(3), km=120000, price=8200))
    scan.main()
    assert any("NOUVELLE ANNONCE" in m and "🇧🇪" in m for m in sent), sent       # ensuite : alertes normales


# --- Golf 7.5 / GTI 7.5 / A3 réintégrées (TVA récupérable obligatoire) -------------
def test_golf7_rline_rules_back():
    c = scan.evaluate(base(title="Volkswagen Golf 1.5 TSI 3x R-Line DSG Panoramadak", year=2018, km=98000,
                           price=19900, text="BTW/marge: BTW verrekenbaar voor ondernemers. Sportstoelen R-Line"))
    assert c["model"] == "golf7" and c["status"] == "match" and c["cost"] == round(19900 / 1.21), c
    marge = scan.evaluate(base(title="Volkswagen Golf 1.5 TSI 3x R-Line DSG Pano", year=2018, km=98000,
                               price=17000, text="BTW/marge: Marge"))
    assert marge["status"] == "rejete" and "TVA non récupérable (marge)" in marge["reasons"]
    no_trim = scan.evaluate(base(title="Volkswagen Golf 1.5 TSI Comfortline DSG Pano", year=2018, km=98000,
                                 price=17000, text="BTW verrekenbaar"))
    assert "pas R-Line/S line" in no_trim["reasons"]
    km = scan.evaluate(base(title="Volkswagen Golf 1.5 TSI 3x R-Line DSG Pano", year=2018, km=170000,
                            price=17000, text="BTW verrekenbaar"))
    assert km["status"] == "rejete"                       # 160 000 km max pour la Golf 7.5


def test_gti7_and_a3_back():
    g = scan.evaluate(base(title="Volkswagen Golf 2.0 TSI GTI Performance DSG Pano", year=2019, km=120000,
                           price=25000, text="BTW verrekenbaar"))
    assert g["model"] == "gti7" and g["status"] == "match"
    a = scan.evaluate(base(family="a3", title="Audi A3 Limousine 35 TFSI CoD Advance Sport 3x S-line S tronic pano",
                           year=2019, km=138000, price=19950, text="BTW/Marge: BTW"))
    assert a["model"] == "a3" and a["status"] == "match" and a["checks"]["interieur"] == "confirmé"
    assert scan.evaluate(base(family="a3", title="Audi A3 Sportback 35 TFSI Edition One S-Line pano", year=2020,
                              km=50000, price=19000, text="BTW"))["status"] == "rejete"


def test_both_searches_coexist():
    # Golf 6 de 2011 : règles « petit budget » (marge acceptée), Golf 7.5 de 2018 : règles « récentes »
    old = scan.evaluate(base(title="Volkswagen Golf 1.4 TSI DSG schuifdak", year=2011, price=8500, text="Marge"))
    assert old["model"] == "golf6" and old["status"] == "match" and "interieur" not in old["checks"]
    assert scan.search_budget_incl("golf") == int(22000 * 1.21 * 1.02)
    assert scan.search_budget_incl("polo") == int(9000 * 1.21 * 1.02)
    assert scan.family_years("golf") == (2004, 2020) and scan.family_max_km("golf") == 200000


def test_readded_models_bootstrap_silently(tmp_path, monkeypatch):
    monkeypatch.setattr(scan, "DATA", tmp_path / "data")
    monkeypatch.setattr(scan, "DOCS", tmp_path / "docs")
    monkeypatch.setattr(scan, "pause", lambda: None)
    sent = []
    monkeypatch.setattr(scan, "whatsapp", lambda t, dry=False: sent.append(t) or True)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "db.json").write_text("{}")
    (tmp_path / "data" / "state.json").write_text(json.dumps({
        "bootstrapped": True, "search_id": scan.CONFIG["search_id"], "rules_version": 9,
        "last_full_sweep": scan.NOW_ISO, "sources_bootstrapped": list(scan.MP_SITES) + list(scan.AS_SITES),
        "source_status": {s: {"ok": True} for s in list(scan.MP_SITES) + list(scan.AS_SITES)}}))
    a3 = {"uid": "mp:a1", "source": "Marktplaats", "country": "NL", "id": "a1", "model": "a3", "family": "a3",
          "title": "Audi A3 Limousine 35 TFSI 3x S-line S tronic pano", "url": "https://x/a1", "price": 19950,
          "km": 120000, "year": 2019, "transmission": "Automaat", "text": ""}
    items = [a3]
    monkeypatch.setattr(scan, "mp_search", lambda pages, site=None: (items if site == "Marktplaats" else [], True))
    monkeypatch.setattr(scan, "as_search", lambda pages, site=None: ([], True))
    monkeypatch.setattr(scan, "mp_detail", lambda c: "BTW/Marge: BTW verrekenbaar")
    monkeypatch.setattr(scan.sys, "argv", ["scan.py"])
    scan.main()
    assert len(sent) == 1 and sent[0].startswith("🔁 Recherches ajoutées") and "Audi A3 8V2 S line : 1 OK" in sent[0]
    sent.clear()
    items.append(dict(a3, uid="mp:a2", id="a2", km=90000, price=21000))
    scan.main()
    assert any("NOUVELLE ANNONCE Audi A3" in m for m in sent), sent


def test_unreadable_listing_does_not_block_bootstrap(tmp_path, monkeypatch):
    monkeypatch.setattr(scan, "DATA", tmp_path / "data")
    monkeypatch.setattr(scan, "DOCS", tmp_path / "docs")
    monkeypatch.setattr(scan, "pause", lambda: None)
    sent = []
    monkeypatch.setattr(scan, "whatsapp", lambda t, dry=False: sent.append(t) or True)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "db.json").write_text("{}")
    srcs = list(scan.MP_SITES) + list(scan.AS_SITES)
    (tmp_path / "data" / "state.json").write_text(json.dumps({
        "bootstrapped": True, "search_id": scan.CONFIG["search_id"], "rules_version": 9,
        "last_full_sweep": scan.NOW_ISO, "sources_bootstrapped": srcs,
        "models_bootstrapped": ["golf6", "golf5gti", "polo6"], "source_status": {s: {"ok": True} for s in srcs}}))
    a3 = {"uid": "as:x", "source": "AutoScout24", "country": "NL", "id": "x", "model": "a3", "family": "a3",
          "title": "Audi A3 Sportback 30 TFSI S-line S tronic pano", "url": "https://x/x", "price": 18695,
          "km": 90000, "year": 2019, "transmission": "Automaat", "text": ""}
    monkeypatch.setattr(scan, "mp_search", lambda pages, site=None: ([], True))
    monkeypatch.setattr(scan, "as_search", lambda pages, site=None: ([dict(a3)] if site == "AutoScout24" else [], True))
    monkeypatch.setattr(scan, "as_detail", lambda c: (None, None))      # la fiche ne s'ouvre jamais
    monkeypatch.setattr(scan.sys, "argv", ["scan.py"])
    for _ in range(3):
        scan.main()
    assert any(m.startswith("🔁 Recherches ajoutées") for m in sent), sent
    st = json.loads((tmp_path / "data" / "state.json").read_text())
    assert set(st["models_bootstrapped"]) == set(scan.MODELS)
    c = json.loads((tmp_path / "data" / "db.json").read_text())["as:x"]
    assert c["status"] == "a_verifier" and "fiche illisible" in c["warnings"]


def test_polo5_engines_not_taken_for_polo6():
    for t in ["Volkswagen Polo 1.2 TSI 66KW DSG 2017", "Volkswagen Polo 1.4 CR TDi Comfortline BMT DSG",
              "Volkswagen Polo 1.8 TSI GTI Panoramadak"]:
        c = scan.evaluate(base(family="polo", title=t + " schuifdak", year=2018, text="Marge"))
        assert c["status"] == "rejete" and "autre version/génération" in c["reasons"], t


def test_polo_roof_optional():
    c = scan.evaluate(base(family="polo", title="Volkswagen Polo 1.0 TSI Highline DSG", year=2019, price=5750, text="Marge"))
    assert c["status"] == "match" and c["checks"]["toit"] == "non"
    g = scan.evaluate(base(title="Volkswagen Golf 1.4 TSI DSG", year=2011, text="Marge"))
    assert "pas de toit ouvrant" in g["reasons"]          # toujours obligatoire pour la Golf


def test_rule_change_reevaluates_rejected_listings(tmp_path, monkeypatch):
    monkeypatch.setattr(scan, "DATA", tmp_path / "data")
    monkeypatch.setattr(scan, "DOCS", tmp_path / "docs")
    monkeypatch.setattr(scan, "pause", lambda: None)
    sent = []
    monkeypatch.setattr(scan, "whatsapp", lambda t, dry=False: sent.append(t) or True)
    (tmp_path / "data").mkdir()
    polo = {"uid": "2d:p1", "source": "2dehands", "country": "BE", "id": "p1", "model": "polo6", "family": "polo",
            "title": "Volkswagen Polo 1.0 TSI Highline DSG", "url": "https://x/p1", "price": 5750, "km": 142742,
            "year": 2019, "transmission": "Automaat", "text": "Marge, Benzine", "detail_done": True,
            "needs_eval": False, "status": "rejete", "reasons": ["pas de toit ouvrant"], "checks": {},
            "first_seen": "2026-11-12", "last_seen": scan.NOW_ISO}
    (tmp_path / "data" / "db.json").write_text(json.dumps({"2d:p1": polo}))
    srcs = list(scan.MP_SITES) + list(scan.AS_SITES)
    (tmp_path / "data" / "state.json").write_text(json.dumps({
        "bootstrapped": True, "search_id": scan.CONFIG["search_id"], "rules_version": 10,
        "sources_bootstrapped": srcs, "models_bootstrapped": list(scan.MODELS),
        "source_status": {s: {"ok": True} for s in srcs}}))
    monkeypatch.setattr(scan, "mp_search", lambda pages, site=None: ([dict(polo)] if site == "2dehands" else [], True))
    monkeypatch.setattr(scan, "as_search", lambda pages, site=None: ([], True))
    monkeypatch.setattr(scan, "mp_detail", lambda c: "Marge, Benzine, DSG")
    monkeypatch.setattr(scan.sys, "argv", ["scan.py"])
    scan.main()
    c = json.loads((tmp_path / "data" / "db.json").read_text())["2d:p1"]
    assert c["status"] == "match" and any("Polo 6" in m for m in sent), (c["status"], sent)


def test_key_snippets_keep_what_rules_need():
    long = ("Mooie auto, altijd onderhouden. " * 80 + "Panoramadak, DSG automaat. " + "Lorem ipsum. " * 80 +
            "BTW/marge: Marge, de BTW is niet aftrekbaar. " + "Nog meer tekst. " * 80 + "R-Line interieur.")
    k = scan.key_snippets(long)
    assert len(k) <= 1500
    c = scan.evaluate(base(title="Volkswagen Golf 1.5 TSI R-Line", year=2018, km=90000, price=17000, text=k))
    assert c["checks"]["toit"] == "oui" and c["checks"]["auto"] == "oui" and c["checks"]["tva"] == "marge"
    assert c["checks"]["interieur"] == "confirmé"


# --- Configuration réelle : Golf 6 GTI + Golf 5 GTI seulement -------------------------
def with_real_config(fn):
    def wrapper(*a, **k):
        old = scan.CONFIG["models"]
        scan.CONFIG["models"] = REAL_MODELS
        try:
            return fn(*a, **k)
        finally:
            scan.CONFIG["models"] = old
    wrapper.__name__ = fn.__name__
    return wrapper


@with_real_config
def test_real_config_only_gti_searched():
    assert set(scan.active_models()) == {"golf6gti", "golf5gti"}
    assert scan.active_families() == ["golf"]
    assert scan.search_budget_incl("golf") == int(11000 * 1.21 * 1.02)
    assert scan.family_years("golf") == (2004, 2013)


@with_real_config
def test_real_config_golf6_gti_rules():
    c = scan.evaluate(base(title="Volkswagen Golf 2.0 GTI 155kW DSG 2010 Grijs", year=2010, price=9000,
                           km=158513, seller_type="particulier", text="DSG"))
    assert c["model"] == "golf6gti" and c["status"] == "match" and c["checks"]["toit"] == "non", c
    assert scan.evaluate(base(title="Volkswagen Golf 2.0 GTI DSG", year=2011, price=11500,
                              text="BTW/marge: Marge, DSG"))["status"] == "rejete"   # budget 11 000 €
    assert scan.evaluate(base(title="Volkswagen Golf 2.0 GTI", year=2011, price=8000,
                              transmission="Handgeschakeld", text="Marge"))["status"] == "rejete"
    assert scan.evaluate(base(title="Volkswagen Golf 1.4 TSI Highline DSG schuifdak", year=2011,
                              text="Marge"))["reasons"] == ["recherche arrêtée"]
    assert scan.evaluate(base(family="polo", title="Volkswagen Polo 1.0 TSI DSG", year=2019,
                              text="Marge"))["reasons"] == ["recherche arrêtée"]
    c5 = scan.evaluate(base(title="Volkswagen Golf 2.0 TFSI GTI DSG", year=2007, price=7500, text="Marge"))
    assert c5["model"] == "golf5gti" and c5["status"] == "match"
