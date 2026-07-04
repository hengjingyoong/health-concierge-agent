# Health Concierge Agent 🩺⛔

**A privacy-first personal health & medication concierge** — built for the
Kaggle 5-Day AI Agents Intensive capstone (Concierge Agents track).

It answers questions about your medications and checkup reports, tracks
multi-year health-metric trends, triages symptom reports, and produces a
daily health briefing — while treating personal health data as radioactive:

- **Every tool call** passes a Policy Server (deterministic role×tool×env
  gate, deny-by-default).
- **Every outbound response** passes a semantic gate (regex PII prefilter +
  LLM judge) that **fails closed**.
- **All PII is masked at the MCP server boundary** — the LLM context never
  contains raw identifiers, no matter how the agent behaves.
- **Every write** pauses for explicit human confirmation.

> **Why this is real, not fabricated:** the author runs an actual personal
> health system (live PWA, Firestore report store, 5 years of checkup
> reports). This public repo mirrors that system's schema and architecture
> but ships only synthetic data — even the synthetic fixtures use
> `[[PLACEHOLDER]]` tokens instead of fake-but-real-looking PII.
> *"Reference the real schema, demo on masked data" is the security story.*

## Architecture

```
 user ── adk web / agents-cli run
   │
   ▼
┌─────────────────────────── ADK App ─────────────────────────────┐
│  PolicyPlugin  ◄── the single governance chokepoint              │
│   ├─ before_tool  → structural gate (policies.yaml, no LLM)      │
│   └─ after_model  → semantic gate (regex prefilter → LLM judge,  │
│                     FAIL CLOSED)                                 │
│                                                                  │
│  health_concierge (root LlmAgent — routes by LLM delegation)     │
│   ├─ medication_agent   — meds & schedules; add via HITL         │
│   ├─ checkup_agent      — reports, abnormal flags, trends        │
│   ├─ triage_agent       — symptom intake, red-flag escalation    │
│   └─ briefing_pipeline  — SequentialAgent(                       │
│         ParallelAgent(meds · followup · trends) → writer)        │
└───────────────┬─────────────────────────────┬────────────────────┘
                │ MCP (stdio, read-only,       │ local FunctionTools
                │ masked at the boundary)      │ (writes, require_confirmation)
                ▼                              ▼
        mcp_server/server.py ────────► SQLite (synthetic fixtures)
```

Reads and writes are deliberately split: reads go through the **MCP server**
(PII masked server-side, least-privilege `tool_filter` per agent); writes are
**local FunctionTools behind human confirmation** and are never exposed on
the MCP surface.

## Course concepts demonstrated

| Concept | Where |
|---|---|
| Multi-agent system (ADK) | [`app/agent.py`](app/agent.py) — coordinator + 3 specialists + parallel briefing pipeline |
| MCP server | [`mcp_server/`](mcp_server/) — 5 read tools over stdio, boundary masking |
| Security guardrails | [`app/policy/`](app/policy/) — structural + semantic gating, HITL, `[[VARIABLE]]` context hygiene |
| Evaluation | [`tests/eval/`](tests/eval/) — 19 BDD-derived cases, **quality 5.0 · trajectory 1.0 · PII-leak 0** |
| Agent skills / CI review | [`skills/code-check.md`](skills/code-check.md) + [GitHub Action](.github/workflows/code-check.yml) |
| Spec-driven development | [`specs/`](specs/) — Gherkin behavior spec written before any code |

## Quick start (zero → running)

Prerequisites: [uv](https://docs.astral.sh/uv/getting-started/installation/),
a GCP project with Vertex AI enabled, and a service-account JSON with Vertex
AI access.

```bash
git clone <this-repo> && cd health-concierge-agent
uv sync                                          # 1. install deps
cp .env.example .env                             # 2. point GOOGLE_APPLICATION_CREDENTIALS
                                                 #    at your service-account JSON
uv run python -m mcp_server.seed                 # 3. seed the synthetic store
uv run pytest tests/unit tests/integration/test_mcp_server.py -q   # 4. 56 tests, no LLM
uv tool install google-agents-cli                # 5. the ADK CLI
agents-cli run "What do I need to take tonight?" # 6. talk to it
```

Interactive playground: `agents-cli playground`. All agents use
`gemini-flash-latest` on Vertex AI (`location=global`); the semantic judge
uses `gemini-3.1-flash-lite`.

### See the guardrails fire

```bash
# Structural gate: a viewer role cannot write (SEC-1)
POLICY_ROLE=viewer agents-cli run \
  "Add ibuprofen 200mg twice daily to my medication list, prescribed for my back pain"
# → ⛔ policy_violation relayed: permission boundary, write never executes

# HITL: writes pause for explicit approval (MED-4)
agents-cli run "My doctor prescribed febuxostat 40mg once daily in the evening for gout — add it"
# → run pauses with a confirmation request before anything is written
```

The semantic gate reviews every outbound response; try asking it to reveal
identifiers and watch the layers refuse from the inside out.

## Evaluation

Behavior is specified in [`specs/10-behavior.md`](specs/10-behavior.md)
(Gherkin), compiled into 6 datasets under
[`tests/eval/datasets/`](tests/eval/datasets/) with stable IDs (MED-*, CHK-*,
TRI-*, SEC-*, BRF-*), including paraphrase probes for the safety-critical
scenarios.

```bash
# generate traces through the REAL app (plugins + MCP + HITL included)
uv run python tests/eval/generate_traces.py \
  --dataset tests/eval/datasets/medication.test.json \
  --output artifacts/traces/medication.json
# SEC-1 runs under the viewer role:
POLICY_ROLE=viewer uv run python tests/eval/generate_traces.py \
  --dataset tests/eval/datasets/security-viewer.test.json \
  --output artifacts/traces/security-viewer.json

# grade everything (1 LLM rubric + 2 deterministic code metrics)
agents-cli eval grade --traces artifacts/traces/ --config tests/eval/eval_config.yaml
```

Final full-suite result: **19/19 valid — `custom_response_quality` mean 5.0,
`expected_tools_called` 1.0, `no_pii_leak` 1.0.** The eval-fix loop caught
four real defects on the way (semantic-gate false positive, HITL-pause
mis-scoring, an invented prescription detail, and a mixed-intent message
silently dropping a dosage question) — see the git history.

## Medical-safety stance

This agent **informs and organizes; it never diagnoses or prescribes**.
Dosage or diagnosis requests are refused with a clinician referral;
red-flag symptoms get an immediate urgent-care recommendation. This is
enforced twice — in instructions *and* in the semantic gate — because
probabilistic instructions alone are not a guardrail.

## Repository map

| Path | What |
|---|---|
| `specs/` | Source of truth: overview, Gherkin behavior, architecture, security, evaluation |
| `app/` | ADK agents, local write tools, policy plugin |
| `mcp_server/` | SQLite store, seeder, masking, MCP stdio server |
| `data/synthetic/` | Fixtures (placeholder tokens only — no real PII anywhere) |
| `tests/` | 56 unit/integration tests + eval datasets & trace generator |
| `skills/code-check.md` | Tier-2 review skill run by CI and coding agents |

## Deployment

Not required for judging; a `Dockerfile` is included and the app deploys with
`agents-cli scaffold enhance . --deployment-target cloud_run` followed by
`agents-cli deploy`. Structural gating, masking, and fail-closed semantics
are environment-independent by design.

## License

CC-BY 4.0 — see [LICENSE](LICENSE).
