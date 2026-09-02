"""Discovery + extraction via APRR's Drupal JSON:API, instead of scraping
rendered HTML page by page.

Confirmed (2026-07, by the user inspecting the real API) that
voyage.aprr.fr (Drupal 10) exposes a standard JSON:API collection at
/jsonapi/node/service_area, paginated via the spec's own `links.next.href`
(no manual offset/limit math needed - just follow the link until it's
absent). The hub listing page (/aires-sur-autoroute/aires-de-services) only
has ~6 editorially-featured links, not the full list - discovery goes
through this API instead, never that page.

IMPORTANT: the field names below (field_locate_content, field_services,
field_highway, ...) come from the user's description of what they saw
inspecting the real API, not from raw JSON this session has verified
directly (no network access here - see README). The JSON:API envelope
itself (data/links.next/included, relationships.*.data) is the formal
spec, not a guess, so that part is solid; the *field* names are the part
that could be subtly off (as hub_pattern and @graph both were earlier for
Vinci) - hence every per-field access below degrades to a logged skip
instead of a crash, and this is still gated behind
config.OPERATORS["aprr"]["enabled_by_default"] = False pending a real
`probe` run.
"""
from __future__ import annotations

import json
import logging
from typing import Iterator
from urllib.parse import urljoin

from ..http import PoliteSession, RobotsDisallowed
from .base import ParsedAire, extract_keyword_equipment

log = logging.getLogger("scraper.adapters.aprr_jsonapi")

BASE = "https://voyage.aprr.fr"
COLLECTION_URL = f"{BASE}/jsonapi/node/service_area?include=field_services&page[limit]=50"


def _included_index(document: dict) -> dict:
    """(type, id) -> resource, for resolving relationships.*.data via the
    top-level `included` array (JSON:API spec, populated when the request
    used ?include=...)."""
    index = {}
    for resource in document.get("included", []) or []:
        rtype, rid = resource.get("type"), resource.get("id")
        if rtype and rid:
            index[(rtype, rid)] = resource
    return index


def _parse_lat_lng(raw) -> tuple[float | None, float | None]:
    """field_locate_content as described: "lat;lon" in a plain string, but
    Drupal geo-ish fields are sometimes a {"value": "..."} object instead -
    handle both without guessing which one this site actually uses."""
    if isinstance(raw, dict):
        raw = raw.get("value")
    if not isinstance(raw, str) or ";" not in raw:
        return None, None
    lat_str, lng_str = raw.split(";", 1)
    try:
        return float(lat_str.strip()), float(lng_str.strip())
    except ValueError:
        return None, None


def _service_names(node: dict, included: dict) -> list[str]:
    rel = (node.get("relationships") or {}).get("field_services", {}).get("data")
    if not rel:
        return []
    if isinstance(rel, dict):
        rel = [rel]
    names = []
    for ref in rel:
        resource = included.get((ref.get("type"), ref.get("id")))
        if not resource:
            continue
        # `title` is a guaranteed Drupal node attribute regardless of
        # content type/bundle, unlike a custom field name we'd be guessing.
        title = (resource.get("attributes") or {}).get("title")
        if title:
            names.append(title)
    return names


def _node_url(node: dict) -> str:
    attrs = node.get("attributes") or {}
    path = attrs.get("path")
    if isinstance(path, dict) and path.get("alias"):
        return urljoin(BASE, path["alias"])
    nid = attrs.get("drupal_internal__nid")
    if nid is not None:
        return f"{BASE}/node/{nid}"
    # Always present per the JSON:API spec - a real, dereferenceable URL,
    # just not a human-browsable page.
    self_link = (node.get("links") or {}).get("self", {})
    return self_link.get("href", f"{BASE}/jsonapi/node/service_area/{node.get('id', '')}")


def _node_to_parsed_aire(node: dict, included: dict, equip_synonyms: dict) -> ParsedAire | None:
    attrs = node.get("attributes") or {}
    name = attrs.get("title")
    if not name:
        log.warning("skipping service_area node without a title: %r", node.get("id"))
        return None

    lat, lng = _parse_lat_lng(attrs.get("field_locate_content"))
    service_names = _service_names(node, included)
    equip = extract_keyword_equipment(". ".join(service_names), equip_synonyms)

    return ParsedAire(
        name=name,
        lat=lat,
        lng=lng,
        equip=equip,
        source_url=_node_url(node),
        extraction_method="jsonapi" if service_names else "none",
        equip_brut={"services": service_names},
        # No reliable "Aire de repos"/"Aire de services" signal identified
        # yet for this API - left unset rather than inferred from e.g.
        # "has any services", which would be a guess dressed up as a fact.
        km=None,
    )


def iter_service_areas(
    http: PoliteSession, equip_synonyms: dict, on_page_issue=None
) -> Iterator[ParsedAire]:
    """Follow JSON:API pagination (links.next.href) from COLLECTION_URL
    until exhausted, yielding every service_area node as a ParsedAire."""
    url = COLLECTION_URL
    while url:

        def _issue(reason: str) -> None:
            log.warning("%s: %s", url, reason)
            if on_page_issue:
                on_page_issue(url, url, reason)

        try:
            resp = http.get(url)
        except RobotsDisallowed:
            _issue("robots.txt disallows this JSON:API page")
            return
        if resp.status_code != 200:
            _issue(f"JSON:API returned HTTP {resp.status_code}")
            return
        try:
            document = json.loads(resp.text)
        except json.JSONDecodeError:
            _issue("could not parse JSON:API response as JSON")
            return

        nodes = document.get("data")
        if not isinstance(nodes, list):
            _issue("JSON:API response has no top-level 'data' array (shape may have changed)")
            return

        included = _included_index(document)
        for node in nodes:
            parsed = _node_to_parsed_aire(node, included, equip_synonyms)
            if parsed is not None:
                yield parsed

        next_href = ((document.get("links") or {}).get("next") or {}).get("href")
        url = urljoin(url, next_href) if next_href else None
