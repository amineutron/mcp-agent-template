"""Ligne de commande : mcp-guard serve | check-policy | --version."""
from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from . import __version__
from .confirm import confirm_mode
from .policy import Policy, PolicyError
from .roles import EnvRoleSource

EXAMPLES = ("enterprise", "ops")

DESCRIPTION = """\
mcp-guard : roles, liste blanche, confirmation humaine et journal d'audit pour serveurs MCP.

Variables d'environnement :
  MCP_GUARD_ROLE        role de l'appelant : lecteur (defaut), operateur, admin
  MCP_GUARD_CONFIRM     elicit (defaut : l'humain confirme via le client) ou client
  MCP_GUARD_AUDIT_DIR   dossier du journal d'audit JSONL (defaut ~/.local/state/mcp-guard)
  MCP_GUARD_DATA_DIR    bases SQLite des exemples (defaut ~/.local/state/mcp-guard-demo)
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mcp-guard", description=DESCRIPTION,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"mcp-guard {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="commande")

    serve = sub.add_parser("serve", help="lance un serveur d'exemple sur stdio (pour un client MCP)")
    serve.add_argument("--example", choices=EXAMPLES, default="enterprise",
                       help="enterprise : tickets, annuaire, inventaire ; ops : systemd et docker")
    serve.add_argument("--policy", help="policy.yaml (defaut : celle de l'exemple)")

    check = sub.add_parser("check-policy", help="valide un policy.yaml et resume ses regles")
    check.add_argument("path")
    return parser


def _check_policy(path: str) -> int:
    try:
        policy = Policy.load(path)
    except PolicyError as e:
        print(f"politique invalide : {e}", file=sys.stderr)
        return 1
    print(f"{path} : valide, outils hors liste {'permis' if policy.default_allow else 'refuses'}")
    for name, rule in sorted(policy.tools.items()):
        parts = [f"role>={rule.role.label}" if rule.role else "role selon le type",
                 *(["desactive"] if not rule.enabled else []),
                 *(f"{k} in {sorted(v)}" for k, v in rule.allowed_values.items())]
        print(f"  {name}: {', '.join(parts)}")
    return 0


def _serve(example: str, policy_path: str | None) -> int:
    try:
        policy = Policy.load(policy_path) if policy_path else None
        EnvRoleSource().current_role()  # role invalide : on le dit au demarrage, pas au premier appel
        confirm_mode()
    except (PolicyError, ValueError) as e:
        print(f"mcp-guard : {e}", file=sys.stderr)
        return 2
    if example == "enterprise":
        from .examples.enterprise import build_server
    else:
        from .examples.ops import build_server
    build_server(policy).run()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        return _serve(args.example, args.policy)
    if args.command == "check-policy":
        return _check_policy(args.path)
    build_parser().print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
