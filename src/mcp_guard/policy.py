"""policy.yaml : liste blanche d'outils, role minimal et valeurs permises par outil.

    version: 1
    default: deny            # outil absent de la liste : refuse (deny) ou permis (allow)
    tools:
      list_tickets: {}                         # permis, role minimal selon le type d'outil
      create_ticket: {role: operateur}
      restart_service:
        role: admin
        allowed_values: {unit: [nginx.service]}
      delete_everything: {enabled: false}

La politique ne peut que DURCIR : le role effectif est le plus eleve entre celui
du type d'outil (lecture/ecriture/destructif) et celui de la politique.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .roles import Role, parse_role

_TOOL_KEYS = {"role", "enabled", "allowed_values"}


class PolicyError(ValueError):
    """policy.yaml invalide : on refuse de demarrer plutot que de deviner."""


@dataclass(frozen=True)
class ToolRule:
    role: Role | None = None
    enabled: bool = True
    allowed_values: Mapping[str, frozenset[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class Policy:
    default_allow: bool = False
    tools: Mapping[str, ToolRule] = field(default_factory=dict)

    def rule_for(self, tool: str) -> ToolRule | None:
        """Regle de l'outil ; None s'il est refuse (desactive, ou absent avec default: deny)."""
        rule = self.tools.get(tool)
        if rule is None:
            return ToolRule() if self.default_allow else None
        return rule if rule.enabled else None

    @classmethod
    def from_mapping(cls, data: Any) -> Policy:
        if not isinstance(data, Mapping):
            raise PolicyError("la politique doit etre un dictionnaire YAML")
        unknown = set(data) - {"version", "default", "tools"}
        if unknown:
            raise PolicyError(f"cles inconnues : {sorted(unknown)}")
        if data.get("version", 1) != 1:
            raise PolicyError(f"version non supportee : {data.get('version')!r} (attendu 1)")
        default = data.get("default", "deny")
        if default not in ("deny", "allow"):
            raise PolicyError(f"default doit valoir deny ou allow, pas {default!r}")
        tools_raw = data.get("tools") or {}
        if not isinstance(tools_raw, Mapping):
            raise PolicyError("tools doit etre un dictionnaire outil -> regle")
        return cls(default_allow=default == "allow",
                   tools={str(name): _parse_rule(str(name), raw) for name, raw in tools_raw.items()})

    @classmethod
    def load(cls, path: str | Path) -> Policy:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as e:
            raise PolicyError(f"lecture de {path} impossible : {e}") from e
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as e:
            raise PolicyError(f"YAML invalide dans {path} : {e}") from e
        return cls.from_mapping(data or {})


def _parse_rule(name: str, raw: Any) -> ToolRule:
    raw = raw or {}
    if not isinstance(raw, Mapping):
        raise PolicyError(f"{name} : la regle doit etre un dictionnaire (ou {{}})")
    unknown = set(raw) - _TOOL_KEYS
    if unknown:
        raise PolicyError(f"{name} : cles inconnues {sorted(unknown)}")
    try:
        role = parse_role(str(raw["role"])) if "role" in raw else None
    except ValueError as e:
        raise PolicyError(f"{name} : {e}") from e
    enabled = raw.get("enabled", True)
    if not isinstance(enabled, bool):
        raise PolicyError(f"{name} : enabled doit valoir true ou false")
    values_raw = raw.get("allowed_values") or {}
    if not isinstance(values_raw, Mapping) or not all(isinstance(v, list) for v in values_raw.values()):
        raise PolicyError(f"{name} : allowed_values doit associer un parametre a une liste")
    allowed = {str(k): frozenset(str(x) for x in v) for k, v in values_raw.items()}
    return ToolRule(role=role, enabled=enabled, allowed_values=allowed)
