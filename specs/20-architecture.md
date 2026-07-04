# Architecture & Technical Design

> Narrative in Markdown; nested schemas in YAML (per SDD format guidance — deep nesting
> parses better as YAML and avoids the JSON format tax).

## 1. System diagram

```
 user ── adk web / CLI
   │
   ▼
┌─────────────────────────── ADK App ────────────────────────────┐
│  PolicyPlugin (BasePlugin — global, runs before agent callbacks)│
│   ├─ before_tool_callback  → structural gate (policies.yaml)   │
│   └─ after_model_callback  → semantic gate (LLM judge, fail-   │
│                              closed) + regex PII prefilter     │
│                                                                 │
│  health_concierge (root LlmAgent, coordinator)                  │
│   ├─ medication_agent   (LlmAgent)                              │
│   ├─ checkup_agent      (LlmAgent)                              │
│   ├─ triage_agent       (LlmAgent)                              │
│   └─ briefing_pipeline  (SequentialAgent)                       │
│        ├─ ParallelAgent: meds_fetcher · followup_fetcher ·      │
│        │                 trend_fetcher   (distinct output_keys) │
│        └─ briefing_writer (merges state keys)                   │
└───────────────┬────────────────────────────┬────────────────────┘
                │ McpToolset (stdio,          │ local FunctionTools
                │ read-only, tool_filter)     │ (writes, require_confirmation)
                ▼                             ▼
        mcp_server/server.py ──────► store.py (SQLite)
        (masks PII at boundary)          ▲
                                         │ seed.py
                                  data/synthetic/*.yaml
```

**Read/write split (deliberate):** all *reads* go through the **MCP server** (masking at
the boundary, least-privilege via `tool_filter`); all *writes* are **local
`FunctionTool`s with `require_confirmation`** (ADK-native HITL) hitting the same SQLite
store. Writes are never exposed on the generic MCP surface — defense in depth, and each
side cleanly demonstrates one course concept.

## 2. Stack (pin exact versions at scaffold time — do not trust model memory)

| Component | Choice | Version policy |
|-----------|--------|----------------|
| Language | Python | 3.11+ |
| Agent framework | `google-adk` | 2.x — pinned by `agents-cli scaffold`; verify with `pip show google-adk` |
| MCP SDK | `mcp` (official Python SDK) | latest 1.x, pin in `pyproject.toml` |
| Model | `gemini-flash-latest` (all agents + semantic judge) | env-configurable |
| Model backend | **Vertex AI** (service-account auth), not AI Studio | see §2.1 |
| Store | SQLite (stdlib `sqlite3`) | — |
| Tests | `pytest` 8.x + `agents-cli eval run` | — |
| Runtime config | `.env` (gitignored) + `.env.example` | no keys in code, ever |

### 2.1 Model backend config (Vertex AI)

Agent code stays backend-agnostic (`Agent(model="gemini-flash-latest")`); the backend is
selected entirely via env vars, documented in `.env.example`:

```bash
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=[[GCP_PROJECT_ID]]
GOOGLE_CLOUD_LOCATION=global            # verify: probe available models per location first
GOOGLE_APPLICATION_CREDENTIALS=[[PATH_TO_SERVICE_ACCOUNT_JSON]]   # gitignored file
```

Before first run, probe which Gemini models the project actually has in which location
(`gcloud ai models` / a one-shot generateContent probe) — regional endpoints may lack
modern Flash models while `global` has them; do not debug this by editing agent code.

## 3. Agent design (ADK)

| Agent | Type | Tools | output_key | Notes |
|-------|------|-------|-----------|-------|
| `health_concierge` | `LlmAgent` (root) | — | — | Routes via `sub_agents` LLM delegation; owns scope-refusal behavior |
| `medication_agent` | `LlmAgent` | MCP: `list_medications`, `get_medication_schedule` · local: `add_medication` (HITL) | — | MED-* scenarios |
| `checkup_agent` | `LlmAgent` | MCP: `list_reports`, `get_report_details`, `get_metric_history` | — | CHK-* scenarios |
| `triage_agent` | `LlmAgent` | local: `log_symptom` (HITL) | — | TRI-*; red-flag list in instruction **and** semantic gate |
| `briefing_pipeline` | `SequentialAgent` | — | — | BRF-1 |
| ├ `meds_fetcher` | `LlmAgent` | MCP read tools | `briefing_meds` | Parallel branch |
| ├ `followup_fetcher` | `LlmAgent` | MCP read tools | `briefing_followup` | Parallel branch |
| ├ `trend_fetcher` | `LlmAgent` | MCP read tools | `briefing_trends` | Parallel branch |
| └ `briefing_writer` | `LlmAgent` | — | — | Instruction interpolates `{briefing_meds}` etc. |

Conventions: every sub-agent has a `description` (required for delegation); sub-agents
built via factory functions (avoids "already has a parent"); HITL uses
`FunctionTool(fn, require_confirmation=True)` with `App(resumability_config=
ResumabilityConfig(is_resumable=True))`.

