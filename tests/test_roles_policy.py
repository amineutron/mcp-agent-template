import pytest

from mcp_guard import EnvRoleSource, Policy, PolicyError, Role, ToolKind, parse_role


@pytest.mark.parametrize("value,role", [
    ("lecteur", Role.LECTEUR), ("Operateur", Role.OPERATEUR), ("opérateur", Role.OPERATEUR),
    ("ADMIN", Role.ADMIN), (" admin ", Role.ADMIN), ("reader", Role.LECTEUR), ("operator", Role.OPERATEUR),
])
def test_parse_role(value, role):
    assert parse_role(value) is role


@pytest.mark.parametrize("value", ["", "root", "superadmin", "3"])
def test_parse_role_refuse(value):
    with pytest.raises(ValueError):
        parse_role(value)


def test_ordre_des_roles_et_types():
    assert Role.LECTEUR < Role.OPERATEUR < Role.ADMIN
    assert [k.min_role for k in ToolKind] == [Role.LECTEUR, Role.OPERATEUR, Role.ADMIN]


@pytest.mark.parametrize("env,expected", [
    ({}, Role.LECTEUR), ({"MCP_GUARD_ROLE": ""}, Role.LECTEUR), ({"MCP_GUARD_ROLE": "admin"}, Role.ADMIN),
])
def test_role_par_variable_defaut_sur(env, expected):
    assert EnvRoleSource(environ=env).current_role() is expected


def test_role_invalide_ne_devine_rien():
    with pytest.raises(ValueError):
        EnvRoleSource(environ={"MCP_GUARD_ROLE": "root"}).current_role()


def test_politique_liste_blanche():
    p = Policy.from_mapping({"tools": {"a": {}, "b": {"role": "admin"}, "c": {"enabled": False},
                                       "d": {"allowed_values": {"unit": ["x.service"]}}}})
    assert p.rule_for("a") is not None
    assert p.rule_for("b").role is Role.ADMIN
    assert p.rule_for("c") is None            # desactive
    assert p.rule_for("inconnu") is None      # default: deny
    assert p.rule_for("d").allowed_values == {"unit": frozenset({"x.service"})}


def test_politique_default_allow():
    assert Policy.from_mapping({"default": "allow"}).rule_for("nimporte") is not None


@pytest.mark.parametrize("data,message", [
    ([], "dictionnaire"),
    ({"version": 2}, "version"),
    ({"default": "maybe"}, "default"),
    ({"extra": 1}, "cles inconnues"),
    ({"tools": {"a": {"role": "root"}}}, "role inconnu"),
    ({"tools": {"a": {"rolle": "admin"}}}, "cles inconnues"),
    ({"tools": {"a": {"enabled": "yes"}}}, "enabled"),
    ({"tools": {"a": {"allowed_values": {"unit": "x"}}}}, "allowed_values"),
    ({"tools": ["a"]}, "dictionnaire"),
])
def test_politique_invalide(data, message):
    with pytest.raises(PolicyError, match=message):
        Policy.from_mapping(data)


def test_politique_fichier(tmp_path):
    f = tmp_path / "policy.yaml"
    f.write_text("version: 1\ntools:\n  list_tickets: {}\n")
    assert Policy.load(f).rule_for("list_tickets") is not None
    f.write_text("tools: [\n")
    with pytest.raises(PolicyError, match="YAML invalide"):
        Policy.load(f)
    with pytest.raises(PolicyError, match="lecture"):
        Policy.load(tmp_path / "absent.yaml")


def test_politiques_livrees_valides():
    from mcp_guard.examples import enterprise, ops
    for path in (enterprise.POLICY, ops.POLICY):
        assert Policy.load(path).tools
