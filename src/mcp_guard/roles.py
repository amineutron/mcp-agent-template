"""Roles de l'appelant et types d'outils.

Trois roles ordonnes, alignes sur les annotations MCP de l'outil :
lecture seule -> lecteur, ecriture non destructrice -> operateur,
destructif -> admin (et confirmation humaine).
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Protocol


class Role(IntEnum):
    LECTEUR = 1
    OPERATEUR = 2
    ADMIN = 3

    @property
    def label(self) -> str:
        return self.name.lower()


_ALIASES = {
    "lecteur": Role.LECTEUR, "reader": Role.LECTEUR, "read": Role.LECTEUR,
    "operateur": Role.OPERATEUR, "opérateur": Role.OPERATEUR, "operator": Role.OPERATEUR,
    "admin": Role.ADMIN, "administrateur": Role.ADMIN,
}


def parse_role(value: str) -> Role:
    """'lecteur' / 'operateur' / 'admin' (casse et accents toleres, alias anglais)."""
    role = _ALIASES.get(value.strip().lower())
    if role is None:
        raise ValueError(f"role inconnu : {value!r} (attendu lecteur, operateur ou admin)")
    return role


class ToolKind(Enum):
    """Nature d'un outil : fixe le role minimal et les annotations MCP publiees."""

    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"

    @property
    def min_role(self) -> Role:
        return {ToolKind.READ: Role.LECTEUR, ToolKind.WRITE: Role.OPERATEUR,
                ToolKind.DESTRUCTIVE: Role.ADMIN}[self]


class RoleSource(Protocol):
    """D'ou vient le role de l'appelant. Une source par jeton (Bearer) pourra
    s'ajouter sans toucher au reste : il suffit d'implementer current_role()."""

    def current_role(self) -> Role: ...


@dataclass(frozen=True)
class EnvRoleSource:
    """Role fixe dans la configuration du client MCP (variable MCP_GUARD_ROLE).

    Absente ou vide : role par defaut, lecteur (le moins de droits possible).
    Invalide : ValueError, pour ne jamais deviner un role."""

    variable: str = "MCP_GUARD_ROLE"
    default: Role = Role.LECTEUR
    environ: Mapping[str, str] = field(default_factory=lambda: os.environ)

    def current_role(self) -> Role:
        value = self.environ.get(self.variable, "")
        return parse_role(value) if value.strip() else self.default


@dataclass(frozen=True)
class FixedRoleSource:
    """Role constant : tests et serveurs mono-utilisateur."""

    role: Role

    def current_role(self) -> Role:
        return self.role
