"""Decorateur de garde : liste blanche, role, valeurs permises, confirmation, audit.

    server = MCPServer("mon-agent")
    guard = Guard(server, Policy.load("policy.yaml"))

    @guard.tool(ToolKind.READ)
    def list_tickets(status: str = "open") -> list[dict]: ...

Chaque appel passe, dans l'ordre : liste blanche -> role -> valeurs permises ->
confirmation humaine (outils destructifs) -> execution. Chaque etape est ecrite
dans le journal d'audit avec le meme identifiant de correlation. Un refus leve
ToolError : le client recoit une erreur lisible, jamais un faux succes.

La confirmation passe par un resolveur du SDK (`Resolve` + `Elicit`) : il suit le
protocole negocie, requete directe au client (<= 2025-11-25) ou aller-retour
`InputRequiredResult` (>= 2026-07-28). Les controles sont faits AVANT la question :
on ne demande jamais a l'humain d'approuver ce que le role n'autorise pas.
"""
from __future__ import annotations

import functools
import inspect
import time
from collections.abc import Callable
from typing import Annotated, Any

from mcp.server.elicitation import AcceptedElicitation, ElicitationResult
from mcp.server.mcpserver import Context, Elicit, MCPServer, Resolve
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from .audit import AuditLog, new_correlation_id
from .confirm import Confirmation, confirm_mode
from .policy import Policy
from .roles import EnvRoleSource, Role, RoleSource, ToolKind

_CTX = "mcp_guard_ctx"
_ANSWER = "mcp_guard_confirmation"


