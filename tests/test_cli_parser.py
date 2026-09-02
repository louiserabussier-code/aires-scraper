"""Regression test for a real usability bug: `probe --operator aprr --limit
5 --enable` failed with argparse's "unrecognized arguments: --enable",
since --enable only existed on the `run` subcommand. probe is never gated
(read-only, no --enable needed) but should still accept the flag as a
no-op so reusing the same flags across both subcommands doesn't error."""
from scraper.cli import build_parser


def test_probe_accepts_enable_flag_as_a_noop():
    args = build_parser().parse_args(["probe", "--operator", "aprr", "--limit", "5", "--enable"])
    assert args.command == "probe"
    assert args.enable is True  # accepted, even though cmd_probe never reads it


def test_probe_enable_defaults_to_false():
    args = build_parser().parse_args(["probe", "--operator", "aprr"])
    assert args.enable is False


def test_run_still_requires_enable_flag_to_be_explicit():
    args = build_parser().parse_args(["run", "--operator", "aprr"])
    assert args.enable is False
    args = build_parser().parse_args(["run", "--operator", "aprr", "--enable"])
    assert args.enable is True
