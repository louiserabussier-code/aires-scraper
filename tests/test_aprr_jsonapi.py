"""Tests for discovery+extraction via APRR's Drupal JSON:API (replaces
scraping rendered pages one by one - see aprr_jsonapi.py docstring for why).
No real network: small synthetic fixtures mirroring the shapes the user
described from direct inspection, not the full real response."""
import json
from pathlib import Path

from scraper.adapters.aprr import AprrAdapter
from scraper.adapters.aprr_jsonapi import (
    COLLECTION_URL,
    _node_to_parsed_aire,
    _parse_lat_lng,
    iter_service_areas,
)
from scraper.http import RobotsDisallowed

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_lat_lng_handles_plain_string_and_value_object():
    assert _parse_lat_lng("46.607356;4.880161") == (46.607356, 4.880161)
    assert _parse_lat_lng({"value": "45.1;5.2"}) == (45.1, 5.2)
    assert _parse_lat_lng(None) == (None, None)
    assert _parse_lat_lng("not-coords") == (None, None)


def test_node_to_parsed_aire_maps_services_to_equip():
    page1 = _load("synthetic_jsonapi_page1.json")
    included = {(r["type"], r["id"]): r for r in page1["included"]}
    node = page1["data"][0]

    parsed = _node_to_parsed_aire(node, included, AprrAdapter.equip_synonyms)

    assert parsed.name == "Aire du Poulet de Bresse"
    assert parsed.lat == 46.607356
    assert parsed.lng == 4.880161
    assert parsed.source_url == "https://voyage.aprr.fr/aires-sur-autoroute/aires-de-services/aire-du-poulet-de-bresse"
    assert parsed.equip == {"restaurant": "ok", "wifi": "ok"}
    assert parsed.equip_brut == {"services": ["Restaurant", "Wifi"]}
    assert parsed.km is None  # no reliable signal for this API - never guessed


def test_node_to_parsed_aire_url_fallback_chain():
    page1 = _load("synthetic_jsonapi_page1.json")
    included = {}

    # No path.alias -> falls back to drupal_internal__nid.
    node2 = page1["data"][1]
    parsed2 = _node_to_parsed_aire(node2, included, AprrAdapter.equip_synonyms)
    assert parsed2.source_url == "https://voyage.aprr.fr/node/4242"
    assert parsed2.equip == {}


def test_node_to_parsed_aire_skips_untitled_node():
    page1 = _load("synthetic_jsonapi_page1.json")
    node3 = page1["data"][2]  # title: null, no relationships key at all
    assert _node_to_parsed_aire(node3, {}, AprrAdapter.equip_synonyms) is None


class FakeResponse:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


class FakeHttp:
    def __init__(self, pages, disallowed=frozenset()):
        self.pages = pages
        self.disallowed = disallowed
        self.requested = []

    def get(self, url):
        self.requested.append(url)
        if url in self.disallowed:
            raise RobotsDisallowed(url)
        return self.pages[url]


def test_iter_service_areas_follows_pagination():
    page1 = _load("synthetic_jsonapi_page1.json")
    page2 = _load("synthetic_jsonapi_page2.json")
    next_url = page1["links"]["next"]["href"]

    http = FakeHttp(
        {
            COLLECTION_URL: FakeResponse(200, json.dumps(page1)),
            next_url: FakeResponse(200, json.dumps(page2)),
        }
    )

    aires = list(iter_service_areas(http, AprrAdapter.equip_synonyms))

    # 3 real aires across both pages (node-3, untitled, was skipped).
    assert len(aires) == 3
    assert {a.name for a in aires} == {
        "Aire du Poulet de Bresse",
        "Aire Sans Services",
        "Aire de la Chaponne",
    }
    assert http.requested == [COLLECTION_URL, next_url]  # stopped once links.next was absent


def test_iter_service_areas_reports_page_failure():
    http = FakeHttp({}, disallowed={COLLECTION_URL})

    issues = []
    aires = list(
        iter_service_areas(
            http,
            AprrAdapter.equip_synonyms,
            on_page_issue=lambda hub_url, data_url, reason: issues.append(reason),
        )
    )

    assert aires == []
    assert len(issues) == 1
    assert "robots.txt" in issues[0]
