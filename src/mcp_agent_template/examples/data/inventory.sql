-- Inventaire FICTIF du parc d'Exemple SA : ouvert en LECTURE SEULE par l'exemple.
CREATE TABLE assets (
    id INTEGER PRIMARY KEY,
    hostname TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    os TEXT NOT NULL,
    owner TEXT,
    location TEXT NOT NULL,
    warranty_end TEXT
);
CREATE TABLE licences (
    id INTEGER PRIMARY KEY,
    product TEXT NOT NULL,
    seats INTEGER NOT NULL,
    used INTEGER NOT NULL,
    expires TEXT NOT NULL
);
CREATE TABLE backups (
    id INTEGER PRIMARY KEY,
    hostname TEXT NOT NULL,
    last_success TEXT NOT NULL,
    size_gb REAL NOT NULL,
    status TEXT NOT NULL
);
INSERT INTO assets (hostname, kind, os, owner, location, warranty_end) VALUES
('srv-fichiers', 'serveur', 'Debian 13', 'tbernard', 'salle serveur', '2028-03-31'),
('srv-ad', 'serveur', 'Windows Server 2022', 'tbernard', 'salle serveur', '2027-06-30'),
('srv-web', 'vm', 'Ubuntu 24.04', 'lmoreau', 'cluster', NULL),
('pc-compta-01', 'poste', 'Windows 11', 'nlaurent', 'etage 2', '2027-01-15'),
('pc-dev-01', 'poste', 'Fedora 42', 'lmoreau', 'etage 1', '2028-09-01'),
('imp-rdc-2', 'imprimante', 'firmware 4.2', NULL, 'etage 2', '2026-12-31');
INSERT INTO licences (product, seats, used, expires) VALUES
('Suite bureautique', 50, 47, '2027-01-31'),
('Antivirus', 60, 58, '2026-11-30'),
('Logiciel comptable', 5, 5, '2027-03-31');
INSERT INTO backups (hostname, last_success, size_gb, status) VALUES
('srv-fichiers', '2026-09-26 02:10:00', 412.5, 'ok'),
('srv-ad', '2026-09-26 02:40:00', 38.2, 'ok'),
('srv-web', '2026-09-19 02:05:00', 12.9, 'en_retard');
