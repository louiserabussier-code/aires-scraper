"""Vinci Autoroutes adapter (ASF / Cofiroute / Escota network).

Discovery: confirmed (2026-07, via user-provided real HTML) that
vinci-autoroutes.com has no working /sitemap.xml (404), and that the root
listing page (/fr/aires-et-services/) mixes two families of single-segment
links:
  - real per-highway hub pages: /fr/aires-et-services/autoroute-a10/,
    .../autoroute-a83/, ... (30 of them) plus the oddball .../duplex-a86/
  - brand/equipment filter pages with no hyphen: .../mcdonalds/, .../bp/,
    .../wifi/, .../electrique/, etc. (not per-highway, but each still lists
    some real aire links, so crawling them isn't wrong, just incomplete on
    its own)
The actual aire detail pages use the short highway code either way:
  https://www.vinci-autoroutes.com/fr/aires-et-services/a83/aire-de-vendee/

First cut of hub_pattern used [a-z0-9]+ (no hyphen), which silently
excluded every "autoroute-aXX" hub link (all hyphenated) and matched only
the 13 hyphen-free brand pages - explaining why a real run only reached
~218 aires (whatever happened to carry one of those 13 brands) instead of
Vinci's full ~1500. Widened to [a-z0-9-]+ so both link families discover
(harmless overlap/redundancy for the brand pages, and dedup already
prevents double-counting a leaf found via multiple hubs).
"""
from __future__ import annotations

import re

from .base import BaseAdapter

EQUIP_SYNONYMS = {
    "restaurant": ["restaurant", "restauration", "brasserie", "fast-food", "fast food"],
    # Per user's domain knowledge of this network: the real wording is
    # "espace canin", not "animaux" - dropped synonyms that used the latter.
    "animaux": ["espace canin", "aire pour chiens"],
    "enfants": ["aire de jeux", "espace enfants", "jeux pour enfants"],
    # PMR-accessible toilets + priority parking are near-universal on this
    # network's aires by law/default, so generic "accessible PMR" wording
    # would be true almost everywhere and carries no real signal. Only a
    # specific loanable-wheelchair mention is an actual variable extra -
    # per user's domain knowledge, that's what "pmr":"ok" should mean here.
    "pmr": ["fauteuil roulant"],
    "douches": ["douche", "douches"],
    "eau": ["point d'eau", "eau potable", "borne d'eau"],
    "wifi": ["wifi", "wi-fi"],
}

_BASE = "https://www.vinci-autoroutes.com"


class VinciAdapter(BaseAdapter):
    key = "vinci"
    label = "Vinci Autoroutes"
    base_url = _BASE
    root_url = f"{_BASE}/fr/aires-et-services/"
    hub_pattern = re.compile(rf"^{re.escape(_BASE)}/fr/aires-et-services/[a-z0-9-]+/?$", re.I)
    url_pattern = re.compile(rf"^{re.escape(_BASE)}/fr/aires-et-services/[a-z0-9-]+/[a-z0-9-]+/?$", re.I)
    # Kept as a fallback in case a real sitemap turns up elsewhere later.
    sitemap_url = f"{_BASE}/sitemap.xml"
    equip_synonyms = EQUIP_SYNONYMS
