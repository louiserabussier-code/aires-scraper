"""Writes the review JSON: one entry per (operator, matched aire), plus a
separate file of "new aire" candidates - real aires found on an operator
site with no match in STATIC_AIRES, proposed with their real scraped
coordinates rather than silently dropped as not-found.

Never touches index.html. Entries from different operators for the same
aire are kept side by side (not merged) so provenance stays visible and
conflicting operator data doesn't get silently resolved on the user's behalf.
"""
from __future__ import annotations

import json
from pathlib import Path

from .aires_data import Aire


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
    equip_brut: dict | None = None,
) -> dict:
    return {
        "nom_aire": nom_aire,
        "id": aire_id,
        # lat/lng as already stored in index.html for this aire - never
        # taken from the operator site (which typically has no GPS data).
        "lat": aire_lat,
        "lng": aire_lng,
        "equip": equip,
        # Raw facility/brand names as scraped, for anything equip's fixed
        # schema doesn't cover (e.g. "Nurserie", "Laverie", brand names) -
        # kept for your own reference, not merged into equip.
        "equip_brut": equip_brut or {},
        "equip_source": equip_source,
        "equip_date": equip_date,
        "source_url": source_url,
        "match_confidence": match_confidence,
        "name_similarity": round(name_similarity, 3),
        "distance_km": round(distance_km, 3) if distance_km is not None else None,
        "extraction_method": extraction_method,
    }


def make_new_aire_entry(
    *,
    nom_aire: str,
    lat: float,
    lng: float,
    equip: dict,
    equip_source: str,
    equip_date: str,
    source_url: str,
    extraction_method: str,
    equip_brut: dict | None = None,
    km: str | None = None,
) -> dict:
    """An aire found on an operator site with no match in STATIC_AIRES -
    proposed as a brand new entry rather than dropped. No `id`: the user
    assigns one when integrating it into index.html. `km` (the aire-type
    category in STATIC_AIRES, e.g. "Aire de repos") is only filled in when
    the source reliably tells us which (e.g. Vinci's page-data `service`
    flag) - left None otherwise, since we have no other reliable way to
    infer it."""
    return {
        "nom_aire": nom_aire,
        "id": None,
        "status": "new_candidate",
        "lat": lat,
        "lng": lng,
        "km": km,
        "equip": equip,
        "equip_brut": equip_brut or {},
        "equip_source": equip_source,
        "equip_date": equip_date,
        "source_url": source_url,
        "extraction_method": extraction_method,
    }


def load_new_aire_candidates(entries_path: str | Path) -> list[Aire]:
    """Reload previously proposed new-aire candidates (from earlier
    invocations of the same operator's run) as synthetic Aire objects
    (id=None) so a resumed run doesn't propose the same gap twice."""
    path = Path(entries_path)
    if not path.exists():
        return []
    candidates = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            candidates.append(
                Aire(
                    id=None,
                    nom=entry["nom_aire"],
                    lat=entry["lat"],
                    lng=entry["lng"],
                    km=None,
                    note=None,
                    equip=entry.get("equip") or {},
                )
            )
    return candidates
