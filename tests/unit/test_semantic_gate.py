"""Semantic gate wrapper behavior with the LLM judge mocked out.

What the judge MODEL decides on real text is eval territory (SEC-2 cases);
here we test the deterministic wrapper: prefilter short-circuit, fail-closed
on judge errors, and verdict parsing.
"""

import json

import pytest
from pydantic import ValidationError

from app.policy.semantic import SemanticGate, Verdict


def make_gate(judge_behavior) -> SemanticGate:
    gate = SemanticGate.__new__(SemanticGate)  # skip __init__: no model, no runner

    async def fake_ask_judge(text: str) -> Verdict:
        return judge_behavior(text)

    gate._ask_judge = fake_ask_judge
    return gate


class TestPrefilter:
    @pytest.mark.asyncio
    async def test_national_id_blocks_without_judge(self):
        gate = make_gate(lambda text: pytest.fail("judge must not be called"))
        verdict = await gate.review("Your ID is A123456789.")
        assert verdict.verdict == "block"
        assert verdict.violated_policy_id == "no-unmasked-pii"

    @pytest.mark.asyncio
    async def test_clean_text_reaches_judge(self):
        gate = make_gate(lambda text: Verdict(verdict="pass", reason="ok"))
        verdict = await gate.review("Your uric acid is 7.9 mg/dL.")
        assert verdict.verdict == "pass"


class TestFailClosed:
    @pytest.mark.asyncio
    async def test_judge_exception_blocks(self):  # SEC-5
        def boom(text):
            raise RuntimeError("model unavailable")

        verdict = await make_gate(boom).review("any outbound text")
        assert verdict.verdict == "block"
        assert "failing closed" in verdict.reason

    @pytest.mark.asyncio
    async def test_unparseable_judge_output_blocks(self):
        def bad_json(text):
            return Verdict.model_validate(json.loads("not json"))

        verdict = await make_gate(bad_json).review("any outbound text")
        assert verdict.verdict == "block"


class TestVerdictSchema:
    def test_block_verdict_roundtrip(self):
        v = Verdict.model_validate(
            {"verdict": "block", "violated_policy_id": "no-unmasked-pii",
             "reason": "contains an ID"}
        )
        assert v.verdict == "block"

    def test_invalid_verdict_value_rejected(self):
        with pytest.raises(ValidationError):
            Verdict.model_validate({"verdict": "maybe", "reason": "?"})
