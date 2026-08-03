"""Tests for the generic two-hop hub-page discovery helper (root -> hub ->
leaf pages) in adapters/base.py. No longer used by Vinci itself (which
switched to page-data.json, see test_vinci_pagedata.py) but kept as a
reusable primitive for other operators (sanef/aprr/area) without a
structured bulk data source. Uses a stub HTTP client - no real network."""
import re

from scraper.adapters.base import crawl_hub_pages
from scraper.http import RobotsDisallowed

ROOT_URL = "https://example.test/aires-et-services/"
HUB_A83 = "https://example.test/aires-et-services/a83/"
LEAF_VENDEE = "https://example.test/aires-et-services/a83/aire-de-vendee/"
LEAF_REMOUILLE = "https://example.test/aires-et-services/a83/aire-de-remouille-est/"

HUB_PATTERN = re.compile(r"^https://example\.test/aires-et-services/[a-z0-9]+/?$", re.I)
LEAF_PATTERN = re.compile(r"^https://example\.test/aires-et-services/[a-z0-9]+/[a-z0-9-]+/?$", re.I)

ROOT_HTML = f"""
<html><body>
<a href="/aires-et-services/a83/">A83</a>
<a href="/mentions-legales/">Mentions legales</a>
</body></html>
"""

HUB_HTML = f"""
<html><body>
<a href="aire-de-vendee/">Aire de Vendee</a>
<a href="aire-de-remouille-est/">Aire de Remouille-Est</a>
<a href="/aires-et-services/a83/">A83</a>
</body></html>
"""


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


def test_crawl_hub_pages_two_hops():
    http = FakeHttp({ROOT_URL: FakeResponse(200, ROOT_HTML), HUB_A83: FakeResponse(200, HUB_HTML)})

    leaves = sorted(crawl_hub_pages(http, ROOT_URL, HUB_PATTERN, LEAF_PATTERN))

    assert leaves == sorted([LEAF_VENDEE, LEAF_REMOUILLE])


def test_crawl_hub_pages_skips_disallowed_hub():
    http = FakeHttp(
        {ROOT_URL: FakeResponse(200, ROOT_HTML), HUB_A83: FakeResponse(200, HUB_HTML)},
        disallowed={HUB_A83},
    )

    leaves = list(crawl_hub_pages(http, ROOT_URL, HUB_PATTERN, LEAF_PATTERN))
    assert leaves == []


def test_crawl_hub_pages_no_root_access():
    http = FakeHttp({}, disallowed={ROOT_URL})
    leaves = list(crawl_hub_pages(http, ROOT_URL, HUB_PATTERN, LEAF_PATTERN))
    assert leaves == []


def test_hub_pattern_rejects_leaf_urls_as_hubs():
    assert HUB_PATTERN.match(HUB_A83)
    assert not HUB_PATTERN.match(LEAF_VENDEE)
    assert LEAF_PATTERN.match(LEAF_VENDEE)
    assert LEAF_PATTERN.match(LEAF_REMOUILLE)
    assert not LEAF_PATTERN.match(HUB_A83)
    assert not LEAF_PATTERN.match(ROOT_URL)
