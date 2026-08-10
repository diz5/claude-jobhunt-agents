---
description: Daily LinkedIn sourcing pass — scan all metros (past 24h), dedup, analyze new roles, present the >6 list with apply links
help: 每日搜岗：扫全 metro 过去 24h → 去重 → 分析 → >6 清单 + apply 链接
---

Run the daily job search — the REGULAR metro track of the `linkedin-sourcing` skill.

First Read `.claude/skills/linkedin-sourcing/SKILL.md` fresh from disk (it changes often), then
follow its pass exactly: guest-search every metro (past 24h, `start=0` and `start=10`), ingest
into the `seen.py` ledger with `--exclude-referral`, triage the todo queue, analyze survivors
with `job-analyzer` (Chinese ⭐ template; confirm scope before large fan-outs), and present every
role scoring >6 with its analysis and apply link — one line each for the rest.

$ARGUMENTS
