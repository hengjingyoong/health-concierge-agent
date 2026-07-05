## The problem (and why it's mine)

I run a personal health system: a live PWA, a Firestore store with five years
of health-checkup reports, and a medication log. It answers *"what's in my
data"* — but not *"what should I pay attention to today?"* For that I wanted
a concierge: something that reminds me what to take tonight, notices that my
uric acid has crept from 6.8 to 7.9 mg/dL across three annual reports, logs
the heartburn I mention, and briefs me every morning.

Handing an LLM agent the keys to my most sensitive personal data is exactly
the situation the course's security day warned about: agents don't judge
whether they *should* do something, only whether they *can*. So the capstone
question became: **what does a health agent look like when it's designed as
if it will touch real medical data the day after submission?**

This repo is the answer. It mirrors my real system's schema and architecture
but ships only synthetic data — even the fixtures use `[[PLACEHOLDER]]`
tokens instead of fake-but-plausible PII. *Reference the real schema, demo on
masked data* — the deployment story and the security story are the same
story.

## What it does

- **Medication concierge** — "What do I take tonight?" → reads the recorded
  schedule; new prescriptions are recorded only after an explicit human
  confirmation.
- **Checkup analyst** — "How has my uric acid changed?" → per-year values
  with reference ranges and the trend direction; abnormal-flag summaries of
  the latest report.
- **Symptom triage** — logs routine symptoms (with confirmation); red-flag
  symptoms (chest pain, one-sided weakness…) get an *emergency-care-first*
  response, never self-care advice.
- **Daily briefing** — one command fans out three parallel fetchers
  (medications due, checkup follow-up, flagged trends) and merges them into
  a sub-200-word briefing.
- **It never diagnoses or prescribes.** Dose questions get a refusal plus a
  clinician referral — enforced twice, in instructions *and* in an external
  gate, because probabilistic instructions alone are not a guardrail.

## Architecture — three course concepts, one chokepoint

**1 · ADK multi-agent system.** A coordinator `LlmAgent` routes by LLM
delegation to three specialists (medication / checkup / triage), plus a
deterministic `SequentialAgent` briefing pipeline whose first stage is a
`ParallelAgent` fan-out into three fetchers with distinct `output_key`s. Both
orchestration styles the course taught — LLM routing and workflow agents —
in one tree.

**2 · MCP server.** All *reads* go through a FastMCP stdio server exposing
five tools over a SQLite store. Two design points matter: **PII is masked
inside the server, per data surface** (a "name" on the profile is a patient;
a "name" on a medication row is a drug — a collision our smoke tests caught
on day one), so the LLM context never contains raw identifiers regardless of
agent behavior; and each agent gets a least-privilege `tool_filter`. Writes
are deliberately *not* on the MCP surface: they are local FunctionTools with
`require_confirmation=True`, so every mutation pauses for a human.

**3 · Security guardrails — a Policy Server as an ADK plugin.** Governance
lives in a `BasePlugin` registered on the App — it runs before agent-level
callbacks for every agent and every tool, with no per-agent opt-out, and the
LLM never sees the policy file:

- `before_tool` → **structural gate**: a pure-function role×tool×environment
  check against `policies.yaml` (owner / viewer / guest; deny-by-default;
  env-blocked tools). Microseconds, no LLM.
- `after_model` → **semantic gate**: a deterministic PII-regex prefilter,
  then a small LLM judge (`gemini-3.1-flash-lite`, Pydantic-schema verdict)
  checking outbound text against natural-language policies (no unmasked PII,
  no medical directives, no guardrail bypass). **Any judge failure blocks
  the response** — a broken guardrail must not degrade to an absent one.

Session role and environment are seeded from the runtime environment, never
from user text. Watch it work: run with `POLICY_ROLE=viewer` and ask to add
a medication — the tool call is intercepted with a `policy_violation` and
the agent explains the permission boundary; the write never executes.

## Built spec-first, verified by evals

Following the Day-5 playbook, the first commit contains no code: `specs/`
holds a Gherkin behavior spec (17 scenarios with stable IDs), the technical
design, the security design, and the eval plan. Code followed the spec.

The scenarios compile into six eval datasets (19 cases, including paraphrase
probes for the safety-critical ones, and a viewer-role dataset). Grading
combines one LLM rubric with two deterministic code metrics (per-case tool
trajectory, PII regex sweep). A note for fellow builders: `agents-cli eval
generate` (0.5.1) can't load MCP-toolset agents and skips App plugins — so a
custom trace generator runs every case through the *real* Runner, plugins
and HITL included, and represents confirmation pauses with an explicit
`[[AWAITING_HUMAN_CONFIRMATION]]` sentinel that the rubric scores as correct
designed behavior.

The eval-fix loop earned its keep — four real defects, none caught by unit
tests or smoke tests:

1. **A semantic-gate false positive**: reading back the recorded schedule
   ("tonight: allopurinol 100mg") was judged a *medical directive*. Fixed in
   the policy wording — recorded data is data, not advice.
2. **HITL mis-scoring**: confirmation-pause "errors" were counted as
   successful writes by the trajectory metric.
3. **An invented detail**: told "once daily", the agent silently picked
   *morning*. The instruction now forbids filling in unstated details.
4. **The dangerous one**: a mixed-intent message ("my joints hurt — can I
   double my allopurinol?") was routed to triage, which logged the symptom
   and *silently dropped the dosage question*. The coordinator and triage
   agent now must address the safety-critical part explicitly.

Final full suite: **19/19 — response quality 5.0, tool trajectory 1.0,
PII-leak 0.**

Continuous review is wired in too: `skills/code-check.md` is a Tier-2 review
skill (secrets/PII in diffs, policy-integrity rules like "every new tool
must be registered in `policies.yaml`" and "fail-closed may not be
weakened"), with its deterministic slice running as a GitHub Action on every
push — the judges' no-keys-in-code rule is machine-enforced, not promised.

## What I'd build next

Point the MCP server at the real Firestore store (the masking boundary and
policy file were designed for exactly that), add Memory Bank for
preferences, and run the briefing pipeline on a Cloud Scheduler → Pub/Sub
trigger as an ambient agent. Deployment is one `agents-cli scaffold enhance
--deployment-target cloud_run` away — a Dockerfile already ships in the
repo.
