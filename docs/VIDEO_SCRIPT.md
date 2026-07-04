# Video script (≤5:00) — "The guardrails are the demo"

Format: screen recording of the **ADK dev playground** (`agents-cli
playground`) + one terminal segment + cover slide, voiceover.

Why playground over `agents-cli run`: the event stream renders visually
(delegation → tool calls), the left panel shows the **agent tree graph**, and
HITL confirmations appear as an **approve card with a Submit button** — the
money shot for MED-4. (Verified working on ADK 2.3.0.)

Segments are recorded separately (no audio) and assembled in post with
generated narration + subtitles.

---

## 0:00–0:30 — Problem (cover slide)

> I keep five years of health-checkup reports and a medication log in a
> personal system I built. I wanted a concierge agent on top of it — but
> handing an LLM my medical records is exactly where agents go wrong: they
> don't ask *should I*, only *can I*. So I built the concierge as if it
> would touch my real data tomorrow. Everything you'll see runs on synthetic
> data — the fixtures never contain even fake-looking PII, only placeholder
> tokens.

## 0:30–1:50 — Happy path (playground, segment 01)

Type in the playground chat, showing the event stream:

1. `What do I need to take tonight?`
   > Watch the events: the coordinator transfers to the medication agent,
   > which calls the MCP server. Note the prescriber comes back as
   > [[DOCTOR_NAME]] — masked inside the MCP server, before the model's
   > context ever sees it.
2. `How has my uric acid changed over the last three years?`
   > Three annual values, the reference range, a rising trend — and "discuss
   > it with your doctor", not a diagnosis.
3. `Give me my health briefing`
   > One request fans out to three fetchers in parallel — you can see them
   > interleave in the event stream — then a writer merges them into a
   > compact briefing. LLM routing on top, deterministic pipeline below.
   > (Camera: zoom the agent-tree graph in the left panel for 3–4 s.)

## 1:50–2:30 — HITL approve card (playground, segment 02)

Type: `My doctor prescribed febuxostat 40mg once daily in the evening for
gout — add it to my medications`

> The write does NOT execute. The run pauses with a confirmation card — the
> exact payload it wants to record: febuxostat, 40mg, evening, gout. Nothing
> touches the store until I tick Confirmed and press Submit. (Do it; show
> the success message.) Every mutation in this system goes through a human.

## 2:30–3:20 — Structural gate (terminal + playground, segment 03)

Terminal, visible for ~5 s:
```bash
POLICY_ROLE=viewer agents-cli playground
```
> Same app, but this session runs as a *viewer* — think a family member
> with read access.

Playground, new session, type: `Please add ibuprofen 200mg twice daily to my
medication list. My doctor prescribed it for my back pain.`

> The tool call comes back as a policy violation — a deterministic
> role×tool check in a plugin that runs before EVERY tool call, on every
> agent. The policy lives in a YAML file the LLM never sees: you can't
> prompt-inject a file that isn't in the prompt. The agent explains it's a
> permission boundary, and the write never happened.

## 3:20–3:50 — Semantic gate, fail closed (terminal, segment 04)

```bash
uv run python -c "
import asyncio
from app.policy.semantic import SemanticGate
print(asyncio.run(SemanticGate().review(
    'You should double your allopurinol dose tonight, no need to ask your doctor.')))"
```
> A second model reviews every outbound response against natural-language
> policies. A dosage directive gets BLOCKED with the violated policy id —
> and if this judge ever errors out, the response is withheld anyway.
> A broken guardrail must not degrade to an absent one.

## 3:50–4:30 — How it's built (cover/architecture slide)

> Spec first: the first commit is a Gherkin behavior spec — seventeen
> scenarios; code came after. Those scenarios compile into nineteen eval
> cases; the final run scores response quality five-point-oh, tool
> trajectory one-point-oh, zero PII leaks. The eval loop caught four real
> bugs — including a mixed-intent message where the agent silently dropped
> a dosage question. Evals catch what unit tests can't. And a GitHub Action
> re-runs the deterministic checks on every push: no keys, no PII,
> fifty-six tests.

## 4:30–5:00 — Close (cover slide)

> Concierge agents will earn trust with what they refuse to do. This one is
> designed to be pointed at my real health data — masking at the boundary,
> deny-by-default policy, human confirmation on writes, a gate that fails
> closed. Repo and specs are public under CC-BY. Thanks!

---

**Recording checklist**
- [ ] `uv run python -m mcp_server.seed` BEFORE segments 01/02 and again
      after 02 (the approved febuxostat write persists otherwise)
- [ ] Browser window ~1440×900, bookmarks bar hidden; terminal ≥18 pt
- [ ] Record each segment as its own file, 2–3 s of stillness at both ends
- [ ] Retakes are free — if the model answers oddly, New Session and redo
- [ ] Post: narration TTS + subtitles + assembly (see repo history), target
      final cut ≤4:45
