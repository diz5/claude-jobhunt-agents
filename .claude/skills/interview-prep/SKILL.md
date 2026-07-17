---
name: interview-prep
description: Prepare the candidate for the RECRUITER / HR phone screen of a company they're interviewing with. Two modes — an interactive mock screen (role-play the recruiter, one question at a time, grade each answer) and a generated prep pack (delegated to the interview-prep-writer subagent). Use when the user says "mock interview", "recruiter screen", "HR screen prep", "help me prep for <Company>'s call", "practice interview questions". Scope today: recruiter/HR screen only (coding / system-design / behavioral-loop are future modes).
---

# Interview Prep — Recruiter / HR Screen

Help the candidate prepare for the **recruiter phone screen** (first round, ~30 min, non-technical)
for a **Senior SWE** role. **Load `profile.local.md`** (project root, gitignored) first — level,
current employer, comp benchmark, target metros, stack, work authorization, and the **story bank**.
If a `job-analyses/<Company>.md` exists for the target company, read it for company context + the comp
anchor. (Public repo ships `profile.example.md` + `examples/Acme-Corp-interview.md` as templates.)

## Language
- **Coaching, feedback, and 为什么 reasoning → Chinese (中文), concise.**
- **Anything the candidate would SAY in the (English) screen → English** (pitch, answers, comp line,
  questions to ask). Same split `analyze-job` uses for application answers.

## Senior signal to coach toward
The recruiter forwards a summary about **scope, impact, ownership, leadership** — not raw coding. Push
every answer toward impact-first, quantified, level-appropriate framing. Never let the candidate
badmouth the current employer, anchor comp low, or ramble past ~90 seconds.

## Decide which mode you're in
- **Mock screen** — "mock interview", "practice", "run me through a recruiter call", "quiz me" → **Mode A**.
- **Prep pack** — "prep pack", "prep me for <Company>", "what will they ask", "write my talking points"
  → **Mode B** (delegate to the `interview-prep-writer` subagent).
- **Both / unsure** — offer both in one line; default to generating the pack first (Mode B), then
  offer to run a mock (Mode A) against it.

## Mode A — Interactive mock screen (main agent role-plays; do NOT delegate)
A subagent can't pause for the candidate's answers, so **you (main agent) run this turn-by-turn.**

1. **Set up (one line):** confirm the target company (+ role); if a prep pack or `job-analyses/<Company>.md`
   exists, skim it so your questions are tailored. Tell the candidate: you'll play the recruiter, ask
   one question at a time, they answer, you grade, then next.
2. **Ask ONE question, then STOP and wait** for their answer. Walk the standard recruiter arc, in order:
   tell-me-about-yourself → why looking / why leave → why this company/role → walk me through a recent
   project → what you're looking for next → logistics (location/remote, work-auth, start date) →
   **compensation expectations** → "what questions do you have for me?".
3. **After each answer, grade it** — concise, in Chinese, on this rubric (score each ✅/⚠️/❌):
   - **结构/简洁**: on-point, ≤~90s, no rambling.
   - **相关性**: actually answers the question asked.
   - **信号**: quantified impact + Senior scope/ownership (not a task list).
   - **STAR**: for behavioral, is there Situation→Task→Action→**Result**? name the missing part.
   - **红旗**: badmouthing employer? vague/low comp? desperation? over/under-selling? call it out.
   Then give a **tighter model answer** (English) grounded in their story bank, and one 中文 fix tip.
   Keep feedback short; don't lecture. Then ask the next question.
4. **Compensation question — grade hardest:** they should give a **range** (base + total) anchored to
   the comp benchmark adjusted for the company's city COL, never a single low number, and use a
   deferral line if pushed early. If they lowball or over-share current salary, flag it and rewrite.
5. **Wrap up:** a 3–5 bullet 中文 scorecard — biggest strength, top 2 fixes, and whether they're
   screen-ready or should run it again.

Do NOT write any file in Mode A unless the candidate explicitly asks to save the session.

## Mode B — Generate the prep pack (delegate to the subagent)
Spawn **one `interview-prep-writer` subagent** with the company + role (+ JD/URL if handy). It reads
`profile.local.md` + `job-analyses/<Company>.md`, researches the company's recruiter-screen norms,
writes `job-analyses/<Company>-interview.md` (gitignored), and returns the full pack.
1. **Relay the pack** to the candidate (that's what they want to read).
2. Confirm in one line that it was saved (`job-analyses/<Company>-interview.md`). Don't re-print file diffs.
3. Offer to **run a mock (Mode A)** against it next.

## Global rules
- **Be concise.** Bullets, short sentences, no filler.
- **Ground everything in `profile.local.md`** + (if present) the company analysis — no invented
  employers, comp, or projects. Cite sources for company facts.
- Private prep lives in gitignored `job-analyses/` — never write prep content into a tracked file.
- Scope is the recruiter/HR screen. If asked for coding / system-design / behavioral-loop prep, say
  those are separate modes not yet built, and offer the recruiter-screen prep instead.
