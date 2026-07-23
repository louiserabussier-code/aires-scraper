"""Shared plumbing for per-operator adapters.

IMPORTANT: none of the selectors/synonyms below have been checked against a
live page (this environment has no network access to the operator sites -
see README). Treat every adapter as a first draft: run `--probe` against a
handful of known URLs per operator before trusting a full run, for vinci and
sanef just as much as for aprr/area.

Two extraction strategies are tried, in order:
1. JSON-LD (schema.org `amenityFeature` / `LocationFeatureSpecification`) -
   a real, structured convention some sites use for amenities. If present,
   this is the most reliable signal and is preferred.
2. Keyword scan of the visible page text, looking for an equipment keyword
   and a nearby negation marker ("fermé", "hors service", "indisponible",
   "en travaux") to decide ok/nok. This is a heuristic fallback, flagged as
   lower-confidence in the output, and extracts only presence/absence facts -
   never copies surrounding descriptive text.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Iterable, Iterator

from bs4 import BeautifulSoup

from ..http import PoliteSession, RobotsDisallowed

log = logging.getLogger("scraper.adapters")

_SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

NEGATION_MARKERS = (
    "ferme",
    "fermee",
    "hors service",
    "indisponible",
    "non disponible",
    "en travaux",
    "temporairement",
    "inaccessible",
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+")


@dataclass
class ParsedAire:
    name: str
    lat: float | None
    lng: float | None
    equip: dict
    source_url: str
    extraction_method: str  # "jsonld" | "keyword" | "none"


def _strip_accents(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()


def iter_sitemap_urls(http: PoliteSession, sitemap_url: str, url_pattern: re.Pattern) -> Iterator[str]:
    """Yield URLs from a sitemap (or sitemap index, recursively) matching url_pattern."""
    try:
        resp = http.get(sitemap_url)
    except RobotsDisallowed:
        log.warning("robots.txt disallows sitemap %s -> skipping discovery via it", sitemap_url)
        return
    if resp.status_code != 200:
        log.warning("sitemap %s returned %s", sitemap_url, resp.status_code)
        return

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError:
        log.warning("could not parse sitemap XML at %s", sitemap_url)
        return

    locs = [el.text.strip() for el in root.findall(".//sm:loc", _SITEMAP_NS) if el.text]

    if root.tag.endswith("sitemapindex"):
        for loc in locs:
            yield from iter_sitemap_urls(http, loc, url_pattern)
    else:
        for loc in locs:
            if url_pattern.search(loc):
                yield loc


def extract_jsonld_amenities(soup: BeautifulSoup, synonyms: dict) -> tuple[dict, float | None, float | None]:
    """Look for schema.org amenityFeature / geo in any JSON-LD block."""
    equip: dict = {}
    lat = lng = None

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for node in candidates:
            if not isinstance(node, dict):
                continue
            geo = node.get("geo")
            if isinstance(geo, dict):
                lat = lat or geo.get("latitude")
                lng = lng or geo.get("longitude")

            features = node.get("amenityFeature")
            if not features:
                continue
            if isinstance(features, dict):
                features = [features]
            for feat in features:
                if not isinstance(feat, dict):
                    continue
                feat_name = _strip_accents(str(feat.get("name", "")))
                value = feat.get("value")
                for equip_key, keywords in synonyms.items():
                    if any(_strip_accents(kw) in feat_name for kw in keywords):
                        equip[equip_key] = "ok" if value in (True, "True", "true") else "nok"

    return equip, lat, lng


def extract_keyword_equipment(visible_text: str, synonyms: dict) -> dict:
    """Scan sentence-by-sentence so a negation elsewhere on the page (e.g. a
    different amenity being closed) can't bleed into an unrelated keyword."""
    text_norm = _strip_accents(visible_text)
    sentences = _SENTENCE_SPLIT_RE.split(text_norm)
    equip: dict = {}
    for equip_key, keywords in synonyms.items():
        for kw in keywords:
            kw_norm = _strip_accents(kw)
            for sentence in sentences:
                if kw_norm in sentence:
                    is_negated = any(marker in sentence for marker in NEGATION_MARKERS)
                    equip[equip_key] = "nok" if is_negated else "ok"
                    break
            if equip_key in equip:
                break
    return equip


def visible_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


class BaseAdapter:
    key: str = ""
    label: str = ""
    base_url: str = ""
    sitemap_url: str = ""
    url_pattern: re.Pattern = re.compile(r"aire", re.I)
    equip_synonyms: dict = field(default_factory=dict)

    def discover(self, http: PoliteSession) -> Iterable[str]:
        return iter_sitemap_urls(http, self.sitemap_url, self.url_pattern)

    def parse(self, html: str, url: str) -> ParsedAire | None:
        soup = BeautifulSoup(html, "lxml")

        name_tag = soup.find("h1")
        name = name_tag.get_text(strip=True) if name_tag else None
        if not name:
            title = soup.find("title")
            name = title.get_text(strip=True) if title else None
        if not name:
            log.warning("no name found on %s -> skipping", url)
            return None

        equip, lat, lng = extract_jsonld_amenities(soup, self.equip_synonyms)
        method = "jsonld" if equip else "none"

        if not equip:
            equip = extract_keyword_equipment(visible_text(soup), self.equip_synonyms)
            method = "keyword" if equip else "none"

        return ParsedAire(
            name=name,
            lat=float(lat) if lat is not None else None,
            lng=float(lng) if lng is not None else None,
            equip=equip,
            source_url=url,
            extraction_method=method,
        )
