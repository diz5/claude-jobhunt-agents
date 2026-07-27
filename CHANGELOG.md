# Changelog

Dated log of what landed on `main`, newest first. One line per change — the "what/when" a
`git log` gives you, kept human-readable. **Rule: every commit to `main` adds its line here in
the same commit** (the pre-push review covers it).

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
