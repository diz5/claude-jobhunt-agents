# Changelog

## 2026-08-11
- **Dual-repo model**: new `pgit.sh` — a second, local-only git layer (`.personal-git/`, no remote, gitignored) that versions the personal data files (board, analyses, profile, ledgers) via scoped force-add snapshots; wired into the nightly backup so history rides into the cloud mirror. `publish_guard.py` REQUIRED_IGNORES extended (`.personal-git/`, `.board-state.json`, `blocked-companies.md`).
- Privacy sweep (semantic layer, publish-guard agent): scrub real company names tied to the author's application history from tracked tooling docs — scoring-precedent citation and example scoreboard row / filename examples now use fictional companies.

Dated log of what landed on `main`, newest first. One line per change — the "what/when" a
`git log` gives you, kept human-readable. **Rule: every commit to `main` adds its line here in
the same commit** (the pre-push review covers it).

## 2026-08-09
- GitHub Pages enabled from `/docs` — the design page is live at diz5.github.io/agentic-workflow-toolkit/design.html; linked from README's Architecture section.
- **Repo renamed `claude-jobhunt-agents` → `agentic-workflow-toolkit`** and README reframed: the project presents as an agentic-workflow toolkit for Claude Code, with job-search as its reference domain (GitHub redirects the old URL).
- Skip rubric (SKILL.md triage step): S1 stack-gate-by-title / S2 recruiter / S3 rejected-company / S4 non-target-metro / S5 level-mismatch / S6 domain-mismatch, with rule codes recorded in every `skipped` note — auditable, session-consistent; ambiguous titles default to analyze, never guess-skip.
- `seen.py digest`: end-of-run full-disposition display (every posting one line, grouped by fate, 📍 location) — the candidate decides everything in one pass; wired into SKILL.md present step as a verbatim relay.
- Blocklist: gitignored `blocked-companies.md` (never-apply companies; ships `blocked-companies.example.md`) — `board-dedup` auto-drops their postings with whole-word matching. Presentation rule added: every >6 result must show 📍 job location at a glance (location is a search criterion).
- `seen.py board-dedup`: deterministic cross-check of the todo queue against the full application history (board + pending) — auto-drops same-company+role re-posts, ⚠-warns on rejected-company history (different role stays allowed). Replaces the ad-hoc inline dedup each sourcing session used to improvise; wired into SKILL.md triage step.
- `scoreboard.py`: new `--channel autosearch` (自动搜岗) tag — marks applications whose role was found by the linkedin-sourcing pipeline, so pipeline accuracy (auto-sourced vs self-found outcome rates) can be compared later.
- Add `/job-hunt-help` command — live cheat-sheet of the project's slash commands + skill entry points. Table is printed by a deterministic script (`job_hunt_help.py`, relayed verbatim — zero LLM reading/translation per run); each entry point's frontmatter carries an optional Chinese `help:` line the script prefers over the English description. Scans fresh every run, so it never goes stale.

## 2026-08-08
- Merge PR #1 (`feature/auto-apply`): linkedin-sourcing skill (guest-search engine + `seen.py` jobId ledger + separate big-tech referral track), auto-apply skill (`apply.py` + `application-drafter` subagent, manual-submit-only), `identity.example.json`, `referral-companies.example.md`, publish-guard updates.
- Fix auto-apply SKILL.md Step 0: sourcing is via anonymous LinkedIn guest search (the console snippet is dead for LinkedIn); gitignore `session-helper/archive/`.
- Add `/job-search` + `/referral-check` slash commands (`.claude/commands/`) — one-word triggers for the linkedin-sourcing regular pass and referral track.
- **Rename `auto-apply` → `application-prep`** (the old name implied automated submission; "auto-apply" kept as a trigger alias) and **drop the `payload.json` layer** (`build-payload` op, `submit_mode` field) — leftovers of the dropped autofill driver; `answers.md` is the sole deliverable. README/design page synced.

## 2026-08-03
- `scoreboard.py remove` falls back to the `_pending.md` staging buffer when the row isn't on the board yet — lets you remove a row analyzed this session before it's flushed. (Contributed by another session; reviewed.)
- **Scoring is now fit-gated** (job-analyzer.md + SKILL.md Mode A): 推荐分 is anchored to 履历适配度, not an average of the three sub-scores. Tech-stack match is the gate (a stack the candidate lacks tanks fit; domain/culture overlap can't rescue it); AI/agentic-harness fit is a co-top positive. If fit < 6 → 推荐分 = fit (salary/company can't lift it); if ≥ 6 → fit anchors, salary+company modify ~±1. Company splits into risk (small down) vs prestige/heat (small up). Fixes bad-fit-but-high-pay jobs scoring ~7.
- Batch display: **clamp the post-script freehand to ONE short single-clause line** (top pick). The old "≤3 lines of closing judgment" license let sessions write multi-clause 三点判断 blocks that corrupt on the terminal (CJK words drop / lines merge) — the recurring "garbled batch summary" bug. Fixed in SKILL.md Mode C + CLAUDE.md floor rule 4. The per-job judgment already lives in the `--full` output; re-synthesizing it is redundant.
- Rejection cooldown: dedup (SKILL.md Step 0) and `job-sourcer` now flag/skip roles whose board status is `被拒`/`已挂`/`已拒` — don't re-suggest a recently-rejected role (~6mo freeze; a *different* role at that company is fine). (Contributed by another session; reviewed.)

