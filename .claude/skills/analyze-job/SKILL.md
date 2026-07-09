---
name: analyze-job
description: Analyze a company/job posting for the candidate's job search, or answer a job-application question. Use when the user pastes a job description or URL, names a company + role, or asks an application question. Produces a concise, evidence-based analysis (company background, prospects, resume fit, industry outlook, career impact, salary-vs-cost-of-living, Glassdoor culture) or a short English application answer.
---

# Analyze Job

Help the candidate evaluate a job/company or answer an application question. **Load `profile.local.md`** (project root, gitignored) for the real profile — level, target metros, comp benchmark, stack, work authorization, and resume story bank. (The public repo ships `profile.example.md` as the template.) Everything below that says "the candidate", "the benchmark", or "target metros" comes from that file.

## Step 0a — Flush the pending buffer (run ONCE at the start of a session, before anything else)

New analyses are staged in `job-analyses/_pending.md` and NOT written to the scoreboard live. So the first time this skill runs in a session, run **`python3 .claude/skills/analyze-job/scoreboard.py flush --date <today>`**. It merges the buffer into the board, re-sorts by 推荐分, re-numbers 排名, skips exact 公司+岗位 duplicates, updates the count/date, and clears the buffer — all deterministically in one atomic write. Relay its one-line output.

Only do this once per session (the first analysis-related turn). Skip if already flushed this session.

## Step 0 — Dedup check (run FIRST for any new posting, before analyzing)

Before spending any research on a new job, check whether it's already on record.
**A posting's identity is `company + role (+ location)`, NOT company alone** — the same company can post several roles, and each is logged separately (its own analysis file + its own scoreboard row).
1. Read `job-scoreboard.md` and list `job-analyses/`. A new posting is a duplicate **only if BOTH the company AND the role/location match** an existing entry (company: case-insensitive, ignore suffixes like "Inc/Security/Health" and 中文/English variants).
2. **If the same company+role is already on record**, do NOT silently re-analyze. Report to the user:
   - the existing scoreboard row (推荐分 + 一句话) and its **状态** (e.g. `未投`, `已投 06-28`, `面试中`).
   - then ask what they want: **(a) skip** — already covered; **(b) refresh** the analysis (company news/comp may have changed); or **(c) update status only** (e.g. mark as applied).
3. **If it's a NEW role at an already-listed company** (same company, different role/location), it is NOT a duplicate — proceed to analyze it as a separate new entry.
4. **If no match at all**, proceed to the normal mode below.

This is the "have I already seen/applied to this?" guard. Always run it first.

## Decide which mode you're in

- **One new posting** — user pasted a job description, a job URL, or "company X, role Y" → **Step 0 first**, then run **Full Analysis**, then **persist it** (see "After every Full Analysis").
- **Multiple new postings at once** — user pasted several jobs / a list → **Step 0 on each**, then run **Batch** (see Mode C) on the ones that aren't duplicates.
- **Status update** — user says "I applied to X" / "mark X as applied" / "X rejected me" / "got an interview at X" → run **Mode D** (update status only, no re-analysis).
- **Application question** — user pasted an English question with no new JD → run **Application Answer** about the *most recent posting discussed in this chat*.

## Global rules

- **Language:** write the analysis and all reasoning in **Chinese (中文)**. Exception: in Mode B, the application answer itself must be in **English** (it will be submitted) — only the surrounding explanation is Chinese.
- **Be concise.** No filler. Prefer bullets and short sentences.
- **Every claim needs a basis.** Cite the source inline (the posting, Glassdoor, Levels.fyi, company site, news). If you couldn't verify something, say so — never invent salary bands, headcount, or review sentiment.
- Use WebSearch/WebFetch for anything not in the posting (company financials, funding, Glassdoor, cost-of-living, comp bands). No MCP required.
- **Never dump `job-scoreboard.md` contents in chat** — no full table, no row diffs, no code blocks of the edits. Confirm in one short line only.
- **Don't imply it's safe to leave while subagents are running.** If `job-analyzer` work is in flight and the user signals they're about to exit/close the session, warn them one line first (e.g. "还有 N 个分析子代理在跑，退出会中断它们——建议等它们返回再退"). (This is a warning only — Claude Code cannot technically block a user from exiting; the workflow is interruption-safe regardless: files write incrementally, `_pending.md` is append-only, the flush is idempotent, so the next session recovers cleanly.)
- **Never hand-edit `job-scoreboard.md` or `job-analyses/_pending.md` with the Edit/Write tools** — a main-agent file edit renders a noisy diff in chat, and manual re-sorting/re-numbering is error-prone. Do ALL board/buffer changes through the deterministic script **`python3 .claude/skills/analyze-job/scoreboard.py`** (ops: `append` / `flush` / `status` / `refresh` / `remove` / `check`). It's exact, atomic, and shows only its one-line stdout — no diff. (This replaced the old `scoreboard-keeper` LLM subagent: mechanical bookkeeping is a job for code, not an LLM — code doesn't hallucinate, doesn't race, and finishes in <1s.) Analysis files (`job-analyses/<Company>.md`) are still written by the `job-analyzer` subagent. So: **LLM does the thinking (job-analyzer); the script does the bookkeeping (scoreboard.py); the main agent orchestrates and talks.**

