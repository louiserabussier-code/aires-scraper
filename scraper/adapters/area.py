"""AREA adapter.

DISABLED BY DEFAULT - same rationale as aprr.py (same corporate group).
Probe first with `--probe --operator area`, enable with `--enable area`
only once the probe output looks right.
"""
from __future__ import annotations

import re

from .base import BaseAdapter
from .vinci import EQUIP_SYNONYMS

class AreaAdapter(BaseAdapter):
    key = "area"
    label = "AREA"
    base_url = "https://www.area-autoroute.fr"
    sitemap_url = "https://www.area-autoroute.fr/sitemap.xml"
    url_pattern = re.compile(r"aire[s]?-de-(service|repos)", re.I)
    equip_synonyms = EQUIP_SYNONYMS
