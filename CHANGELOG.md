# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions [SemVer](https://semver.org/lang/fr/).

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
