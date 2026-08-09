---
description: Referral-track pass — one guest search per referral company (past week), analyze new fits, show the latest/best role per company
---

Run the REFERRAL track of the `linkedin-sourcing` skill (fully separate from the regular pass).

First Read `.claude/skills/linkedin-sourcing/SKILL.md` fresh from disk, then follow its referral
section exactly: for each company in `referral-companies.md`, run ONE guest search with
`&f_C=<company_id>` (past week, `f_TPR=r604800`), ingest into the referral ledger
(`--db .linkedin-referral.db`), triage, analyze new fits, save ≥6 analyses with post date,
regenerate `referral-queue.md`, and show the latest / best-fit referral role per company so the
candidate can decide whether to ask for a referral.

$ARGUMENTS
