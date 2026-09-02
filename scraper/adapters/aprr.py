"""APRR adapter.

DISABLED BY DEFAULT (see config.OPERATORS["aprr"]["enabled_by_default"]).

Confirmed (2026-07, via a real HTML page the user shared) that the traveler
site is at voyage.aprr.fr (not www.aprr.fr - the corporate site), runs
Drupal 10 (data-drupal-selector, "Generator: Drupal 10"), not Gatsby -
so there's no page-data.json equivalent for discovery. Its JSON-LD is a
generic Article schema (headline/description/image), not a Place with
geo/amenityFeature, so it gives us nothing for equipment or coordinates.
Content is editorial prose ("Le restaurant, situé sur l'aire, vous
propose..."), not a structured facility/icon list - extraction falls back
to the generic keyword+negation scan in BaseAdapter.parse().

Discovery is not yet wired up: the user confirmed the hub listing page
(/aires-sur-autoroute/aires-de-services) has direct static <a href> links
to each aire (no JS-only button like Vinci's "Voir plus"), but we haven't
seen that page's HTML yet to know its pagination or exact link pattern -
and we're checking whether Drupal's JSON:API (/jsonapi/...) offers a bulk
shortcut similar to Vinci's page-data.json before committing to a crawl
pattern. Still requires a successful `probe` (and real discovery wiring)
before --enable.
"""
from __future__ import annotations

import re

from .base import BaseAdapter
from .vinci import EQUIP_SYNONYMS  # same French keyword set as a starting point


class AprrAdapter(BaseAdapter):
    key = "aprr"
    label = "APRR"
    base_url = "https://voyage.aprr.fr"
    sitemap_url = "https://voyage.aprr.fr/sitemap.xml"
    url_pattern = re.compile(r"aire[s]?-de-(service|repos)", re.I)
    equip_synonyms = EQUIP_SYNONYMS
