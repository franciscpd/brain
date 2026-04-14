"""Logging setup for brain-mcp.

CLI commands may write to stdout + stderr. The MCP server process (Phase 2)
must use stderr_only=True so that logging never corrupts the JSON-RPC stream.
"""

import logging
import os
import sys


def setup_logging(*, stderr_only: bool = False) -> None:
    """Configure the root 'brain_mcp' logger. Idempotent."""
    logger = logging.getLogger("brain_mcp")
    if logger.handlers:
        return

    level_name = os.environ.get("BRAIN_LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, level_name, logging.INFO))

    stream = sys.stderr  # always stderr for now (stderr_only reserved for Phase 2)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        logging.Formatter("%(levelname)s [%(name)s] %(message)s")
    )
    logger.addHandler(handler)
    logger.propagate = False
