import json
import subprocess

import pytest
from conftest import elicitation, text_of
from mcp import Client

from mcp_guard import AuditLog, FixedRoleSource, Role
from mcp_guard.examples import enterprise, ops
from mcp_guard.examples.ops import check_unit, parse_docker_ps, parse_show, systemctl_argv
from mcp_guard.examples.stores import Directory, ReadOnlyDatabase, TicketStore

# --- backends (logique pure) -------------------------------------------------


def test_tickets(tmp_path):
    store = TicketStore(tmp_path / "t.db")
    assert len(store.list()) == 5
    new = store.create("Ecran casse", "", "haute", "sdubois")
    assert new["status"] == "ouvert" and store.get(new["id"])["title"] == "Ecran casse"
    assert store.close(new["id"], "remplace")["status"] == "ferme"
    store.delete(new["id"])
    with pytest.raises(LookupError):
        store.get(new["id"])
    with pytest.raises(ValueError):
        store.create("x", "", "urgentissime", "a")
    with pytest.raises(ValueError):
        store.create("  ", "", "basse", "a")


def test_tickets_base_creee_une_seule_fois(tmp_path):
    TicketStore(tmp_path / "t.db").create("persiste", "", "basse", "a")
    assert len(TicketStore(tmp_path / "t.db").list()) == 6  # la graine n'est pas rejouee


def test_annuaire():
    d = Directory()
    assert [u["uid"] for u in d.search("admin")] == ["tbernard"]
    assert d.search("simon") == []                              # compte desactive masque
    assert [u["uid"] for u in d.search("simon", include_inactive=True)] == ["psimon"]
    assert {g["cn"] for g in d.get("cmartin")["groups"]} == {"direction", "admins-si"}
    assert "phone" not in d.get("cmartin")
    assert d.members("vpn") == ["lmoreau", "nlaurent"]
    with pytest.raises(ValueError):
        d.search("a")
    with pytest.raises(LookupError):
        d.get("inconnu")


def test_base_lecture_seule(tmp_path):
    db = ReadOnlyDatabase(tmp_path / "inv.db")
    assert {t["table"] for t in db.tables()} == {"assets", "licences", "backups"}
    res = db.query("SELECT hostname FROM backups WHERE status = 'en_retard'")
    assert res == {"columns": ["hostname"], "rows": [["srv-web"]], "truncated": False}
    assert db.query("SELECT * FROM assets", limit=2)["truncated"] is True


@pytest.mark.parametrize("sql", [
    "DELETE FROM assets",
    "UPDATE licences SET seats = 0",
    "SELECT 1; DROP TABLE assets",
    "PRAGMA writable_schema = 1",
    "ATTACH DATABASE '/tmp/x.db' AS x",
    "WITH x AS (SELECT 1) DELETE FROM assets",
])
def test_base_refuse_toute_ecriture(tmp_path, sql):
    db = ReadOnlyDatabase(tmp_path / "inv.db")
    with pytest.raises(ValueError):
        db.query(sql)
    assert len(db.query("SELECT * FROM assets", limit=200)["rows"]) == 6


# --- ops (parsing, sans rien executer) ---------------------------------------


def test_ops_parsing():
    assert parse_show("ActiveState=active\nSubState=running\n") == {"ActiveState": "active", "SubState": "running"}
    rows = parse_docker_ps(json.dumps({"Names": "web", "Image": "nginx", "State": "running", "X": 1}) + "\n")
    assert rows == [{"Names": "web", "Image": "nginx", "State": "running", "Status": None, "Ports": None}]
    assert systemctl_argv("user", "show", "a.service") == ["systemctl", "--user", "show", "a.service"]


@pytest.mark.parametrize("unit", ["nginx", "a;rm -rf /.service", "../x.service", "-x.service" * 20])
def test_ops_unite_invalide(unit):
    with pytest.raises(ValueError):
        check_unit(unit)


# --- serveurs d'exemple par un client MCP ------------------------------------



class FakeRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, argv):
        self.calls.append(list(argv))
        out = "ActiveState=active\nSubState=running\n" if "show" in argv else ""
        return subprocess.CompletedProcess(argv, 0, out, "")


@pytest.mark.anyio
async def test_serveur_entreprise(tmp_path):
    server = enterprise.build_server(data_dir=tmp_path, role_source=FixedRoleSource(Role.OPERATEUR),
                                     audit=AuditLog(tmp_path / "audit"))
    async with Client(server) as client:
        names = {t.name for t in (await client.list_tools()).tools}
        assert {"list_tickets", "create_ticket", "delete_ticket", "search_directory", "query_inventory"} <= names
        created = await client.call_tool("create_ticket", {"title": "Wifi coupe", "priority": "haute"})
        assert not created.is_error
        critique = await client.call_tool("create_ticket", {"title": "x", "priority": "critique"})
        assert critique.is_error                     # politique : critique reserve aux humains
        supprime = await client.call_tool("delete_ticket", {"ticket_id": 1})
        assert supprime.is_error and "admin requis" in text_of(supprime)
        sql = await client.call_tool("query_inventory", {"sql": "SELECT count(*) FROM assets"})
        assert "6" in text_of(sql)


@pytest.mark.anyio
async def test_serveur_ops_redemarrage_confirme(tmp_path):
    runner = FakeRunner()
    server = ops.build_server(runner=runner, role_source=FixedRoleSource(Role.ADMIN),
                              audit=AuditLog(tmp_path))
    async with Client(server, elicitation_callback=elicitation("accept")) as client:
        interdit = await client.call_tool("restart_service", {"unit": "sshd.service"})
        assert interdit.is_error and runner.calls == []
        ok = await client.call_tool("restart_service", {"unit": "nginx.service"})
    assert not ok.is_error
    assert ["systemctl", "restart", "nginx.service"] in runner.calls
