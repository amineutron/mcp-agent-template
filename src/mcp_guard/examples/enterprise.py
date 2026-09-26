"""Exemple entreprise : support (tickets), annuaire (lecture seule), inventaire (SQL lecture seule).

    mcp-guard serve --example enterprise
    MCP_GUARD_ROLE=operateur mcp-guard serve --example enterprise --policy ma-politique.yaml
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from ..guard import Guard
from ..policy import Policy
from ..roles import ToolKind
from . import default_data_dir
from .stores import Directory, ReadOnlyDatabase, TicketStore

POLICY = Path(__file__).parent / "policies" / "enterprise.yaml"


def build_server(policy: Policy | None = None, data_dir: Path | None = None, **guard_kwargs: Any) -> MCPServer:
    data = data_dir or default_data_dir()
    tickets = TicketStore(data / "tickets.db")
    directory = Directory()
    inventory = ReadOnlyDatabase(data / "inventory.db")

    server = MCPServer("mcp-guard-enterprise", instructions=(
        "Serveur d'exemple mcp-guard : support, annuaire et inventaire d'une entreprise FICTIVE. "
        "Chaque appel est controle (role, liste blanche) et journalise ; les actions destructrices "
        "demandent la confirmation d'un humain."))
    guard = Guard(server, policy or Policy.load(POLICY), **guard_kwargs)

    @guard.tool(ToolKind.READ, title="Lister les tickets")
    def list_tickets(status: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        """Tickets du support, les plus recents d'abord. status : ouvert, en_cours, resolu ou ferme."""
        return tickets.list(status, limit)

    @guard.tool(ToolKind.READ, title="Lire un ticket")
    def get_ticket(ticket_id: int) -> dict[str, Any]:
        """Detail d'un ticket."""
        return tickets.get(ticket_id)

    @guard.tool(ToolKind.WRITE, title="Creer un ticket")
    def create_ticket(title: str, description: str = "", priority: str = "normale",
                      requester: str = "agent-ia") -> dict[str, Any]:
        """Ouvre un ticket. priority : basse, normale, haute ou critique."""
        return tickets.create(title, description, priority, requester)

    @guard.tool(ToolKind.WRITE, title="Clore un ticket")
    def close_ticket(ticket_id: int, resolution: str) -> dict[str, Any]:
        """Passe un ticket a l'etat ferme avec sa resolution."""
        return tickets.close(ticket_id, resolution)

    @guard.tool(ToolKind.DESTRUCTIVE, title="Supprimer un ticket")
    def delete_ticket(ticket_id: int) -> dict[str, Any]:
        """Supprime definitivement un ticket (confirmation humaine, role admin)."""
        return tickets.delete(ticket_id)

    @guard.tool(ToolKind.READ, title="Chercher dans l'annuaire")
    def search_directory(query: str, include_inactive: bool = False) -> list[dict[str, Any]]:
        """Personnes dont le nom, l'identifiant, le mail, la fonction ou le service contient query."""
        return directory.search(query, include_inactive)

    @guard.tool(ToolKind.READ, title="Fiche annuaire")
    def get_user(uid: str) -> dict[str, Any]:
        """Fiche d'une personne et ses groupes."""
        return directory.get(uid)

    @guard.tool(ToolKind.READ, title="Membres d'un groupe")
    def group_members(group: str) -> list[str]:
        """Identifiants des membres actifs d'un groupe de l'annuaire."""
        return directory.members(group)

    @guard.tool(ToolKind.READ, title="Tables de l'inventaire")
    def list_tables() -> list[dict[str, Any]]:
        """Tables et colonnes de la base d'inventaire (parc, licences, sauvegardes)."""
        return inventory.tables()

    @guard.tool(ToolKind.READ, title="Requete SQL (lecture seule)")
    def query_inventory(sql: str, limit: int = 50) -> dict[str, Any]:
        """Une requete SELECT sur l'inventaire ; toute ecriture est refusee par la base elle-meme."""
        return inventory.query(sql, limit)

    return server
