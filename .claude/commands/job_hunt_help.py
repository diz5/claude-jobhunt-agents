#!/usr/bin/env python3
"""Deterministic cheat-sheet for /job-hunt-help.

Scans this project's entry points and prints a ready-to-display Markdown table,
so the LLM relays the output verbatim instead of reading + translating the
frontmatter itself every run (zero tokens, identical output every time):

  .claude/commands/*.md        -> slash commands (name = filename without .md)
  .claude/skills/*/SKILL.md    -> skills (each also invocable as /<name>)

Each file's YAML frontmatter may carry an optional `help:` line — a one-line
Chinese description used for the table. Files without `help:` fall back to the
first sentence of their English `description:`. No caching needed: the scan IS
the cheap part (a dozen small local files), and scanning fresh every run is
what keeps the sheet from ever going stale.
"""
import os
import re

# .claude/commands/job_hunt_help.py -> project root is three levels up.
ROOT: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COMMANDS_DIR: str = os.path.join(ROOT, ".claude", "commands")
SKILLS_DIR: str = os.path.join(ROOT, ".claude", "skills")

# The helper never lists itself.
SELF_NAME: str = "job-hunt-help"


def frontmatter(path: str) -> dict[str, str]:
    """Parse the YAML frontmatter block (between the first two `---` lines)
    of a Markdown file into a flat {key: value} dict.

    Only handles the simple `key: value` lines these files actually use —
    not a full YAML parser, and doesn't need to be.
    """
    fields: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return fields
    if not lines or lines[0].strip() != "---":
        return fields
    for line in lines[1:]:
        if line.strip() == "---":  # end of frontmatter
            break
        m = re.match(r"^(\w[\w-]*):\s*(.+?)\s*$", line)
        if m:
            fields[m.group(1)] = m.group(2)
    return fields


def one_liner(fields: dict[str, str]) -> str:
    """Pick the table description: prefer the Chinese `help:` line, else the
    first sentence of the English `description:`, hard-capped for table width."""
    text = fields.get("help") or fields.get("description") or "?"
    # First sentence: cut at the first ". " (English) or "。" (Chinese).
    text = re.split(r"(?<=\.)\s|。", text)[0]
    return text[:70] + ("…" if len(text) > 70 else "")


def main() -> None:
    """Print the cheat-sheet table (commands first, then skills) + 2 hint lines."""
    rows: list[tuple[str, str, str]] = []

    if os.path.isdir(COMMANDS_DIR):
        for fn in sorted(os.listdir(COMMANDS_DIR)):
            if not fn.endswith(".md") or fn[:-3] == SELF_NAME:
                continue
            rows.append((f"/{fn[:-3]}", "command",
                         one_liner(frontmatter(os.path.join(COMMANDS_DIR, fn)))))

    if os.path.isdir(SKILLS_DIR):
        for d in sorted(os.listdir(SKILLS_DIR)):
            skill_md = os.path.join(SKILLS_DIR, d, "SKILL.md")
            if os.path.isfile(skill_md):
                rows.append((f"/{d}", "skill", one_liner(frontmatter(skill_md))))

    print("| 命令 | 类型 | 干什么 |")
    print("|---|---|---|")
    for name, kind, desc in rows:
        print(f"| `{name}` | {kind} | {desc} |")
    print()
    print("带参数：`/job-search <补充说明>`。"
          "文件位置：`.claude/commands/`（命令）、`.claude/skills/`（playbook）。")


if __name__ == "__main__":
    main()
