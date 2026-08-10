---
name: linkedin-sourcing
description: Source senior-SWE jobs by the candidate's criteria (level + past-24h + target metros), score them against the profile, and surface the ones worth applying to — each with an apply link. Also runs a separate REFERRAL track for big-tech companies the candidate can get referred into. Use when the user says "search LinkedIn", "run my job search", "check for new jobs", "daily job pass", "source jobs", "what's new", "referral companies". Sources via anonymous LinkedIn guest search (server-side, no account risk), dedups every posting in a jobId ledger so re-runs skip what's already seen, analyzes fresh ones with job-analyzer, and presents >6 with an apply URL.
help: 搜岗 skill 本体（/job-search、/referral-check 是它的快捷方式）
---

# LinkedIn Sourcing — the daily multi-metro pass

Turn the candidate's search **criteria** into a short, ranked list of **new** roles worth applying
to, each with an apply link. Split: **LLM does judgment** (triage, scoring, apply-URL extraction),
**code does mechanics** (`seen.py`: the jobId ledger — dedup, disposition, queries).

**Load the profile** (`profile.local.md` at the project root, or `~/dev/resume/profile.local.md`)
for the fit bar — level, stack, target metros, comp benchmark, and the scoring guide. Source of truth.

## Sourcing engine: anonymous LinkedIn guest search (NOT the console snippet)
Decision (2026-08): source via the **public LinkedIn guest jobs endpoint**, fetched server-side with
`WebFetch`. Why this over the alternatives:
- **The console snippet is dead for LinkedIn** — the logged-in results list now lives in a
  **cross-origin iframe**, unreachable from the DevTools console (only the single open job is
  visible). (`linkedin_extract.js` stays in this dir for any *other* site that renders a normal DOM.)
- **No authenticated automation** (Playwright / headless login) — ToS violation + account-ban risk.
- The candidate **doesn't need his exact personalized list** — as long as the *criteria* match
  (senior + past-24h + his metros), real fitting jobs come back. The guest view is depersonalized
  (fine) and runs from a **server IP → zero account/IP risk**.

Guest endpoint, per metro:
```
https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=senior%20software%20engineer&location=<Metro>%2C%20United%20States&f_TPR=r86400&start=<0|10>
```
- `f_TPR=r86400` = **past 24h** (honored by guest). It **ignores** the experience-level filter →
  judge seniority in the analysis and drop non-senior.
- **~20 per metro per run**: WebFetch `start=0` **and** `start=10` (two calls ≈ 20 jobs). Configurable
  — add `start=20/30…` for more coverage. From each response extract every card:
  `jobId | title | company | location | posted-age`.

## Metros & scoring
Metros: `sanjose`, `nyc`, `seattle`, `dallas`, `remote`.
> **Per-metro scoring is handled by the analyzer** — comp is scored against the profile's Dallas
> $-benchmark adjusted for that city's COL + state tax (NYC / San Jose need a big nominal premium;
> Seattle / remote-from-Dallas score better at equal nominal). No per-metro config here.

## The pass

### 1 — Fetch + ingest each metro
For each metro: WebFetch the guest URL (`start=0` then `start=10`), collect the cards, convert each
card's **age** ("11 hours ago") to an absolute `posted` date (today − age), and ingest — tagging the
metro. Build `[{jobId,title,company,location,posted,viewUrl}]` and pipe it:
```
python3 .claude/skills/linkedin-sourcing/seen.py ingest --metro sanjose -i cards.json
```
`ingest` upserts by **jobId** (new → `seen`; existing → refresh + union metro), stamps `posted`, and
**auto-flags `referral`** when the company is on `referral-companies.md`.

### 2 — To-do queue
`seen.py todo [--metro M]` — postings still `seen` (new since last time). Anything triaged or
analyzed before is remembered and won't reappear.

### 3 — Triage
**First run `seen.py board-dedup`** — it deterministically cross-checks every `seen` row against
the full application history (`job-scoreboard.md` + `_pending.md`) and the never-apply blocklist
(`blocked-companies.md`, gitignored): auto-drops blocked companies (🚫) and same-company+role
duplicates (✂, even re-posts under a new jobId), and prints a ⚠ line per posting whose company has
a rejection row (`被拒`/`已挂`/`已拒`) — those are NOT auto-dropped (different role at the same
company is allowed) but weigh the history in your triage. Never re-implement this check inline.
Then drop the remaining noise by judgment, recording each so it never resurfaces:
- Recruiter / staffing / anonymized → `mark --status triaged_out --note "recruiter/anon"`.

