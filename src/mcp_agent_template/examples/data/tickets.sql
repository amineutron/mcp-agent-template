-- Tickets FICTIFS du support d'Exemple SA (jeu de demonstration).
CREATE TABLE tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    priority TEXT NOT NULL CHECK (priority IN ('basse', 'normale', 'haute', 'critique')),
    status TEXT NOT NULL DEFAULT 'ouvert' CHECK (status IN ('ouvert', 'en_cours', 'resolu', 'ferme')),
    requester TEXT NOT NULL,
    assignee TEXT,
    resolution TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO tickets (title, description, priority, status, requester, assignee, created_at) VALUES
('Imprimante du 2e etage hors ligne', 'L''imprimante RDC-2 ne repond plus depuis ce matin.', 'normale', 'ouvert', 'nlaurent', 'sdubois', '2026-09-21 09:12:00'),
('Acces VPN refuse', 'Erreur d''authentification sur le VPN depuis le changement de mot de passe.', 'haute', 'en_cours', 'lmoreau', 'tbernard', '2026-09-22 08:40:00'),
('Disque plein sur srv-fichiers', 'Alerte supervision : /srv a 94 %.', 'critique', 'ouvert', 'tbernard', 'tbernard', '2026-09-23 02:05:00'),
('Nouveau poste pour arrivee', 'Preparer un portable pour une arrivee le 1er octobre.', 'normale', 'ouvert', 'cmartin', NULL, '2026-09-24 14:30:00'),
('Messagerie lente', 'Ouverture de la messagerie tres lente l''apres-midi.', 'basse', 'resolu', 'psimon', 'sdubois', '2026-09-15 16:20:00');
