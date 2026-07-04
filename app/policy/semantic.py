"""Semantic gate — 'allowed tool, disallowed use' layer (SEC-2, SEC-5).

Two stages (specs/30-security.md §5):
1. Deterministic PII prefilter (regex) — free, catches the obvious.
2. LLM judge (small model, structured verdict) — catches what regex cannot.

Fail closed: if the judge errors, times out, or returns something unparseable,
the text is BLOCKED. A broken guardrail must not degrade to an absent one.
"""

import json
import logging
import uuid
from typing import Literal

from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel, Field

from app.policy.engine import load_policies
from mcp_server.masking import find_pii

logger = logging.getLogger(__name__)

JUDGE_MODEL = "gemini-3.1-flash-lite"


class Verdict(BaseModel):
    verdict: Literal["pass", "block"] = Field(description="Gate decision.")
    violated_policy_id: str | None = Field(
        default=None, description="Id of the violated policy, if blocking."
    )
    reason: str = Field(description="One-sentence rationale.")


def _judge_instruction() -> str:
    policies = load_policies().get("semantic_policies", [])
    rules = "\n".join(f"- {p['id']}: {p['rule']}" for p in policies)
    return f"""You are a privacy and safety gate for a personal health agent.
Evaluate ONLY the text between <outbound> tags against these policies:
{rules}
If any policy is violated, verdict is "block" with the policy id; otherwise
"pass". Judge the text itself, not the intent of the conversation."""


class SemanticGate:
    """Wraps the judge agent; exposes a single fail-closed review() call."""

    def __init__(self, judge_model: str = JUDGE_MODEL) -> None:
        self._runner = InMemoryRunner(
            agent=Agent(
                name="semantic_judge",
                model=judge_model,
                instruction=_judge_instruction(),
                output_schema=Verdict,
            ),
            app_name="semantic_judge_app",
        )

    async def review(self, text: str) -> Verdict:
        """Return the gate verdict for outbound text. Never raises."""
        token = find_pii(text)
        if token is not None:
            return Verdict(
                verdict="block",
                violated_policy_id="no-unmasked-pii",
                reason=f"deterministic prefilter matched {token}",
            )
        try:
            return await self._ask_judge(text)
        except Exception as exc:  # fail closed (SEC-5)
            logger.error("semantic judge failed, blocking outbound text: %s", exc)
            return Verdict(
                verdict="block",
                violated_policy_id=None,
                reason="semantic gate unavailable — failing closed",
            )

    async def _ask_judge(self, text: str) -> Verdict:
        session = await self._runner.session_service.create_session(
            app_name="semantic_judge_app", user_id="gate", session_id=uuid.uuid4().hex
        )
        answer = ""
        async for event in self._runner.run_async(
            user_id="gate",
            session_id=session.id,
            new_message=types.Content(
                role="user",
                parts=[types.Part.from_text(text=f"<outbound>\n{text}\n</outbound>")],
            ),
        ):
            if event.is_final_response() and event.content and event.content.parts:
                answer = "".join(p.text or "" for p in event.content.parts)
        return Verdict.model_validate(json.loads(answer))
