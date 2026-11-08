"""Tests hors-ligne : python -m pytest -q  (aucun accès réseau)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scan  # noqa: E402


def base(**kw):
    c = {"uid": "t:1", "source": "Test", "id": "1", "url": "https://x", "price": 19900,
         "km": 98000, "year": 2018, "transmission": "", "text": ""}
    c.update(kw)
    return c


def test_golf_full_match():
    c = scan.evaluate(base(model="golf",
        title="Volkswagen Golf 1.5 TSI DSG 3x R-Line Panoramadak",
        text="BTW/marge: BTW verrekenbaar voor ondernemers. Sportstoelen R-Line alcantara."))
    assert c["status"] == "match", c
    assert c["price_ht"] == round(19900 / 1.21)


def test_golf_exterior_only_is_flagged():
    c = scan.evaluate(base(model="golf", title="Golf 1.5 TSI R-Line DSG pano",
                           text="R-Line exterieur. Prijs excl. BTW € 16.400"))
    assert c["status"] == "a_verifier"
    assert c["checks"]["interieur"] == "extérieur seul ?"
    assert c["price_ht"] == 16400


def test_margin_car_rejected():
    c = scan.evaluate(base(model="a3", title="Audi A3 Sportback 35 TFSI S line S tronic schuifdak",
                           text="BTW/marge: Marge. S line interieur"))
    assert c["status"] == "rejete"
    assert any("marge" in r for r in c["reasons"])


def test_a3_sportpakket_match():
    c = scan.evaluate(base(model="a3", title="Audi A3 Limousine 1.5 TFSI S line sportpakket S tronic",
                           text="Panoramadak · Btw auto · S line sportpakket"))
    assert c["status"] == "match", c


def test_manual_and_climate_automatisch_not_auto():
    c = scan.evaluate(base(model="golf", title="Golf 1.5 TSI 3x R-Line pano",
                           transmission="Handgeschakeld",
                           text="airco automatisch, BTW verrekenbaar"))
    assert c["checks"]["auto"] == "non"
    c2 = scan.evaluate(base(model="golf", title="Golf 1.5 TSI 3x R-Line pano",
                            text="climate control automatische airco, BTW verrekenbaar"))
    assert c2["checks"]["auto"] == "non"


def test_wrong_generation_and_models():
    for title, model in [("Golf 1.5 eTSI R-Line DSG pano", "golf"), ("Volkswagen Golf R 2.0 TSI DSG pano", "golf"),
                         ("Golf Sportsvan R-Line DSG", "golf"), ("Audi S3 Sportback S tronic pano", "a3"),
                         ("Volkswagen Polo R-Line DSG", "golf")]:
        c = scan.evaluate(base(model=model, title=title, text="BTW verrekenbaar R-Line interieur S line interieur"))
        assert c["status"] == "rejete", title


def test_r_line_word_variants_not_excluded():
    c = scan.evaluate(base(model="golf", title="Volkswagen Golf R Line 1.5 TSI DSG schuifdak",
                           text="R-Line interieur, btw auto"))
    assert c["status"] == "match", c


def test_limits():
    assert scan.evaluate(base(model="golf", km=170000, title="Golf R-Line DSG pano",
                              text="R-Line interieur BTW verrekenbaar"))["status"] == "rejete"
    assert scan.evaluate(base(model="golf", price=21500, title="Golf R-Line DSG pano",
                              text="R-Line interieur BTW verrekenbaar"))["status"] == "rejete"
    assert scan.evaluate(base(model="golf", year=2016, title="Golf R-Line DSG pano",
                              text="R-Line interieur BTW verrekenbaar"))["status"] == "rejete"


def test_panorama_camera_is_not_a_roof():
    c = scan.evaluate(base(model="golf", title="Golf 1.5 TSI R-Line DSG",
                           text="panorama camera, R-Line interieur, btw verrekenbaar"))
    assert c["checks"]["toit"] == "non"


def test_structured_vat_flag():
    c = scan.evaluate(base(model="a3", title="Audi A3 Sportback 35 TFSI 3x S-line S tronic pano",
                           vat_flag=True))
    assert c["checks"]["tva"] == "récupérable" and c["status"] == "match"


def test_mp_parse_fixture():
    raw = {"itemId": "m2426128902", "title": "Audi A3 1.5 TFSI CoD 3x S-line Virtual Pano",
           "categorySpecificDescription": "S tronic, BTW verrekenbaar",
           "priceInfo": {"priceCents": 1995000, "priceType": "FIXED"},
           "location": {"cityName": "Utrecht"}, "vipUrl": "/v/auto-s/audi/m2426128902-audi-a3",
           "extendedAttributes": [{"key": "constructionYear", "value": "2018"},
                                  {"key": "mileage", "value": "128.968"},
                                  {"key": "transmission", "value": "Automaat"}],
           "sellerInformation": {"sellerName": "Dealer BV"}}
    c = scan.mp_parse(raw, "a3")
    assert (c["price"], c["km"], c["year"], c["transmission"]) == (19950, 128968, 2018, "Automaat")
    assert c["url"].startswith("https://www.marktplaats.nl/v/")
    assert scan.evaluate(c)["status"] == "match"


def test_as_parse_and_next_data():
    data = {"props": {"pageProps": {"listings": [{
        "id": "abc-123", "url": "/aanbod/volkswagen-golf-abc-123",
        "price": {"priceFormatted": "€ 18.950,-"},
        "vehicle": {"make": "Volkswagen", "model": "Golf", "modelVersionInput": "1.5 TSI R-Line DSG Pano",
                    "transmission": "Automatisch"},
        "tracking": {"firstRegistration": "05-2018", "mileage": "101000", "price": "18950"},
        "location": {"city": "Breda"}}], "numberOfResults": 1}}}
    html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'
    nodes = scan.as_listing_nodes(scan.next_data(html))
    c = scan.as_parse(nodes[0], "golf")
    assert (c["price"], c["km"], c["year"]) == (18950, 101000, 2018)
    assert c["url"] == "https://www.autoscout24.nl/aanbod/volkswagen-golf-abc-123"
    c = scan.evaluate(c)
    assert c["checks"]["auto"] == "oui" and c["checks"]["toit"] == "oui"


def test_btw_marge_field_and_private_seller():
    marge = scan.evaluate(base(model="golf", title="Golf 1.5 TSI 3x R-Line DSG pano",
                               text="Financiële informatie BTW/marge:  BTW niet verrekenbaar voor ondernemers (marge)"))
    assert marge["checks"]["tva"] == "marge" and marge["status"] == "rejete"
    btw = scan.evaluate(base(model="golf", title="Golf 1.5 TSI 3x R-Line DSG pano",
                             text="BTW/Marge : BTW verrekenbaar voor ondernemers"))
    assert btw["checks"]["tva"] == "récupérable" and btw["status"] == "match"
    priv = scan.evaluate(base(model="golf", title="Golf 1.5 TSI 3x R-Line DSG pano", seller_type="particulier",
                              text="BTW verrekenbaar"))
    assert priv["status"] == "rejete" and priv["checks"]["tva"] == "particulier"
