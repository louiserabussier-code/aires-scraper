from pathlib import Path

from scraper.aires_data import load_aires

FIXTURE = Path(__file__).parent / "fixtures" / "mini_index.html"


def test_load_aires_parses_all_rows():
    aires = load_aires(FIXTURE)
    assert len(aires) == 4


def test_load_aires_fields():
    aires = load_aires(FIXTURE)
    by_id = {a.id: a for a in aires}
    assert by_id[3003].nom == "Aire des Brouzils"
    assert by_id[3003].equip == {"restaurant": "ok", "wifi": "ok"}
    assert by_id[1000].equip == {}
    assert by_id[1000].note is None
