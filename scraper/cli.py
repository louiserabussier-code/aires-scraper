"""CLI entrypoint.

  python run_scraper.py probe --operator vinci --limit 5
  python run_scraper.py probe --operator aprr --urls https://www.aprr.fr/...
  python run_scraper.py run --operator vinci --limit 200
  python run_scraper.py run --operator aprr --enable   # only after probing aprr

`probe` never writes output/state - it's a read-only diagnostic to check an
operator's page structure before trusting it. `run` is the resumable full
crawl: safe to Ctrl-C and re-invoke, it picks up where it left off.
"""
from __future__ import annotations

import argparse
import itertools
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .adapters import ADAPTERS
from .aires_data import load_aires
from .http import PoliteSession, RobotsDisallowed
from .matching import find_match
from .output import append_entry, compile_json, make_entry
from .state import RunState

log = logging.getLogger("scraper.cli")


def cmd_probe(args: argparse.Namespace) -> None:
    adapter = ADAPTERS[args.operator]
    http = PoliteSession()

    if args.urls:
        urls = args.urls
    else:
        print(f"Discovering candidate URLs for {adapter.label} via sitemap...")
        urls = list(itertools.islice(adapter.discover(http), args.limit))
        if not urls:
            print(
                "No URLs discovered. The sitemap URL or url_pattern in "
                f"scraper/adapters/{args.operator}.py is likely wrong for the "
                "real site - inspect it manually and adjust, or pass --urls "
                "with known aire page URLs to probe directly."
            )
            return

    for url in urls:
        print(f"\n=== {url} ===")
        try:
            resp = http.get(url)
        except RobotsDisallowed:
            print("  BLOCKED by robots.txt - not fetched.")
            continue
        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code}")
            continue

        parsed = adapter.parse(resp.text, url)
        if parsed is None:
            print("  Could not find a name on this page (selector needs adjusting).")
            continue

        print(f"  name        : {parsed.name}")
        print(f"  lat/lng     : {parsed.lat}, {parsed.lng}")
        print(f"  extraction  : {parsed.extraction_method}")
        print(f"  equip facts : {parsed.equip or '(none found)'}")

    print(
        "\nReview the above before running a full crawl. If names/equip look "
        "wrong, adjust the selectors/synonyms/url_pattern in "
        f"scraper/adapters/{args.operator}.py and probe again."
    )


def cmd_run(args: argparse.Namespace) -> None:
    op_conf = config.OPERATORS[args.operator]
    if not op_conf["enabled_by_default"] and not args.enable:
        print(
            f"Operator '{args.operator}' is disabled by default pending a "
            f"successful `probe` run (see scraper/adapters/{args.operator}.py). "
            "Pass --enable once you've verified its page structure."
        )
        sys.exit(1)

    adapter = ADAPTERS[args.operator]
    aires = load_aires(args.index_html)
    http = PoliteSession()
    state = RunState(args.operator, state_dir=args.state_dir, logs_dir=args.logs_dir)

    output_dir = Path(args.output_dir)
    entries_path = output_dir / f"enrichment_{args.operator}.jsonl"
    equip_date = datetime.now(timezone.utc).strftime("%Y-%m")

    processed_this_run = 0
    for url in adapter.discover(http):
        if args.limit and processed_this_run >= args.limit:
            break
        if state.is_processed(url):
            continue
        processed_this_run += 1

        try:
            resp = http.get(url)
        except RobotsDisallowed:
            state.log_not_found(url, "robots.txt disallow")
            continue
        if resp.status_code != 200:
            state.log_not_found(url, f"http {resp.status_code}")
            continue

        parsed = adapter.parse(resp.text, url)
        if parsed is None:
            state.log_not_found(url, "no name extracted from page")
            continue
        if not parsed.equip:
            state.log_not_found(url, f"no equipment facts extracted for {parsed.name!r}")
            continue

        match = find_match(parsed.name, parsed.lat, parsed.lng, aires)
        if match.aire is None:
            state.log_not_found(url, f"no STATIC_AIRES match for {parsed.name!r}")
            continue

        entry = make_entry(
            nom_aire=match.aire.nom,
            aire_id=match.aire.id,
            equip=parsed.equip,
            equip_source=args.operator,
            equip_date=equip_date,
            source_url=url,
            match_confidence=match.confidence,
            name_similarity=match.name_similarity,
            distance_km=match.distance_km,
            extraction_method=parsed.extraction_method,
        )
        append_entry(entries_path, entry)
        state.log_found(url, match.aire.id, match.aire.nom, match.confidence)

        if processed_this_run % 20 == 0:
            log.info("%s: %d URLs processed this run so far", args.operator, processed_this_run)

    output_json = output_dir / f"enrichment_{args.operator}.json"
    total = compile_json(entries_path, output_json)
    print(
        f"\n{adapter.label}: {processed_this_run} URL(s) processed this run. "
        f"Totals so far -> found: {state.counts['found']}, not found: {state.counts['not_found']}."
    )
    print(f"Review file written: {output_json} ({total} entries)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="aires. equipment enrichment scraper")
    parser.add_argument("--index-html", default="index.html", help="Path to index.html")
    parser.add_argument("--state-dir", default="state")
    parser.add_argument("--logs-dir", default="logs")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Debug logging (per-request detail)"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_probe = sub.add_parser("probe", help="Diagnostic: fetch a few pages, print detected structure")
    p_probe.add_argument("--operator", required=True, choices=sorted(ADAPTERS))
    p_probe.add_argument("--limit", type=int, default=5)
    p_probe.add_argument("--urls", nargs="*", help="Specific URLs to probe instead of sitemap discovery")
    p_probe.set_defaults(func=cmd_probe)

    p_run = sub.add_parser("run", help="Full resumable crawl for one operator")
    p_run.add_argument("--operator", required=True, choices=sorted(ADAPTERS))
    p_run.add_argument("--limit", type=int, default=None, help="Max new URLs to process this invocation")
    p_run.add_argument(
        "--enable", action="store_true", help="Required for operators disabled by default (aprr, area)"
    )
    p_run.set_defaults(func=cmd_run)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args.func(args)


if __name__ == "__main__":
    main()