## 2026-07-31
- Add `interview-intel` agent + interview-prep **Mode C** (technical rounds): researches one company×stage's recent (≤6mo) 面经 across 1point3acres/Reddit/Glassdoor/LeetCode Discuss under a strict budget (≤12 searches, ≤10 fetches, ≤3 per source; login walls listed for the candidate, never bypassed), then the skill builds a profile-aware prep plan.
- Add `.claude/hooks/web_budget_guard.py` + shipped `.claude/settings.json`: PreToolUse hook hard-capping WebSearch/WebFetch at 40 calls per agent session (WEB_BUDGET_MAX to tune) — deterministic runaway protection for ALL research agents. Design page synced (agents 7→8).
- Outcome analytics: `status_report.py` gains a 结果转化 section (interview/rejection conversion by score band and DFW-local/remote/onsite); `scoreboard.py status` now auto-date-stamps every status change and accepts `--channel cold|referral|recruiter|inbound` — data discipline for future time-to-response and channel analysis.
- Merge audit log simplified: drop the `--session-name` flag (sessions never passed it — log showed "unnamed"); `.merge-log.md` records the always-available `$CLAUDE_CODE_SESSION_ID` only. SKILL/design page synced.

## 2026-07-30
- `batch_summary.py`: chart is now a markdown TABLE (公司/⭐/适配/薪资/风险); 💰-block parsed structurally (fixes ⚠️未解析 on phrasing variants); range-aware money extraction (comma/K-notation ranges as one token); wider note cells. Mode C gains a stall-recovery step (resume = rerun display+stage from disk, never re-analyze).

## 2026-07-29
- Add `CLAUDE.md` project floor rules (loaded in EVERY session): re-read the playbook before first analysis, 中文-only analysis output, no Edit on board/buffer, Mode C verbatim protocol — the antidote to stale-playbook sessions.
- `batch_summary.py --full` — the entire end-of-batch display in one deterministic call: full ⭐ analyses for ≥6 (from files, highest first) + ❌ one-liners for <6 + the chart. Mode C now renders nothing by hand.
- `scoreboard.py flush` gains `--session-name` + an append-only `.merge-log.md` audit log (who merged, when, counts) — concurrent-session visibility. (Contributed by another session; reviewed.)

## 2026-07-28
- Add `batch_summary.py` + strict Mode C display protocol — progress-counter-only while a batch runs, full template only for ≥6 (one-line reason for <6/skips), deterministic Chinese end-of-batch chart relayed verbatim. Fixes cross-session batch-output drift (improvised tables, English wrap-ups, mid-batch detail dumps). Design page synced (scripts 4→5).

## 2026-07-27
- Add `status_report.py` + analyze-job **Mode G** — deterministic job-hunt status snapshot (funnel + deltas vs previous run, interviews, bands, top targets); replaces error-prone ad-hoc board parsing. `.status-history.json` gitignored. Design page synced (scripts 3→4).

## 2026-07-26
- `md2docx.py`: non-bold inline segments no longer inherit bold from a bold prototype run (skills lines rendered fully bold).
- `md2docx.py`: all education-table rows clone the same prototype row — mixed reference rows carried different paragraph spacing (uneven line gaps).
- `md2docx.py`: education-table rows render on one line (degree — school | date) instead of two — denser and more ATS-parse-friendly.
- Add `md2docx.py` — convert a Markdown résumé to .docx by cloning the look of a reference .docx (auto-detects name/heading/bullet/job-header/skills prototypes + education table; no configuration).
- Add `CHANGELOG.md` (this file) — dated history of changes on main.

## 2026-07-23
- Add `job-sourcer` agent + analyze-job **Mode F** — proactive ATS sweep (Greenhouse/Lever/Ashby/Workday) for new postings matching the profile.
- Gitignore hardening: resume drafts (`*[Rr]esume*`), scoreboard backups, interview-prep output.

## 2026-07-22
- Add `role-scout` agent — "good company, wrong role" → scout that company's careers/ATS for a better-fitting req; sync README + design page.
- Add `backup.example.sh` — template for mirroring gitignored personal data into cloud storage (live repo stays OUT of cloud-synced folders); README privacy note.

## 2026-07-20
- Publish the "read-aloud test" answer-voice guide into `application-kit.example.md`.

## 2026-07-19
- `application-answerer` pinned to Opus for best human-voice adherence.

## 2026-07-17
- Add `application-answerer` agent (grounded application answers) + `interview-prep` skill / `interview-prep-writer` agent (recruiter-screen prep).
- Add `docs/design.html` (self-contained architecture page) + `design-doc-writer` agent (low-cost surgical sync) + `application-kit.example.md` template.
- Sync README component table with actual `scoreboard.py` ops.

## 2026-07-13
- `scoreboard.py`: min-score cutoff (<6 auto-skip), `prune`, `refresh`, and `.board-state.json` freshness marker (`state` op).

## 2026-07-09
- Gitignore `*.local.md`; `publish_guard.py` uses real `git check-ignore`; README repo-layout tree.

## 2026-07-08
- Initial public release: analyze-job skill + scoreboard script, job-analyzer agent, publish guard, profile template, fictional examples.
