---
name: application-prep
description: Prep job applications from the ranked scoreboard. Use when the user says "apply to X", "queue up applications", "auto-apply" (legacy name), "draft the answers for X", "fill the form for X", or wants to see which roles to apply to next. Picks roles off job-scoreboard.md, scaffolds a per-job packet, and drafts a review-ready answer sheet you use to fill and submit the ATS form yourself. No automated form-filling or submission — you apply manually.
help: 申请打包：排队 → 起草 answers.md → 你审阅后手动提交
---

# Application Prep (formerly auto-apply)

Turn ranked roles into filed applications, keeping the same split as the rest of this repo:
**LLM does judgment** (drafting answers), **code does mechanics** (`apply.py`: queue,
packet scaffold). Personal data lives only under `applications/` (gitignored).

**Load `profile.local.md`** for the candidate; **`application-kit.md`** for reusable answers.
Both are gitignored (the repo ships `profile.example.md` / `identity.example.json` as templates).

## Step 0 — Sourcing (see the `linkedin-sourcing` skill)
Finding the roles to apply to is its own workflow, owned by the **`linkedin-sourcing`** skill:
it sources by criteria via anonymous LinkedIn **guest search** (server-side, no account risk), the
`seen.py` jobId ledger dedups across daily runs, survivors are analyzed (⭐, location-aware) and the
>6 list is presented with an apply link. (ATS-board sweeps are the `job-sourcer` agent; both feed
the analysis flow.)

Roles the candidate then wants to apply to move into the packet flow below.

## Data model — one folder per job (all gitignored)
```
applications/<slug>/
├── packet.json    # machine record: identity + questions[{label,answer,...}] + ats/url + state
├── answers.md     # human-readable answer sheet — the review surface (the deliverable)
└── run.log        # append-only pipeline log
applications/identity.json   # shared applicant identity (copy from identity.example.json), gitignored
```
`slug = kebab(company + role)`. A posting's identity is **company + role** (same as the
scoreboard), so one company's multiple roles get separate packets.

## Apply-state (mirrors the scoreboard 状态 column, extended)
`未投 → 排队中 → 草稿就绪 → 已投 MM-DD`
- The board is **single-writer through `scoreboard.py`** — never hand-edit it. When a job
  moves state, update the board with
  `python3 .claude/skills/analyze-job/scoreboard.py status --company C --role R --set "<state>"`.
- The packet's own `state` field is updated by `apply.py` as it progresses.

## The mechanical CLI — `apply.py`
`python3 .claude/skills/application-prep/apply.py <op>`:
- `queue [--min-score N] [--status S] [--json]` — roles to apply to, ranked (default: 状态=未投, 推荐分≥6).
- `init --company C --role R [--url U] [--ats A] [--location L]` — scaffold the packet (seeds identity from `applications/identity.json`).
- `list [--json]` — all packets, their state and answered-question count.
Show only its one-line stdout — do not paste packet/board contents into chat.

## Flow

### Step 1 — Pick what to apply to
Run `apply.py queue`. Relay the short list (rank, company, role, 推荐分, 一句话). Ask the user
which to prep (or "top N"). Only roles already **analyzed** (on the board) can be queued — if
the user names an un-analyzed company, run the `analyze-job` skill first.

### Step 2 — Scaffold the packet
For each chosen role: `apply.py init --company … --role … --url … --ats …`.
Then set the board state: `scoreboard.py status … --set 排队中`.

### Step 3 — Draft the answers (subagent)
Spawn one **`application-drafter`** subagent per job (in parallel for several). Give it the
packet **slug**, the job's **analysis file** (`job-analyses/<Company>.md`), and the **form URL**
(or a pre-scraped question list). It scrapes/uses the questions, drafts short human answers per
the Mode B rules, and writes `answers.md` + fills `packet.json`. Relay its summary — including
any `needs_confirm` questions the candidate must answer. Then set board state → `草稿就绪`.

### Step 4 — Review
Show the user `answers.md` (this is the review surface — the answers, not the board). Once the
candidate approves / edits, check `apply.py list` shows every question answered; resolve any
`needs_confirm` items before proceeding. Board state stays `草稿就绪`.

### Step 5 — Apply manually (no automated autofill/submit — by design)
The tool intentionally does **not** fill or submit forms for the candidate — we run no browser
automation on their behalf. The pipeline ends with a review-ready answer sheet:
- Deliver `answers.md` (the answers) + the ATS URL.
- The candidate fills the ATS form themselves (copying from the sheet) and clicks Submit.
- After they apply, record it: `scoreboard.py status … --set "已投 <MM-DD>"` and — if the role came
  through the LinkedIn ledger — `seen.py mark --job-id … --status applied`.

(An autofill/submit driver — and its `payload.json` fill spec — was considered and dropped to
avoid browser automation; every application is submitted by the candidate.)

## Rules
- **Never fabricate identity or experience.** Answers come from `profile.local.md` +
  `application-kit.md`; identity from `applications/identity.json`. Missing data → flag it
  (`needs_confirm`), ask the candidate, never invent.
- **Never submit for the candidate.** The tool never fills or submits an application — the
  candidate does that themselves. We prepare the answers only.
- **Don't dump packet/board contents into chat.** `answers.md` is the review surface — show that.
  Board changes go through `scoreboard.py` (one-line output only).
- **Privacy:** everything under `applications/` is gitignored; run `python3 publish_guard.py`
  before any commit/push. The repo only ships generic templates.
