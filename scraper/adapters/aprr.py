"""APRR adapter.

DISABLED BY DEFAULT (see config.OPERATORS["aprr"]["enabled_by_default"]) -
still requires a successful `probe --operator aprr` before --enable, since
the field names in aprr_jsonapi.py are unverified from this side (see that
module's docstring).

Confirmed (2026-07, via real pages the user shared) that the traveler site
is at voyage.aprr.fr (not www.aprr.fr - the corporate site), runs Drupal 10,
not Gatsby. Its per-aire JSON-LD is a generic Article schema (no
geo/amenityFeature) and content is editorial prose, not a structured
facility list - but Drupal exposes a standard JSON:API collection at
/jsonapi/node/service_area covering every aire with pagination, GPS
coordinates, and a service-name relationship, which is what
aprr_jsonapi.py uses instead of scraping rendered pages. The hub listing
page (/aires-sur-autoroute/aires-de-services) only has ~6 editorially
featured links, not the full list - not used for discovery.
"""
from __future__ import annotations

from typing import Iterator

from .aprr_jsonapi import iter_service_areas
from .base import BaseAdapter, ParsedAire
from .vinci import EQUIP_SYNONYMS  # same French keyword set as a starting point


class AprrAdapter(BaseAdapter):
    key = "aprr"
    label = "APRR"
    base_url = "https://voyage.aprr.fr"
    equip_synonyms = EQUIP_SYNONYMS

    # See VinciAdapter - same bulk-source mechanism, different API shape.
    has_page_data = True

    def iter_page_data_aires(self, http, on_highway_issue=None) -> Iterator[ParsedAire]:
        yield from iter_service_areas(http, self.equip_synonyms, on_page_issue=on_highway_issue)
