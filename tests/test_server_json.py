"""server.json doit rester acceptable par le registre MCP officiel et coherent avec le paquet."""

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
PROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]

# Limite imposee par le registre (erreur 422 "expected length <= 100" constatee a la publication).
REGISTRY_DESCRIPTION_MAX = 100


def test_description_fits_registry_limit():
    assert len(SERVER["description"]) <= REGISTRY_DESCRIPTION_MAX


def test_server_json_matches_package():
    assert SERVER["version"] == PROJECT["version"]
    for package in SERVER["packages"]:
        assert package["identifier"] == PROJECT["name"]
        assert package["version"] == PROJECT["version"]
