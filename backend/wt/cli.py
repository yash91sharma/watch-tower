"""The `wt` command: serve, reset-admin, openapi."""

import argparse
import json
from collections.abc import Callable, Sequence

import uvicorn

from wt.auth import reset
from wt.config import Env, configure_logging
from wt.db import open_db
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
        # WT does not use X-Forwarded-*. No WT feature needs the client IP.
        proxy_headers=False,
        server_header=False,
        # Use the WT log setup.
        log_config=None,
    )


def reset_admin() -> None:
    """Delete the admin password, TOTP secret and all sessions."""
    engine = open_db(Env().data_dir)
    try:
        reset.reset_admin(engine)
    finally:
        engine.dispose()
    print(f"The admin is reset. {reset.NEXT_STEP}")


def openapi() -> None:
    """Write the OpenAPI schema (JSON) to stdout. `pnpm gen:api` makes the TS types from it."""
    schema = create_app(Env()).openapi()
    print(json.dumps(schema, indent=2))


# Subcommand name -> (help text, function).
COMMANDS: dict[str, tuple[str, Callable[[], None]]] = {
    "serve": ("Start the API and the workers.", serve),
    "reset-admin": ("Delete the admin password, TOTP and sessions.", reset_admin),
    "openapi": ("Write the OpenAPI schema to stdout.", openapi),
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
    COMMANDS[args.command][1]()
