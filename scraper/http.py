"""A polite HTTP client: robots.txt-aware, rate-limited per domain."""
from __future__ import annotations

import logging
import random
import time
from urllib.parse import urlparse

import requests

from . import config
from .robots import RobotsCache

log = logging.getLogger("scraper.http")


class RobotsDisallowed(Exception):
    def __init__(self, url: str):
        super().__init__(f"robots.txt disallows fetching {url}")
        self.url = url


class PoliteSession:
    """Wraps requests.Session with:
    - robots.txt checks (raises RobotsDisallowed instead of fetching)
    - a per-domain rate limiter: max(hard floor + jitter, robots Crawl-delay)
    """

    def __init__(self):
        self._session = requests.Session()
        # Beyond User-Agent, a couple of standard content-negotiation
        # headers - not browser fingerprint spoofing (no Sec-Fetch-*, no JS
        # capability claims), just what any well-formed HTTP client sends,
        # since a request with only a User-Agent header is itself an
        # unusual-looking fingerprint some basic bot filters flag.
        self._session.headers.update(
            {
                "User-Agent": config.USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            }
        )
        self._robots = RobotsCache(self._session)
        self._last_request_at: dict[str, float] = {}

    def _domain(self, url: str) -> str:
        return urlparse(url).netloc

    def _wait_for_turn(self, url: str) -> None:
        domain = self._domain(url)
        floor = random.uniform(config.MIN_DELAY_SECONDS, config.MAX_DELAY_SECONDS)
        crawl_delay = self._robots.crawl_delay(url)
        delay = max(floor, crawl_delay or 0.0)

        last = self._last_request_at.get(domain)
        if last is not None:
            elapsed = time.monotonic() - last
            remaining = delay - elapsed
            if remaining > 0:
                time.sleep(remaining)

    def get(self, url: str, **kwargs) -> requests.Response:
        if not self._robots.can_fetch(url):
            raise RobotsDisallowed(url)

        self._wait_for_turn(url)
        kwargs.setdefault("timeout", config.REQUEST_TIMEOUT_SECONDS)
        resp = self._session.get(url, **kwargs)
        self._last_request_at[self._domain(url)] = time.monotonic()
        return resp
