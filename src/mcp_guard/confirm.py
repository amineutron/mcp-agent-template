"""Confirmation humaine avant une action destructrice : mode et formulaire.

Mode par defaut « elicit » : le serveur fait poser la question a l'humain par le
client (formulaire oui/non, voir guard.py). Tout ce qui n'est pas un « oui »
explicite vaut refus, y compris un client qui ne sait pas afficher la question.

Mode « client » (MCP_GUARD_CONFIRM=client), a activer en connaissance de cause :
le client fait deja confirmer l'humain en lisant l'annotation destructiveHint
(c'est le cas de Lyra). Le journal d'audit note alors que la confirmation a ete
deleguee au client.
"""
from __future__ import annotations

import os
from collections.abc import Mapping

from pydantic import BaseModel, Field

CONFIRM_MODES = ("elicit", "client")


class Confirmation(BaseModel):
    confirm: bool = Field(description="Confirmer l'action (oui / non)")


def confirm_mode(environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    mode = (env.get("MCP_GUARD_CONFIRM") or "elicit").strip().lower()
    if mode not in CONFIRM_MODES:
        raise ValueError(f"MCP_GUARD_CONFIRM inconnu : {mode!r} (attendu {' ou '.join(CONFIRM_MODES)})")
    return mode
