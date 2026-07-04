"""Structural gate — deterministic role x tool x env check (SEC-1, SEC-3).

Pure functions over policies.yaml: no LLM, no I/O beyond the one-time YAML
load, microsecond decisions, exhaustively unit-testable. Deny-by-default,
mirroring the origin system's Firestore-rules philosophy.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

POLICIES_PATH = Path(__file__).with_name("policies.yaml")


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


def load_policies(path: Path = POLICIES_PATH) -> dict:
    return yaml.safe_load(path.read_text())


def check_tool(tool_name: str, role: str, env: str, policies: dict) -> Decision:
    """Decide whether a role may execute a tool in an environment."""
    if tool_name in policies.get("system_tools", []):
        return Decision(True, "system tool")

    blocked_in_env = policies.get("environments", {}).get(env, {}).get(
        "blocked_tools", []
    )
    if tool_name in blocked_in_env:
        return Decision(
            False, f"tool '{tool_name}' is blocked in the '{env}' environment"
        )

    roles = policies.get("roles", {})
    if role not in roles:
        fallback = policies.get("defaults", {}).get("unknown_role", "guest")
        role = fallback if fallback in roles else "guest"

    allowed_tools = roles.get(role, {}).get("allowed_tools") or []
    if tool_name in allowed_tools:
        return Decision(True, f"allowed for role '{role}'")

    # Unknown tools and known-but-unlisted tools both land here: deny.
    return Decision(False, f"tool '{tool_name}' is not permitted for role '{role}'")
