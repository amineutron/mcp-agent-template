import stat

from conftest import read_audit

from mcp_guard import AuditLog, new_correlation_id, redact
from mcp_guard.audit import default_audit_dir


def test_fichier_et_dossier_prives(tmp_path):
    log = AuditLog(tmp_path / "audit")
    log.record("allowed", "cid1", tool="t")
    (path,) = (tmp_path / "audit").glob("audit-*.jsonl")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "audit").stat().st_mode) == 0o700


def test_droits_resserres_sur_fichier_existant(tmp_path):
    log = AuditLog(tmp_path)
    entry = log.record("allowed", "cid", tool="t")
    path = next(tmp_path.glob("audit-*.jsonl"))
    path.chmod(0o644)
    log.record("result", entry["correlation_id"], tool="t")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_une_ligne_json_par_evenement(tmp_path):
    log = AuditLog(tmp_path)
    cid = new_correlation_id()
    log.record("allowed", cid, tool="t", params={"a": 1}, reason=None)
    log.record("result", cid, tool="t", status="success")
    lines = read_audit(tmp_path)
    assert [e["event"] for e in lines] == ["allowed", "result"]
    assert {e["correlation_id"] for e in lines} == {cid}
    assert "reason" not in lines[0]  # champs None omis


def test_secrets_masques():
    assert redact({"password": "x", "api_key": "y", "Token": "z", "user": "u"}) == {
        "password": "***", "api_key": "***", "Token": "***", "user": "u"}


def test_secrets_masques_dans_le_journal(tmp_path):
    AuditLog(tmp_path).record("allowed", "c", params={"db_password": "hunter2", "host": "h"})
    assert "hunter2" not in next(tmp_path.glob("*.jsonl")).read_text()


def test_dossier_par_defaut():
    assert str(default_audit_dir({"MCP_GUARD_AUDIT_DIR": "/x/y"})) == "/x/y"
    assert str(default_audit_dir({"XDG_STATE_HOME": "/s"})) == "/s/mcp-guard"
    assert default_audit_dir({}).name == "mcp-guard"


def test_identifiants_uniques():
    assert len({new_correlation_id() for _ in range(100)}) == 100
