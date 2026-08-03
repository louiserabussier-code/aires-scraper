"""Tests for discovery+extraction via Gatsby page-data.json (replaces the
old rendered-HTML hub crawl for Vinci, which only ever found a small
brand-biased subset of aires - see git history / README). No real network:
a small synthetic page-data.json fixture, not the full real file."""
import json
from pathlib import Path

from scraper.adapters.vinci import VinciAdapter
from scraper.adapters.vinci_pagedata import (
    HIGHWAY_HUB_PATTERN,
    iter_highway_page_data,
    page_data_url,
    parse_page_data,
)
from scraper.http import RobotsDisallowed

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://www.vinci-autoroutes.com"
ROOT_URL = f"{BASE}/fr/aires-et-services/"
HUB_A10 = f"{BASE}/fr/aires-et-services/autoroute-a10/"
DATA_URL_A10 = f"{BASE}/page-data/fr/aires-et-services/autoroute-a10/page-data.json"


def _load_fixture() -> dict:
    return json.loads((FIXTURES / "synthetic_page_data.json").read_text(encoding="utf-8"))


def test_page_data_url_construction():
    assert page_data_url(BASE, "/fr/aires-et-services/autoroute-a10/") == DATA_URL_A10
    # No trailing slash on the hub path should still work.
    assert page_data_url(BASE, "/fr/aires-et-services/autoroute-a10") == DATA_URL_A10


def test_highway_hub_pattern_distinguishes_highways_from_brand_pages():
    assert HIGHWAY_HUB_PATTERN.match(HUB_A10)
    assert HIGHWAY_HUB_PATTERN.match(f"{BASE}/fr/aires-et-services/duplex-a86/")
    assert not HIGHWAY_HUB_PATTERN.match(f"{BASE}/fr/aires-et-services/mcdonalds/")
    assert not HIGHWAY_HUB_PATTERN.match(f"{BASE}/fr/aires-et-services/a10/aire-de-vendee/")


def test_parse_page_data_maps_facilities_and_brands_to_equip():
    data = _load_fixture()
    aires = parse_page_data(data, BASE, VinciAdapter.equip_synonyms)
    assert len(aires) == 3

    service_area = next(a for a in aires if a.name == "Poitou Charentes Nord")
    assert service_area.lat == 46.296787591464
    assert service_area.lng == -0.37757781892178
    assert service_area.source_url == f"{BASE}/fr/aires-et-services/a10/aire-de-poitou-charentes-nord/"
    assert service_area.km == "Aire de services"
    assert service_area.equip == {"enfants": "ok", "wifi": "ok", "douches": "ok", "restaurant": "ok"}
    assert "Vidange" in service_area.equip_brut["facilities"]  # kept raw even though unmapped
    assert "McDonald's (BUFFET)" in service_area.equip_brut["brands"]

    rest_area = next(a for a in aires if a.name == "La Picardière")
    assert rest_area.km == "Aire de repos"
    assert rest_area.equip == {}  # camping-car/parking-pl/electrique aren't in the tracked schema

    canine_area = next(a for a in aires if a.name == "Aire de Test Canine")
    # "Espace canin" isn't in FACILITY_MACHINE_NAME_TO_EQUIP but is caught
    # by the keyword-scan safety net over raw facility/brand names.
    assert canine_area.equip == {"animaux": "ok"}


def test_iter_highway_page_data_end_to_end():
    class FakeResponse:
        def __init__(self, status_code, text=""):
            self.status_code = status_code
            self.text = text

    class FakeHttp:
        def __init__(self, pages):
            self.pages = pages

        def get(self, url):
            if url not in self.pages:
                raise RobotsDisallowed(url)
            return self.pages[url]

    root_html = f"""
    <html><body>
    <a href="/fr/aires-et-services/autoroute-a10/">A10</a>
    <a href="/fr/aires-et-services/mcdonalds/">McDonald's</a>
    </body></html>
    """
    http = FakeHttp(
        {
            ROOT_URL: FakeResponse(200, root_html),
            DATA_URL_A10: FakeResponse(200, json.dumps(_load_fixture())),
        }
    )

    aires = list(iter_highway_page_data(http, ROOT_URL, BASE, VinciAdapter.equip_synonyms))
    assert len(aires) == 3
    assert {a.name for a in aires} == {"Poitou Charentes Nord", "La Picardière", "Aire de Test Canine"}
    # The brand page (mcdonalds) must not have been treated as a highway hub.


def test_iter_highway_page_data_reports_per_highway_failures():
    # Real-world case that motivated this: a run with no --limit only
    # yielded aires from 1 of 29 highways, with the other 28 failures only
    # ever logged as an ephemeral console warning - on_highway_issue lets
    # the caller (RunState) record these durably instead.
    class FakeResponse:
        def __init__(self, status_code, text=""):
            self.status_code = status_code
            self.text = text

    class FakeHttp:
        def __init__(self, pages):
            self.pages = pages

        def get(self, url):
            if url not in self.pages:
                raise RobotsDisallowed(url)
            return self.pages[url]

    hub_a83 = f"{BASE}/fr/aires-et-services/autoroute-a83/"
    data_url_a83 = f"{BASE}/page-data/fr/aires-et-services/autoroute-a83/page-data.json"
    root_html = f"""
    <html><body>
    <a href="/fr/aires-et-services/autoroute-a10/">A10</a>
    <a href="/fr/aires-et-services/autoroute-a83/">A83</a>
    </body></html>
    """
    http = FakeHttp(
        {
            ROOT_URL: FakeResponse(200, root_html),
            DATA_URL_A10: FakeResponse(200, json.dumps(_load_fixture())),
            data_url_a83: FakeResponse(404),
            # hub_a83 itself is never fetched (only its page-data.json is).
        }
    )

    issues = []
    aires = list(
        iter_highway_page_data(
            http,
            ROOT_URL,
            BASE,
            VinciAdapter.equip_synonyms,
            on_highway_issue=lambda hub_url, data_url, reason: issues.append((hub_url, data_url, reason)),
        )
    )

    assert len(aires) == 3  # A10's aires still came through
    assert len(issues) == 1
    hub_url, data_url, reason = issues[0]
    assert hub_url == hub_a83
    assert data_url == data_url_a83
    assert "404" in reason