## Mode A — Full Analysis

### The chat display MUST use this EXACT template (copy the shape, including the emoji headers)
Do all the research first (internally), then render the analysis in EXACTLY this format so it looks identical in every session. This template is mandatory — do not fall back to a plain 7-heading essay.

```
⭐ 推荐分：X/10 —— <一句话是否值得投的结论>

- 履历适配度：X/10 — <一句>
- 薪资性价比：X/10 — <一句>
- 公司/风险：X/10 — <一句>

💰 建议目标年薪
- <已披露区间+来源，或 "未披露*，面试问清 base/bonus/equity"（给估算区间+来源）>
- 目标 base $X–Y，total comp $X–Y（<一句谈判/结构策略>）
- vs 基准：<购买力对比——同城无 COL 变化则工资数字即购买力；异地按 COL+州税折算是否真涨/打平/倒退>（基准 = profile.local.md 的 comp benchmark）

1. 背景 — <2–3 句：做什么、规模/阶段、融资或上市、HQ + 岗位地点>
2. 前景 — 🟢 <绿灯，带来源> 🔴 <红灯，带来源>（把 Glassdoor 近两年 SDE 口碑折进这里）
3. 适配度 — 🟢 <强匹配：候选人 stack（profile.local.md）哪些用得上> 🔴 <差距：栈错位、专长用不上、定级/纸面降级>；work-auth / no-sponsorship 视情况点一句
4. 行业前景 — <近中期赛道走向>
```

Hard rules for the template:
- **薪资性价比 与「vs 基准」必须给具体美元区间**——绝不能只写"打平/降/购买力↓"而无数字。未披露就写 `未披露*` + 估算区间（标来源）。
- 🟢/🔴 用真 emoji；每个子分后面都要跟一句理由。
- 保持紧凑，整块约 ≤20 行；`💰` 里已含 COL/薪资对比，`2. 前景` 里已含 Glassdoor，所以不再单列"薪资 vs 生活成本""工作氛围"两节。
- 若该岗有明显"职业影响/纸面降级/是否偏离 AI 方向"要点，在推荐分那句或 `3. 适配度` 里点出即可。仅当用户要更全时，再追加 `5. 职业影响` 和一行 `Bottom line`。

