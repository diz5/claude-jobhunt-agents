/* ────────────────────────────────────────────────────────────────────────────
 * linkedin_extract.js — read YOUR logged-in LinkedIn job-search results.
 *
 * WHAT IT IS: a one-off, read-only DOM read you run yourself. It does NOT log in,
 * drive your session, or send any automated traffic — it only reads what's already
 * on your screen. This is deliberately NOT authenticated automation (that would risk
 * your account); it's you copying your own results, just structured.
 *
 * HOW TO USE:
 *   1. Open your LinkedIn job search (logged in) in Chrome.
 *   2. Open DevTools: Cmd+Option+J (Mac) → Console tab.
 *   3. Paste this whole file, press Enter. It gently scrolls to load the page's
 *      cards, then copies a JSON array to your clipboard (and prints it).
 *   4. Paste the JSON back to Claude.
 *   5. For more pages: click to the next page, re-run — it MERGES (dedupes by jobId),
 *      so the clipboard grows to cover every page you ran it on.
 *   6. To start fresh: run  delete window.__liJobs  first, then re-run.
 * ──────────────────────────────────────────────────────────────────────────── */
(async () => {
  const SCROLL_STEPS = 12;     // enough for a full ~25-card page
  const SCROLL_PAUSE = 350;    // ms — gentle, human-ish
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const clean = (s) => (s || "").replace(/\s+/g, " ").trim();

  // The results list scrolls inside its own container in most LinkedIn layouts;
  // fall back to the window if we can't find it.
  const container =
    document.querySelector(".jobs-search-results-list") ||
    document.querySelector("div.scaffold-layout__list") ||
    document.querySelector(".jobs-search__results-list")?.parentElement ||
    null;

  // Gentle auto-scroll so lazy-rendered cards on THIS page mount.
  for (let i = 0; i < SCROLL_STEPS; i++) {
    if (container) container.scrollBy(0, container.clientHeight * 0.9);
    else window.scrollBy(0, window.innerHeight * 0.9);
    await sleep(SCROLL_PAUSE);
  }
  if (container) container.scrollTo(0, 0);
  else window.scrollTo(0, 0);
  await sleep(300);

  // Accumulate across pages / re-runs.
  window.__liJobs = window.__liJobs || new Map();

  // Layout-agnostic: every job card has a /jobs/view/<id> link. Dedupe by jobId.
  const links = Array.from(document.querySelectorAll('a[href*="/jobs/view/"]'));
  let added = 0;

  for (const a of links) {
    const m = a.href.match(/\/jobs\/view\/(\d+)/);
    if (!m) continue;
    const jobId = m[1];
    if (window.__liJobs.has(jobId)) continue;

    const card =
      a.closest("li") ||
      a.closest("[data-job-id]") ||
      a.closest(".job-card-container") ||
      a.parentElement;

    // Title: aria-label is the cleanest; else first line of the link text
    // (LinkedIn duplicates the title in a visually-hidden span).
    let title = clean(a.getAttribute("aria-label"));
    if (!title) {
      const t = clean(a.innerText);
      title = t.split("\n")[0] || t;
    }

    const pick = (sels) => {
      for (const s of sels) {
        const el = card && card.querySelector(s);
        if (el && clean(el.innerText)) return clean(el.innerText);
      }
      return "";
    };
    const company = pick([
      ".job-card-container__primary-description",
      ".artdeco-entity-lockup__subtitle",
      ".job-card-container__company-name",
      '[class*="subtitle"]',
    ]);
    const location = pick([
      ".job-card-container__metadata-item",
      ".artdeco-entity-lockup__caption",
      ".job-card-container__metadata-wrapper",
      '[class*="caption"]',
    ]);

    window.__liJobs.set(jobId, {
      jobId,
      title,
      company,
      location,
      viewUrl: `https://www.linkedin.com/jobs/view/${jobId}`,
    });
    added++;
  }

  const out = Array.from(window.__liJobs.values());
  const json = JSON.stringify(out, null, 2);
  try {
    await navigator.clipboard.writeText(json);
    console.log(
      `%c✅ ${out.length} jobs total (+${added} new this run) — JSON copied to clipboard. Paste it back to Claude.`,
      "color:#0a0;font-weight:bold;font-size:13px;"
    );
  } catch (e) {
    console.log(
      `✅ ${out.length} jobs total (+${added} new). Clipboard blocked (click the page once, or copy the JSON below):`
    );
  }
  console.log(json);
  return out.length;
})();