## 4. MCP server tool contracts

Read-only; every response passes `mask()` before returning — identity fields are
replaced with `[[PLACEHOLDER]]` tokens **server-side** (SEC-4).

```yaml
server:
  name: health-data-mcp
  transport: stdio            # SseConnectionParams documented for prod in README
  tools:
    - name: list_medications
      args: {}
      returns: "list of {name, dose, frequency, start_date, prescriber_masked, status}"
    - name: get_medication_schedule
      args: { time_of_day: "morning|noon|evening|any" }
      returns: "medications due at that time, derived from frequency"
    - name: list_reports
      args: {}
      returns: "list of {report_id, date, provider, abnormal_count}"
    - name: get_report_details
      args: { report_id: string }
      returns: "full metric list for one report: {metric, value, unit, ref_range, flag}"
    - name: get_metric_history
      args: { metric: string }
      returns: "time series across reports: [{date, value, unit, ref_range, flag}]"
```

Local write tools (NOT on MCP): `add_medication(name, dose, frequency, reason)`,
`log_symptom(description, severity, suspected_trigger)` — both `require_confirmation`,
both re-checked by the structural gate (role must allow writes).

## 5. Data model (synthetic fixtures → SQLite)

Mirrors the author's real system: one document per checkup report with a metrics map
(Firestore `healthReports` shape) and a medication table (name/dose/frequency/start
date/prescriber — same columns as the real medication log). Simplified where the real
system's fields don't serve the demo.

```yaml
# data/synthetic/profile.yaml
profile:
  name: "[[PATIENT_NAME]]"
  national_id: "[[PATIENT_ID]]"      # placeholders IN THE FIXTURES — raw PII never exists
  birth_year: 1994
  allergies: ["penicillin"]

# data/synthetic/medications.yaml
medications:
  - {name: allopurinol, dose: 100mg, frequency: once_daily_evening,
     start_date: 2026-05-10, prescriber: "[[DOCTOR_NAME]]", status: active}
  - {name: omeprazole, dose: 20mg, frequency: once_daily_morning,
     start_date: 2026-03-02, prescriber: "[[DOCTOR_NAME]]", status: active}
  - {name: fish_oil, dose: 1000mg, frequency: once_daily_morning,
     start_date: 2025-11-01, prescriber: null, status: active}

# data/synthetic/reports/2026-06.yaml   (one file per report; 3 report-years total)
report:
  report_id: "2026-06-clinic-a"
  date: 2026-06-15
  provider: "Clinic A"
  metrics:
    uric_acid:  {value: 7.9, unit: mg/dL, ref: "3.5-7.2", flag: high}
    alt:        {value: 44,  unit: U/L,   ref: "10-40",  flag: high}
    glucose_ac: {value: 92,  unit: mg/dL, ref: "70-100", flag: normal}
    # ~10 metrics per report; uric_acid rises 6.8 → 7.4 → 7.9 across the 3 years
```

## 6. Repository layout (No-YOLO: confirm before scaffold)

```
health-concierge-agent/
├── specs/                      # this folder — source of truth
├── app/                        # ADK agent package (agents-cli scaffold layout)
│   ├── __init__.py
│   ├── agent.py                # root_agent + sub-agent factories
│   ├── tools.py                # local write tools (HITL)
│   ├── policy/
│   │   ├── engine.py           # structural check (pure function — unit-testable)
│   │   ├── semantic.py         # LLM judge, fail-closed wrapper
│   │   ├── plugin.py           # PolicyPlugin(BasePlugin)
│   │   └── policies.yaml
│   └── context/resolver.py     # [[VARIABLE]] → env resolution (UI layer only)
├── mcp_server/
│   ├── server.py               # MCP tools + boundary masking
│   ├── store.py                # SQLite access
│   └── seed.py                 # fixtures → SQLite
├── data/
│   ├── synthetic/              # committed fixtures (above)
│   └── private/                # gitignored — never used in this repo
├── tests/
│   ├── unit/                   # policy engine, masking, store, resolver
│   └── eval/
│       ├── eval_config.yaml
│       └── datasets/           # compiled from specs/10-behavior.md IDs
├── .github/workflows/code-check.yml
├── skills/code-check.md        # Tier-2 review skill (40-evaluation.md §5)
├── .env.example
└── README.md
```

## 7. Build phases (each phase gated by its tests — see 40-evaluation.md)

0. **Scaffold**: `agents-cli scaffold enhance .` (repo exists) — confirm generated
   layout matches §6 before proceeding.
1. **Store + MCP server** + seed + unit tests (masking is unit-tested here, SEC-4).
2. **Agents**: coordinator + 3 specialists on MCP reads; MED/CHK/TRI happy paths pass.
3. **Policy layer**: plugin + policies.yaml + HITL writes; SEC-* scenarios pass.
4. **Briefing pipeline**; full eval suite green.
5. **Docs & pitch**: README, writeup, video, cover image.
