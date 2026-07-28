from pathlib import Path

from scraper.adapters.vinci import VinciAdapter

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_jsonld_amenities_preferred_over_keyword_scan():
    html = (FIXTURES / "synthetic_jsonld_page.html").read_text(encoding="utf-8")
    adapter = VinciAdapter()
    parsed = adapter.parse(html, "https://example.test/aire-des-brouzils")

    assert parsed.name == "Aire des Brouzils"
    assert parsed.extraction_method == "jsonld"
    assert parsed.equip == {"restaurant": "ok", "wifi": "ok", "douches": "nok"}
    assert parsed.lat == 46.87924
    assert parsed.lng == -1.28946
    # Editorial text must never leak into the extracted facts.
    assert "marketing copy" not in str(parsed.equip)


def test_parse_keyword_fallback_with_negation():
    html = (FIXTURES / "synthetic_textonly_page.html").read_text(encoding="utf-8")
    adapter = VinciAdapter()
    parsed = adapter.parse(html, "https://example.test/aire-remouille-est")

    assert parsed.name == "Aire de Remouillé-Est"
    assert parsed.extraction_method == "keyword"
    assert parsed.equip["restaurant"] == "ok"
    assert parsed.equip["douches"] == "nok"
    assert parsed.equip["enfants"] == "ok"
    assert parsed.lat is None and parsed.lng is None


def test_parse_returns_none_without_a_name():
    adapter = VinciAdapter()
    parsed = adapter.parse("<html><body><p>no title, no h1</p></body></html>", "https://example.test/x")
    assert parsed is None


def test_parse_finds_equipment_conveyed_via_icon_alt_text():
    # Real pages often list amenities as icons (<img alt="Restaurant">)
    # rather than flowing sentences - get_text() alone misses these.
    html = (FIXTURES / "synthetic_icon_based_page.html").read_text(encoding="utf-8")
    adapter = VinciAdapter()
    parsed = adapter.parse(html, "https://example.test/aire-de-la-picardiere")

    assert parsed.name == "Aire de la Picardière"
    assert parsed.extraction_method == "keyword"
    assert parsed.equip["restaurant"] == "ok"
    assert parsed.equip["wifi"] == "ok"
    assert parsed.equip["douches"] == "nok"