### Do the analysis via a subagent (so no file diffs hit the chat)
Run **one `job-analyzer` subagent** for the single job. It writes `job-analyses/<Company>.md` itself and returns the full 中文 report **plus** a final scoreboard row line. Then:
1. **Relay the report** to the user (that's the content he wants to read).
2. **Stage the row**: write the returned row line to a temp file and run `python3 .claude/skills/analyze-job/scoreboard.py append --rows-file <tmp>` (it appends to `_pending.md`). Don't touch `job-scoreboard.md` directly.
   - **状态 defaults to 已投** — the candidate applies to a job first, THEN asks for analysis, so assume already applied UNLESS they say they haven't (then `未投`). The `job-analyzer` sets this in the row.
   - The buffer is merged + re-sorted into the board at the next session's Step 0a flush — this decouples analysis from the scoreboard rewrite and keeps concurrent sessions from clobbering the board.
   - **Exception — refreshing an existing row** (Step 0 dedup, user chose "refresh"): run `scoreboard.py refresh --row "<new row>"` (matched by 公司+岗位; preserves 状态). Don't route a refresh through the buffer.

## Mode C — Batch (multiple postings)

When the user pastes more than one job at once:
1. **Fan out**: spawn one `job-analyzer` subagent per job **in parallel** (one Agent call each, in a single message). Give each the company + role + JD text/URL.
2. Each subagent researches, writes its own `job-analyses/<Company>.md`, and returns a scoreboard row.
3. **Stage in one write**: collect all returned rows into one temp file, then run a **single** `python3 .claude/skills/analyze-job/scoreboard.py append --rows-file <tmp>` to append them all to `_pending.md`. (One atomic append, no races.) The actual re-sort happens at the next session's Step 0a flush.
4. Report a short summary in chat: each new company with its 推荐分 and one-liner (from its returned row). Note they're staged and will land in the ranking at next session start.

**状态 in batch:** all newly-analyzed rows default to **已投** (see rule above). If the user says some of the batch aren't applied yet, mark ONLY those as `未投` — ask which ones if it's ambiguous.

## Mode D — Status update (no re-analysis)

When the user reports an application-status change (applied / interviewing / rejected / offer):
1. Run `python3 .claude/skills/analyze-job/scoreboard.py status --company "X" --role "Y" --set "<value>"` (Applied → `已投 MM-DD` today; Interviewing → `面试中`; Rejected/ghosted → `已拒`/`已挂`; Offer → `Offer`). It locates the posting by 公司+岗位 (board or `_pending.md`) and edits only that cell; if the company has several rows and the role is ambiguous, it lists them instead of guessing — refine and re-run. Relay its one-line output.
2. If the keeper reports the company isn't found anywhere, tell the user it hasn't been analyzed — offer to analyze it first.

## Mode B — Application Answer

The submittable answer is **English**, and it must read like a real engineer typed it in a hurry — NOT like a cover-letter generator. The candidate's #1 complaint: answers are too long and too AI-ish. Follow these hard rules.

**Length — short by default.**
- Match the box: if it's a text field, aim **2–4 sentences (~40–90 words)**. Only go longer if the question explicitly asks (e.g. "describe in detail") or gives a big word budget.
- If the form states a word/char limit, obey it exactly.
- One concrete point beats three vague ones. Don't cover everything — pick the single most relevant thing and say it well.

**Voice — plain and human.**
- First person, direct, contractions OK ("I've", "it's"). Say it the way you'd say it out loud to a hiring manager.
- Lead with the substance, not a warm-up. **No throat-clearing openers** ("I'm excited about…", "I'm passionate about…", "What draws me to…").
- Use a real specific from his resume — a number, a system, a concrete problem — instead of adjectives. Show, don't gush.

**Banned AI-tells** (do not use): leverage, spearheaded, passionate, thrilled, excited to, deeply resonate(s), "at the intersection of", "uniquely positioned", robust, seamless(ly), elevate, unlock, world-class, cutting-edge, "I'd love the opportunity to", em-dash-triads, and rows of buzzword adjectives. If a sentence would survive on any company's application, it's too generic — make it specific to THIS role.

**Grounding.** Anchor in the candidate's real experience — use the story bank in `profile.local.md` (and `application-kit.md`). If they genuinely lack something the question probes, say so plainly in one clause rather than inflating.

After the answer, add a **one-line** Chinese note "为什么这样答" — just the framing choice, not a paragraph.

**Use the answer kit.** Before writing, read `application-kit.md`:
- **Fixed questions** (work auth / sponsorship / notice / W2 / expected salary / relocation / why-leaving / referral) → reuse section A directly (salary follows its per-role rule). Don't re-improvise these.
- **Open-ended questions** → pull ONE most-relevant item from section B (story bank) and build on it, so answers stay grounded and consistent. Anything marked `⚠️需确认` — confirm with the candidate before submitting.
- **Save it**: after the candidate approves a tailored per-company answer, append it to that company's `job-analyses/<Company>.md` under a `## 申请回答` heading (question + final answer), so approved answers live with the analysis and can be reused/adapted. (This save is a file edit — route it through the `job-analyzer` subagent, or do it once they confirm; per-company answers are NOT added to `application-kit.md`, which stays reusable-only.)
