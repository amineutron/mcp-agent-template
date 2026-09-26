"""Garde de bout en bout, par un vrai client MCP en memoire."""
import pytest
from conftest import elicitation, read_audit, text_of
from mcp import Client
from mcp.server.mcpserver import MCPServer

from mcp_guard import AuditLog, FixedRoleSource, Guard, Policy, Role, ToolKind

pytestmark = pytest.mark.anyio

POLICY = {"tools": {"lire": {}, "ecrire": {}, "detruire": {}, "sensible": {"role": "admin"},
                    "redemarrer": {"allowed_values": {"unit": ["ok.service"]}}, "panne": {}}}


def make(tmp_path, role=Role.ADMIN, confirm="elicit"):
    server = MCPServer("test")
    guard = Guard(server, Policy.from_mapping(POLICY), role_source=FixedRoleSource(role),
                  audit=AuditLog(tmp_path), confirm=confirm)
    calls = []

    @guard.tool(ToolKind.READ)
    def lire(n: int = 1) -> int:
        return n

    @guard.tool(ToolKind.WRITE)
    def ecrire(texte: str) -> str:
        calls.append(("ecrire", texte))
        return texte.upper()

    @guard.tool(ToolKind.DESTRUCTIVE)
    async def detruire(cible: str) -> str:
        calls.append(("detruire", cible))
        return f"{cible} detruit"

    @guard.tool(ToolKind.READ)
    def sensible() -> str:
        return "secret"

    @guard.tool(ToolKind.READ)
    def redemarrer(unit: str) -> str:
        return unit

    @guard.tool(ToolKind.READ)
    def panne() -> str:
        raise RuntimeError("disque plein")

    @guard.tool(ToolKind.READ)
    def hors_liste() -> str:
        return "jamais"

    return server, calls


async def test_annotations_publiees(tmp_path):
    server, _ = make(tmp_path)
    async with Client(server) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    assert tools["lire"].annotations.read_only_hint is True
    assert tools["ecrire"].annotations.read_only_hint is False
    assert tools["ecrire"].annotations.destructive_hint is False
    assert tools["detruire"].annotations.destructive_hint is True
    assert "mcp_guard_ctx" not in str(tools["lire"].input_schema)  # le Context n'est pas un argument


@pytest.mark.parametrize("role,tool,args,ok", [
    (Role.LECTEUR, "lire", {}, True),
    (Role.LECTEUR, "ecrire", {"texte": "a"}, False),
    (Role.OPERATEUR, "ecrire", {"texte": "a"}, True),
    (Role.OPERATEUR, "detruire", {"cible": "x"}, False),
    (Role.OPERATEUR, "sensible", {}, False),   # la politique durcit une simple lecture
    (Role.ADMIN, "sensible", {}, True),
])
async def test_roles(tmp_path, role, tool, args, ok):
    server, _ = make(tmp_path, role)
    async with Client(server, elicitation_callback=elicitation("accept")) as client:
        result = await client.call_tool(tool, args)
    assert result.is_error is (not ok)
    if not ok:
        assert "insuffisant" in text_of(result)


async def test_liste_blanche(tmp_path):
    server, _ = make(tmp_path)
    async with Client(server) as client:
        result = await client.call_tool("hors_liste", {})
    assert result.is_error and "liste blanche" in text_of(result)
    assert read_audit(tmp_path)[-1]["event"] == "denied"


async def test_valeurs_permises(tmp_path):
    server, _ = make(tmp_path)
    async with Client(server) as client:
        assert not (await client.call_tool("redemarrer", {"unit": "ok.service"})).is_error
        refuse = await client.call_tool("redemarrer", {"unit": "sshd.service"})
    assert refuse.is_error and "hors des valeurs permises" in text_of(refuse)


MODES = pytest.mark.parametrize("mode", ["auto", "legacy"])  # 2026-07-28 (aller-retour) et 2025-11-25


