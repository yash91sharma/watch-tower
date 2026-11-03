"""The `wt` command. Each subcommand that has no code yet is a stub."""

import argparse
import sys
from collections.abc import Callable, Sequence

import uvicorn

from wt.config import Env, configure_logging
from wt.main import create_app

PORT = 8000


def serve() -> None:
    """Start the API and the workers."""
    env = Env()
    configure_logging(env.log_level)
    uvicorn.run(
        create_app(env),
        # All interfaces in the container. Docker publishes the port.
        host="0.0.0.0",  # noqa: S104
        port=PORT,
        workers=1,
        # WT reads X-Forwarded-* itself, only from WT_TRUSTED_PROXIES (see wt.main).
        proxy_headers=False,
        server_header=False,
        # Use the WT log setup.
        log_config=None,
    )


# Subcommand name -> (help text, function). None: not implemented yet.
COMMANDS: dict[str, tuple[str, Callable[[], None] | None]] = {
    "serve": ("Start the API and the workers.", serve),
    "reset-admin": ("Delete the admin password, TOTP and sessions.", None),
    "openapi": ("Write the OpenAPI schema to stdout.", None),
}


def build_parser() -> argparse.ArgumentParser:
    """Make the parser for the `wt` command and its subcommands."""
    parser = argparse.ArgumentParser(prog="wt", description="Watch Tower.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, (help_text, _) in COMMANDS.items():
        subparsers.add_parser(name, help=help_text, description=help_text)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Run the `wt` command. `argv` is for tests. The default is `sys.argv[1:]`."""
    args = build_parser().parse_args(argv)
    command = COMMANDS[args.command][1]
    if command is None:
        sys.exit(f"wt {args.command}: not implemented")
    command()
