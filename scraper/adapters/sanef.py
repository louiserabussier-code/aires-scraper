"""Sanef adapter.

Corrected 2026-07: the traveler site is autoroutes.sanef.com, not
www.sanef.com (the corporate site) - confirmed via a real aire page URL
the user found (https://www.autoroutes.sanef.com/en/area/service/...).
Beyond the domain, everything else here (sitemap_url, url_pattern,
EQUIP_SYNONYMS) is still an unverified guess - no real HTML from this
domain has been checked yet. Gated behind --enable pending a successful
`probe` run, like aprr/area (was previously enabled_by_default=True,
pointed at the wrong domain the whole time - flipped off until verified).
"""
from __future__ import annotations

import re

from .base import BaseAdapter

EQUIP_SYNONYMS = {
    "restaurant": ["restaurant", "restauration", "brasserie", "fast-food", "fast food"],
    "animaux": ["espace canin", "aire pour chiens", "animaux acceptes", "espace animalier"],
    "enfants": ["aire de jeux", "espace enfants", "jeux pour enfants"],
    "pmr": ["pmr", "acces pmr", "accessible pmr", "personnes a mobilite reduite"],
    "douches": ["douche", "douches"],
    "eau": ["point d'eau", "eau potable", "borne d'eau"],
    "wifi": ["wifi", "wi-fi"],
}


class SanefAdapter(BaseAdapter):
    key = "sanef"
    label = "Sanef"
    base_url = "https://www.autoroutes.sanef.com"
    sitemap_url = "https://www.autoroutes.sanef.com/sitemap.xml"
    url_pattern = re.compile(r"aire[s]?-de-(service|repos)", re.I)
    equip_synonyms = EQUIP_SYNONYMS
