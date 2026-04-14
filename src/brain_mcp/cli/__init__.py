"""brain CLI — typer app and top-level exception handler."""

from __future__ import annotations

import logging
import sys

import typer

from brain_mcp.cli.init import init_command
from brain_mcp.errors import BrainError
from brain_mcp.logging import setup_logging

app = typer.Typer(
    help="brain-mcp: local-first personal knowledge server.",
    no_args_is_help=True,
)


@app.callback(invoke_without_command=True)
def _root_callback(ctx: typer.Context) -> None:
    """brain-mcp: local-first personal knowledge server."""


app.command("init")(init_command)


def main() -> None:
    setup_logging()
    try:
        app()
    except BrainError as exc:
        logging.getLogger("brain_mcp").error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
