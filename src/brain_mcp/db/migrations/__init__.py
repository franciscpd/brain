"""Alembic migrations for brain-mcp.

Exposes run_upgrade_head() as the programmatic entry point used by `brain init`
and by the pytest fixtures.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config

_PACKAGE_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_CFG_PATH = _PACKAGE_ROOT.parent / "alembic.ini"


def run_upgrade_head() -> None:
    """Equivalent to `alembic upgrade head`. Uses brain_mcp.db.connection under the hood."""
    cfg = Config(str(_ALEMBIC_CFG_PATH))
    command.upgrade(cfg, "head")


def run_downgrade_base() -> None:
    """Equivalent to `alembic downgrade base`."""
    cfg = Config(str(_ALEMBIC_CFG_PATH))
    command.downgrade(cfg, "base")
