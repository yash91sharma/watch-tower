"""The `wt` command. Each subcommand is a stub until its task adds the code."""

import argparse
import sys
from collections.abc import Sequence

# Subcommand name -> help text.
COMMANDS = {
    "serve": "Start the API and the workers.",
    "reset-admin": "Delete the admin password, TOTP and sessions.",
    "openapi": "Write the OpenAPI schema to stdout.",
}


def build_parser() -> argparse.ArgumentParser:
    """Make the parser for the `wt` command and its subcommands."""
    parser = argparse.ArgumentParser(prog="wt", description="Watch Tower.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, help_text in COMMANDS.items():
        subparsers.add_parser(name, help=help_text, description=help_text)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Run the `wt` command. `argv` is for tests. The default is `sys.argv[1:]`."""
    args = build_parser().parse_args(argv)
    sys.exit(f"wt {args.command}: not implemented")
