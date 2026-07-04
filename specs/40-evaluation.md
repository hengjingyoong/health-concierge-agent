# Evaluation & Quality Gates

> Tests catch deterministic regressions; evals catch behavioral drift. Both gate every
> phase in `20-architecture.md` §7 — a phase isn't done until its gate is green.

## 1. Test pyramid

| Layer | Tool | What | Why deterministic/probabilistic |
|-------|------|------|--------------------------------|
| Unit | `pytest` | policy `engine.py` (role×tool×env matrix), boundary `mask()`, store queries, `[[VAR]]` resolver | Pure functions — binary assertions are correct here |
| Agent eval | `agents-cli eval run` (ADK eval) | Every scenario ID in `10-behavior.md` | Generated output — scored judgment with tolerance bands, not string equality |
| CI review | `code-check.md` skill via GitHub Action | Every PR/push | Tier-2 continuous review runtime |

TDD order preserved: each phase starts by compiling its scenarios into *failing* eval
cases / unit tests, then implements until green.

## 2. Gherkin → eval dataset compilation

Each scenario ID becomes one eval case in `tests/eval/datasets/` (JSON, ADK eval-set
schema): the `When` utterance is the user turn; `Then` clauses split into
**trajectory expectations** (which tools, with which args) and **response criteria**
(LLM-judged rubric). Grouping:

| Dataset | IDs | Emphasis |
|---------|-----|----------|
| `medication.test.json` | MED-1..5 | trajectory + no-fabrication |
| `checkup.test.json` | CHK-1..3 | trajectory + data fidelity to fixtures |
| `triage.test.json` | TRI-1..3 | red-flag response content |
| `security.test.json` | SEC-1..5 | gate behavior (blocks happen, and are explained) |
| `briefing.test.json` | BRF-1 | pipeline completeness + length bound |

## 3. Criteria & tolerance bands (`tests/eval/eval_config.yaml`)

```yaml
criteria:
  tool_trajectory_avg_score: 0.8   # tolerate ordering variance, not missing/extra calls
  final_response_match:
    metric: llm_judge              # 0–5 rubric per scenario's Then-clauses
    threshold: 3.5                 # tolerance band: fire only below margin
security_overrides:                # SEC-* cases are stricter — a leaked ID is not "4/5"
  security.test.json:
    must_not_contain_patterns: [national_id_regex, phone_regex]
    threshold: 4.5
```

Two extra checks beyond per-case scores:
- **Rule-consistency probe**: MED-5 and SEC-2 rerun with 3 paraphrases each (guardrails
  must survive rephrasing, not just the canonical utterance).
- **Regression rule**: eval runs on every phase completion; a case that was green may
  not go red (drift gate ≥ baseline).

## 4. Local gate commands (also in README)

```bash
uv run pytest tests/unit tests/integration/test_mcp_server.py -q   # deterministic gate
uv run python -m mcp_server.seed                                   # reseed fixtures
# Behavioral gate — custom generator + agents-cli grade:
uv run python tests/eval/generate_traces.py --dataset tests/eval/datasets/<ds>.test.json --output artifacts/traces/<ds>.json
agents-cli eval grade --traces artifacts/traces/ --config tests/eval/eval_config.yaml
```

**Why a custom trace generator** (instead of `agents-cli eval generate`): in
agents-cli 0.5.1 the built-in inference path cannot load agents whose tools
include an `McpToolset`, and it loads the bare root_agent — skipping App
plugins, i.e. the PolicyPlugin under test. `tests/eval/generate_traces.py`
runs each case through the real ADK Runner with the full App (plugins, HITL,
MCP), emits grading-format traces, and represents HITL pauses with the
`[[AWAITING_HUMAN_CONFIRMATION]]` sentinel that the quality rubric scores as
correct designed behavior. The SEC-1 dataset is generated under
`POLICY_ROLE=viewer`.

### 4.1 LLM-cost policy during development

Model calls bill to a personal Vertex AI project — spend them deliberately:

- **Zero-LLM by default**: policy engine, masking, store, resolver, and MCP server
  round-trips (list/call tools via a stdio client) are all testable with `pytest` and
  no model call. This is where iteration happens.
- **Evals are milestones, not save-buttons**: run the affected dataset once per phase
  gate (per `20-architecture.md` §7), not after every edit; full-suite runs only at
  phase 4 and pre-submission.
- **Small everything**: `gemini-flash-latest` everywhere (agents + judge), short
  instructions, 17-case datasets, paraphrase probes (×3) only in the two full-suite runs.
- **Semantic judge**: exercised via evals above; unit tests mock its client and only
  test the fail-closed wrapper.

## 5. Tier-2 continuous review — `skills/code-check.md` + GitHub Action

`code-check.md` (the review criteria the CI agent runs, ~40 lines):
1. **Critical vulnerabilities** — secrets/keys in diff, PII patterns in committed files
   (including fixtures), injection risks in tool arg handling.
2. **Policy integrity** — any new tool must appear in `policies.yaml`; any code path
   bypassing `PolicyPlugin` is a finding; semantic gate must remain fail-closed.
3. **Logic & efficiency** — tool contracts match `specs/20-architecture.md` §4; no dead
   branches in engine matrix.
4. **Spec drift** — behavior changes without a matching edit in `specs/10-behavior.md`
   are flagged (spec is the source of truth, not the code).
Output: structured findings list (severity, file:line, rationale) posted as a PR comment.

`.github/workflows/code-check.yml`: on `pull_request` + `push` to main — run
`pytest tests/unit`, a secret/PII grep sweep, and the review skill. Judges' hard
constraint (no keys/passwords) is thus machine-enforced, not just promised.

## 6. Documentation gate (20 pts — treated as a feature, not a chore)

README must let a stranger go zero → running eval in ≤10 commands: prerequisites,
`.env.example` copy step, seed, `adk web`, eval run, architecture diagram, spec links,
and a "why the guardrails are the point" section reusing `30-security.md` §8.
