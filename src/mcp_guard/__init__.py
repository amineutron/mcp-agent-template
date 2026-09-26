"""mcp-guard : roles, liste blanche, confirmation humaine et audit pour serveurs MCP."""
from importlib.metadata import PackageNotFoundError, version

from .audit import AuditLog, new_correlation_id, redact
from .confirm import Confirmation, confirm_mode
from .guard import Denied, Guard, annotations_for, confirmation_message
from .policy import Policy, PolicyError, ToolRule
from .roles import EnvRoleSource, FixedRoleSource, Role, RoleSource, ToolKind, parse_role

try:
    __version__ = version("mcp-guard")
except PackageNotFoundError:  # pragma: no cover - lance depuis les sources sans installation
    __version__ = "0.0.0"

__all__ = [
    "AuditLog", "Confirmation", "Denied", "EnvRoleSource", "FixedRoleSource", "Guard", "Policy",
    "PolicyError", "Role", "RoleSource", "ToolKind", "ToolRule", "__version__", "annotations_for",
    "confirm_mode", "confirmation_message", "new_correlation_id", "parse_role", "redact",
]