class Denied(Exception):
    def __init__(self, reason: str, role: Role | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.role = role


def annotations_for(kind: ToolKind, title: str | None = None) -> ToolAnnotations:
    """Annotations MCP publiees : le client sait ce qui est dangereux sans liste a maintenir."""
    return ToolAnnotations(
        title=title,
        read_only_hint=kind is ToolKind.READ,
        destructive_hint=kind is ToolKind.DESTRUCTIVE,
        idempotent_hint=kind is ToolKind.READ,
        open_world_hint=False,
    )


def confirmation_message(tool: str, params: dict[str, Any]) -> str:
    args = ", ".join(f"{k}={v!r}" for k, v in params.items())
    return f"Action destructrice : {tool}({args}). Confirmer ?"


def client_can_ask(ctx: Any) -> bool:
    """Le client a-t-il declare l'elicitation par formulaire ? Sans elle, pas de question possible."""
    caps = getattr(ctx, "client_capabilities", None)
    elicitation = getattr(caps, "elicitation", None)
    if elicitation is None:
        return False
    form = getattr(elicitation, "form", None)
    url = getattr(elicitation, "url", None)
    # une capacite vide ({}) vaut formulaire (spec 2025-06-18) ; seule « url » ne suffit pas
    return form is not None or url is None


class Guard:
    def __init__(self, server: MCPServer, policy: Policy, *, role_source: RoleSource | None = None,
                 audit: AuditLog | None = None, confirm: str | None = None) -> None:
        self.server = server
        self.policy = policy
        self.role_source = role_source or EnvRoleSource()
        self.audit = audit or AuditLog()
        self.confirm = confirm or confirm_mode()
        self.registered: dict[str, ToolKind] = {}

    def tool(self, kind: ToolKind, *, name: str | None = None, title: str | None = None,
             description: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            tool_name = name or fn.__name__
            wrapper = self._wrap(fn, tool_name, kind)
            self.server.tool(name=tool_name, title=title, description=description or inspect.getdoc(fn),
                             annotations=annotations_for(kind, title))(wrapper)
            self.registered[tool_name] = kind
            return fn

        return decorator

    # --- controles --------------------------------------------------------

    def check(self, tool: str, kind: ToolKind, params: dict[str, Any]) -> Role:
        """Liste blanche, role, valeurs permises. Leve Denied avec la raison."""
        rule = self.policy.rule_for(tool)
        if rule is None:
            raise Denied("outil absent de la liste blanche (policy.yaml)")
        try:
            role = self.role_source.current_role()
        except ValueError as e:
            raise Denied(str(e)) from e
        required = max(kind.min_role, rule.role or kind.min_role)
        if role < required:
            raise Denied(f"role {role.label} insuffisant, {required.label} requis", role)
        for param, allowed in rule.allowed_values.items():
            value = params.get(param)
            if value is not None and str(value) not in allowed:
                raise Denied(f"{param}={value!r} hors des valeurs permises par la politique", role)
        return role

    def _deny(self, cid: str, tool: str, kind: ToolKind, params: dict[str, Any], denied: Denied) -> ToolError:
        self.audit.record("denied", cid, tool=tool, kind=kind.value, params=params,
                          role=denied.role.label if denied.role else None, reason=denied.reason)
        return ToolError(f"refuse : {denied.reason}")

    # --- enveloppe ----------------------------------------------------------

    def _wrap(self, fn: Callable[..., Any], tool_name: str, kind: ToolKind) -> Callable[..., Any]:
        sig = inspect.signature(fn)
        tool_params = [p for p in sig.parameters.values() if p.name not in (_CTX, _ANSWER)]
        ask_human = kind is ToolKind.DESTRUCTIVE and self.confirm == "elicit"

        @functools.wraps(fn)
        async def wrapper(**kwargs: Any) -> Any:
            kwargs.pop(_CTX, None)
            answer = kwargs.pop(_ANSWER, None)
            cid = new_correlation_id()
            params = {p.name: kwargs.get(p.name, p.default) for p in tool_params
                      if p.name in kwargs or p.default is not inspect.Parameter.empty}
            try:
                role = self.check(tool_name, kind, params)
            except Denied as d:
                raise self._deny(cid, tool_name, kind, params, d) from None
            self.audit.record("allowed", cid, tool=tool_name, kind=kind.value, params=params, role=role.label)
            if kind is ToolKind.DESTRUCTIVE:
                self._confirmation(cid, tool_name, answer if ask_human else "client")
            start = time.monotonic()
            try:
                result = fn(**kwargs)
                if inspect.isawaitable(result):
                    result = await result
            except ToolError as e:
                self._finish(cid, tool_name, role, start, error=str(e))
                raise
            except Exception as e:
                self._finish(cid, tool_name, role, start, error=f"{type(e).__name__}: {e}")
                raise ToolError(f"{tool_name} a echoue : {e}") from e
            self._finish(cid, tool_name, role, start)
            return result

        extra = [inspect.Parameter(_CTX, inspect.Parameter.KEYWORD_ONLY, default=None, annotation=Context)]
        annotations = {**getattr(fn, "__annotations__", {}), _CTX: Context}
        if ask_human:
            answer_type = Annotated[ElicitationResult[Confirmation], Resolve(self._gate(tool_name, kind, tool_params))]
            extra.append(inspect.Parameter(_ANSWER, inspect.Parameter.KEYWORD_ONLY, default=None,
                                           annotation=answer_type))
            annotations[_ANSWER] = answer_type
        # Le serveur lit la signature (schema des arguments, injection du Context et du
        # resolveur) : on garde celle de la fonction et on y ajoute nos parametres.
        wrapper.__signature__ = sig.replace(parameters=tool_params + extra)  # type: ignore[attr-defined]
        wrapper.__annotations__ = annotations
        return wrapper

    def _gate(self, tool: str, kind: ToolKind, tool_params: list[inspect.Parameter]) -> Callable[..., Any]:
        """Resolveur de l'outil destructif : controle, puis question a l'humain."""

        def gate(**kwargs: Any) -> Elicit[Confirmation]:
            ctx = kwargs.pop(_CTX, None)
            params = kwargs
            try:
                self.check(tool, kind, params)
                if not client_can_ask(ctx):
                    raise Denied("le client ne sait pas demander de confirmation a l'humain (elicitation) ; "
                                 "si le client confirme lui-meme, MCP_GUARD_CONFIRM=client")
            except Denied as d:
                raise self._deny(new_correlation_id(), tool, kind, params, d) from None
            return Elicit(confirmation_message(tool, params), Confirmation)

        # meme nom pour chaque outil : le SDK numerote les resolveurs d'une meme fabrique
        gate.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
            [p.replace(kind=inspect.Parameter.KEYWORD_ONLY) for p in tool_params]
            + [inspect.Parameter(_CTX, inspect.Parameter.KEYWORD_ONLY, annotation=Context)])
        gate.__annotations__ = {**{p.name: p.annotation for p in tool_params
                                   if p.annotation is not inspect.Parameter.empty},
                                _CTX: Context, "return": Elicit[Confirmation]}
        gate.__qualname__ = gate.__name__ = f"mcp_guard_gate_{tool}"
        return gate

    def _confirmation(self, cid: str, tool: str, answer: Any) -> None:
        if answer == "client":
            self.audit.record("confirmation", cid, tool=tool, confirmed=True, how="client")
            return
        ok = isinstance(answer, AcceptedElicitation) and bool(answer.data.confirm)
        reason = None if ok else f"refuse par l'humain ({getattr(answer, 'action', 'pas de reponse')})"
        self.audit.record("confirmation", cid, tool=tool, confirmed=ok, how="elicit", reason=reason)
        if not ok:
            raise ToolError(f"refuse : {reason}")

    def _finish(self, cid: str, tool: str, role: Role, start: float, error: str | None = None) -> None:
        self.audit.record("result", cid, tool=tool, role=role.label,
                          duration_ms=round((time.monotonic() - start) * 1000, 1),
                          status="error" if error else "success", error=error)
