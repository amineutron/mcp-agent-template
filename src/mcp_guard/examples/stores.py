"""Backends factices des exemples entreprise : tickets, annuaire, inventaire.

Aucun service externe : SQLite et un fichier JSON, crees depuis des donnees
FICTIVES a la premiere utilisation. A remplacer par l'outil de ticketing,
l'annuaire LDAP ou la base de l'entreprise ; les outils MCP ne changent pas.
"""
from __future__ import annotations

import json
import sqlite3
from importlib import resources
from pathlib import Path
from typing import Any

PRIORITIES = ("basse", "normale", "haute", "critique")
MAX_ROWS = 200


def _seed(name: str) -> str:
    return resources.files("mcp_guard.examples").joinpath("data", name).read_text(encoding="utf-8")


def _create_from_seed(path: Path, seed: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    with sqlite3.connect(tmp) as db:
        db.executescript(_seed(seed))
    tmp.replace(path)  # jamais de base a moitie creee sous le vrai nom


class TicketStore:
    """Tickets du support (lecture, creation, cloture, suppression)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        _create_from_seed(path, "tickets.sql")

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def list(self, status: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(limit, MAX_ROWS))
        with self._db() as db:
            if status:
                rows = db.execute("SELECT * FROM tickets WHERE status = ? ORDER BY id DESC LIMIT ?",
                                  (status, limit))
            else:
                rows = db.execute("SELECT * FROM tickets ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(r) for r in rows]

    def get(self, ticket_id: int) -> dict[str, Any]:
        with self._db() as db:
            row = db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            raise LookupError(f"ticket {ticket_id} introuvable")
        return dict(row)

    def create(self, title: str, description: str, priority: str, requester: str) -> dict[str, Any]:
        if not title.strip():
            raise ValueError("le titre est obligatoire")
        if priority not in PRIORITIES:
            raise ValueError(f"priorite {priority!r} inconnue (attendu {', '.join(PRIORITIES)})")
        with self._db() as db:
            cur = db.execute("INSERT INTO tickets (title, description, priority, requester) VALUES (?, ?, ?, ?)",
                             (title.strip(), description, priority, requester))
            new_id = cur.lastrowid
        return self.get(int(new_id))

    def close(self, ticket_id: int, resolution: str) -> dict[str, Any]:
        self.get(ticket_id)
        with self._db() as db:
            db.execute("UPDATE tickets SET status = 'ferme', resolution = ? WHERE id = ?", (resolution, ticket_id))
        return self.get(ticket_id)

    def delete(self, ticket_id: int) -> dict[str, Any]:
        ticket = self.get(ticket_id)
        with self._db() as db:
            db.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
        return ticket


class Directory:
    """Annuaire en lecture seule (structure inspiree de LDAP : uid, cn, mail, ou, groupes)."""

    def __init__(self, path: Path | None = None) -> None:
        raw = path.read_text(encoding="utf-8") if path else _seed("directory.json")
        data = json.loads(raw)
        self.users: list[dict[str, Any]] = data["users"]
        self.groups: dict[str, str] = {g["cn"]: g["description"] for g in data["groups"]}

    def search(self, query: str, include_inactive: bool = False) -> list[dict[str, Any]]:
        q = query.strip().lower()
        if len(q) < 2:
            raise ValueError("recherche d'au moins 2 caracteres")
        fields = ("uid", "cn", "mail", "title", "ou")
        return [self._public(u) for u in self.users
                if (include_inactive or u["active"]) and any(q in str(u[f]).lower() for f in fields)]

    def get(self, uid: str) -> dict[str, Any]:
        for user in self.users:
            if user["uid"] == uid:
                entry = self._public(user)
                entry["groups"] = [{"cn": g, "description": self.groups.get(g, "")} for g in user["groups"]]
                return entry
        raise LookupError(f"utilisateur {uid!r} introuvable")

    def members(self, group: str) -> list[str]:
        if group not in self.groups:
            raise LookupError(f"groupe {group!r} introuvable")
        return sorted(u["uid"] for u in self.users if group in u["groups"] and u["active"])

    @staticmethod
    def _public(user: dict[str, Any]) -> dict[str, Any]:
        return {k: user[k] for k in ("uid", "cn", "mail", "title", "ou", "active")}


_ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}


def _read_only_authorizer(action: int, *_: Any) -> int:
    """Seules les lectures passent : toute ecriture, PRAGMA ou ATTACH est refusee par SQLite."""
    return sqlite3.SQLITE_OK if action in _ALLOWED_ACTIONS else sqlite3.SQLITE_DENY


class ReadOnlyDatabase:
    """Base d'inventaire ouverte en lecture seule, deux verrous : fichier en mode=ro
    et autorisateur SQLite qui n'accepte que SELECT."""

    def __init__(self, path: Path) -> None:
        self.path = path
        _create_from_seed(path, "inventory.sql")

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        db.set_authorizer(_read_only_authorizer)
        return db

    def tables(self) -> list[dict[str, Any]]:
        db = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)  # sqlite_master : lecture de schema
        try:
            names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                              "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            return [{"table": n, "columns": [c[1] for c in db.execute(f"PRAGMA table_info({n})")]}  # noqa: S608
                    for n in names]
        finally:
            db.close()

    def query(self, sql: str, limit: int = 50) -> dict[str, Any]:
        statement = sql.strip().rstrip(";")
        if ";" in statement:
            raise ValueError("une seule requete a la fois")
        if not statement.lower().startswith(("select", "with")):
            raise ValueError("lecture seule : seules les requetes SELECT sont acceptees")
        limit = max(1, min(limit, MAX_ROWS))
        db = self._db()
        try:
            cur = db.execute(statement)
            rows = cur.fetchmany(limit + 1)
            columns = [d[0] for d in cur.description or []]
        except sqlite3.DatabaseError as e:
            raise ValueError(f"requete refusee : {e}") from e
        finally:
            db.close()
        return {"columns": columns, "rows": [list(r) for r in rows[:limit]], "truncated": len(rows) > limit}
