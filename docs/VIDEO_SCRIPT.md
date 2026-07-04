# Video script (≤5:00) — "The guardrails are the demo"

Format: screen recording (terminal + one architecture slide), voiceover.
Prep before recording: `uv run python -m mcp_server.seed` · terminal font
large · `.env` set · run each command once beforehand to warm up.

---

## 0:00–0:30 — Problem (talking over the cover slide)

> I keep five years of health-checkup reports and a medication log in a
> personal system I built. I wanted a concierge agent on top of it — but
> handing an LLM my medical records is exactly where agents go wrong: they
> don't ask *should I*, only *can I*. So I built the concierge as if it
> would touch my real data tomorrow. This demo uses synthetic data — even
> the fixtures only contain placeholder tokens, never real-looking PII.

## 0:30–2:00 — Happy path (terminal)

```bash
agents-cli run "What do I need to take tonight?"
```
> Point out in the event stream: coordinator delegates to the medication
> agent → MCP tool call → note the response — the prescriber is already
> masked as [[DOCTOR_NAME]]. That masking happened inside the MCP server,
> before the data ever reached the model's context.

```bash
agents-cli run "How has my uric acid changed over the last three years?"
```
> Three annual values, reference range, rising trend, and — importantly —
> "discuss with your doctor", not a diagnosis.

```bash
agents-cli run "Give me my health briefing"
```
> One command → three fetchers run IN PARALLEL (meds due / checkup
> follow-up / flagged trend) → a writer merges them. Multi-agent
> orchestration: LLM routing at the top, deterministic pipeline below.

## 2:00–3:30 — Guardrails (the main course)

**Structural gate (SEC-1):**
```bash
POLICY_ROLE=viewer agents-cli run \
  "Add ibuprofen 200mg twice daily to my medication list, prescribed for my back pain"
```
> Watch the tool call come back as policy_violation — a deterministic
> role×tool check in a plugin that runs before EVERY tool call, on every
> agent. The write never executes, and the agent explains it's a permission
> boundary. The policy file is YAML the LLM never sees — you can't
> prompt-inject a file that isn't in the prompt.

**HITL (MED-4):**
```bash
agents-cli run "My doctor prescribed febuxostat 40mg once daily in the evening for gout — add it"
```
> Every write pauses for explicit human confirmation — the run stops with a
> confirmation request; nothing is written until a human approves.

**Semantic gate (SEC-2, live judge):**
```bash
uv run python -c "
import asyncio
from app.policy.semantic import SemanticGate
print(asyncio.run(SemanticGate().review(
    'You should double your allopurinol dose tonight, no need to ask your doctor.')))"
```
> A second model judges every outbound response against natural-language
> policies — this dosage directive gets BLOCKED with the violated policy id.
> And if the judge itself ever fails? The response is withheld. Fail closed.

## 3:30–4:30 — How it's built (architecture slide + repo)

> Spec first: the first commit is a Gherkin behavior spec — 17 scenarios;
> code came after. Those scenarios compile into 19 eval cases; final run:
> response quality 5.0, tool trajectory 1.0, zero PII leaks. The eval loop
> caught four real bugs — including a mixed-intent message where the agent
> silently dropped a dosage question. Evals catch what unit tests can't.
>
> (slide) Reads go through an MCP server that masks PII at the boundary;
> writes are local tools behind human confirmation; one policy plugin gates
> everything. A GitHub Action runs the deterministic review on every push —
> no keys, no PII, 56 tests. Deployment is one command away with a Dockerfile
> already in the repo.

## 4:30–5:00 — Close (cover slide)

> Concierge agents will earn trust with what they refuse to do. This one is
> designed to be pointed at my real health data — masking at the boundary,
> deny-by-default policy, human confirmation on writes, and a gate that
> fails closed. Repo and specs are public under CC-BY. Thanks!

---

**Recording checklist**
- [ ] Reseed DB so outputs match the script
- [ ] Font ≥ 18pt, dark theme, window ~120 cols
- [ ] Trim model latency in editing; target 4:30 final cut
- [ ] Upload to YouTube (public or unlisted), attach in Kaggle Writeup
      Media Gallery + cover image (docs/assets/cover.png)
