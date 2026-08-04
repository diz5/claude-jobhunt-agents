---
name: auto-apply
description: Prep and (optionally) submit job applications from the ranked scoreboard. Use when the user says "apply to X", "queue up applications", "auto-apply", "draft the answers for X", "fill the form for X", or wants to see which roles to apply to next. Picks roles off job-scoreboard.md, scaffolds a per-job packet, drafts human answers, and builds an autofill payload. Browser autofill/submit are gated (see Submit modes).
---

# Auto-Apply

Turn ranked roles into filed applications, keeping the same split as the rest of this repo:
**LLM does judgment** (drafting answers), **code does mechanics** (`apply.py`: queue,
packet scaffold, payload). Personal data lives only under `applications/` (gitignored).

**Load `profile.local.md`** for the candidate; **`application-kit.md`** for reusable answers.
Both are gitignored (the repo ships `profile.example.md` / `identity.example.json` as templates).

## Step 0 — Sourcing (see the `linkedin-sourcing` skill)
Finding the roles to apply to is its own workflow, owned by the **`linkedin-sourcing`** skill:
the candidate runs `linkedin_extract.js` on their logged-in searches, the `seen.py` jobId ledger
dedups across daily runs, survivors are analyzed (⭐, location-aware) and the >6 list is presented
with an apply link. (ATS-board sweeps are the `job-sourcer` agent; both feed the analysis flow.)

Roles the candidate then wants to apply to move into the packet flow below.

## Data model — one folder per job (all gitignored)
```
applications/<slug>/
├── packet.json    # machine-fillable: identity + questions[{label,answer,...}] + ats/url + submit_mode + state
├── answers.md     # human-readable answer sheet — the review surface
├── payload.json   # flat field→value fill spec (produced by build-payload; consumed by the autofill driver)
└── run.log        # append-only pipeline log
applications/identity.json   # shared applicant identity (copy from identity.example.json), gitignored
```
`slug = kebab(company + role)`. A posting's identity is **company + role** (same as the
scoreboard), so one company's multiple roles get separate packets.

## Apply-state (mirrors the scoreboard 状态 column, extended)
`未投 → 排队中 → 草稿就绪 → 已填(待提交) → 已投 MM-DD`
- The board is **single-writer through `scoreboard.py`** — never hand-edit it. When a job
  moves state, update the board with
  `python3 .claude/skills/analyze-job/scoreboard.py status --company C --role R --set "<state>"`.
- The packet's own `state` field is updated by `apply.py`/the driver as it progresses.

## The mechanical CLI — `apply.py`
`python3 .claude/skills/auto-apply/apply.py <op>`:
- `queue [--min-score N] [--status S] [--json]` — roles to apply to, ranked (default: 状态=未投, 推荐分≥6).
- `init --company C --role R [--url U] [--ats A] [--location L] [--submit-mode M]` — scaffold the packet (seeds identity from `applications/identity.json`).
- `build-payload --slug S` — packet.json → payload.json (flat fill spec); warns about any unanswered question.
- `list [--json]` — all packets and their state.
Show only its one-line stdout — do not paste packet/board contents into chat.

## Flow

### Step 1 — Pick what to apply to
Run `apply.py queue`. Relay the short list (rank, company, role, 推荐分, 一句话). Ask the user
which to prep (or "top N"). Only roles already **analyzed** (on the board) can be queued — if
the user names an un-analyzed company, run the `analyze-job` skill first.

### Step 2 — Scaffold the packet
For each chosen role: `apply.py init --company … --role … --url … --ats … --submit-mode manual`.
Default **`--submit-mode manual`** unless the user has chosen otherwise (see Submit modes).
Then set the board state: `scoreboard.py status … --set 排队中`.

### Step 3 — Draft the answers (subagent)
Spawn one **`application-drafter`** subagent per job (in parallel for several). Give it the
packet **slug**, the job's **analysis file** (`job-analyses/<Company>.md`), and the **form URL**
(or a pre-scraped question list). It scrapes/uses the questions, drafts short human answers per
the Mode B rules, and writes `answers.md` + fills `packet.json`. Relay its summary — including
any `needs_confirm` questions the candidate must answer. Then set board state → `草稿就绪`.

### Step 4 — Review + payload
Show the user `answers.md` (this is the review surface — the answers, not the board). Once the
candidate approves / edits, run `apply.py build-payload --slug …`. If it warns about unanswered
questions, resolve them before proceeding. Set packet ready for fill; board state → depends on
submit mode (see below).

### Step 5 — Autofill / submit  ⚠️ NOT YET IMPLEMENTED (Phase 2/3)
The Playwright driver (`autofill.py`) and the submit gate are **not built yet**. Until they are:
- Deliver `answers.md` + `payload.json` and tell the user to fill/submit manually, OR
- If they ask to build it, that's Phase 2/3 work — say so; don't pretend to fill or submit.
When built, this step opens the ATS URL, fills from `payload.json`, and follows the submit mode.

## Submit modes (capability exists for all three; default = manual)
Set per packet via `init --submit-mode` (or the user's session default):
- **`manual`** (default, safest) — driver fills every field and **stops at the submit button**.
  The candidate reviews the filled form and clicks Submit themselves.
- **`confirm`** — driver fills, screenshots the completed form, and submits **only after the
  candidate explicitly OKs that specific job** in chat.
- **`auto`** — driver fills and submits without per-job confirmation. Highest risk; use only
  when the user has explicitly opted a batch into it.
On a real submit: append to `run.log` and set board state
`scoreboard.py status … --set "已投 <MM-DD>"`.

## Rules
- **Never fabricate identity or experience.** Answers come from `profile.local.md` +
  `application-kit.md`; identity from `applications/identity.json`. Missing data → flag it
  (`needs_confirm`), ask the candidate, never invent.
- **Never auto-submit unless the packet's `submit_mode` says so.** When in doubt, `manual`.
- **Don't dump packet/board contents into chat.** `answers.md` is the review surface — show that.
  Board changes go through `scoreboard.py` (one-line output only).
- **Privacy:** everything under `applications/` is gitignored; run `python3 publish_guard.py`
  before any commit/push. The repo only ships generic templates.
