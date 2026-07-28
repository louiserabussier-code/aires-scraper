"""Match a scraped aire (name, optional lat/lng) against STATIC_AIRES.

Two aires from the same physical site (opposite carriageways) are often
~100-300m apart with names differing only by "Est"/"Ouest" or "Nord"/"Sud" -
so distance alone cannot disambiguate. We require both a name-similarity
score and a distance bound, and never strip direction suffixes.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from . import config
from .aires_data import Aire
from .geo import haversine_km

_PREFIXES = ("aire de l'", "aire de la ", "aire des ", "aire du ", "aire de ", "aire d'", "aire ")


def normalize_name(name: str) -> str:
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    n = n.lower().strip()
    for prefix in _PREFIXES:
        if n.startswith(prefix):
            n = n[len(prefix) :]
            break
    return " ".join(n.split())


def name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_name(a), normalize_name(b)).ratio()


@dataclass
class MatchResult:
    aire: Aire | None
    confidence: str  # "high" | "low" | "none"
    name_similarity: float
    distance_km: float | None


def find_match(
    scraped_name: str,
    scraped_lat: float | None,
    scraped_lng: float | None,
    candidates: list[Aire],
) -> MatchResult:
    best: MatchResult = MatchResult(None, "none", 0.0, None)

    for aire in candidates:
        distance = None
        if scraped_lat is not None and scraped_lng is not None:
            distance = haversine_km(scraped_lat, scraped_lng, aire.lat, aire.lng)
            if distance > config.MAX_MATCH_DISTANCE_REVIEW_KM:
                continue

        sim = name_similarity(scraped_name, aire.nom)

        if distance is not None:
            if sim >= config.NAME_SIMILARITY_THRESHOLD and distance <= config.MAX_MATCH_DISTANCE_KM:
                confidence = "high"
            elif (
                sim >= config.NAME_SIMILARITY_REVIEW_THRESHOLD
                and distance <= config.MAX_MATCH_DISTANCE_REVIEW_KM
            ):
                confidence = "low"
            else:
                continue
        else:
            # No coordinates scraped: geography can't back this up at all,
            # so it's capped at "low" no matter how good the name match
            # looks, and needs a much stricter bar to even qualify (see
            # config.NAME_SIMILARITY_NO_COORDS_THRESHOLD).
            if sim >= config.NAME_SIMILARITY_NO_COORDS_THRESHOLD:
                confidence = "low"
            else:
                continue

        rank = (confidence == "high", sim, -(distance or 0))
        best_rank = (best.confidence == "high", best.name_similarity, -(best.distance_km or 0))
        if best.aire is None or rank > best_rank:
            best = MatchResult(aire, confidence, sim, distance)

    return best
