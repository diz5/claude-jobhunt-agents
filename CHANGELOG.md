# Changelog

Dated log of what landed on `main`, newest first. One line per change — the "what/when" a
`git log` gives you, kept human-readable. **Rule: every commit to `main` adds its line here in
the same commit** (the pre-push review covers it).

## 2026-07-31
- Add `interview-intel` agent + interview-prep **Mode C** (technical rounds): researches one company×stage's recent (≤6mo) 面经 across 1point3acres/Reddit/Glassdoor/LeetCode Discuss under a strict budget (≤12 searches, ≤10 fetches, ≤3 per source; login walls listed for the candidate, never bypassed), then the skill builds a profile-aware prep plan.
- Add `.claude/hooks/web_budget_guard.py` + shipped `.claude/settings.json`: PreToolUse hook hard-capping WebSearch/WebFetch at 40 calls per agent session (WEB_BUDGET_MAX to tune) — deterministic runaway protection for ALL research agents.
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