@MODES
async def test_destructif_confirme(tmp_path, mode):
    server, calls = make(tmp_path)
    ask = elicitation("accept", confirm=True)
    async with Client(server, elicitation_callback=ask, mode=mode) as client:
        result = await client.call_tool("detruire", {"cible": "srv"})
    assert not result.is_error and "srv detruit" in text_of(result)
    assert calls == [("detruire", "srv")]
    assert "detruire" in ask.asked[0] and "srv" in ask.asked[0]
    events = read_audit(tmp_path)
    assert [e["event"] for e in events] == ["allowed", "confirmation", "result"]
    assert len({e["correlation_id"] for e in events}) == 1
    assert events[1]["confirmed"] is True and events[1]["how"] == "elicit"


@MODES
@pytest.mark.parametrize("answer,confirm", [("accept", False), ("decline", True), ("cancel", True)])
async def test_destructif_refuse_rien_n_est_execute(tmp_path, answer, confirm, mode):
    server, calls = make(tmp_path)
    async with Client(server, elicitation_callback=elicitation(answer, confirm), mode=mode) as client:
        result = await client.call_tool("detruire", {"cible": "srv"})
    assert result.is_error and "refuse" in text_of(result)
    assert calls == []
    last = read_audit(tmp_path)[-1]
    assert last["event"] == "confirmation" and last["confirmed"] is False


@MODES
async def test_client_sans_elicitation_refuse(tmp_path, mode):
    server, calls = make(tmp_path)
    async with Client(server, mode=mode) as client:  # aucun callback : le client ne sait pas demander
        result = await client.call_tool("detruire", {"cible": "srv"})
    assert result.is_error and "elicitation" in text_of(result) and calls == []
    assert read_audit(tmp_path)[-1]["event"] == "denied"


async def test_confirmation_deleguee_au_client(tmp_path):
    server, calls = make(tmp_path, confirm="client")
    async with Client(server) as client:
        result = await client.call_tool("detruire", {"cible": "srv"})
    assert not result.is_error and calls == [("detruire", "srv")]
    confirmation = [e for e in read_audit(tmp_path) if e["event"] == "confirmation"][0]
    assert confirmation["how"] == "client"


async def test_erreur_journalisee_et_lisible(tmp_path):
    server, _ = make(tmp_path)
    async with Client(server) as client:
        result = await client.call_tool("panne", {})
    assert result.is_error and "disque plein" in text_of(result)
    last = read_audit(tmp_path)[-1]
    assert last["event"] == "result" and last["status"] == "error" and "disque plein" in last["error"]


async def test_role_invalide_refuse(tmp_path):
    class Broken:
        def current_role(self):
            raise ValueError("role inconnu : 'root'")

    server = MCPServer("t")
    guard = Guard(server, Policy.from_mapping({"tools": {"lire": {}}}), role_source=Broken(),
                  audit=AuditLog(tmp_path))

    @guard.tool(ToolKind.READ)
    def lire() -> str:
        return "x"

    async with Client(server) as client:
        result = await client.call_tool("lire", {})
    assert result.is_error and "role inconnu" in text_of(result)


@MODES
async def test_pas_de_question_si_le_role_ne_suffit_pas(tmp_path, mode):
    server, calls = make(tmp_path, Role.OPERATEUR)
    ask = elicitation("accept")
    async with Client(server, elicitation_callback=ask, mode=mode) as client:
        result = await client.call_tool("detruire", {"cible": "srv"})
    assert result.is_error and "admin requis" in text_of(result)
    assert ask.asked == [] and calls == []  # l'humain n'est jamais sollicite pour rien


@MODES
async def test_une_seule_question_par_appel(tmp_path, mode):
    server, _ = make(tmp_path)
    ask = elicitation("accept")
    async with Client(server, elicitation_callback=ask, mode=mode) as client:
        await client.call_tool("detruire", {"cible": "a"})
        await client.call_tool("detruire", {"cible": "b"})
    assert len(ask.asked) == 2
