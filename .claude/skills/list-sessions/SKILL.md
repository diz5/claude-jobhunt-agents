---
name: list-sessions
description: List past Claude Code sessions for the current project as a quick summary table — session ID, last-active time, transcript size, and name (the /rename custom title, else the auto-generated title). Use when the user wants to see, list, browse, or summarize related/past sessions for this project.
help: 列出本项目历史会话速查表
---

# List Sessions

Show a summary of all Claude Code sessions belonging to the **current project** so the
user can quickly find and resume one.

## How to run

Run the helper script (it derives the project's session folder from the working directory):

```
python3 .claude/skills/list-sessions/list_sessions.py
```

Then present its output. The script already prints a clean table with:
- **ID** — short session id (first 8 chars; full id is the `.jsonl` filename)
- **Last active** — file modified time
- **Size** — transcript size
- **Name** — user `/rename` title if set, else the auto-generated AI title, else a
  truncated first prompt
- **↳ summary** — an optional hand-curated one-liner shown under a session, if one exists

Rows are sorted newest-first; the current session (if detectable) is marked `▶`.

## Curated summaries (best of both worlds)

The live columns above are always regenerated from disk, so nothing goes stale. The
optional **summary** line is read from `session-helper/session-info.md` — a small,
hand-maintained table of `| ` + backtick-quoted session id + ` | summary |` rows. To add
or edit a session's summary, edit that file directly (no script/regeneration needed).

> This replaced the older `session-helper/refresh-sessions.sh` (which regenerated a
> full registry and had a hardcoded "current session" id, so it went stale). That script
> is retired; `session-info.md` is now just the curated-summary store this skill reads.

## Notes
- Sessions live in `~/.claude/projects/<encoded-cwd>/*.jsonl`, where Claude Code encodes
  the project path by replacing every `/` and `.` with `-`.
- To inspect a different project, pass its absolute path as an argument:
  `python3 .claude/skills/list-sessions/list_sessions.py /some/other/project`
- This skill is **read-only** — it never modifies session files.
- After showing the table, remind the user they can reopen one with `/resume` (in-session
  picker) or `claude --resume` from the terminal.
