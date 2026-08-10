---
description: Show this project's slash commands and skill entry points, with a one-line usage hint for each
---

Show the user a compact 中文 cheat-sheet of THIS project's entry points. Build it live — do
NOT answer from memory:

1. List `.claude/commands/*.md` and read each file's frontmatter `description` — these are the
   slash commands (command name = filename without `.md`).
2. List `.claude/skills/*/SKILL.md` and read each frontmatter `name` + the first sentence of its
   `description` — these are the skills (each also invocable as `/<name>`).

Render ONE table: `命令 | 类型(command/skill) | 干什么(one short line, 中文)`, commands first.
Skip this helper command itself. After the table, add at most two lines: how to pass arguments
(`/job-search <补充说明>`), and where the files live (`.claude/commands/`, `.claude/skills/`).
Keep the whole output under ~20 lines — it's a cheat-sheet, not documentation.
