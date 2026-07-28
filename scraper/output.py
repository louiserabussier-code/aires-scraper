"""Writes the review JSON: one entry per (operator, matched aire).

Never touches index.html. Entries from different operators for the same
aire are kept side by side (not merged) so provenance stays visible and
conflicting operator data doesn't get silently resolved on the user's behalf.
"""
from __future__ import annotations

import json
from pathlib import Path


def append_entry(entries_path: str | Path, entry: dict) -> None:
    path = Path(entries_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def compile_json(entries_path: str | Path, output_path: str | Path) -> int:
    path = Path(entries_path)
    if not path.exists():
        entries = []
    else:
        with path.open(encoding="utf-8") as f:
            entries = [json.loads(line) for line in f if line.strip()]

    Path(output_path).write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return len(entries)


def make_entry(
    *,
    nom_aire: str,
    aire_id: int,
    aire_lat: float,
    aire_lng: float,
    equip: dict,
    equip_source: str,
    equip_date: str,
    source_url: str,
    match_confidence: str,
    name_similarity: float,
    distance_km: float | None,
    extraction_method: str,
) -> dict:
    return {
        "nom_aire": nom_aire,
        "id": aire_id,
        # lat/lng as already stored in index.html for this aire - never
        # taken from the operator site (which typically has no GPS data).
        "lat": aire_lat,
        "lng": aire_lng,
        "equip": equip,
        "equip_source": equip_source,
        "equip_date": equip_date,
        "source_url": source_url,
        "match_confidence": match_confidence,
        "name_similarity": round(name_similarity, 3),
        "distance_km": round(distance_km, 3) if distance_km is not None else None,
        "extraction_method": extraction_method,
    }
