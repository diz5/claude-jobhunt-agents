---
name: analyze-job
description: Analyze a company/job posting for the candidate's job search, or answer a job-application question. Use when the user pastes a job description or URL, names a company + role, or asks an application question. Produces a concise, evidence-based analysis (company background, prospects, resume fit, industry outlook, career impact, salary-vs-cost-of-living, Glassdoor culture) or a short English application answer.
help: 单岗/批量分析（⭐ 模板），或答申请题
---

# Analyze Job

Help the candidate evaluate a job/company or answer an application question. **Load `profile.local.md`** (project root, gitignored) for the real profile — level, target metros, comp benchmark, stack, work authorization, and resume story bank. (The public repo ships `profile.example.md` as the template.) Everything below that says "the candidate", "the benchmark", or "target metros" comes from that file.

## Step 0a — Flush the pending buffer (run ONCE at the start of a session, before anything else)

New analyses are staged in `job-analyses/_pending.md` and NOT written to the scoreboard live. So the first time this skill runs in a session, run **`python3 .claude/skills/analyze-job/scoreboard.py flush --date <today>`**. It merges the buffer into the board, re-sorts by 推荐分, re-numbers 排名, skips exact 公司+岗位 duplicates, updates the count/date, and clears the buffer — all deterministically in one atomic write. Relay its one-line output.

- **Merge audit log**: every flush appends one line to `.merge-log.md` (gitignored) recording which session merged and when — `时间 · session id · merged/dup/cutoff/total`. The session id is captured automatically from `$CLAUDE_CODE_SESSION_ID`; nothing to pass.

Only do this once per session (the first analysis-related turn). Skip if already flushed this session.

## Step 0 — Dedup check (run FIRST for any new posting, before analyzing)

