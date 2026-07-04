"""Structural gate matrix — deterministic, so binary assertions are correct."""

import pytest

from app.policy.engine import check_tool, load_policies

POLICIES = load_policies()

READ_TOOLS = [
    "list_medications", "get_medication_schedule", "list_reports",
    "get_report_details", "get_metric_history",
]
WRITE_TOOLS = ["add_medication", "log_symptom"]


class TestOwner:
    @pytest.mark.parametrize("tool", READ_TOOLS + WRITE_TOOLS)
    def test_owner_allowed_everything_listed(self, tool):
        assert check_tool(tool, "owner", "demo", POLICIES).allowed

    def test_owner_cannot_use_unknown_tool(self):
        # deny-by-default: a tool nobody registered is nobody's tool (SEC surface)
        assert not check_tool("export_profile", "owner", "demo", POLICIES).allowed


class TestViewer:
    @pytest.mark.parametrize("tool", ["list_medications", "list_reports",
                                      "get_metric_history"])
    def test_viewer_reads_allowed(self, tool):
        assert check_tool(tool, "viewer", "demo", POLICIES).allowed

    @pytest.mark.parametrize("tool", WRITE_TOOLS)
    def test_viewer_writes_blocked(self, tool):  # SEC-1
        decision = check_tool(tool, "viewer", "demo", POLICIES)
        assert not decision.allowed
        assert "viewer" in decision.reason


class TestGuestAndUnknownRole:
    @pytest.mark.parametrize("tool", READ_TOOLS + WRITE_TOOLS)
    def test_guest_blocked_everywhere(self, tool):
        assert not check_tool(tool, "guest", "demo", POLICIES).allowed

    def test_unknown_role_falls_back_to_guest(self):
        assert not check_tool("list_medications", "hacker", "demo", POLICIES).allowed


class TestEnvironmentGate:
    def test_env_blocked_tool_beats_role(self):  # SEC-3
        decision = check_tool("send_notification", "owner", "demo", POLICIES)
        assert not decision.allowed
        assert "demo" in decision.reason

    def test_same_tool_not_env_blocked_in_prod_but_still_role_denied(self):
        decision = check_tool("send_notification", "owner", "prod", POLICIES)
        assert not decision.allowed  # not in owner's allowed_tools either


class TestSystemTools:
    @pytest.mark.parametrize("role", ["owner", "viewer", "guest"])
    def test_transfer_to_agent_always_allowed(self, role):
        # Delegation plumbing must never be strangled by the gate.
        assert check_tool("transfer_to_agent", role, "demo", POLICIES).allowed
