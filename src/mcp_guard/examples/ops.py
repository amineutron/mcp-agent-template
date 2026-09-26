"""Exemple ops generique : etat systemd et docker en lecture, redemarrage avec confirmation.

    mcp-guard serve --example ops

Le redemarrage d'un service systeme demande des droits : preferer une regle sudoers
limitee a une unite precise, jamais un NOPASSWD sur systemctl entier. La politique
fixe la liste des unites redemarrables (allowed_values).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from ..guard import Guard
from ..policy import Policy
from ..roles import ToolKind

POLICY = Path(__file__).parent / "policies" / "ops.yaml"
UNIT_RE = re.compile(r"^[A-Za-z0-9@_.:-]{1,128}\.(service|timer|socket)$")
SHOW_PROPS = ("Description", "LoadState", "ActiveState", "SubState", "ActiveEnterTimestamp", "MainPID")

Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def run_command(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Execute sans shell, avec un delai : un appel bloque ne fige pas l'agent."""
    return subprocess.run(list(argv), capture_output=True, text=True, timeout=30, check=False)  # noqa: S603


def check_unit(unit: str) -> str:
    if not UNIT_RE.match(unit):
        raise ValueError(f"nom d'unite invalide : {unit!r} (ex. nginx.service)")
    return unit


def systemctl_argv(scope: str, *args: str) -> list[str]:
    if scope not in ("system", "user"):
        raise ValueError("scope doit valoir system ou user")
    return ["systemctl", *(["--user"] if scope == "user" else []), *args]


def parse_show(output: str) -> dict[str, str]:
    """Sortie de `systemctl show -p A -p B` (lignes cle=valeur) -> dict."""
    return dict(line.split("=", 1) for line in output.splitlines() if "=" in line)


def parse_docker_ps(output: str) -> list[dict[str, Any]]:
    """`docker ps --format '{{json .}}'` : un objet JSON par ligne."""
    keep = ("Names", "Image", "State", "Status", "Ports")
    return [{k: row.get(k) for k in keep} for row in (json.loads(line) for line in output.splitlines() if line.strip())]


def build_server(policy: Policy | None = None, runner: Runner = run_command, **guard_kwargs: Any) -> MCPServer:
    server = MCPServer("mcp-guard-ops", instructions=(
        "Serveur d'exemple mcp-guard : etat des services systemd et des conteneurs docker, "
        "redemarrage d'un service autorise par la politique apres confirmation humaine."))
    guard = Guard(server, policy or Policy.load(POLICY), **guard_kwargs)

    def run(argv: list[str]) -> str:
        proc = runner(argv)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout).strip() or f"code de sortie {proc.returncode}")
        return proc.stdout

    @guard.tool(ToolKind.READ, title="Etat d'un service")
    def service_status(unit: str, scope: str = "system") -> dict[str, str]:
        """Etat d'une unite systemd (chargee, active, depuis quand). scope : system ou user."""
        props = [a for p in SHOW_PROPS for a in ("-p", p)]
        return parse_show(run(systemctl_argv(scope, "show", *props, check_unit(unit))))

    @guard.tool(ToolKind.READ, title="Conteneurs docker")
    def list_containers(all_containers: bool = False) -> list[dict[str, Any]]:
        """Conteneurs docker (en marche, ou tous avec all_containers)."""
        if shutil.which("docker") is None and runner is run_command:
            raise RuntimeError("docker n'est pas installe sur cette machine")
        argv = ["docker", "ps", "--format", "{{json .}}", *(["--all"] if all_containers else [])]
        return parse_docker_ps(run(argv))

    @guard.tool(ToolKind.DESTRUCTIVE, title="Redemarrer un service")
    def restart_service(unit: str, scope: str = "system") -> dict[str, str]:
        """Redemarre une unite autorisee par la politique, apres confirmation humaine, et renvoie son etat."""
        run(systemctl_argv(scope, "restart", check_unit(unit)))
        props = [a for p in SHOW_PROPS for a in ("-p", p)]
        return parse_show(run(systemctl_argv(scope, "show", *props, unit)))

    return server
