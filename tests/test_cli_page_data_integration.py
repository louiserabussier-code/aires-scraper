"""End-to-end test of the run loop for an operator with a bulk structured
data source (adapter.has_page_data), as used by Vinci's page-data.json -
verifies cli.py takes the iter_page_data_aires() branch instead of
discover()/parse(), and that equip_brut/km propagate into the output."""
import argparse
import json
from pathlib import Path

import scraper.cli as cli_mod
from scraper.adapters.base import ParsedAire

FIXTURE_INDEX = Path(__file__).parent / "fixtures" / "mini_index.html"


class StubPageDataAdapter:
    key = "vinci"
    label = "Stub Vinci (page-data)"
    has_page_data = True

    def discover(self, http):
        raise AssertionError("discover() should not be called for a has_page_data adapter")

    def parse(self, html, url):
        raise AssertionError("parse() should not be called for a has_page_data adapter")

    def iter_page_data_aires(self, http):
        yield ParsedAire(
            name="Aire des Brouzils",
            lat=46.87924,
            lng=-1.28946,
            equip={"restaurant": "ok"},
            source_url="https://example.test/a10/aire-des-brouzils/",
            extraction_method="page-data",
            equip_brut={"facilities": ["Vidange"], "brands": ["McDonald's (BUFFET)"]},
            km="Aire de services",
        )
        yield ParsedAire(
            name="Aire Nouvelle Inconnue",
            lat=48.0,
            lng=2.0,
            equip={"wifi": "ok"},
            source_url="https://example.test/a10/aire-nouvelle/",
            extraction_method="page-data",
            equip_brut={"facilities": ["Wifi"], "brands": []},
            km="Aire de repos",
        )


class StubHttp:
    def get(self, url):
        class R:
            status_code = 200
            text = "<html></html>"

        return R()


def test_page_data_branch_writes_expected_output(tmp_path, monkeypatch):
    monkeypatch.setitem(cli_mod.ADAPTERS, "vinci", StubPageDataAdapter())
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
    cli_mod.cmd_run(args)  # would raise via discover()/parse() if the branch were wrong

    output_path = tmp_path / "output" / "enrichment_vinci.json"
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["nom_aire"] == "Aire des Brouzils"
    assert data[0]["equip_brut"] == {"facilities": ["Vidange"], "brands": ["McDonald's (BUFFET)"]}

    new_output_path = tmp_path / "output" / "new_aires_vinci.json"
    new_data = json.loads(new_output_path.read_text(encoding="utf-8"))
    assert len(new_data) == 1
    assert new_data[0]["nom_aire"] == "Aire Nouvelle Inconnue"
    assert new_data[0]["km"] == "Aire de repos"
    assert new_data[0]["equip_brut"] == {"facilities": ["Wifi"], "brands": []}


def test_page_data_branch_is_resumable(tmp_path, monkeypatch):
    monkeypatch.setitem(cli_mod.ADAPTERS, "vinci", StubPageDataAdapter())
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
    cli_mod.cmd_run(args)  # resumed: both aires already checkpointed by source_url

    new_output_path = tmp_path / "output" / "new_aires_vinci.json"
    new_data = json.loads(new_output_path.read_text(encoding="utf-8"))
    assert len(new_data) == 1  # not duplicated
