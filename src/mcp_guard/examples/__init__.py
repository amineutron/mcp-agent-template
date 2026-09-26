"""Exemples de serveurs gardes : entreprise (tickets, annuaire, base) puis ops (systemd, docker)."""
from __future__ import annotations

import os
from pathlib import Path

from ..audit import default_audit_dir


def default_data_dir() -> Path:
    """MCP_GUARD_DATA_DIR, sinon <dossier d'etat>/demo (bases SQLite des exemples)."""
    if os.environ.get("MCP_GUARD_DATA_DIR"):
        return Path(os.environ["MCP_GUARD_DATA_DIR"])
    return default_audit_dir().parent / "mcp-guard-demo"
