# Project instructions — claude-jobhunt-agents

Hard floor rules for EVERY session in this workspace. They apply before and above any skill,
and they exist because long-running sessions have repeatedly drifted on exactly these points.

1. **Re-read the playbook before analyzing.** Before the FIRST job analysis of this session,
   Read `.claude/skills/analyze-job/SKILL.md` from disk — it changes often, and the copy in a
   resumed session's context is stale. Stale playbooks are the #1 cause of protocol violations.
2. **Job-analysis output is Chinese (中文).** Analyses, batch reports, verdicts, status
   summaries — all 中文. English only inside application-answer text (submittable) and quoted
   material. An English wrap-up is a bug: stop and rewrite.
3. **Never touch `job-scoreboard.md` or `job-analyses/_pending.md` with Edit/Write tools.**
   Every board/buffer mutation goes through `python3 .claude/skills/analyze-job/scoreboard.py`.
   No placeholder/PENDING rows, ever.
4. **Batch analyses follow SKILL.md Mode C exactly**: progress-counter lines only while
   analyzers run; when all are back, one `batch_summary.py --full` call relayed verbatim.
   Never improvise tables, per-job commentary, or your own summary format. **After the script
   output, write AT MOST one short single-clause line (the top pick). NEVER a multi-point
   判断/总结 paragraph** — long CJK prose corrupts on the terminal (words drop, lines merge),
   and it just repeats what the script already printed.
5. **Personal data never enters git.** `publish_guard.py` + `.gitignore` enforce the split;
   anything named `*.local.md`, résumés, the board, and `job-analyses/` stay local. When in
   doubt, don't commit.
