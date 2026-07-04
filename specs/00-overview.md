# Health Concierge Agent — Capstone Overview

> Spec-first source of truth. Code is disposable; these specs are the asset.
> Read order: this file → `10-behavior.md` → `20-architecture.md` → `30-security.md` → `40-evaluation.md`.

## 1. What & Why

A **personal health & medication concierge agent**: it answers questions about your
medications and checkup reports, tracks multi-year health-metric trends, triages symptom
reports, and produces a daily health briefing — while treating personal health data as
radioactive: **every tool call passes a Policy Server (structural + semantic gating), all
PII is masked at the data boundary, and writes require human confirmation.**

**Track**: Concierge Agents (Kaggle 5-Day AI Agents Intensive capstone, deadline 2026-07-06 23:59 PT).

**Why this is real, not fabricated**: the author runs an actual personal health system
(live PWA, Firestore report store, 5 years of checkup reports, medication log). This
public repo **mirrors that system's schema and architecture** but ships **only synthetic
data**. "Reference the real schema, demo on masked data" *is* the security story — the
agent is designed as if it will be pointed at the real store the day after submission.

## 2. Demo persona

- **Patient**: `[[PATIENT_NAME]]` — a synthetic 32-year-old with 3 years of checkup
  reports (a slowly rising uric-acid trend, one borderline liver metric), 2 active
  medications + 1 supplement, and an allergy record.
- All identity fields are `[[PLACEHOLDER]]` tokens resolved at runtime from env vars
  (defaults to obviously-synthetic values). No real PII exists anywhere in this repo.

## 3. Course-concept evidence map (need ≥3)

| # | Concept | Where judges see it | Our implementation |
|---|---------|--------------------|--------------------|
| 1 | **Multi-agent system (ADK)** | Code | Coordinator `LlmAgent` + 3 specialist sub-agents + a `SequentialAgent`/`ParallelAgent` briefing pipeline (`20-architecture.md` §3) |
| 2 | **MCP server** | Code | `mcp_server/` — health-data store exposed as MCP tools over stdio, PII masking at the server boundary (`20-architecture.md` §4) |
| 3 | **Security guardrails** | Code + Video | Policy engine as ADK `BasePlugin` (structural `policies.yaml` gate + semantic LLM gate), HITL `require_confirmation` on writes, `[[VARIABLE]]` context hygiene (`30-security.md`) |
| + | Evaluation | Code | Gherkin scenarios compiled into ADK eval datasets + pytest gates (`40-evaluation.md`) |
| + | Agent skills / CI review | Code | Tier-2 `code-check.md` review skill run by GitHub Action (`40-evaluation.md` §5) |
| + | Deployability | Video | Dockerfile + `agents-cli deploy cloud-run` walkthrough (documented, live deploy not required) |

## 4. Scoring map (100 pts)

| Rubric | Pts | What we ship |
|--------|-----|--------------|
| Core concept & value | 10 | Real problem (own health system), clear differentiator: **privacy-first concierge** |
| YouTube video ≤5 min | 10 | Script: problem (30s) → happy-path demo (90s) → **guardrail demo: watch the policy gate block a PII exfil + HITL on a write** (90s) → architecture + deploy (60s) → close (30s) |
| Writeup ≤2500 words | 10 | Reuses these specs; cover image = architecture diagram |
| Technical implementation | 50 | 3+ concepts above, working end-to-end via `adk web` |
| Documentation (README) | 20 | Setup-from-zero instructions, arch diagram, spec links, eval instructions |

Judge signal: Day 3 skills author is on the panel — eval + security rigor is weighted
in our favor; the guardrail demo is the centerpiece of the video, not an afterthought.

## 5. Scope (MoSCoW) & timeline

**Must** (submission-blocking):
- MCP server with masked read tools + synthetic SQLite store
- Coordinator + medication / checkup / triage sub-agents
- Policy plugin: structural gate + semantic gate, fail-closed
- HITL confirmation on all write tools
- Eval dataset from Gherkin scenarios + pytest for the policy engine
- README + Writeup + video + cover image

**Should**:
- Daily-briefing pipeline (`ParallelAgent` fan-out → briefing writer)
- `code-check.md` skill + GitHub Action
- `.env.example` with `[[VARIABLE]]` documentation

**Could** (only if time remains):
- Memory Bank for user preferences · Dockerfile deploy walkthrough recorded live

**Won't** (this round):
- Real LifeOS data integration · live cloud deployment · A2A · web UI beyond `adk web`

| Date (PT) | Milestone |
|-----------|-----------|
| 07-03 | Specs approved (this folder) |
| 07-04 | Phase 0–2: scaffold, MCP server + store + unit tests, agents wired |
| 07-05 | Phase 3–4: policy plugin + HITL, eval passing; README |
| 07-06 | Writeup + video + cover image; submit with buffer |

## 6. Non-goals & medical-safety stance

This agent **informs and organizes; it never diagnoses or prescribes**. Dosage-change or
diagnosis requests are refused with a clinician referral; red-flag symptoms trigger an
urgent-care recommendation. Enforced twice: in instructions *and* in the semantic gate
(`30-security.md` §6) — probabilistic instructions alone are not a guardrail.
