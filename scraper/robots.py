"""robots.txt compliance: fetch, cache, and check per-domain rules."""
from __future__ import annotations

import logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from . import config

log = logging.getLogger("scraper.robots")


class RobotsCache:
    """Fetches robots.txt once per domain (via our own polite HTTP call, not
    urllib's built-in fetch) and answers can_fetch / crawl_delay questions."""

    def __init__(self, session: requests.Session):
        self._session = session
        self._parsers: dict[str, RobotFileParser] = {}

    def _domain(self, url: str) -> str:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}"

    def _get_parser(self, url: str) -> RobotFileParser:
        domain = self._domain(url)
        if domain in self._parsers:
            return self._parsers[domain]

        rfp = RobotFileParser()
        robots_url = domain + "/robots.txt"
        try:
            resp = self._session.get(
                robots_url,
                timeout=config.REQUEST_TIMEOUT_SECONDS,
                headers={"User-Agent": config.USER_AGENT},
            )
            if resp.status_code == 200:
                rfp.parse(resp.text.splitlines())
                log.info("robots.txt loaded for %s", domain)
            elif resp.status_code in (401, 403):
                # Per RFC 9309 convention: treat as fully disallowed.
                rfp.parse(["User-agent: *", "Disallow: /"])
                log.warning(
                    "robots.txt for %s returned %s -> treating as fully disallowed",
                    domain,
                    resp.status_code,
                )
            else:
                # 404 or other: no robots.txt means everything is allowed.
                rfp.parse([])
                log.info(
                    "no robots.txt for %s (status %s) -> allow-all",
                    domain,
                    resp.status_code,
                )
        except requests.RequestException as exc:
            rfp.parse(["User-agent: *", "Disallow: /"])
            log.warning(
                "failed to fetch robots.txt for %s (%s) -> treating as fully disallowed",
                domain,
                exc,
            )

        self._parsers[domain] = rfp
        return rfp

    def can_fetch(self, url: str) -> bool:
        rfp = self._get_parser(url)
        return rfp.can_fetch(config.USER_AGENT, url)

    def crawl_delay(self, url: str) -> float | None:
        rfp = self._get_parser(url)
        delay = rfp.crawl_delay(config.USER_AGENT)
        return float(delay) if delay else None
