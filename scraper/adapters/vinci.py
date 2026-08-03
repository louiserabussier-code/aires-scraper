"""Vinci Autoroutes adapter (ASF / Cofiroute / Escota network).

Discovery + extraction go through Gatsby's page-data.json (see
vinci_pagedata.py) rather than scraping rendered HTML: the old hub-page
HTML crawl only ever found a small, brand-biased subset of aires (~218 of
~1500) because the real per-highway aire list turned out to be rendered
entirely client-side behind a "Voir plus" button, with zero aire links in
the static HTML. page-data.json is the exact data Gatsby hydrates that list
from, published as a plain static JSON file per hub page (no JS execution
needed) - confirmed against a real file: full aire list, exact coordinates,
`service` flag (Aire de repos/de services), and structured facilities/brands.
"""
from __future__ import annotations

from typing import Iterator

from .base import BaseAdapter, ParsedAire
from .vinci_pagedata import iter_highway_page_data

EQUIP_SYNONYMS = {
    "restaurant": ["restaurant", "restauration", "brasserie", "fast-food", "fast food"],
    # Per user's domain knowledge of this network: the real wording is
    # "espace canin", not "animaux" - dropped synonyms that used the latter.
    # (Not seen as a Vinci facility/brand in real page-data so far - kept as
    # a keyword-scan safety net in vinci_pagedata's fallback pass.)
    "animaux": ["espace canin", "aire pour chiens"],
    "enfants": ["aire de jeux", "espace enfants", "jeux pour enfants"],
    # PMR-accessible toilets + priority parking are near-universal on this
    # network's aires by law/default, so generic "accessible PMR" wording
    # would be true almost everywhere and carries no real signal. Narrowed
    # to only "fauteuil roulant" (loanable wheelchair), an actual variable
    # extra - per user's domain knowledge, that's what "pmr":"ok" means here.
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
    equip_synonyms = EQUIP_SYNONYMS

    # Tells cli.py to use iter_page_data_aires() instead of the generic
    # discover()-then-fetch-then-parse() loop: page-data.json already gives
    # us fully parsed aires, so there's no separate per-aire page to fetch.
    has_page_data = True

    def iter_page_data_aires(self, http, on_highway_issue=None) -> Iterator[ParsedAire]:
        yield from iter_highway_page_data(
            http, self.root_url, self.base_url, self.equip_synonyms, on_highway_issue=on_highway_issue
        )
