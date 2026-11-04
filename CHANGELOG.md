# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions [SemVer](https://semver.org/lang/fr/).

## [0.2.0] - 2026-11-04

### Modifie

- Renommage : le paquet, le module Python, la commande et le nom dans le registre MCP passent de
  `mcp-guard` a `mcp-agent-template` (PyPI refuse `mcp-guard`, trop proche de `mcpguard`). Les
  variables d'environnement `MCP_GUARD_*` deviennent `MCP_AGENT_TEMPLATE_*`. La version 0.1.0
  n'a jamais ete publiee sur PyPI.

## [0.1.0] - 2026-09-27

### Ajoute

- `Guard` : liste blanche (`policy.yaml`), role de l'appelant (`lecteur` / `operateur` / `admin`,
  derive du type d'outil et durci par la politique), valeurs permises par parametre, confirmation
  humaine des outils destructifs (elicitation MCP, protocoles 2025-11-25 et 2026-07-28), journal
  d'audit JSONL en 0600 avec identifiant de correlation et masquage des secrets.
- Exemple entreprise : tickets, annuaire en lecture seule, inventaire SQL en lecture seule
  (donnees fictives locales).
- Exemple ops : etat systemd et docker, redemarrage limite par la politique et confirme.
- `mcp-guard` : `serve`, `check-policy`, `--version`.
