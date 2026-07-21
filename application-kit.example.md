# Application Kit — EXAMPLE (copy to `application-kit.md` and fill in your own)

`application-kit.md` is gitignored. Copy this file to `application-kit.md` and replace the
placeholders with your real answers. The `analyze-job` skill (Mode B) and the
`application-answerer` agent read it at runtime.

Two parts: **A. Fixed answers** repeat on nearly every application — reuse them verbatim.
**B. Story bank** is the raw material for open-ended answers — pick the single most relevant
story and build on it, so answers stay grounded and consistent.

Style: short, spoken, no AI-tells. Mark anything you must confirm per role with `⚠️需确认`.

---

## Voice rules — the "read-aloud test"

Open-ended answers should sound like something you'd **say out loud** on a phone screen — not a résumé line or an echo of the job post. Read each answer aloud; if it doesn't sound like you talking, rewrite it.

1. **One idea per sentence.** Short declaratives. Don't cram several clauses together with dashes or colons.
2. **Don't parrot the JD's product/marketing wording.** Describe the work in your own plain words ("I built integrations with X and Y"), not the posting's phrasing.
3. **Round numbers the way you'd say them** — "about a third", "over 90% in production" — not stiff decimals. Keep the credibility hedges a real engineer uses ("in production", "end to end").
4. **One genuine personal reaction is allowed** — "That's the kind of work I really enjoy." — plain and sincere, never "I'm passionate about…".
5. **Cut meta-commentary aimed at scoring points.** Delete lines that argue your case to the reader ("which sounds like what you weight most", "so it isn't just a buzzword"). If your stack doesn't match, say so plainly in one clause and move on.

**Before → after (illustrative):**
- ❌ "The core of this role — scaling the platform across partners through backend integration — is close to what I've done, so it isn't just a buzzword to me, and the JD reads like that's what you weight most."
- ✅ "This is pretty close to what I did before. I owned backend integrations with a bunch of external partners, end to end. That's the kind of work I really enjoy. My background is mostly Java and Kafka rather than the exact stack here, but the integration work maps directly."

---

## A. Fixed answers (reuse directly)

**Work authorization / sponsorship**
> `<e.g. "I'm authorized to work for any US employer and don't need sponsorship now or in the future.">`

**Need visa sponsorship?** → `<Yes / No>`

**Notice period** → `<e.g. "2 weeks.">`

**Full-time W2 employee?** → `<Yes / No>`

**Expected salary — not a fixed number; compute per role:**
- Disclosed range → quote the **upper-middle**, never the floor. Undisclosed → target by metro,
  adjusted for that city's cost-of-living + state tax against your comp benchmark (`profile.local.md`).
- Template: `My base target is $<X>, flexible on the total package (base, bonus, equity).`
- Gating "are you in range $A–$B?" → one word: `Yes.` / `No.`

**Relocation / location** `⚠️需确认 per role`
> `<your target cities / remote preference; answer honestly to the role's location>`

**Why are you leaving / looking to move?** `⚠️需确认`
> `<forward-looking: what you want next and why THIS role fits — never negative about the current employer>`

**Referral / how did you hear about us?** → `<honest: LinkedIn / company site / recruiter>`

---

## B. Story bank (material for open-ended answers)

Each story carries a **real, measurable result**. When answering, pick the ONE most relevant and
build on it — don't list them all.

**1. `<project title — domain>`**
- `<the concrete problem, the tech you used, and a measurable outcome, e.g. "cut production incidents ~95%">`
- Good for: `<question types this fits — e.g. reliability, distributed systems, hardest problem>`

**2. `<project title>`**
- `<problem → tech → measurable result>`
- Good for: `<AI/LLM in production, document workflows, "something you shipped with AI">`

**3. `<project title>`**
- `<problem → tech → measurable result>`
- Good for: `<security / regulated / compliance / 0-to-1>`

**Baseline positioning:** `<years of experience; primary stack; a differentiator or two>`.
