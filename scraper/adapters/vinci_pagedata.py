"""Discovery + extraction via vinci-autoroutes.com's Gatsby page-data.json,
instead of scraping rendered hub-page HTML.

Confirmed (2026-07, via a real page-data.json the user fetched for A10) that
each highway hub page (/fr/aires-et-services/autoroute-a10/) has a Gatsby
page-data file at /page-data/fr/aires-et-services/autoroute-a10/page-data.json
containing the FULL list of that highway's service areas in one shot: exact
name, precise lat/lng, a `service` boolean (true = "Aire de services", false
= "Aire de repos" - this is STATIC_AIRES' `km` category), and a structured
list of `facilities` (internal `machineName`, e.g. "airedejeux") and
`brands` (name + `categoryCode`, e.g. "BUFFET"/"RESTAURATION").

This replaces the old rendered-HTML hub crawl entirely for Vinci: the
"Voir plus" button on hub pages turned out to be a client-side-only
control with zero aire links in the static HTML (see git history), so that
crawl only ever found aires indirectly via brand/category filter pages -
a small, brand-biased subset. Fetching one JSON file per highway (~30
requests total) instead of one page per aire (~1500 requests) is also far
gentler on the site.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Iterator

from bs4 import BeautifulSoup

from ..http import PoliteSession, RobotsDisallowed
from .base import ParsedAire, _extract_matching_links, extract_keyword_equipment

log = logging.getLogger("scraper.adapters.vinci_pagedata")

# Only real highway (or "duplex", e.g. A86's duplex section) hub links -
# distinct from the root page's brand/fuel filter links (mcdonalds, bp,
# wifi, ...), which have no page-data serviceAreas of their own.
# `_extract_matching_links` anchors with re.match(), so this must match from
# the start of the full absolute URL, not just the path.
HIGHWAY_HUB_PATTERN = re.compile(
    r"^https://www\.vinci-autoroutes\.com/fr/aires-et-services/(autoroute-[a-z0-9]+|duplex-[a-z0-9]+)/?$",
    re.I,
)

# Vinci's internal facility machineName -> our equip schema. Anything not
# listed here (vidange, gonflage, dab, nurserie, bornerecharge, laverie,
# presse, infotrafic, coworking, hotel, remarquable, bornesvlr,
# boiteauxlettres, produitsregionaux, brumisateur, gpl, parkingpl,
# parkingcaravane, stationservice, distribboissonnourriture...) has no
# equivalent in the app's tracked equip and is only kept in equip_brut.
FACILITY_MACHINE_NAME_TO_EQUIP = {
    "airedejeux": "enfants",
    "wifi": "wifi",
    "douches": "douches",
}

# Brand categoryCode -> equip. BUFFET (fast-food/snack chains, e.g.
# McDonald's, KFC) and RESTAURATION (sit-down restaurants) both count as
# "restaurant" being present.
BRAND_CATEGORY_TO_EQUIP = {
    "BUFFET": "restaurant",
    "RESTAURATION": "restaurant",
}


def page_data_url(base_url: str, hub_path: str) -> str:
    """/fr/aires-et-services/autoroute-a10/ -> {base}/page-data/fr/aires-et-services/autoroute-a10/page-data.json"""
    return f"{base_url}/page-data{hub_path.rstrip('/')}/page-data.json"


def _service_area_to_parsed_aire(entity: dict, base_url: str, equip_synonyms: dict) -> ParsedAire | None:
    url_path = entity.get("entityUrl", {}).get("path")
    name = entity.get("title")
    geo = entity.get("geolocation") or {}
    if not url_path or not name or "lat" not in geo or "lng" not in geo:
        log.warning("skipping incomplete serviceArea entry: %r", entity.get("guid"))
        return None

    facilities = [f["entity"] for f in entity.get("facilities", []) if f.get("entity")]
    brands = [b["entity"] for b in entity.get("brands", []) if b.get("entity")]

    equip: dict = {}
    for facility in facilities:
        equip_key = FACILITY_MACHINE_NAME_TO_EQUIP.get(facility.get("machineName", ""))
        if equip_key:
            equip[equip_key] = "ok"
    for brand in brands:
        equip_key = BRAND_CATEGORY_TO_EQUIP.get(brand.get("categoryCode", ""))
        if equip_key:
            equip[equip_key] = "ok"

    # Safety net for equip keys this network doesn't structure as a
    # facility/brand (animaux, pmr, eau) - scan the raw names in case one
    # ever does turn up phrased the way our synonyms expect (e.g. a future
    # "Espace canin" facility), without inventing facts that aren't there.
    names_text = ". ".join(f.get("name", "") for f in facilities + brands)
    for equip_key, value in extract_keyword_equipment(names_text, equip_synonyms).items():
        equip.setdefault(equip_key, value)

    equip_brut = {
        "facilities": [f.get("name") for f in facilities if f.get("name")],
        "brands": [
            f"{b.get('name')} ({b['categoryCode']})" if b.get("categoryCode") else b.get("name")
            for b in brands
            if b.get("name")
        ],
    }

    # entityUrl.path lacks a trailing slash in the JSON, but the site's real
    # URLs (confirmed by the user) always have one.
    source_url = f"{base_url}{url_path}/" if not url_path.endswith("/") else f"{base_url}{url_path}"

    return ParsedAire(
        name=name,
        lat=float(geo["lat"]),
        lng=float(geo["lng"]),
        equip=equip,
        source_url=source_url,
        extraction_method="page-data",
        equip_brut=equip_brut,
        km="Aire de services" if entity.get("service") else "Aire de repos",
    )


def parse_page_data(data: dict, base_url: str, equip_synonyms: dict) -> list[ParsedAire]:
    try:
        service_areas = data["result"]["data"]["content"]["serviceAreas"]
    except (KeyError, TypeError):
        log.warning("page-data.json has no result.data.content.serviceAreas - shape may have changed")
        return []

    aires = []
    for row in service_areas:
        entity = row.get("entity")
        if not entity:
            continue
        parsed = _service_area_to_parsed_aire(entity, base_url, equip_synonyms)
        if parsed is not None:
            aires.append(parsed)
    return aires


def iter_highway_page_data(
    http: PoliteSession, root_url: str, base_url: str, equip_synonyms: dict
) -> Iterator[ParsedAire]:
    """Fetch the root listing page for highway hub links, then one
    page-data.json per highway, yielding every aire found across all of
    them (already fully parsed - no further per-aire fetch needed)."""
    try:
        resp = http.get(root_url)
    except RobotsDisallowed:
        log.warning("robots.txt disallows root %s -> cannot discover highways", root_url)
        return
    if resp.status_code != 200:
        log.warning("root %s returned %s", root_url, resp.status_code)
        return

    soup = BeautifulSoup(resp.text, "lxml")
    hub_urls = list(_extract_matching_links(soup, root_url, HIGHWAY_HUB_PATTERN))
    if not hub_urls:
        log.warning("no highway hub links found on %s - HIGHWAY_HUB_PATTERN may need adjusting", root_url)
        return
    log.info("found %d highway hub(s) on %s", len(hub_urls), root_url)

    for hub_url in hub_urls:
        hub_path = hub_url[len(base_url) :] if hub_url.startswith(base_url) else hub_url
        data_url = page_data_url(base_url, hub_path)
        try:
            data_resp = http.get(data_url)
        except RobotsDisallowed:
            log.warning("robots.txt disallows %s -> skipping this highway", data_url)
            continue
        if data_resp.status_code != 200:
            log.warning("%s returned %s", data_url, data_resp.status_code)
            continue
        try:
            data = json.loads(data_resp.text)
        except json.JSONDecodeError:
            log.warning("could not parse JSON at %s", data_url)
            continue

        aires = parse_page_data(data, base_url, equip_synonyms)
        log.info("%s: %d aire(s)", data_url, len(aires))
        yield from aires
