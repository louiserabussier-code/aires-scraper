import json

from scraper.output import append_entry, compile_json, make_entry


def test_append_and_compile_roundtrip(tmp_path):
    entries_path = tmp_path / "enrichment_vinci.jsonl"
    entry = make_entry(
        nom_aire="Aire des Brouzils",
        aire_id=3003,
        equip={"restaurant": "ok"},
        equip_source="vinci",
        equip_date="2026-07",
        source_url="https://example.test/aire-des-brouzils",
        match_confidence="high",
        name_similarity=1.0,
        distance_km=0.0,
        extraction_method="jsonld",
    )
    append_entry(entries_path, entry)
    append_entry(entries_path, entry)

    output_path = tmp_path / "enrichment_vinci.json"
    count = compile_json(entries_path, output_path)

    assert count == 2
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data[0]["nom_aire"] == "Aire des Brouzils"
    assert data[0]["equip_source"] == "vinci"
    assert data[0]["distance_km"] == 0.0


def test_compile_json_missing_entries_file_gives_empty_list(tmp_path):
    output_path = tmp_path / "out.json"
    count = compile_json(tmp_path / "does_not_exist.jsonl", output_path)
    assert count == 0
    assert json.loads(output_path.read_text(encoding="utf-8")) == []
