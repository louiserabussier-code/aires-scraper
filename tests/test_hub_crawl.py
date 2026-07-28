"""Tests for the two-hop hub-page discovery (root -> per-highway hub ->
aire pages), added after vinci-autoroutes.com turned out to have no
sitemap.xml. Uses a stub HTTP client - no real network."""
import re

from scraper.adapters.base import crawl_hub_pages
from scraper.adapters.vinci import VinciAdapter
from scraper.http import RobotsDisallowed

ROOT_URL = "https://www.vinci-autoroutes.com/fr/aires-et-services/"
HUB_A83 = "https://www.vinci-autoroutes.com/fr/aires-et-services/a83/"
LEAF_VENDEE = "https://www.vinci-autoroutes.com/fr/aires-et-services/a83/aire-de-vendee/"
LEAF_REMOUILLE = "https://www.vinci-autoroutes.com/fr/aires-et-services/a83/aire-de-remouille-est/"

ROOT_HTML = f"""
<html><body>
<a href="/fr/aires-et-services/a83/">A83</a>
<a href="/fr/mentions-legales/">Mentions legales</a>
</body></html>
"""

HUB_HTML = f"""
<html><body>
<a href="aire-de-vendee/">Aire de Vendee</a>
<a href="aire-de-remouille-est/">Aire de Remouille-Est</a>
<a href="/fr/aires-et-services/a83/">A83</a>
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
    adapter = VinciAdapter()

    leaves = sorted(crawl_hub_pages(http, ROOT_URL, adapter.hub_pattern, adapter.url_pattern))

    assert leaves == sorted([LEAF_VENDEE, LEAF_REMOUILLE])


def test_crawl_hub_pages_skips_disallowed_hub():
    http = FakeHttp(
        {ROOT_URL: FakeResponse(200, ROOT_HTML), HUB_A83: FakeResponse(200, HUB_HTML)},
        disallowed={HUB_A83},
    )
    adapter = VinciAdapter()

    leaves = list(crawl_hub_pages(http, ROOT_URL, adapter.hub_pattern, adapter.url_pattern))
    assert leaves == []


def test_crawl_hub_pages_no_root_access():
    http = FakeHttp({}, disallowed={ROOT_URL})
    adapter = VinciAdapter()
    leaves = list(crawl_hub_pages(http, ROOT_URL, adapter.hub_pattern, adapter.url_pattern))
    assert leaves == []


def test_vinci_hub_pattern_rejects_leaf_urls_as_hubs():
    adapter = VinciAdapter()
    assert adapter.hub_pattern.match(HUB_A83)
    assert not adapter.hub_pattern.match(LEAF_VENDEE)
    assert adapter.url_pattern.match(LEAF_VENDEE)
    assert adapter.url_pattern.match(LEAF_REMOUILLE)
    assert not adapter.url_pattern.match(HUB_A83)
    assert not adapter.url_pattern.match(ROOT_URL)


def test_vinci_hub_pattern_matches_real_hyphenated_highway_links():
    # Real root page (2026-07): highway hub links are hyphenated
    # ("autoroute-a10", not "a10"), and a first-cut hub_pattern of
    # [a-z0-9]+ (no hyphen) silently excluded all 30 of them, matching
    # only 13 coincidentally hyphen-free brand pages (mcdonalds, bp, wifi,
    # ...) instead - explaining a real run that only reached ~218 aires.
    adapter = VinciAdapter()
    real_hub_links = [
        "https://www.vinci-autoroutes.com/fr/aires-et-services/autoroute-a10/",
        "https://www.vinci-autoroutes.com/fr/aires-et-services/autoroute-a83/",
        "https://www.vinci-autoroutes.com/fr/aires-et-services/duplex-a86/",
        "https://www.vinci-autoroutes.com/fr/aires-et-services/mcdonalds/",
    ]
    for url in real_hub_links:
        assert adapter.hub_pattern.match(url), url


def test_crawl_hub_pages_via_hyphenated_hub_link():
    hub_url = "https://www.vinci-autoroutes.com/fr/aires-et-services/autoroute-a10/"
    leaf = "https://www.vinci-autoroutes.com/fr/aires-et-services/a10/aire-de-poitou-charentes-nord/"
    root_html = """
    <html><body><a href="/fr/aires-et-services/autoroute-a10/">A10</a></body></html>
    """
    # The hub page links to the short-code leaf path, not a path relative
    # to its own (long-form) URL.
    hub_html = f'<html><body><a href="{leaf}">Aire de Poitou-Charentes Nord</a></body></html>'

    http = FakeHttp({ROOT_URL: FakeResponse(200, root_html), hub_url: FakeResponse(200, hub_html)})
    adapter = VinciAdapter()

    leaves = list(crawl_hub_pages(http, ROOT_URL, adapter.hub_pattern, adapter.url_pattern))
    assert leaves == [leaf]
