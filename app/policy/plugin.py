"""PolicyPlugin — the single governance chokepoint (specs/30-security.md §3).

Registered on the ADK App, so it runs before agent-level callbacks for EVERY
agent and EVERY tool with no per-agent opt-out:

- before_run:  seed session role/env from environment (never from user text)
- before_tool: structural gate — deterministic policies.yaml lookup
- after_model: semantic gate — regex prefilter + LLM judge on outbound text,
  fail-closed

Execution logic lives in agents/tools; governance logic lives here.
"""

import os

from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.tools import BaseTool, ToolContext
from google.genai import types

from app.policy import engine
from app.policy.semantic import SemanticGate

BLOCKED_RESPONSE_TEXT = (
    "⛔ Policy Violation: this response was withheld by the semantic gate ({reason})."
)


def _session_role_env(state) -> tuple[str, str]:
    role = state.get("policy_role") or os.environ.get("POLICY_ROLE", "owner")
    env = state.get("policy_env") or os.environ.get("POLICY_ENV", "demo")
    return role, env


class PolicyPlugin(BasePlugin):
    def __init__(self, semantic_gate: SemanticGate | None = None) -> None:
        super().__init__(name="policy_plugin")
        self._policies = engine.load_policies()
        # Lazily built so unit tests can inject a fake gate with no model.
        self._semantic_gate = semantic_gate

    def _gate(self) -> SemanticGate:
        if self._semantic_gate is None:
            self._semantic_gate = SemanticGate()
        return self._semantic_gate

    async def before_run_callback(
        self, *, invocation_context: InvocationContext
    ) -> types.Content | None:
        state = invocation_context.session.state
        role, env = _session_role_env(state)
        state["policy_role"] = role
        state["policy_env"] = env
        return None

    async def before_tool_callback(
        self, *, tool: BaseTool, tool_args: dict, tool_context: ToolContext
    ) -> dict | None:
        role, env = _session_role_env(tool_context.state)
        decision = engine.check_tool(tool.name, role, env, self._policies)
        if decision.allowed:
            return None
        # Returning a dict skips the tool; the agent relays the violation.
        return {
            "status": "policy_violation",
            "reason": decision.reason,
            "hint": (
                "Tell the user plainly that their current access level does "
                "not permit this action. Do not retry, do not promise it "
                "will be recorded later, and do not call it a technical issue."
            ),
        }

    async def after_model_callback(
        self, *, callback_context: CallbackContext, llm_response: LlmResponse
    ) -> LlmResponse | None:
        content = llm_response.content
        if not content or not content.parts:
            return None
        text = "\n".join(p.text or "" for p in content.parts).strip()
        if not text:
            return None  # pure function-call responses are not outbound text
        if callback_context.agent_name == "semantic_judge":
            return None  # never gate the gate
        verdict = await self._gate().review(text)
        if verdict.verdict == "pass":
            return None
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part.from_text(
                        text=BLOCKED_RESPONSE_TEXT.format(reason=verdict.reason)
                    )
                ],
            )
        )
