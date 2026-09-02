"""CLI entrypoint.

  python run_scraper.py probe --operator vinci --limit 5
  python run_scraper.py probe --operator aprr --urls https://voyage.aprr.fr/...
  python run_scraper.py run --operator vinci --limit 200
  python run_scraper.py run --operator aprr --enable   # only after probing aprr

`probe` never writes output/state - it's a read-only diagnostic to check an
operator's page structure before trusting it. `run` is the resumable full
crawl: safe to Ctrl-C and re-invoke, it picks up where it left off.

Vinci is special-cased (adapter.has_page_data): instead of one HTML page
per aire, it's discovered+parsed in bulk from Gatsby page-data.json files
(one per highway) - see adapters/vinci_pagedata.py.
"""
from __future__ import annotations

import argparse
import itertools
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .adapters import ADAPTERS
from .adapters.base import ParsedAire
from .aires_data import Aire, load_aires
from .http import PoliteSession, RobotsDisallowed
from .matching import find_match
from .output import append_entry, compile_json, load_new_aire_candidates, make_entry, make_new_aire_entry
from .state import RunState

log = logging.getLogger("scraper.cli")


def _slug_for_url(url: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", url).strip("_")[:150] + ".html"


def _probe_urls(adapter, http: PoliteSession, args: argparse.Namespace) -> None:
    for url in args.urls:
        print(f"\n=== {url} ===")
        try:
            resp = http.get(url)
        except RobotsDisallowed:
            print("  BLOCKED by robots.txt - not fetched.")
            continue
        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code}")
            continue

        if args.save_html:
            out_dir = Path(args.save_html)
            out_dir.mkdir(parents=True, exist_ok=True)
            html_path = out_dir / _slug_for_url(url)
            html_path.write_text(resp.text, encoding="utf-8")
            print(f"  saved raw HTML -> {html_path}")

        parsed = adapter.parse(resp.text, url)
        if parsed is None:
            print("  Could not find a name on this page (selector needs adjusting).")
            continue

        print(f"  name        : {parsed.name}")
        print(f"  lat/lng     : {parsed.lat}, {parsed.lng}")
        print(f"  extraction  : {parsed.extraction_method}")
        print(f"  equip facts : {parsed.equip or '(none found)'}")


def cmd_probe(args: argparse.Namespace) -> None:
    adapter = ADAPTERS[args.operator]
    http = PoliteSession()

    if args.urls:
        _probe_urls(adapter, http, args)
        print("\nReview the above before running a full crawl.")
        return

    if getattr(adapter, "has_page_data", False):
        print(f"Fetching bulk structured data for {adapter.label}...")
        shown = 0
        for parsed in adapter.iter_page_data_aires(http):
            if shown >= args.limit:
                break
            shown += 1
            print(f"\n=== {parsed.source_url} ===")
            print(f"  name        : {parsed.name}")
            print(f"  lat/lng     : {parsed.lat}, {parsed.lng}")
            print(f"  km category : {parsed.km}")
            print(f"  equip facts : {parsed.equip or '(none found)'}")
            print(f"  equip_brut  : {parsed.equip_brut}")
        if shown == 0:
            print(
                "No aires found via the bulk data source. The discovery pattern "
                f"in scraper/adapters/{args.operator}_pagedata.py or "
                f"scraper/adapters/{args.operator}_jsonapi.py (whichever this "
                "operator uses) is likely wrong for the real site - inspect it "
                "manually and adjust."
            )
        else:
            print(f"\n{shown} aire(s) shown (limited by --limit; a full run covers the whole source).")
        return

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
    args.urls = urls
    _probe_urls(adapter, http, args)
    print(
        "\nReview the above before running a full crawl. If names/equip look "
        "wrong, adjust the selectors/synonyms/url_pattern in "
        f"scraper/adapters/{args.operator}.py and probe again."
    )


