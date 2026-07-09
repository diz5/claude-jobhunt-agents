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

## Architecture

```
🧠 main agent (orchestrator)         reads the skill, delegates, talks to you
├── 📖 analyze-job (skill)           the playbook: dedup, analyze, batch, answer, status
├── 👷 job-analyzer (subagent)       JUDGMENT: research + score one posting (runs in parallel)
├── ⚙️ scoreboard.py (script)        MECHANICAL: append / flush / status / refresh / remove / check
└── 🛡️ publish-guard (agent+script)  verifies no personal data before you publish
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
| `.claude/skills/analyze-job/SKILL.md` | The orchestrator playbook (analyze / batch / application-answer / status modes). |
| `.claude/skills/analyze-job/scoreboard.py` | Deterministic scoreboard bookkeeping (CLI: `flush`/`append`/`status`/`refresh`/`remove`/`check`). |
| `.claude/agents/job-analyzer.md` | Subagent that researches + scores one posting and returns a ⭐ report + scoreboard row. |
| `.claude/agents/publish-guard.md` | Read-only agent that verifies the repo is safe to publish. |
| `.claude/skills/list-sessions/` | Utility skill: list past Claude Code sessions for the project. |
| `publish_guard.py` | The deterministic secret scanner the guard agent runs. |
| `profile.example.md` | Template for your (gitignored) `profile.local.md`. |
| `examples/` | A fictional sample scoreboard + analysis, so you can see the output shape. |

## Quick start

1. Open this folder in Claude Code.
2. `cp profile.example.md profile.local.md` and fill in your real profile (it's gitignored).
3. `cp .claude/settings.example.json .claude/settings.local.json`.
4. Paste a job description in chat → the `analyze-job` skill runs and files the analysis.
5. Run `python3 .claude/skills/analyze-job/scoreboard.py check` any time to sanity-check the board.

## Privacy

Personal data lives **outside git**, and a guard proves it before anything ships:

- **Gitignored (local only):** `profile.local.md`, `job-scoreboard.md`, `job-analyses/`,
  `application-kit.md`, résumés, `.claude/settings.local.json`, `.secrets.local`.
- **Committed (generic):** the skills, agents, script, templates, and fictional examples.
- **Guard:** `python3 publish_guard.py` scans every *git-tracked* file for personal data
  (home paths, emails, salary figures, and your own secret tokens from `.secrets.local`) and
  fails if anything leaks. The `publish-guard` agent runs it and adds a judgment pass.

## License

MIT — see [`LICENSE`](LICENSE).
