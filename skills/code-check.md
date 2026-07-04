# code-check — Tier-2 review skill for this repository

Reviewer runtime: any coding agent (Claude Code, Gemini CLI, Antigravity)
pointed at a diff of this repo. Run every section against the CHANGED files
only; report findings as a structured list. CI runs the deterministic subset
of these checks on every push (`.github/workflows/code-check.yml`); this
skill is the full review an agent performs on a pull request.

## 1. Critical vulnerabilities (blocking)

- Any credential material in the diff: API keys, tokens, service-account
  JSON, passwords, `GOOGLE_APPLICATION_CREDENTIALS` values. The ONLY
  acceptable form is a `[[PLACEHOLDER]]` in `.env.example`.
- Any PII-shaped literal in committed files, including test fixtures:
  TW national IDs (`[A-Z][12]\d{8}`), phone numbers, emails, real names.
  Synthetic fixtures must use `[[PLACEHOLDER]]` tokens, not fake-but-real-
  looking values.
- Tool-argument handling that interpolates user text into SQL (must use
  parameterized queries as `mcp_server/store.py` does).

## 2. Policy integrity (blocking)

- Every NEW tool (MCP or local FunctionTool) must appear in
  `app/policy/policies.yaml` under the roles that may use it — an
  unregistered tool is denied at runtime, and an unreviewed grant is a
  finding.
- No code path may construct an agent/Runner that bypasses `PolicyPlugin`
  (e.g. a new `App(...)` or `Runner(...)` without the plugin), except the
  judge's own runner inside `app/policy/semantic.py`.
- `SemanticGate.review` must remain fail-closed: any edit that makes a judge
  failure return "pass" is a blocking finding.
- Write paths must keep `require_confirmation=True`; new write tools must
  never be exposed on the MCP server.

## 3. Logic & efficiency

- MCP tool contracts must match `specs/20-architecture.md` §4 (names, args,
  masked fields).
- Masking must stay at the server boundary (`mcp_server/server.py`), keyed
  by the correct per-surface token map — remember the drug-name/patient-name
  collision regression (`tests/unit/test_masking.py`).
- No dead branches in `app/policy/engine.py`'s matrix; deny-by-default must
  be preserved.

## 4. Spec drift (advisory)

- Behavior changes without a matching edit in `specs/10-behavior.md` (and an
  eval case update in `tests/eval/datasets/`) — the spec is the source of
  truth, code follows it.
- New Gherkin scenarios without a corresponding trajectory rule in
  `tests/eval/eval_config.yaml`.

## Output format

For each finding: `severity (blocking|advisory) · file:line · what · why`.
End with a verdict: APPROVE / REQUEST CHANGES.
