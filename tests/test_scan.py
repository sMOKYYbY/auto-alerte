"""Tests hors-ligne : python -m pytest -q  (aucun accès réseau)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scan  # noqa: E402


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
    assert c["model"] == "golf6" and c["status"] == "match"


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
    monkeypatch.setattr(scan, "mp_search", lambda pages: ([], True))
    monkeypatch.setattr(scan, "as_search", lambda pages: ([], True))
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
    monkeypatch.setattr(scan, "mp_search", lambda pages: ([new], True))
    monkeypatch.setattr(scan, "as_search", lambda pages: ([], True))
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
