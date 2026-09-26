"""Journal d'audit JSONL : une ligne JSON par evenement, fichier en 0600.

Chaque appel d'outil recoit un identifiant de correlation qui suit toutes ses
lignes (decision, confirmation, resultat). L'ecriture est synchrone : la ligne
est sur disque avant de rendre la main, meme si le processus s'arrete aussitot.
Repris du journal de fedora-agents (src/logger.ts).
"""
from __future__ import annotations

import json
import os
import re
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_SECRET_KEY = re.compile(r"pass|secret|token|key|credential|authorization", re.IGNORECASE)
REDACTED = "***"


def new_correlation_id() -> str:
    return uuid.uuid4().hex


def default_audit_dir(environ: Mapping[str, str] | None = None) -> Path:
    """MCP_GUARD_AUDIT_DIR, sinon $XDG_STATE_HOME/mcp-guard, sinon ~/.local/state/mcp-guard."""
    env = os.environ if environ is None else environ
    if env.get("MCP_GUARD_AUDIT_DIR"):
        return Path(env["MCP_GUARD_AUDIT_DIR"])
    state = env.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(state) / "mcp-guard"


def redact(params: Mapping[str, Any]) -> dict[str, Any]:
    """Masque les valeurs dont le nom ressemble a un secret (password, token, api_key...)."""
    return {k: (REDACTED if _SECRET_KEY.search(k) else v) for k, v in params.items()}


class AuditLog:
    def __init__(self, directory: str | Path | None = None) -> None:
        self.directory = Path(directory) if directory is not None else default_audit_dir()

    def path_for(self, when: datetime) -> Path:
        return self.directory / f"audit-{when:%Y-%m-%d}.jsonl"

    def record(self, event: str, correlation_id: str, **fields: Any) -> dict[str, Any]:
        now = datetime.now(UTC)
        entry: dict[str, Any] = {"ts": now.isoformat(timespec="milliseconds"), "event": event,
                                 "correlation_id": correlation_id}
        entry.update({k: v for k, v in fields.items() if v is not None})
        if isinstance(entry.get("params"), Mapping):
            entry["params"] = redact(entry["params"])
        self._append(self.path_for(now), json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        return entry

    def _append(self, path: Path, line: str) -> None:
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.fchmod(fd, 0o600)  # un fichier cree ailleurs avec d'autres droits est resserre
            os.write(fd, line.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
