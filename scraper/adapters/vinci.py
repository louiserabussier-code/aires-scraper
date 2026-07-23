"""Vinci Autoroutes adapter (ASF / Cofiroute / Escota network).

URL pattern and sitemap location are best-effort defaults, not verified
against a live page - run `--probe` and adjust before a full crawl.
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


class VinciAdapter(BaseAdapter):
    key = "vinci"
    label = "Vinci Autoroutes"
    base_url = "https://www.vinci-autoroutes.com"
    sitemap_url = "https://www.vinci-autoroutes.com/sitemap.xml"
    url_pattern = re.compile(r"aire[s]?-de-(service|repos)|aires-de-service", re.I)
    equip_synonyms = EQUIP_SYNONYMS
