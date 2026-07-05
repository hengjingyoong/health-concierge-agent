# Kaggle Writeup — field-by-field submission pack

Copy-paste source for the writeup form. Deadline: **Jul 7 2026 2:59 PM GMT+8**
(= Jul 6 23:59 PT). One submission per team — final check before pressing
Submit.

## Basic Details

**Title** (71/80):

```
Health Concierge Agent — a privacy-first medication & checkup concierge
```

**Writeup URL** (36/50):

```
health-concierge-agent-privacy-first
```

**Subtitle** (137/140):

```
A medication & checkup concierge that treats health data as radioactive — masked at the boundary, deny-by-default, human-approved writes.
```

**Card and Thumbnail Image** (560×280): upload
`docs/assets/kaggle-card-560x280.png`

**Submission Track**: ✅ **Concierge Agents**

## Media Gallery

**Video**: the YouTube URL (unlisted is fine).

**Images** — upload in this order; first image doubles as the gallery cover.
Captions to paste per image:

| # | File | Caption |
|---|------|---------|
| 1 | `docs/assets/cover.png` | Architecture: one Policy Server plugin gates every tool call and every response |
| 2 | `docs/assets/gallery/01-medication-schedule.png` | "What do I take tonight?" — coordinator delegates to the medication specialist over MCP |
| 3 | `docs/assets/gallery/02-masked-payload.png` | The MCP function response: prescriber already masked as [[DOCTOR_NAME]] before the LLM context sees it |
| 4 | `docs/assets/gallery/03-uric-acid-trend.png` | Three-year uric-acid trend with reference ranges — data, not diagnosis |
| 5 | `docs/assets/gallery/04-briefing-parallel-fanout.png` | Daily briefing: three fetchers fan out in parallel, a writer merges |
| 6 | `docs/assets/gallery/05-hitl-confirmation-card.png` | Every write pauses: human confirmation card with the exact payload |
| 7 | `docs/assets/gallery/06-viewer-write-blocked.png` | Viewer role blocked by the structural policy gate — the write never executes |
| 8 | `docs/assets/gallery/07-eval-results.png` | Final eval: 19/19 — response quality 5.0, tool trajectory 1.0, zero PII leaks |

## Project Description (≤2500 words; ours ≈1,050)

Paste the body of `docs/WRITEUP.md` **from "## The problem (and why it's
mine)" onward** — skip the title header and the "Project link / Video" line
(those live in Project Links), and drop the final "## Links" section for the
same reason. Use the editor's heading button for the `##` sections.

## Project Links (Attachments → Add a link)

Link 1:

```
URL:   https://github.com/hengjingyoong/health-concierge-agent
Title: GitHub — code, specs, eval suite (CC-BY 4.0)
Desc:  Spec-first repo: Gherkin behavior spec, ADK multi-agent system, MCP server with boundary masking, Policy Server plugin, 19-case eval suite, CI. Setup-from-zero in 6 commands.
```

Link 2:

```
URL:   <YOUTUBE_URL>
Title: Demo video (3.5 min) — the guardrails are the demo
Desc:  Happy path, human-in-the-loop write approval, viewer blocked by the policy gate, and the semantic gate failing closed — all recorded live against the running agent.
```

## Pre-submit checklist

- [ ] YouTube video is **unlisted** (not private) and plays in an incognito
      window
- [ ] `final.srt` uploaded as CC; custom thumbnail = `docs/assets/cover.png`
- [ ] Both `<YOUTUBE_URL>` placeholders in `docs/WRITEUP.md` replaced (repo
      copy too, for consistency)
- [ ] GitHub repo loads in incognito (public), CI badge green
- [ ] Track = Concierge Agents selected
- [ ] Checklist shows 8/8 → Submit
