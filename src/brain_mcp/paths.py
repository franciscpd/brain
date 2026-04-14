"""Filesystem path resolution for brain-mcp.

All paths derive from BRAIN_HOME (default: ~/.brain). BRAIN_DB_PATH overrides
just the database location without affecting the rest of the tree.
"""

import os
from pathlib import Path


def brain_home() -> Path:
    """Return the brain home directory. Honors BRAIN_HOME, defaults to ~/.brain."""
    return Path(os.environ.get("BRAIN_HOME", Path.home() / ".brain")).expanduser()


def db_path() -> Path:
    """Return the SQLite database path. BRAIN_DB_PATH overrides, else derived from brain_home()."""
    override = os.environ.get("BRAIN_DB_PATH")
    return Path(override).expanduser() if override else brain_home() / "brain.db"


def model_cache_dir() -> Path:
    """Return the fastembed model cache directory."""
    return brain_home() / "models"


def device_id_path() -> Path:
    """Return the path to the persistent device_id file."""
    return brain_home() / "device_id"
