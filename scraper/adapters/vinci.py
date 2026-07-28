"""Vinci Autoroutes adapter (ASF / Cofiroute / Escota network).

Discovery: confirmed (2026-07, via user-provided real URLs) that
vinci-autoroutes.com has no working /sitemap.xml (404). Real aire page URLs
look like:
  https://www.vinci-autoroutes.com/fr/aires-et-services/a83/aire-de-vendee/
  https://www.vinci-autoroutes.com/fr/aires-et-services/a83/aire-de-remouille-est/
i.e. /fr/aires-et-services/{autoroute-code}/{aire-slug}/. So we crawl in two
hops instead: the /fr/aires-et-services/ root should list one hub link per
highway (hub_pattern, one path segment), and each hub page should list its
aire pages (url_pattern, two path segments) - see base.crawl_hub_pages.

This discovery mechanism is inferred from two known-good URLs, not from
inspecting the root/hub pages themselves (still no live access from this
side) - if the root page doesn't actually list per-highway hub links this
way, `--probe` will report "no hub links matching pattern found" and
hub_pattern/root_url need adjusting. The equip_synonyms keyword list and
JSON-LD extraction are still unverified against a real page - probe with
--urls on the two URLs above to check.
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

_BASE = "https://www.vinci-autoroutes.com"


class VinciAdapter(BaseAdapter):
    key = "vinci"
    label = "Vinci Autoroutes"
    base_url = _BASE
    root_url = f"{_BASE}/fr/aires-et-services/"
    hub_pattern = re.compile(rf"^{re.escape(_BASE)}/fr/aires-et-services/[a-z0-9]+/?$", re.I)
    url_pattern = re.compile(rf"^{re.escape(_BASE)}/fr/aires-et-services/[a-z0-9]+/[a-z0-9-]+/?$", re.I)
    # Kept as a fallback in case a real sitemap turns up elsewhere later.
    sitemap_url = f"{_BASE}/sitemap.xml"
    equip_synonyms = EQUIP_SYNONYMS
