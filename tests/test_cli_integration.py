"""End-to-end test of the run loop (discover -> fetch -> parse -> match ->
log -> output) with a stub adapter and stub HTTP client - no real network."""
import argparse
import json
from pathlib import Path

import scraper.cli as cli_mod
from scraper.adapters.base import ParsedAire

FIXTURE_INDEX = Path(__file__).parent / "fixtures" / "mini_index.html"


class StubAdapter:
    key = "vinci"
    label = "Stub Vinci"

    def discover(self, http):
        return [
            "https://example.test/aire-des-brouzils",
            "https://example.test/aire-nouvelle",
            "https://example.test/aire-sans-coords",
        ]

    def parse(self, html, url):
        if "brouzils" in url:
            return ParsedAire(
                name="Aire des Brouzils",
                lat=46.87924,
                lng=-1.28946,
                equip={"restaurant": "ok"},
                source_url=url,
                extraction_method="jsonld",
            )
        if "nouvelle" in url:
            # A real aire with real coords, but nothing in mini_index.html
            # nearby - should become a new-aire candidate, not be dropped.
            return ParsedAire(
                name="Aire Nouvelle Inconnue",
                lat=48.0,
                lng=2.0,
                equip={"wifi": "ok"},
                source_url=url,
                extraction_method="keyword",
            )
        # No coordinates and no plausible name match: genuinely not-found.
        return ParsedAire(
            name="Endroit sans rapport",
            lat=None,
            lng=None,
            equip={"wifi": "ok"},
            source_url=url,
            extraction_method="keyword",
        )


class StubHttp:
    def get(self, url):
        class R:
            status_code = 200
            text = "<html></html>"

        return R()


def _run(tmp_path, monkeypatch, limit=None):
    monkeypatch.setitem(cli_mod.ADAPTERS, "vinci", StubAdapter())
    monkeypatch.setitem(
        cli_mod.config.OPERATORS, "vinci", {"label": "Stub", "base_url": "", "enabled_by_default": True}
    )
    monkeypatch.setattr(cli_mod, "PoliteSession", lambda: StubHttp())

    args = argparse.Namespace(
        operator="vinci",
        index_html=str(FIXTURE_INDEX),
        state_dir=str(tmp_path / "state"),
        logs_dir=str(tmp_path / "logs"),
        output_dir=str(tmp_path / "output"),
        limit=limit,
        enable=False,
    )
    cli_mod.cmd_run(args)


def test_run_loop_writes_expected_output(tmp_path, monkeypatch):
    _run(tmp_path, monkeypatch)

    output_path = tmp_path / "output" / "enrichment_vinci.json"
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["nom_aire"] == "Aire des Brouzils"
    assert data[0]["id"] == 3003
    assert data[0]["equip_source"] == "vinci"

    not_found_log = (tmp_path / "logs" / "vinci_not_found.log").read_text(encoding="utf-8")
    assert "Endroit sans rapport" in not_found_log


def test_run_loop_proposes_new_aire_when_unmatched_but_geolocated(tmp_path, monkeypatch):
    _run(tmp_path, monkeypatch)

    new_output_path = tmp_path / "output" / "new_aires_vinci.json"
    data = json.loads(new_output_path.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["nom_aire"] == "Aire Nouvelle Inconnue"
    assert data[0]["id"] is None
    assert data[0]["lat"] == 48.0
    assert data[0]["lng"] == 2.0
    assert data[0]["equip"] == {"wifi": "ok"}

    new_candidates_log = (tmp_path / "logs" / "vinci_new_candidates.log").read_text(encoding="utf-8")
    assert "Aire Nouvelle Inconnue" in new_candidates_log


def test_resumed_run_does_not_repropose_same_new_candidate(tmp_path, monkeypatch):
    _run(tmp_path, monkeypatch)  # first pass processes all 3 URLs

    class StubAdapterWithDuplicateNewUrl(StubAdapter):
        def discover(self, http):
            # A different URL (e.g. the opposite-direction page) describing
            # the same physical aire, discovered in a later resumed run.
            return super().discover(http) + ["https://example.test/aire-nouvelle-doublon"]

        def parse(self, html, url):
            if "doublon" in url:
                return ParsedAire(
                    name="Aire Nouvelle Inconnue",
                    lat=48.0001,
                    lng=2.0001,
                    equip={"restaurant": "ok"},
                    source_url=url,
                    extraction_method="keyword",
                )
            return super().parse(html, url)

    monkeypatch.setitem(cli_mod.ADAPTERS, "vinci", StubAdapterWithDuplicateNewUrl())
    args = argparse.Namespace(
        operator="vinci",
        index_html=str(FIXTURE_INDEX),
        state_dir=str(tmp_path / "state"),
        logs_dir=str(tmp_path / "logs"),
        output_dir=str(tmp_path / "output"),
        limit=None,
        enable=False,
    )
    cli_mod.cmd_run(args)

    new_output_path = tmp_path / "output" / "new_aires_vinci.json"
    data = json.loads(new_output_path.read_text(encoding="utf-8"))
    assert len(data) == 1  # the near-duplicate wasn't proposed again

    not_found_log = (tmp_path / "logs" / "vinci_not_found.log").read_text(encoding="utf-8")
    assert "duplicate of already-proposed new aire" in not_found_log
