"""Bout en bout : `mcp-guard serve` lance comme processus, client MCP sur stdio."""
import sys

import pytest
from conftest import read_audit, text_of
from mcp import Client, StdioServerParameters

pytestmark = pytest.mark.anyio


async def test_serveur_entreprise_sur_stdio(tmp_path):
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "mcp_guard.cli", "serve", "--example", "enterprise"],
        env={"MCP_GUARD_ROLE": "lecteur", "MCP_GUARD_AUDIT_DIR": str(tmp_path / "audit"),
             "MCP_GUARD_DATA_DIR": str(tmp_path / "data")})
    async with Client(params) as client:
        ok = await client.call_tool("search_directory", {"query": "support"})
        refuse = await client.call_tool("create_ticket", {"title": "x"})
    assert not ok.is_error and "sdubois" in text_of(ok)
    assert refuse.is_error and "operateur requis" in text_of(refuse)
    events = [(e["event"], e["tool"]) for e in read_audit(tmp_path / "audit")]
    assert events == [("allowed", "search_directory"), ("result", "search_directory"), ("denied", "create_ticket")]
    assert (tmp_path / "data" / "tickets.db").exists()