def _process_parsed_aire(
    parsed: ParsedAire | None,
    url: str,
    candidates: list[Aire],
    operator: str,
    equip_date: str,
    state: RunState,
    entries_path: Path,
    new_entries_path: Path,
) -> None:
    if parsed is None:
        state.log_not_found(url, "no name extracted from page")
        return

    match = find_match(parsed.name, parsed.lat, parsed.lng, candidates)

    if match.aire is None:
        if parsed.lat is not None and parsed.lng is not None:
            new_entry = make_new_aire_entry(
                nom_aire=parsed.name,
                lat=parsed.lat,
                lng=parsed.lng,
                equip=parsed.equip,
                equip_source=operator,
                equip_date=equip_date,
                source_url=url,
                extraction_method=parsed.extraction_method,
                equip_brut=parsed.equip_brut,
                km=parsed.km,
            )
            append_entry(new_entries_path, new_entry)
            candidates.append(
                Aire(
                    id=None,
                    nom=parsed.name,
                    lat=parsed.lat,
                    lng=parsed.lng,
                    km=parsed.km,
                    note=None,
                    equip=parsed.equip,
                )
            )
            state.log_new_candidate(url, parsed.name, parsed.lat, parsed.lng)
        else:
            state.log_not_found(url, f"no STATIC_AIRES match and no coordinates for {parsed.name!r}")
        return

    if match.aire.id is None:
        # Matched a new-aire candidate already proposed earlier this run
        # (or a resumed one) - nothing further to record.
        state.log_not_found(url, f"duplicate of already-proposed new aire {match.aire.nom!r}")
        return

    if not parsed.equip:
        state.log_not_found(
            url, f"matched id={match.aire.id} {match.aire.nom!r} but no equipment facts extracted"
        )
        return

    entry = make_entry(
        nom_aire=match.aire.nom,
        aire_id=match.aire.id,
        aire_lat=match.aire.lat,
        aire_lng=match.aire.lng,
        equip=parsed.equip,
        equip_source=operator,
        equip_date=equip_date,
        source_url=url,
        match_confidence=match.confidence,
        name_similarity=match.name_similarity,
        distance_km=match.distance_km,
        extraction_method=parsed.extraction_method,
        equip_brut=parsed.equip_brut,
    )
    append_entry(entries_path, entry)
    state.log_found(url, match.aire.id, match.aire.nom, match.confidence)


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
    new_entries_path = output_dir / f"new_aires_{args.operator}.jsonl"
    equip_date = datetime.now(timezone.utc).strftime("%Y-%m")

    # Candidates to match against: existing STATIC_AIRES plus any new-aire
    # candidates already proposed in a previous (possibly interrupted) run of
    # this operator, so we don't propose the same gap twice. New ones found
    # this run are appended here too, so later URLs in the same run see them.
    candidates = aires + load_new_aire_candidates(new_entries_path)

    processed_this_run = 0

    if getattr(adapter, "has_page_data", False):
        # Bulk structured source (one JSON per highway covers many aires) -
        # already fully parsed, no separate per-aire fetch needed. A failed
        # highway fetch (robots disallow, non-200, bad/empty JSON) is logged
        # durably instead of only as a console warning, so an unexpectedly
        # low total is diagnosable afterwards.
        for parsed in adapter.iter_page_data_aires(http, on_highway_issue=state.log_highway_issue):
            if args.limit and processed_this_run >= args.limit:
                break
            if state.is_processed(parsed.source_url):
                continue
            processed_this_run += 1
            _process_parsed_aire(
                parsed, parsed.source_url, candidates, args.operator, equip_date, state, entries_path, new_entries_path
            )
            if processed_this_run % 20 == 0:
                log.info("%s: %d aires processed this run so far", args.operator, processed_this_run)
    else:
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
            _process_parsed_aire(
                parsed, url, candidates, args.operator, equip_date, state, entries_path, new_entries_path
            )
            if processed_this_run % 20 == 0:
                log.info("%s: %d URLs processed this run so far", args.operator, processed_this_run)

    output_json = output_dir / f"enrichment_{args.operator}.json"
    total = compile_json(entries_path, output_json)
    new_output_json = output_dir / f"new_aires_{args.operator}.json"
    total_new = compile_json(new_entries_path, new_output_json)
    print(
        f"\n{adapter.label}: {processed_this_run} URL(s) processed this run. "
        f"Totals so far -> found: {state.counts['found']}, not found: {state.counts['not_found']}, "
        f"new candidates: {state.counts['new_candidate']}."
    )
    if state.highway_issue_count:
        print(
            f"WARNING: {state.highway_issue_count} highway/hub fetch issue(s) this run - "
            f"see {state.highway_issues_log_path} (some highways may be under-represented above)."
        )
    print(f"Review file written: {output_json} ({total} entries)")
    print(f"New-aire candidates written: {new_output_json} ({total_new} entries)")


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
    p_probe.add_argument("--urls", nargs="*", help="Specific URLs to probe instead of automatic discovery")
    p_probe.add_argument(
        "--save-html", metavar="DIR", help="Save each probed page's raw HTML into DIR for inspection"
    )
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
