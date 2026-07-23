import requests

from scraper.robots import RobotsCache


class FakeResponse:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


class FakeSession:
    def __init__(self, responses):
        self.responses = responses  # url -> FakeResponse
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        return self.responses[url]


def test_allows_when_no_robots_txt():
    session = FakeSession({"https://example.com/robots.txt": FakeResponse(404)})
    cache = RobotsCache(session)
    assert cache.can_fetch("https://example.com/aire-de-test") is True


def test_respects_disallow():
    robots_txt = "User-agent: *\nDisallow: /private/\n"
    session = FakeSession({"https://example.com/robots.txt": FakeResponse(200, robots_txt)})
    cache = RobotsCache(session)
    assert cache.can_fetch("https://example.com/private/x") is False
    assert cache.can_fetch("https://example.com/public/x") is True


def test_treats_403_on_robots_as_fully_disallowed():
    session = FakeSession({"https://example.com/robots.txt": FakeResponse(403)})
    cache = RobotsCache(session)
    assert cache.can_fetch("https://example.com/anything") is False


def test_treats_fetch_exception_as_fully_disallowed():
    class RaisingSession:
        def get(self, url, **kwargs):
            raise requests.exceptions.ConnectionError("blocked")

    cache = RobotsCache(RaisingSession())
    assert cache.can_fetch("https://example.com/anything") is False


def test_crawl_delay_parsed():
    robots_txt = "User-agent: *\nCrawl-delay: 5\n"
    session = FakeSession({"https://example.com/robots.txt": FakeResponse(200, robots_txt)})
    cache = RobotsCache(session)
    assert cache.crawl_delay("https://example.com/x") == 5.0


def test_robots_only_fetched_once_per_domain():
    session = FakeSession({"https://example.com/robots.txt": FakeResponse(404)})
    cache = RobotsCache(session)
    cache.can_fetch("https://example.com/a")
    cache.can_fetch("https://example.com/b")
    assert session.calls == ["https://example.com/robots.txt"]