### 4 — Analyze survivors (+ apply URL)
One `job-analyzer` per survivor (⭐ template, location-aware). It WebFetches the `view_url` for the JD
and determines the apply path: `offsite` → capture the external ATS URL; `easy_apply` → the apply
link is the LinkedIn page. Record it:
```
seen.py mark --job-id 444 --status analyzed --score 7.5 --apply-type offsite \
    --apply-url "https://boards.greenhouse.io/acme/jobs/444" --posted 2026-08-06
```
Run several in parallel, but **confirm scope before large fan-outs** — and the `web_budget_guard`
hook hard-caps WebSearch/WebFetch per agent as the runaway backstop.

### 5 — Present
`seen.py filter --status analyzed --min-score 6` — for every role **>6**: its ⭐ analysis + rating +
apply link (external ATS URL when we have one, else the LinkedIn page) **+ 📍 the job's location**
(city + onsite/hybrid/remote if known). Location is a search criterion, so it must be visible at a
glance in the final list — put it in the scoreboard row's 岗位 column (e.g. `(Seattle)`) AND as a
`📍` line next to each apply link; never make the candidate open the analysis to find out where the
job is. One line each for the rest. The candidate applies manually.

### 6 — Close the loop
Candidate applies to all by default and **names the skips**. `mark --status applied` / `skipped`.
Move applied roles into `application-prep` if they want answers drafted; set board status via `scoreboard.py`.

## The referral track (big-tech the candidate can be referred into)
A **separate, bounded** pass for companies on **`referral-companies.md`** (gitignored;
`Name | linkedin_company_id | note`). Goal: catch **new fitting roles** at these companies so the
candidate can decide whether to ask a friend for a referral.

> **Fully separate from the regular flow (by design).** The referral track uses its **own ledger**
> `--db .linkedin-referral.db`; it never touches the regular `.linkedin-seen.db`. The regular
> metro pass ingests with **`--exclude-referral`** so referral companies never appear in the regular
> list — the two flows are disjoint and can't affect each other.
1. For each referral company, run **one** guest search with the company filter `&f_C=<company_id>`
   (precise; keyword fallback if the id is blank) + senior keywords + his metros — widen `f_TPR` to
   `r604800` (past week), since a referral is worth catching a few days late. **One guest call per
   company** = naturally bounded (4 companies → 4 calls); `web_budget_guard` backs it up.
2. Ingest (auto-flags `referral=1`), triage, analyze new ones.
3. For **≥6** fits: **save** the ⭐ analysis to `job-analyses/<Company>-<role>.md` **with the post
   date**, and record it in the ledger. Then regenerate `referral-queue.md` from
   `seen.py filter --referral --min-score 6 --json` (best-fit + newest first, grouped by company).
4. **Every run, show the candidate the latest / best-fit referral role per company** so they can
   decide on a referral. They say applied / skipped → `mark`.
After editing `referral-companies.md`, run `seen.py reflag` to re-flag already-ingested rows.

## The mechanical CLI — `seen.py`
`python3 .claude/skills/linkedin-sourcing/seen.py <op>` (ledger: gitignored `.linkedin-seen.db`):
- `ingest --metro M [-i FILE|-]` — upsert `[{jobId,title,company,location,posted,viewUrl}]`; stamps `posted`, auto-flags `referral`.
- `todo [--metro M] [--json]` — new postings needing triage/analysis.
- `board-dedup [--dry-run]` — auto-triage `seen` rows already on the board/pending (company+role match) and rows from `blocked-companies.md`; ⚠-warns on rejected-company history without dropping.
- `mark --job-id ID --status {seen,triaged_out,analyzed,applied,skipped} [--score N] [--apply-type {easy_apply,offsite,unknown}] [--apply-url U] [--posted YYYY-MM-DD] [--note ...]`
- `filter [--metro M] [--status S] [--min-score N] [--referral] [--json]` — query. **Referral review = `--referral --min-score 6`.**
- `reflag` — re-apply referral flags from the current list. `stats` · `list [--json]`.
Show only its one-line stdout — don't paste ledger contents into chat.

## Rules
- **No authenticated LinkedIn automation, ever.** Source via the server-side guest fetch.
- **The ledger is the memory** — `ingest` before triaging, `mark` every disposition, or postings
  re-surface. Dedup by jobId (ledger) AND company+role (scoreboard) — different cases.
- **Bounded fan-out** — ~20/metro; one guest call per referral company; confirm before large
  analyzer batches; `web_budget_guard` hard-caps web calls per agent.
- **Privacy:** `.linkedin-seen.db`, `referral-companies.md`, `referral-queue.md` are gitignored; run
  `python3 publish_guard.py` before any commit. Don't dump ledger/board contents into chat.
- **中文 for the analysis** (⭐ template); English for titles/URLs.
