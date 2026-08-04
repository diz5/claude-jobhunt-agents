---
name: linkedin-sourcing
description: Run the candidate's LinkedIn job search across their target metros, score the new postings, and surface the ones worth applying to — with a direct apply link. Use when the user says "search LinkedIn", "run my LinkedIn searches", "check for new jobs", "daily job pass", "source jobs", "what's new on LinkedIn", or pastes the linkedin_extract.js JSON. Reads the candidate's real logged-in results via a console snippet (never automated login — no account risk), remembers every posting in a jobId ledger so re-runs skip what you've already seen, analyzes the fresh ones with the job-analyzer, and presents >6 with an apply URL.
---

# LinkedIn Sourcing — the daily multi-metro pass

Turn the candidate's LinkedIn searches into a short, ranked list of **new** roles worth
applying to, each with an apply link. Same split as the rest of the repo:
**LLM does judgment** (triage, scoring, pulling the apply URL out of a JD),
**code does mechanics** (`seen.py`: the jobId ledger — dedup, disposition, queries).

**Load `profile.local.md`** for the fit bar (level, stack, target metros, comp benchmark).
It's the source of truth — never hard-code candidate facts.

## Why the console snippet (and not an automated search)
Getting the candidate's **real** logged-in results matters, and their account must stay safe:
- **Never** automate a logged-in LinkedIn session (Playwright/headless login). It violates the
  User Agreement and trips bot-detection → risks banning their real account.
