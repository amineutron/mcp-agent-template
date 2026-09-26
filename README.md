# mcp-agent-template — un agent MCP d'entreprise, garde
<!-- mcp-name: io.github.amineutron/mcp-guard -->

[![CI](https://github.com/amineutron/mcp-agent-template/actions/workflows/ci.yml/badge.svg)](https://github.com/amineutron/mcp-agent-template/actions/workflows/ci.yml) [![License: AGPL-3.0 + commercial](https://img.shields.io/badge/license-AGPL--3.0%20%2B%20commercial-blue.svg)](COMMERCIAL-LICENSE.md) [![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

**English summary.** A template for MCP servers that an IT department can let an
LLM agent use: every tool call goes through an allowlist policy (`policy.yaml`),
a caller role (`lecteur` / `operateur` / `admin`, derived from the MCP tool
annotations), per-parameter allowed values, a human confirmation for destructive
actions (MCP elicitation, both the 2025-11-25 and 2026-07-28 protocols), and a
JSONL audit log (mode 0600, one correlation id per call). The `mcp-guard` package
ships two runnable examples: an enterprise one (tickets, a read-only LDAP-like
directory, a read-only SQL inventory, all on fictitious local data) and a generic
ops one (systemd and docker status, restart with confirmation). Local-first,
self-hosted, on-prem; no cloud, no telemetry. Dual licensed: AGPL-3.0, or a
commercial licence for companies of any size.

---

Donner des outils a un agent IA dans une entreprise pose toujours les memes
questions : **qui** a le droit de faire **quoi**, **qui a valide** une action
dangereuse, et **ou est la trace**. Ce depot est un modele (bouton « Use this
template ») qui y repond une fois pour toutes, autour du SDK MCP officiel.

## Ce que fait la garde

Chaque appel d'outil passe, dans l'ordre :

1. **Liste blanche** (`policy.yaml`) : un outil absent est refuse.
2. **Role de l'appelant** : le role minimal vient du type d'outil, et la
   politique peut seulement le durcir.

   | Type d'outil | Annotation MCP publiee | Role minimal |
   |---|---|---|
   | lecture | `readOnlyHint` | lecteur |
   | ecriture non destructrice | — | operateur |
   | destructif | `destructiveHint` | admin + confirmation humaine |

3. **Valeurs permises** : par exemple, seules certaines unites systemd peuvent
   etre redemarrees.
4. **Confirmation humaine** pour les outils destructifs : le client affiche la
   question a l'humain (elicitation MCP). Les controles 1 a 3 passent AVANT : on
   ne demande jamais a l'humain d'approuver ce que le role n'autorise pas. Tout ce
   qui n'est pas un « oui » explicite vaut refus, y compris un client qui ne sait
   pas poser la question.
5. **Journal d'audit** JSONL, fichier en 0600, un identifiant de correlation par
   appel qui relie la decision, la confirmation et le resultat. Les parametres qui
   ressemblent a des secrets (`password`, `token`, `api_key`...) sont masques.

Un refus renvoie une erreur lisible a l'agent, jamais un faux succes.

## Essayer

```bash
uvx mcp-guard --help
uvx mcp-guard serve --example enterprise   # tickets, annuaire, inventaire (donnees fictives)
uvx mcp-guard serve --example ops          # systemd et docker
uvx mcp-guard check-policy policy.yaml     # valide une politique et resume ses regles
```

Dans un client MCP (Claude Code, Claude Desktop...) :

```json
{
  "mcpServers": {
    "entreprise": {
      "command": "uvx",
      "args": ["mcp-guard", "serve", "--example", "enterprise"],
      "env": { "MCP_GUARD_ROLE": "operateur" }
    }
  }
}
```

| Variable | Role | Defaut |
|---|---|---|
| `MCP_GUARD_ROLE` | role de l'appelant : `lecteur`, `operateur`, `admin` | `lecteur` |
| `MCP_GUARD_CONFIRM` | `elicit` : l'humain confirme via le client ; `client` : le client confirme deja lui-meme (il lit `destructiveHint`) | `elicit` |
| `MCP_GUARD_AUDIT_DIR` | dossier du journal d'audit | `~/.local/state/mcp-guard` |
| `MCP_GUARD_DATA_DIR` | bases SQLite des exemples | `~/.local/state/mcp-guard-demo` |

Le role vient pour l'instant de la configuration du client : chaque poste ou
chaque profil recoit le sien. La source du role est une petite interface
(`RoleSource`) : une authentification par jeton pourra s'y brancher sans toucher
aux outils.

## Les exemples

**Entreprise** (`--example enterprise`), sur des donnees FICTIVES d'une societe
« Exemple SA » creees en local, sans aucun service externe :

- support : `list_tickets`, `get_ticket`, `create_ticket` (la priorite « critique »
  est reservee aux humains par la politique), `close_ticket`, `delete_ticket`
  (admin + confirmation) ;
- annuaire en lecture seule, facon LDAP : `search_directory`, `get_user`,
  `group_members` ;
- inventaire en SQL lecture seule : `list_tables`, `query_inventory`. Deux
  verrous : la base est ouverte en `mode=ro`, et un autorisateur SQLite refuse
  toute ecriture, `PRAGMA` ou `ATTACH`, meme cachee dans un `WITH`.

**Ops** (`--example ops`) : `service_status` et `list_containers` en lecture,
`restart_service` limite aux unites listees par la politique, apres confirmation.

## Ecrire son propre serveur

```python
from mcp.server.mcpserver import MCPServer
from mcp_guard import Guard, Policy, ToolKind

server = MCPServer("mon-agent")
guard = Guard(server, Policy.load("policy.yaml"))

@guard.tool(ToolKind.READ, title="Lister les commandes")
def list_orders(status: str = "ouverte") -> list[dict]:
    """Commandes du jour."""
    ...

@guard.tool(ToolKind.DESTRUCTIVE, title="Annuler une commande")
def cancel_order(order_id: int) -> dict:
    """Annule une commande (admin + confirmation humaine)."""
    ...

server.run()
```

```yaml
# policy.yaml
version: 1
default: deny
tools:
  list_orders: {}
  cancel_order:
    allowed_values:
      order_id: ["1042", "1043"]
```

Pour brancher un vrai outil de tickets, un vrai annuaire LDAP ou une vraie base,
remplacer les classes de `src/mcp_guard/examples/stores.py` : les outils MCP et
la garde ne changent pas.

## Developpement

```bash
uv sync
uv run pytest        # garde, politique, audit, exemples, protocoles 2025-11-25 et 2026-07-28, stdio
uv run ruff check src tests
```

Un devcontainer est fourni (`.devcontainer/`).

## Licence

Double licence :

- **AGPL-3.0** ([LICENSE](LICENSE)) : gratuite pour les particuliers, les
  associations et l'enseignement ou la recherche ;
- **licence commerciale** pour les entreprises, quelle que soit leur taille :
  voir [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md).

Les contributions sont acceptees sous l'accord [CLA.md](CLA.md).

## Fait partie de l'ecosysteme Lyra

Meme approche que [fedora-agents](https://github.com/amineutron/fedora-agents)
(journal d'audit avec identifiant de correlation, annotations MCP) et
[Lyra](https://github.com/amineutron/lyra), l'assistant vocal French-first qui
fait confirmer l'humain avant chaque action sensible.
