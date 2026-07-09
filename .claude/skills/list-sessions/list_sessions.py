#!/usr/bin/env python3
"""List Claude Code sessions for the current project.

Outputs a table: ID | Last active | Size | Name, with an optional curated
summary line under each session.

Live data (id / last-active / size / name) is read straight from the per-project
transcript folder under ~/.claude/projects/<encoded-cwd>/*.jsonl. Claude Code
encodes the project's absolute path by replacing every '/' and '.' with '-'.

Curated summaries (optional, hand-maintained) are read from
  <project>/session-helper/session-info.md
as table rows of the form:  | `<full-session-id>` | <summary text> |
Sessions without a curated summary simply show none — nothing goes stale, because
the live columns are always regenerated from disk on every run.

Name resolution per session (first that exists wins):
  custom-title (user /rename)  ->  ai-title (auto)  ->  last-prompt (truncated)
"""
import json
import os
import re
import sys
import time

def encode_project_dir(cwd):
    # Claude Code replaces '/' and '.' with '-' in the stored folder name.
    enc = "".join("-" if c in "/." else c for c in cwd)
    return os.path.expanduser(f"~/.claude/projects/{enc}")

def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024

def extract_meta(path):
    """Scan a session .jsonl for its best display name. Last record wins."""
    custom = ai = prompt = None
    try:
        with open(path, "r", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # cheap prefilter before json.loads
                if '"custom-title"' in line:
                    try: custom = json.loads(line).get("customTitle") or custom
                    except Exception: pass
                elif '"ai-title"' in line:
                    try: ai = json.loads(line).get("aiTitle") or ai
                    except Exception: pass
                elif '"last-prompt"' in line:
                    try: prompt = json.loads(line).get("lastPrompt") or prompt
                    except Exception: pass
    except Exception:
        pass
    name = custom or ai
    if not name and prompt:
        name = "(" + prompt.strip().replace("\n", " ")[:40] + "…)"
    return name or "—"

def load_summaries(cwd):
    r"""Curated summaries: <cwd>/session-helper/session-info.md, rows `| \`id\` | summary |`."""
    path = os.path.join(cwd, "session-helper", "session-info.md")
    out = {}
    row = re.compile(r"^\s*\|\s*`([0-9a-fA-F-]{36})`\s*\|\s*(.+?)\s*\|\s*$")
    try:
        with open(path, "r", errors="ignore") as f:
            for line in f:
                m = row.match(line)
                if not m:
                    continue
                sid, summ = m.group(1), m.group(2)
                if summ and "TODO" not in summ and "待补充" not in summ:
                    out[sid] = summ
    except Exception:
        pass
    return out

def main():
    cwd = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    proj = encode_project_dir(cwd)
    if not os.path.isdir(proj):
        print(f"No session folder for this project:\n  {proj}")
        return
    files = [os.path.join(proj, f) for f in os.listdir(proj) if f.endswith(".jsonl")]
    if not files:
        print(f"No sessions found in {proj}")
        return

    summaries = load_summaries(cwd)
    current = os.environ.get("CLAUDE_SESSION_ID", "")
    rows = []
    for path in files:
        st = os.stat(path)
        sid = os.path.basename(path)[:-6]  # strip .jsonl
        rows.append({
            "id": sid,
            "mtime": st.st_mtime,
            "size": st.st_size,
            "name": extract_meta(path),
            "summary": summaries.get(sid, ""),
        })
    rows.sort(key=lambda r: r["mtime"], reverse=True)

    print(f"# Sessions for {cwd}  ({len(rows)} total)\n")
    print(f"{'ID (short)':<12}  {'Last active':<17}  {'Size':>8}  Name")
    print(f"{'-'*12}  {'-'*17}  {'-'*8}  {'-'*30}")
    for r in rows:
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(r["mtime"]))
        mark = "▶ " if r["id"] == current else "  "
        print(f"{mark}{r['id'][:8]:<10}  {when:<17}  {human_size(r['size']):>8}  {r['name']}")
        if r["summary"]:
            print(f"              ↳ {r['summary']}")
    if not summaries:
        print("\n(no curated summaries found — add them in session-helper/session-info.md)")
    print("\nResume one with:  claude --resume   (or /resume in a session)")

if __name__ == "__main__":
    main()