Before spending any research on a new job, check whether it's already on record.
**A posting's identity is `company + role (+ location)`, NOT company alone** — the same company can post several roles, and each is logged separately (its own analysis file + its own scoreboard row).
1. Read `job-scoreboard.md` and list `job-analyses/`. A new posting is a duplicate **only if BOTH the company AND the role/location match** an existing entry (company: case-insensitive, ignore suffixes like "Inc/Security/Health" and 中文/English variants).
2. **If the same company+role is already on record**, do NOT silently re-analyze. Report to the user:
   - the existing scoreboard row (推荐分 + 一句话) and its **状态** (e.g. `未投`, `已投 06-28`, `面试中`).
   - **被拒冷冻 (reapply freeze):** if that 状态 contains `被拒` / `已挂` / `已拒`, flag it plainly — 这个岗**近期被拒过**(状态里有日期),不建议重投。Reapply cooldowns 一般 ~6 个月(因公司而异);除非用户明确说要重投或冷冻期已过,**不要建议或鼓励重新申请**。同公司的*不同*岗位不受影响(见 #3)。
   - then ask what they want: **(a) skip** — already covered; **(b) refresh** the analysis (company news/comp may have changed); or **(c) update status only** (e.g. mark as applied).
3. **If it's a NEW role at an already-listed company** (same company, different role/location), it is NOT a duplicate — proceed to analyze it as a separate new entry.
4. **If no match at all**, proceed to the normal mode below.

This is the "have I already seen/applied to this?" guard. Always run it first.

## Decide which mode you're in

- **One new posting** — user pasted a job description, a job URL, or "company X, role Y" → **Step 0 first**, then run **Full Analysis**, then **persist it** (see "After every Full Analysis").
- **Multiple new postings at once** — user pasted several jobs / a list → **Step 0 on each**, then run **Batch** (see Mode C) on the ones that aren't duplicates.
- **Status update** — user says "I applied to X" / "mark X as applied" / "X rejected me" / "got an interview at X" → run **Mode D** (update status only, no re-analysis).
- **Application question** — user pasted an English question with no new JD → run **Application Answer** about the *most recent posting discussed in this chat*.
- **Refresh / re-sync** — user says "refresh" / "sync" / "resync" / "刷新" / "重新同步" → run **Mode E** (merge pending, re-read the board from disk, drop stale in-context postings, then only analyze genuinely new jobs from here).
- **Proactive sourcing** — user asks to FIND new jobs rather than bringing one ("找新岗位" / "source new roles" / "search LinkedIn/Indeed for me") → run **Mode F** (spawn `job-sourcer` slices → shortlist → user picks → normal analyze flow).
- **Status report** — user asks how the hunt is going ("how's my job hunting" / "求职进展" / "status") → run **Mode G** (deterministic `status_report.py` snapshot + a few lines of judgment).

## Global rules

- **Language:** write the analysis and all reasoning in **Chinese (中文)**. Exception: in Mode B, the application answer itself must be in **English** (it will be submitted) — only the surrounding explanation is Chinese.
- **Be concise.** No filler. Prefer bullets and short sentences.
- **Every claim needs a basis.** Cite the source inline (the posting, Glassdoor, Levels.fyi, company site, news). If you couldn't verify something, say so — never invent salary bands, headcount, or review sentiment.
- Use WebSearch/WebFetch for anything not in the posting (company financials, funding, Glassdoor, cost-of-living, comp bands). No MCP required.
- **Never dump `job-scoreboard.md` contents in chat** — no full table, no row diffs, no code blocks of the edits. Confirm in one short line only.
- **Don't imply it's safe to leave while subagents are running.** If `job-analyzer` work is in flight and the user signals they're about to exit/close the session, warn them one line first (e.g. "还有 N 个分析子代理在跑，退出会中断它们——建议等它们返回再退"). (This is a warning only — Claude Code cannot technically block a user from exiting; the workflow is interruption-safe regardless: files write incrementally, `_pending.md` is append-only, the flush is idempotent, so the next session recovers cleanly.)
- **推荐分 fit-gated（见 Mode A 模板硬规则）：** 推荐分锚定履历适配度（主导项=技术栈匹配，AI 契合为同级正向项）；履历适配度 < 6 时推荐分=履历适配度，薪资/公司不能救上榜；≥6 时薪资(次)+公司(再次)最多 ~±1 微调。这是为什么高薪但错栈的岗位（如全栈 TS / 强制 AWS）会正确落到 <6。
- **推荐分 < 6 = 直接跳过，不入榜（硬门槛）。** 低于候选人门槛的岗位不进 `job-scoreboard.md`。`scoreboard.py` 的 `append`/`flush` 会自动丢弃 <6 的行（你无需手动过滤，但也别指望能把 <6 塞进榜单）。Mode A/C 里若分析结果 <6：照常把 ⭐ 报告呈现给用户（让他看到为什么低），但**不要** stage 该行——用一句话说明"X 分 < 6，未入榜"。历史遗留的 <6 行用 `scoreboard.py prune` 清理。
- **Never touch `job-scoreboard.md` or `job-analyses/_pending.md` with the Edit/Write tools — not even one line.** A main-agent file edit renders a noisy `Update(...)` diff in chat (which the candidate does NOT want to see) and bypasses the min-score gate, dedup, and re-numbering. Do ALL board/buffer changes through the deterministic script **`python3 .claude/skills/analyze-job/scoreboard.py`** (ops: `append` / `flush` / `status` / `refresh` / `remove` / `prune` / `state` / `check`) — it prints only one line of stdout, no diff.
  - **No placeholder/"分析中"/PENDING rows in the buffer, ever.** Each job yields **exactly one complete, scored row**, appended via `scoreboard.py append` **only after** its 推荐分 is known. A row without a numeric 推荐分 is never staged. Show in-progress status in chat text only ("正在分析 Microsoft MAI…"), never by writing a partial row to `_pending.md`. It's exact, atomic, and shows only its one-line stdout — no diff. (This replaced the old `scoreboard-keeper` LLM subagent: mechanical bookkeeping is a job for code, not an LLM — code doesn't hallucinate, doesn't race, and finishes in <1s.) Analysis files (`job-analyses/<Company>.md`) are still written by the `job-analyzer` subagent. So: **LLM does the thinking (job-analyzer); the script does the bookkeeping (scoreboard.py); the main agent orchestrates and talks.**

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
- **推荐分是 FIT-GATED，不是三个子分的平均。** 推荐分锚定在 **履历适配度** 上；薪资和公司只能微调，**绝不能把差 fit 的岗位救上榜**。这是求职——一个薪资很高但栈错位（候选人过不了技术关）的岗位价值≈0，不是 7 分。
  - 履历适配度先算，**主导项是技术栈匹配**：候选人生产环境没有的栈（见 `profile.local.md` 的 🔴/gaps——如 TS/全栈、.NET、mobile、Go/Rust、profile 标零经验或硬要求的云）**把履历适配度压低**，叙事/领域/文化/SRE 流程的重合**不能**把它拉回门槛之上。
  - **栈错位分两档，按 JD 原文措辞判定**（Proofpoint 判例，2026-08）：**硬语言关** = 该语言是岗位主栈/代码库主体，或 JD 写 "deep/strong proficiency"、"8+ yrs <lang>"、岗位名就是该栈（如 Haskell 主栈、"strong Go proficiency"、Node/React 全栈岗）→ 照上一条压低适配度。**软语言项** = JD 只要 "working knowledge"/次要工具级、或明示 AI-assisted 编码即可，且岗位真正的筛选主体是别的能力（agent 架构、领域专长等）→ **不按栈错位 gate**，最多 −0.5~1，适配度主导项改为该岗真实的筛选主体。拿不准措辞档位时从严按硬档算。AI/agentic 契合（日常 AI 编码工具、生产级 applied-LLM、agent 工具——profile 标的顶级 🟢）是**同级正向项，命中时抬高履历适配度**；缺席不扣分。
  - **履历适配度 < 6 → 推荐分 = 履历适配度，薪资/公司不加分。**（实例：一个高薪、口碑好、但栈错位的 SRE 岗——全栈 TypeScript + 强制 AWS——履历适配度 5.5 → 推荐分 **5.5**，不入榜，哪怕薪资远超基准、Glassdoor 分很高。）
  - **履历适配度 ≥ 6 → 推荐分 = 履历适配度为锚，薪资+公司合计最多 ~±1 微调。** Fit 主导，薪资次要，公司再次要。
  - **公司拆成两个相反的力**：公司**风险**（裁员/衰退/外资母体美国团队自治度）是小幅**下调**；公司**档次/热度**（BigTech、热门且资金充足的 AI——见 profile 的目标）是小幅**上抬**。别把两者混成一个笼统分。
- **薪资性价比 与「vs 基准」必须给具体美元区间**——绝不能只写"打平/降/购买力↓"而无数字。未披露就写 `未披露*` + 估算区间（标来源）。
- 🟢/🔴 用真 emoji；每个子分后面都要跟一句理由。
- 保持紧凑，整块约 ≤20 行；`💰` 里已含 COL/薪资对比，`2. 前景` 里已含 Glassdoor，所以不再单列"薪资 vs 生活成本""工作氛围"两节。
- 若该岗有明显"职业影响/纸面降级/是否偏离 AI 方向"要点，在推荐分那句或 `3. 适配度` 里点出即可。仅当用户要更全时，再追加 `5. 职业影响` 和一行 `Bottom line`。

### Do the analysis via a subagent (so no file diffs hit the chat)
Run **one `job-analyzer` subagent** for the single job. It writes `job-analyses/<Company>.md` itself and returns the full 中文 report **plus** a final scoreboard row line. Then:
1. **Relay the report** to the user (that's the content he wants to read).
2. **Stage the row — unless 推荐分 < 6.** If the score is below 6, do NOT stage it (the job is below the candidate's bar); just relay the report and add one line: "X 分 < 6，未入榜". Otherwise write the returned row line to a temp file and run `python3 .claude/skills/analyze-job/scoreboard.py append --rows-file <tmp>` (it appends to `_pending.md`, and it will itself drop the row if <6 as a safety net). Don't touch `job-scoreboard.md` directly.
   - **状态 defaults to 已投** — the candidate applies to a job first, THEN asks for analysis, so assume already applied UNLESS they say they haven't (then `未投`). The `job-analyzer` sets this in the row.
   - The buffer is merged + re-sorted into the board at the next session's Step 0a flush — this decouples analysis from the scoreboard rewrite and keeps concurrent sessions from clobbering the board.
   - **Exception — refreshing an existing row** (Step 0 dedup, user chose "refresh"): run `scoreboard.py refresh --row "<new row>"` (matched by 公司+岗位; preserves 状态). Don't route a refresh through the buffer.

## Mode C — Batch (multiple postings)

When the user pastes more than one job at once, follow this **strict display protocol** — it must look the SAME in every session (past sessions each improvised their own tables/languages/verdict styles; that inconsistency is exactly what this protocol kills):

1. **Fan out**: spawn one `job-analyzer` subagent per job **in parallel** (one Agent call each, in a single message). Then post ONE line: `本批 N 个：A、B、C…（并行分析中）`.
2. **Progress counter ONLY while waiting.** As each subagent returns, output a single line — `进度 k/N ✅ <公司> <推荐分>` — and NOTHING else. **Do NOT render any template, table, verdict, or commentary until ALL N are back.** Partial detail mid-batch is forbidden.
3. **When all N are back — the ENTIRE display is ONE deterministic call**: run
   `python3 .claude/skills/analyze-job/batch_summary.py --full <本批各分析文件名或公司名>`
   and **relay its output VERBATIM**. It prints, in order: every ≥6 job's full ⭐ analysis (highest score first, straight from the analysis files — identical in every session, always 中文), one `❌` line per <6 job (no details for those), and the standardized batch chart (每岗 适配/薪资/风险 子分 + 披露区间→争取目标). **You render NOTHING yourself in this phase** — no templates, no hand-drawn tables (they garble in the terminal), no rephrasing. After the script output you may append **only**: one `❌` line per agency/hidden-employer skip the script can't know about, and — optionally — **ONE short single-clause line** naming the top pick (e.g. `🎯 本批 project44 栈最全，优先`). That is the hard limit. **NEVER write a multi-point 判断/总结/三点 block.** Two reasons: (a) the per-job 履历/薪资/风险 judgment is already in the `--full` output above, so re-synthesizing it is pure redundancy; (b) long multi-clause Chinese paragraphs streamed to the terminal **corrupt** — words drop, lines merge — which is the exact garble this protocol exists to prevent. Short single lines render fine (the progress counters prove it); long freehand CJK does not. If you feel the urge to summarize, resist it — the script already did.
4. **Stage in one write**: collect the ≥6 rows into one temp file → a single `python3 .claude/skills/analyze-job/scoreboard.py append --rows-file <tmp>` (it auto-drops <6 as a safety net). Re-sort happens at next session's Step 0a flush.
5. **Language: 全程中文**（专有名词/引文除外）。If you catch yourself writing English prose in this mode, stop and rewrite in Chinese — English wrap-ups are a known failure mode.
6. **Stall recovery**: if the turn gets interrupted after the analyzers finished (recap shown, no batch output, user nudges you), do NOT re-analyze anything — the analysis files on disk are the source of truth. Just run steps 3–4 directly (`batch_summary.py --full …`, then stage). Idempotent and safe.

**状态 in batch:** all newly-analyzed rows default to **已投** (see rule above); Mode F-sourced roles default 未投. If the user says some of the batch aren't applied yet, mark ONLY those as `未投` — ask which ones if it's ambiguous.

## Mode D — Status update (no re-analysis)

When the user reports an application-status change (applied / interviewing / rejected / offer):
1. Run `python3 .claude/skills/analyze-job/scoreboard.py status --company "X" --role "Y" --set "<value>"` (Applied → `已投`; Interviewing → `面试中`; Rejected/ghosted → `已拒`/`已挂`; Offer → `Offer`). **The script auto-stamps today's date** on every status value — don't add dates yourself. If the user mentions HOW the contact happened, pass `--channel cold|referral|recruiter|inbound` (记渠道 — the most predictive variable for outcome analytics); omit when unknown, never guess. It locates the posting by 公司+岗位 (board or `_pending.md`) and edits only that cell; if the company has several rows and the role is ambiguous, it lists them instead of guessing — refine and re-run. Relay its one-line output.
2. If the keeper reports the company isn't found anywhere, tell the user it hasn't been analyzed — offer to analyze it first.

## Mode B — Application Answer

Delegate the drafting to the **`application-answerer`** subagent — it reads the job analysis for background, grounds the answer in `profile.local.md` + `application-kit.md`, and writes in the house style (short, human, one concrete resume specific, no AI-tells). Running it as a subagent keeps the multi-file reading and any save-edit out of the chat.

**Flow:**
1. **Spawn `application-answerer`** with the **company + role + the exact question text** (include any word/char limit, and the JD/URL if handy). One subagent per company; it can handle several questions for that company in one call. If the user just pasted a bare question, infer the company from the *most recent posting discussed in this chat* and pass it.
2. **Relay its answer(s) verbatim** — the English answer (submittable) + the one-line 为什么这样答.
3. **Iterate in the main chat** for tweaks ("shorter", "swap the story") — adjust directly or re-spawn; don't over-round-trip.
4. **Save on approval**: once the candidate approves a tailored answer, re-invoke `application-answerer` telling it the answer is **APPROVED** — it appends `Q/A` to that company's `job-analyses/<Company>.md` under `## 申请回答` (off-chat, no diff). Per-company answers do NOT go into `application-kit.md` (reusable-only); a genuinely reusable new fixed line does.

**Non-negotiables** (the agent enforces these; hold it to them when relaying): 2–4 sentences / ~40–90 words by default (one word/line for gating questions like salary-in-range, W2, sponsorship); first person + contractions; lead with substance, no throat-clearing; **one real resume specific** (a number/system) instead of adjectives; obey any stated limit; salary follows the kit's per-role rule (never a raw guessed number); never negative about the current employer; flag `⚠️需确认` items. If a sentence would survive on any company's application, it's too generic.

## Mode E — Refresh / Re-sync (for a long-running session)

**Why this exists:** a session that has been open a while holds a *stale* mental copy of the board and of the jobs pasted earlier this chat. Meanwhile another session may have flushed new rows to `job-scoreboard.md`, or the buffer may have merged. Without a reset, this session keeps reasoning off its in-context memory (e.g. re-summarizing yesterday's posting) instead of the real current board. "Refresh" forces a clean re-sync.

When the user says **refresh / sync / resync / 刷新 / 重新同步**, do exactly this:

1. **Merge + re-read from disk.** Run `python3 .claude/skills/analyze-job/scoreboard.py flush --date <today>` (merges any staged rows; idempotent — safe even if another session already flushed). Then run `python3 .claude/skills/analyze-job/scoreboard.py state` to read the authoritative marker (`last_updated`, `last_op`, `rows`, `pending_rows`). Then **re-Read `job-scoreboard.md` fresh** — do not trust the copy in your context.
2. **Reset the working set. This is the whole point:** from this moment, the freshly-read board is the *single source of truth*. **Discard your in-context memory of any job postings pasted earlier in this chat** — anything already on the board (or already merged) is DONE; do not re-analyze, re-summarize, or reason about it from memory. If the user later refers to one, re-Read its `job-analyses/<Company>.md` rather than recalling it.
3. **Continue with new jobs only.** After the refresh, treat only *genuinely new* postings the user provides (not already on the board per Step 0 dedup) as work to analyze.
4. **Confirm in one line**, e.g. `🔄 已重新同步：榜单 N 行（更新于 <last_updated>），暂存区已并入。从现在起只分析新岗位。` No board dump.

Track `last_updated` from the `state` call in your context; if you run `state` again later and it changed, another session moved the board — re-Read it before reporting board facts.

## Mode G — Status report (求职状态)

When the user asks how the job hunt is going:
1. **Freshness first** — if this session hasn't flushed yet, run Step 0a's flush so staged rows are included.
2. Run **`python3 .claude/skills/analyze-job/status_report.py`** (options: `--top N`, `--min-score S`). It deterministically prints: totals + deltas vs its own previous run, the interview/offer list, score bands, top unapplied targets, and last-7-days applications. **Never hand-count the board with ad-hoc parsing, and never dump the table in chat** — hand-rolled parsers have misread rank columns as scores before.
3. Relay the script's output, then add AT MOST a few lines of judgment: what changed, the biggest risk, and 1–3 recommended actions grounded in `profile.local.md` priorities (interview prep > high-fit unapplied targets > referrals/sourcing).

## Mode F — Proactive sourcing (find new postings, don't wait for them)

When the user asks you to FIND jobs (instead of bringing one), delegate the hunting to
**`job-sourcer`** subagents:

1. **Build 2–4 search slices** from `profile.local.md` — cross its 🟢 strong-fit domains with
   its target metros/remote (e.g. "<domain A> × <metro 1>", "<domain B> × remote-US"). If the
   user named a specific direction ("only security roles", "only NYC"), use their slices instead.
2. **Fan out**: spawn one `job-sourcer` per slice **in parallel** (one Agent call each, single
   message). Each reads the profile + board itself, sweeps ATS/public job sources, and returns
   a ranked shortlist with direct apply URLs (`JOB_SOURCED:` sentinel lines).
3. **Merge + dedupe** across slices (same company+role found by two slices = one entry) and
   against the board (Step 0 identity rule). Present ONE compact shortlist: company, role,
   location, posted date, apply URL, 契合度一句话. This is new-postings output, not a board dump.
4. **User picks → normal analyze flow** (Mode A/C). **Status override:** sourced roles are by
   definition NOT yet applied — their rows get `未投`, overriding the usual 已投 default.
5. **Scope honesty:** the sourcer sweeps ATS boards (Greenhouse/Lever/Ashby/Workday) and
   fetch-friendly job sites. LinkedIn/Indeed are login-walled to anonymous automation — if the
   user asks for those specifically, say in one line that they should browse those themselves
   and paste links into the normal flow; don't pretend to search them.
