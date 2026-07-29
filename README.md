# claude-jobhunt-agents

A **multi-agent workspace for [Claude Code](https://claude.com/claude-code)** that turns a
job posting into a structured, evidence-based analysis and keeps a ranked scoreboard of
every role — with a clean split between what an LLM should do (judgment) and what code
should do (bookkeeping).

It's built as a set of **skills + subagents + a deterministic script**, and it keeps all
personal data out of the repo by design (see [Privacy](#privacy)).

---

## What it does

Paste a job description (or a company + role). The system:

1. **De-dupes** against everything already on record (identity = company + role).
2. **Researches** the company — funding, comp bands, Glassdoor, cost-of-living — via web search.
3. **Scores** it against your profile on a fixed rubric and writes a Chinese analysis in a
   consistent ⭐ template (see [`examples/`](examples/)).
4. **Files** it: one analysis per posting, plus a one-line row appended to a ranked scoreboard.
5. Handles **application questions** (short, human answers grounded in your real story bank)
   and **status tracking** (applied / interviewing / offer).
6. **Sources new postings proactively** — sweeps ATS job boards (Greenhouse, Lever, Ashby,
   Workday) for fresh roles matching your profile, deduped against everything already tracked.
7. **Preps you for the interview** — generates a tailored recruiter/HR phone-screen prep pack and
   runs interactive mock screens (see [`examples/Acme-Corp-interview.md`](examples/Acme-Corp-interview.md)).

## Architecture

```
🧠 main agent (orchestrator)         reads the skill, delegates, talks to you
├── 📖 analyze-job (skill)           the playbook: dedup, analyze, batch, answer, status
├── 👷 job-analyzer (subagent)       JUDGMENT: research + score one posting (runs in parallel)
├── 🔭 role-scout (subagent)         JUDGMENT: good company, wrong role → find a better-fitting req
├── 🔎 job-sourcer (subagent)        JUDGMENT: proactively sweep ATS job boards for new fitting roles
├── ✍️ application-answerer (agent)  JUDGMENT: draft a job-application answer from the analysis + profile
├── ⚙️ scoreboard.py (script)        MECHANICAL: append / flush / status / refresh / remove / prune / state / check
├── 🎤 interview-prep (skill)        the playbook: recruiter-screen mock (interactive) + prep pack
├── 📝 interview-prep-writer (agent) JUDGMENT: research + write one company's recruiter-screen pack
├── 🛡️ publish-guard (agent+script)  verifies no personal data before you publish
└── 📐 design-doc-writer (agent)     keeps docs/design.html in sync with the tooling (low-cost)
```

**Design principle — LLM for judgment, code for mechanics.** Research and scoring need
reasoning, so they run in an LLM subagent. Sorting, re-numbering, de-duping and merging the
scoreboard are deterministic, so they run in `scoreboard.py` — exact, atomic, race-free, and
finished in under a second. (This replaced an earlier LLM "scoreboard-keeper" subagent that
was slower and could race on the file.)

**Staging buffer.** New analyses are appended to a `_pending.md` buffer and merged into the
ranked board in one atomic `flush` — so multiple concurrent sessions never clobber the board,
and a batch of analyses doesn't block on a full re-sort.

## Components

| Path | What it is |
|---|---|
| `.claude/skills/analyze-job/SKILL.md` | The orchestrator playbook (analyze / batch / application-answer / status / refresh / sourcing modes). |
| `.claude/skills/analyze-job/scoreboard.py` | Deterministic scoreboard bookkeeping (CLI: `append`/`flush`/`status`/`refresh`/`remove`/`prune`/`state`/`check`). |
| `.claude/skills/analyze-job/status_report.py` | Deterministic job-hunt status snapshot — funnel + deltas, live interviews, score bands, top unapplied targets. |
| `.claude/skills/analyze-job/batch_summary.py` | Deterministic end-of-batch chart — per-job fit/salary/risk sub-scores in a fixed Chinese format, so batch output never drifts between sessions. |
| `.claude/agents/job-analyzer.md` | Subagent that researches + scores one posting and returns a ⭐ report + scoreboard row. |
| `.claude/agents/role-scout.md` | Subagent that scouts a company's careers page / ATS for a better-fitting role when the analyzed one missed. |
| `.claude/agents/job-sourcer.md` | Subagent that proactively sweeps ATS job boards (Greenhouse/Lever/Ashby/Workday) for new postings matching your profile. |
| `.claude/agents/application-answerer.md` | Subagent that drafts a job-application answer, grounded in the saved analysis + your profile/kit. |
| `.claude/agents/publish-guard.md` | Read-only agent that verifies the repo is safe to publish. |
| `.claude/skills/interview-prep/SKILL.md` | Recruiter/HR-screen playbook: interactive mock screen + prep-pack generation. |
| `.claude/agents/interview-prep-writer.md` | Subagent that researches + writes one company's recruiter-screen prep pack. |
| `.claude/agents/design-doc-writer.md` | Low-cost agent that keeps `docs/design.html` in sync with the tooling (surgical edits). |
| `.claude/skills/list-sessions/` | Utility skill: list past Claude Code sessions for the project. |
| `publish_guard.py` | The deterministic secret scanner the guard agent runs. |
| `profile.example.md` | Template for your (gitignored) `profile.local.md`. |
| `application-kit.example.md` | Template for your (gitignored) `application-kit.md` — fixed answers + story bank. |
| `backup.example.sh` | Optional: template for backing up your gitignored personal data to a cloud-synced folder. |
| `md2docx.py` | Convert your Markdown résumé to .docx, cloning the exact look (fonts, bullets, tabs, education table) of a reference .docx you already like. |
| `docs/design.html` | Self-contained architecture/design page (open in a browser, or serve via GitHub Pages). |
| `examples/` | Fictional sample output — a scoreboard, a job analysis, and a recruiter-screen prep pack — so you can see the output shapes. |

## Repo layout

```
claude-jobhunt-agents/
├── README.md                       # this file
├── LICENSE                         # MIT
├── CHANGELOG.md                    # dated log of changes landed on main
├── .gitignore                      # keeps all personal data out of git
├── publish_guard.py                # secret scanner the pre-commit hook runs
├── md2docx.py                      # markdown résumé → .docx (clones a reference docx's look)
├── profile.example.md              # copy → profile.local.md (gitignored) and fill in
├── application-kit.example.md      # copy → application-kit.md (gitignored) and fill in
├── backup.example.sh               # copy → ~/backup.sh: mirror personal data to cloud storage
├── docs/
│   └── design.html                 # self-contained architecture/design page
├── examples/                       # fictional sample output
│   ├── sample-scoreboard.md
│   ├── Acme-Corp.md
│   └── Acme-Corp-interview.md      # sample recruiter-screen prep pack
└── .claude/
    ├── settings.example.json       # copy → .claude/settings.local.json
    ├── agents/
    │   ├── job-analyzer.md          # subagent: research + score one posting
    │   ├── role-scout.md            # subagent: scout a better-fitting role at one company
    │   ├── job-sourcer.md           # subagent: sweep job boards for new fitting postings
    │   ├── application-answerer.md  # subagent: draft a job-application answer
    │   ├── interview-prep-writer.md # subagent: write one company's recruiter-screen pack
    │   ├── publish-guard.md         # agent: verify repo is safe to publish
    │   └── design-doc-writer.md     # agent: keep docs/design.html in sync
    └── skills/
        ├── analyze-job/
        │   ├── SKILL.md             # orchestrator playbook
        │   └── scoreboard.py        # deterministic scoreboard bookkeeping
        ├── interview-prep/
        │   └── SKILL.md             # recruiter-screen mock + prep-pack playbook
        └── list-sessions/
            ├── SKILL.md
            └── list_sessions.py
```

Personal data is never committed — it lives in gitignored local files:
`profile.local.md`, `job-scoreboard.md`, `job-analyses/`, `application-kit.md`,
`.claude/settings.local.json`, `.secrets.local`.

## Quick start

1. Open this folder in Claude Code.
2. `cp profile.example.md profile.local.md` and fill in your real profile (it's gitignored).
3. `cp application-kit.example.md application-kit.md` and fill in your reusable answers (gitignored).
4. `cp .claude/settings.example.json .claude/settings.local.json`.
5. Paste a job description in chat → the `analyze-job` skill runs and files the analysis.
6. Run `python3 .claude/skills/analyze-job/scoreboard.py check` any time to sanity-check the board.

## Privacy

Personal data lives **outside git**, and a guard proves it before anything ships:

- **Gitignored (local only):** `profile.local.md`, `job-scoreboard.md`, `job-analyses/`,
  `application-kit.md`, résumés, `.claude/settings.local.json`, `.secrets.local`.
- **Committed (generic):** the skills, agents, script, templates, and fictional examples.
- **Guard:** `python3 publish_guard.py` scans every *git-tracked* file for personal data
  (home paths, emails, salary figures, and your own secret tokens from `.secrets.local`) and
  fails if anything leaks. The `publish-guard` agent runs it and adds a judgment pass.
- **Backup:** since the personal data is out of git, git isn't backing it up either. Copy
  [`backup.example.sh`](backup.example.sh) to `~/backup.sh` and schedule it (launchd/cron) to
  mirror the workspace — gitignored files included — into iCloud/Dropbox. One rule: the **live
  repo must not live inside a cloud-synced folder** (syncing a live `.git` corrupts it, and
  macOS `~/Desktop`/`~/Documents` add random permission failures) — only the rsync copies go in.

## License

MIT — see [`LICENSE`](LICENSE).
