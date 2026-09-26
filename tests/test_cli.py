import pytest

from mcp_guard import cli


def test_aide(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "MCP_GUARD_ROLE" in out and "serve" in out and "check-policy" in out


def test_version(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--version"])
    assert capsys.readouterr().out.startswith("mcp-guard ")


def test_check_policy(tmp_path, capsys):
    good = tmp_path / "p.yaml"
    good.write_text("tools:\n  a: {role: admin}\n  b: {allowed_values: {unit: [x.service]}}\n")
    assert cli.main(["check-policy", str(good)]) == 0
    out = capsys.readouterr().out
    assert "a: role>=admin" in out and "x.service" in out
    bad = tmp_path / "bad.yaml"
    bad.write_text("tools:\n  a: {role: root}\n")
    assert cli.main(["check-policy", str(bad)]) == 1


def test_serve_refuse_un_role_invalide_au_demarrage(monkeypatch, capsys):
    monkeypatch.setenv("MCP_GUARD_ROLE", "root")
    assert cli.main(["serve"]) == 2
    assert "role inconnu" in capsys.readouterr().err
