"""Command-line entry point for awkit."""

from __future__ import annotations

import argparse
import sys

from . import __version__

PROG = "awkit"
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "awkit harness: tool registry, adapters, state graph, rules, "
            "tick/run loop and dashboard for the awkit tools."
        ),
    )
    parser.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON output")
    parser.add_subparsers(dest="command", metavar="<command>")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help(sys.stderr)
        return EXIT_USAGE
    return 0
