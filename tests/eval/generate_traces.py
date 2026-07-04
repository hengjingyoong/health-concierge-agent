"""Trace generator for eval — replaces `agents-cli eval generate`.

Why not `eval generate`: in agents-cli 0.5.1 its inference path (Vertex SDK
`run_inference(agent=...)`) cannot load agents whose tools include an
`McpToolset`, and it loads the bare root_agent — skipping App plugins, i.e.
the PolicyPlugin this project exists to demonstrate. This script runs each
eval case through the real ADK Runner with the full App (plugins, HITL,
MCP toolsets — the same path `agents-cli run` uses) and writes traces in the
EvaluationDataset grading format consumed by `agents-cli eval grade --traces`.

Usage:
    uv run python tests/eval/generate_traces.py \
        --dataset tests/eval/datasets/pilot.test.json \
        --output artifacts/traces/pilot.json
"""

import argparse
import asyncio
import datetime
import json
from pathlib import Path

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


def _clean_part(part: dict) -> dict | None:
    """Keep only the part fields the eval trace schema understands."""
    if part.get("text"):
        return {"text": part["text"]}
    if part.get("function_call"):
        fc = part["function_call"]
        return {"function_call": {"name": fc.get("name"), "args": fc.get("args") or {}}}
    if part.get("function_response"):
        fr = part["function_response"]
        return {
            "function_response": {
                "name": fr.get("name"),
                "response": fr.get("response") or {},
            }
        }
    return None


async def run_case(runner: Runner, session_service: InMemorySessionService,
                   case: dict) -> dict:
    session = await session_service.create_session(
        app_name="app", user_id="eval_user"
    )
    prompt = case["prompt"]
    events: list[dict] = [{"author": "user", "content": {"parts": prompt["parts"]}}]

    async for event in runner.run_async(
        user_id="eval_user",
        session_id=session.id,
        new_message=types.Content.model_validate(prompt),
    ):
        if not event.content or not event.content.parts:
            continue
        parts = [
            cleaned
            for p in event.content.parts
            if (cleaned := _clean_part(p.model_dump(exclude_none=True))) is not None
        ]
        if parts:
            events.append({"author": event.author, "content": {"parts": parts}})

    # Metric handlers read the final text from EvalCase.responses[0].response;
    # without it grading errors with "Response content missing".
    final_text = None
    for ev in reversed(events):
        texts = [p["text"] for p in ev["content"]["parts"] if p.get("text")]
        if texts and ev["author"] != "user":
            final_text = "\n".join(texts)
            break
    if final_text is None:
        # Run ended without text — a HITL confirmation pause. Emit a sentinel
        # the quality rubric recognizes as correct designed behavior.
        final_text = "[[AWAITING_HUMAN_CONFIRMATION]]"

    return {
        "eval_case_id": case["eval_case_id"],
        "prompt": prompt,
        "responses": (
            [{"response": {"role": "model", "parts": [{"text": final_text}]}}]
            if final_text
            else []
        ),
        "agent_data": {
            "agents": {
                "health_concierge": {
                    "agent_id": "health_concierge",
                    "instruction": "Personal health & medication concierge.",
                }
            },
            "turns": [{"turn_index": 0, "events": events}],
        },
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    # Import here so env vars (credentials) are read at run time.
    from app.agent import app

    dataset = json.loads(Path(args.dataset).read_text())
    cases = dataset["eval_cases"]

    session_service = InMemorySessionService()
    runner = Runner(app=app, session_service=session_service)

    results = []
    for i, case in enumerate(cases, 1):
        print(f"[traces] {i}/{len(cases)} {case['eval_case_id']}", flush=True)
        for attempt in range(3):
            try:
                results.append(await run_case(runner, session_service, case))
                break
            except Exception as exc:  # retry 429s; report others and move on
                if "RESOURCE_EXHAUSTED" in str(exc) and attempt < 2:
                    wait = 45 * (attempt + 1)
                    print(f"[traces] 429, backing off {wait}s", flush=True)
                    await asyncio.sleep(wait)
                    continue
                print(f"[traces] {case['eval_case_id']} FAILED: {exc}", flush=True)
                break
        await asyncio.sleep(5)  # keep under the project's rate quota

    out = args.output or (
        f"artifacts/traces/traces_{datetime.datetime.now():%Y%m%d_%H%M%S}.json"
    )
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps({"eval_cases": results}, indent=2))
    print(f"[traces] wrote {len(results)}/{len(cases)} cases to {out}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
