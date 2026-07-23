"""APRR adapter.

DISABLED BY DEFAULT (see config.OPERATORS["aprr"]["enabled_by_default"]).
The user asked to verify aprr.fr's page structure resembles vinci-autoroutes.com
before committing to it - that check cannot be done from this sandbox (no
network access to aprr.fr here, see README). Run `--probe --operator aprr`
against a couple of known aire URLs first; only pass `--enable aprr` once
that probe shows sensible extraction.
"""
from __future__ import annotations

import re

from .base import BaseAdapter
from .vinci import EQUIP_SYNONYMS  # same French keyword set as a starting point


class AprrAdapter(BaseAdapter):
    key = "aprr"
    label = "APRR"
    base_url = "https://www.aprr.fr"
    sitemap_url = "https://www.aprr.fr/sitemap.xml"
    url_pattern = re.compile(r"aire[s]?-de-(service|repos)", re.I)
    equip_synonyms = EQUIP_SYNONYMS
