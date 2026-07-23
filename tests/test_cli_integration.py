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
            "https://example.test/aire-inconnue",
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
        return ParsedAire(
            name="Endroit sans rapport",
            lat=10.0,
            lng=10.0,
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


def test_run_loop_writes_expected_output(tmp_path, monkeypatch):
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
        limit=None,
        enable=False,
    )
    cli_mod.cmd_run(args)

    output_path = tmp_path / "output" / "enrichment_vinci.json"
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["nom_aire"] == "Aire des Brouzils"
    assert data[0]["id"] == 3003
    assert data[0]["equip_source"] == "vinci"

    not_found_log = (tmp_path / "logs" / "vinci_not_found.log").read_text(encoding="utf-8")
    assert "Endroit sans rapport" in not_found_log