- **Never** rely on an anonymous `WebFetch` of the search URL for sourcing. LinkedIn's guest view
  returns a *different, depersonalized* set than the candidate sees logged in (the "phantom
  JPMorgan" mismatch) and **ignores the experience/date filters**.

So the candidate runs **`linkedin_extract.js`** (this skill dir) themselves — a read-only DOM
read in their own tab. It sends no automated traffic and doesn't drive the session → no realistic
block risk. Fetching an *individual public JD* with `WebFetch` afterward is fine (server IP, no login).

## Setup (candidate does once): one saved search per metro
Each search is logged-in, with the filters LinkedIn honors: **Experience = Mid-Senior**,
**Date posted = Past 24 hours**, **Location** = the metro. Their metros:
`sanjose`, `nyc`, `seattle`, `dallas`, `remote`. (`remote` = a Remote-filter search they can stay
in Dallas for — the profile values this highly.)

> **Per-metro scoring is already handled** by the analyzer: it scores each offer's comp against
> the profile's **Dallas $-benchmark adjusted for that city's cost-of-living + state tax** — so a
> NYC / San Jose number needs a large nominal premium to clear the bar, while Seattle/Dallas/remote
> (no state income tax) score more favorably at the same nominal comp. No per-metro config here.

## The pass

### 1 — Ingest each metro's results
For each metro the candidate is checking: they open that logged-in search → run
`linkedin_extract.js` (DevTools console) → paste the JSON array back. Pipe it straight into the
ledger, tagging the metro:
```
pbpaste | python3 .claude/skills/linkedin-sourcing/seen.py ingest --metro nyc
# or from a file they saved:
python3 .claude/skills/linkedin-sourcing/seen.py ingest --metro nyc -i nyc.json
```
`ingest` upserts by LinkedIn **jobId**: brand-new ids become `seen`; ones already in the ledger
just refresh `last_seen` and union the metro (a job that shows in both `nyc` and `remote` keeps
both tags). It prints `N new, M already seen`.

### 2 — Pull the to-do queue
```
python3 .claude/skills/linkedin-sourcing/seen.py todo [--json]
```
These are the postings still `seen` — i.e. **new since last time**. Anything you triaged out or
already analyzed on a previous day is remembered and will NOT reappear.

### 3 — Triage (read-only judgment)
Walk the to-do list and drop the noise, recording each decision so it never resurfaces:
- **Recruiter / staffing / anonymized** ("Confidential", "Stealth", "via <Agency>") → the
  candidate won't apply. `mark --status triaged_out --note "anonymized/recruiter"`.
- **Already on the board** — compare company+role against `job-scoreboard.md`
  (`scoreboard.py check`/`state`). If it's the same role (even a re-post under a new jobId),
  `mark --status triaged_out --note "already boarded"`.
- **Rejection cooldown** — if the board shows `被拒`/`已挂`/`已拒` for that role, don't resurface it.
- Everything left is a real candidate → analyze it.

### 4 — Analyze the survivors (+ extract the apply URL)
For each survivor, `WebFetch` its `view_url` (the public JD) and, in the same read, determine the
**apply path** — this is what makes the apply link real:
- Ask explicitly: *is this LinkedIn Easy Apply (in-platform), or does it link out to a company
  application site? If external, what is the exact apply URL?*
- `offsite` → capture that external ATS URL. `easy_apply` → there is no external URL; the apply
  link is the LinkedIn page. If the server-IP fetch hits a login wall, fall back to `unknown` and
  use the `view_url` (the candidate is logged in and can apply from there).

Then run one **`job-analyzer`** subagent per role (⭐ template, location-aware scoring) and board
it the normal way (`scoreboard.py append` → `flush`). Record the disposition in the ledger:
```
python3 .claude/skills/linkedin-sourcing/seen.py mark --job-id 444 \
    --status analyzed --score 7.5 --apply-type offsite \
    --apply-url "https://boards.greenhouse.io/acme/jobs/444"
```
Run several analyzers in parallel for a batch, but confirm scope with the candidate before large
fan-outs (they prefer explaining first over auto-launching heavy batches).

### 5 — Present what's worth applying to
```
python3 .claude/skills/linkedin-sourcing/seen.py filter --status analyzed --min-score 6
```
For **every role scoring > 6**: show its ⭐ analysis + rating + the **apply link**
(external ATS URL when we have one, else the LinkedIn page). One line each for the rest.
The candidate applies manually.

### 6 — Close the loop
The candidate applies to all by default and **names the ones they skipped** (standing rule).
Record it so tomorrow's pass reflects reality:
```
python3 .claude/skills/linkedin-sourcing/seen.py mark --job-id 444 --status applied
python3 .claude/skills/linkedin-sourcing/seen.py mark --job-id 222 --status skipped
```
Then move applied roles into the `auto-apply` packet flow if they want answers drafted, and set
the board status via `scoreboard.py status … --set "已投 <MM-DD>"`.

## The mechanical CLI — `seen.py`
`python3 .claude/skills/linkedin-sourcing/seen.py <op>` (ledger at gitignored `.linkedin-seen.db`):
- `ingest --metro M [-i FILE|-]` — upsert a snippet's JSON array; new jobIds → `seen`.
- `todo [--metro M] [--json]` — postings still needing triage/analysis (the new ones).
- `mark --job-id ID --status {seen,triaged_out,analyzed,applied,skipped} [--score N] [--apply-type {easy_apply,offsite,unknown}] [--apply-url U] [--note ...]`
- `filter [--metro M] [--status S] [--min-score N] [--json]` — query (e.g. the suggested list).
- `stats` — counts by status and metro. `list [--json]` — dump everything.
Show only its one-line stdout — don't paste the ledger contents into chat.

## Rules
- **No authenticated LinkedIn automation, ever.** Sourcing = the candidate's own console snippet.
- **The ledger is the memory** — always `ingest` before triaging and `mark` every disposition, or
  postings will re-surface. Dedup by jobId (ledger) AND company+role (scoreboard) — they catch
  different cases (exact re-fetch vs. re-post under a new id).
- **Privacy:** `.linkedin-seen.db` is gitignored personal data; run `python3 publish_guard.py`
  before any commit. Don't dump ledger/board contents into chat — confirm actions in one line.
- **中文 for the analysis** (job-analyzer's ⭐ template); English for titles/URLs.
