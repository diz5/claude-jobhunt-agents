#!/usr/bin/env python3
"""Deterministic 'seen jobs' ledger for the LinkedIn sourcing pass.

Sibling to `scoreboard.py` / `apply.py`: the LLM does the *judgment* (triage,
scoring, extracting the apply URL from a JD); this script does the *mechanics* —
remembering every LinkedIn posting you've already looked at (keyed by the numeric
LinkedIn jobId) so a daily multi-metro re-run never re-triages the same junk, and
so you can query "what did I see in NYC scoring >6 that I haven't applied to."

Why a jobId ledger on top of job-scoreboard.md:
  - The board dedups by company+role and only records postings that reached
    analysis. Postings you triaged OUT (recruiters / anonymized / poor-fit) are
    NOT on the board, so without this ledger they reappear every single day.
  - LinkedIn re-posts a role under a NEW jobId; company+role dedup still catches
    that at the board level, this ledger catches the exact-same-posting case.

Storage: a single gitignored SQLite file at <root>/.linkedin-seen.db (personal
data — never committed). SQLite is Python stdlib, so nothing to install.

Status vocabulary (the `status` column):
  seen         ingested from the snippet, not yet triaged/analyzed  (== the to-do queue)
  triaged_out  dropped in triage (recruiter / anonymized / dup / clear poor-fit)
  analyzed     scored + boarded (score is set)
  applied      you applied
  skipped      you chose to skip a >6 role

Ops:
  ingest  --metro M [-i FILE|-] [--date D]     upsert the snippet's JSON array; new jobIds -> 'seen'
  todo    [--metro M] [--json]                 rows still 'seen' (need triage/analysis)
  mark    --job-id ID --status S [--score N] [--apply-type T] [--apply-url U] [--note ...] [--date D]
  filter  [--metro M] [--status S] [--min-score N] [--json]   query (e.g. suggested list)
  stats                                        counts by status and by metro
  list    [--json]                             dump the whole ledger
"""
import argparse
import datetime
import json
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.abspath(os.path.join(__file__, "..", "..", "..")))
DEFAULT_DB = os.path.join(ROOT, ".linkedin-seen.db")
DEFAULT_REFERRAL = os.path.join(ROOT, "referral-companies.md")

STATUSES = ["seen", "triaged_out", "analyzed", "applied", "skipped"]
APPLY_TYPES = ["easy_apply", "offsite", "unknown"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  job_id     TEXT PRIMARY KEY,
  company    TEXT NOT NULL DEFAULT '',
  title      TEXT NOT NULL DEFAULT '',
  card_loc   TEXT NOT NULL DEFAULT '',   -- location text shown on the card
  metros     TEXT NOT NULL DEFAULT '',   -- comma-set of searches that surfaced it (nyc,remote,...)
  view_url   TEXT NOT NULL DEFAULT '',   -- LinkedIn job page
  apply_type TEXT NOT NULL DEFAULT '',   -- easy_apply | offsite | unknown
  apply_url  TEXT NOT NULL DEFAULT '',   -- external ATS URL if extracted, else ''
  score      REAL,                        -- NULL until analyzed
  status     TEXT NOT NULL DEFAULT 'seen',
  posted     TEXT NOT NULL DEFAULT '',   -- posting date (derived from the card's "N hours/days ago")
  referral   INTEGER NOT NULL DEFAULT 0, -- 1 if company is on referral-companies.md
  first_seen TEXT NOT NULL DEFAULT '',
  last_seen  TEXT NOT NULL DEFAULT '',
  note       TEXT NOT NULL DEFAULT ''
);
"""


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def today(args=None):
    if args is not None and getattr(args, "date", None):
        return args.date
    return datetime.date.today().isoformat()


def connect(path):
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL;")
    con.executescript(SCHEMA)
    _migrate(con)
    return con


def _migrate(con):
    """Add columns missing from an older DB (SQLite has no ADD COLUMN IF NOT EXISTS)."""
    have = {r[1] for r in con.execute("PRAGMA table_info(jobs)")}
    for col, ddl in (("posted", "posted TEXT NOT NULL DEFAULT ''"),
                     ("referral", "referral INTEGER NOT NULL DEFAULT 0")):
        if col not in have:
            con.execute(f"ALTER TABLE jobs ADD COLUMN {ddl}")
    con.commit()


def referral_names(path):
    """Company names from referral-companies.md — one per line; '#' comments and blanks skipped.
    A line may be 'Name | linkedin_company_id | note'; only the part before the first '|' is the name."""
    if not path or not os.path.exists(path):
        return []
    out = []
    for line in open(path, encoding="utf-8"):
        t = line.strip()
        if t and not t.startswith("#"):
            out.append(t.split("|")[0].strip())
    return [n for n in out if n]


def is_referral(company, names):
    """True if the ledger company matches a referral name as a whole word (so 'Apple' != 'Applied ...')."""
    c = (company or "").lower()
    return any(re.search(r"\b" + re.escape(n.lower()) + r"\b", c) for n in names if n)


def merge_metros(existing, new):
    s = {m for m in (existing or "").split(",") if m}
    if new:
        s.add(new)
    return ",".join(sorted(s))


def best_url(row):
    """The link to hand the user: the external ATS URL if we extracted one, else the LinkedIn page."""
    return row["apply_url"] or row["view_url"]


def _load_input(path):
    if path in (None, "-"):
        if sys.stdin.isatty():
            die("no input — pipe the linkedin_extract.js JSON array in (`... | seen.py ingest`) "
                "or pass -i FILE")
        text = sys.stdin.read()
    else:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    if not text.strip():
        die("no input — pipe the linkedin_extract.js JSON array in, or pass -i FILE")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        die(f"input is not valid JSON: {e}")


def _rows_to_dicts(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


# ---------- ops ----------

def op_ingest(args):
    data = _load_input(args.input)
    if not isinstance(data, list):
        die("expected a JSON array from linkedin_extract.js (got %s)" % type(data).__name__)
    con = connect(args.db)
    day = today(args)
    names = referral_names(args.referral_companies or DEFAULT_REFERRAL)
    new = seen = bad = excl = 0
    for r in data:
        if not isinstance(r, dict):
            bad += 1
            continue
        jid = str(r.get("jobId") or "").strip()
        if not jid:
            bad += 1
            continue
        company = (r.get("company") or "").strip()
        title = (r.get("title") or "").strip()
        loc = (r.get("location") or "").strip()
        view = (r.get("viewUrl") or f"https://www.linkedin.com/jobs/view/{jid}").strip()
        posted = (r.get("posted") or "").strip()      # absolute date the caller derived from the card age
        ref = 1 if is_referral(company, names) else 0
        if args.exclude_referral and ref:
            excl += 1                                 # regular flow: leave referral companies to the referral track
            continue
        cur = con.execute("SELECT metros FROM jobs WHERE job_id=?", (jid,)).fetchone()
        if cur is None:
            con.execute(
                "INSERT INTO jobs (job_id, company, title, card_loc, metros, view_url, posted, "
                "referral, status, first_seen, last_seen) VALUES (?,?,?,?,?,?,?, ?, 'seen', ?, ?)",
                (jid, company, title, loc, args.metro or "", view, posted, ref, day, day))
            new += 1
        else:
            con.execute(
                "UPDATE jobs SET metros=?, last_seen=?, referral=?, "
                "company  = CASE WHEN company=''  THEN ? ELSE company  END, "
                "title    = CASE WHEN title=''    THEN ? ELSE title    END, "
                "card_loc = CASE WHEN card_loc='' THEN ? ELSE card_loc END, "
                "view_url = CASE WHEN view_url='' THEN ? ELSE view_url END, "
                "posted   = CASE WHEN posted=''   THEN ? ELSE posted   END "
                "WHERE job_id=?",
                (merge_metros(cur[0], args.metro), day, ref, company, title, loc, view, posted, jid))
            seen += 1
    con.commit()
    msg = f"metro={args.metro or '-'}: {new + seen} card(s) — {new} new, {seen} already seen"
    if excl:
        msg += f" · {excl} referral-company card(s) excluded (referral track)"
    else:
        ref_n = sum(1 for r in data if isinstance(r, dict) and is_referral((r.get('company') or ''), names))
        if ref_n:
            msg += f" · {ref_n} on referral list"
    if bad:
        msg += f", {bad} skipped (no jobId)"
    print(msg)


def op_todo(args):
    con = connect(args.db)
    q = ("SELECT job_id, company, title, card_loc, metros, view_url "
         "FROM jobs WHERE status='seen'")
    params = []
    if args.metro:
        q += " AND (','||metros||',') LIKE ?"
        params.append(f"%,{args.metro},%")
    q += " ORDER BY first_seen, company"
    rows = _rows_to_dicts(con.execute(q, params))
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        print(f"nothing new to analyze (metro={args.metro or 'any'})")
        return
    print(f"{len(rows)} new posting(s) to triage/analyze (metro={args.metro or 'any'}):")
    for r in rows:
        print(f"  [{r['job_id']}] {r['company']} — {r['title']}  ({r['card_loc']})")
        print(f"       {r['view_url']}")


def _norm_text(s: str) -> str:
    """Normalize a company/role string for fuzzy matching: lowercase, strip
    markdown bold stars, punctuation, and collapse whitespace."""
    s = s.replace("*", "").lower()
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()


def _board_history() -> "list[tuple[str, str, str]]":
    """Read the candidate's application history — every row of job-scoreboard.md
    PLUS the staged rows in job-analyses/_pending.md — as (company, role, status)
    tuples, all normalized. Read-only; never writes either file."""
    out: list[tuple[str, str, str]] = []
    for path in (os.path.join(ROOT, "job-scoreboard.md"),
                 os.path.join(ROOT, "job-analyses", "_pending.md")):
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.startswith("|"):
                    continue
                c = line.split("|")
                # board/pending row shape: | 排名 | 公司 | 岗位 | 状态 | 推荐分 | ...
                if len(c) >= 6 and re.search(r"\d", c[5]):
                    out.append((_norm_text(c[2]), _norm_text(c[3]), c[4].strip()))
    return out


REJECT_KEYS = ("被拒", "已挂", "已拒")
APPLIED_KEYS = ("已投", "面试", "Offer")


def blocked_names() -> "list[str]":
    """Read blocked-companies.md (project root, gitignored): companies the
    candidate never wants to apply to. Returns normalized names; empty list
    when the file doesn't exist. Format per line: `Name | note`."""
    path = os.path.join(ROOT, "blocked-companies.md")
    names: list[str] = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                names.append(_norm_text(line.split("|")[0]))
    return [n for n in names if n]


def op_board_dedup(args):
    """Cross-check every still-'seen' ledger row against the application history.

    - Company on blocked-companies.md (never-apply list) → auto-mark
      triaged_out (note 'blocked company') unless --dry-run.
    - Same company + same role already on the board/pending  → auto-mark
      triaged_out (note 'already boarded') unless --dry-run.
    - Company with >= 2 prior applications (status contains 已投/面试/Offer or
      a rejection marker — a rejection means he applied) → auto-mark
      triaged_out (note 'multi-applied company'): the candidate won't stack
      more applications on a company he already covered (candidate rule,
      2026-08-11). Printed as ✋ lines so the triage pass can resurrect one
      that is clearly a better fit.
    - Same company with a rejection-status row (被拒/已挂/已拒) but a DIFFERENT
      role → NOT auto-dropped (different role at the same company is allowed);
      printed as a ⚠ warning line so the triage pass can weigh it.
    Role match = normalized containment either way (board roles are often
    abbreviated versions of the posting title).
    """
    history = _board_history()
    if not history:
        die(f"no board history found under {ROOT}")
    blocked = blocked_names()
    # prior applications per company — ANY application evidence counts
    # (applied/interviewing/offer AND rejected: a rejection means he applied);
    # >= 2 means the candidate already covered this company — drop new postings
    applied_counts: dict[str, int] = {}
    for b_comp, _b_role, b_status in history:
        if any(k in b_status for k in APPLIED_KEYS + REJECT_KEYS):
            applied_counts[b_comp] = applied_counts.get(b_comp, 0) + 1
    con = connect(args.db)
    rows = _rows_to_dicts(con.execute(
        "SELECT job_id, company, title FROM jobs WHERE status='seen'"))
    dup_ids, blocked_ids, multi_ids, warns = [], [], [], []
    for r in rows:
        comp, role = _norm_text(r["company"]), _norm_text(r["title"])
        # whole-word match so "citi" hits "Citi"/"Citi Bank" but never "Citizens Bank";
        # list name variants (Citigroup, Citibank) explicitly in blocked-companies.md
        if any(re.search(rf"\b{re.escape(b)}\b", comp) for b in blocked):
            blocked_ids.append((r["job_id"], r["company"], r["title"]))
            continue
        is_dup = False
        for b_comp, b_role, b_status in history:
            if not (comp and b_comp) or (comp not in b_comp and b_comp not in comp):
                continue
            if b_role and role and (b_role in role or role in b_role):
                dup_ids.append((r["job_id"], r["company"], r["title"]))
                is_dup = True
                break
            if any(k in b_status for k in REJECT_KEYS):
                warns.append((r["job_id"], r["company"], r["title"], b_status))
        if is_dup:
            continue
        n_live = max((n for b_comp, n in applied_counts.items()
                      if comp and (comp in b_comp or b_comp in comp)), default=0)
        if n_live >= 2:
            multi_ids.append((r["job_id"], r["company"], r["title"], n_live))
    if not args.dry_run:
        for job_id, _, _ in dup_ids:
            con.execute(
                "UPDATE jobs SET status='triaged_out', note='already boarded (board-dedup)', "
                "last_seen=? WHERE job_id=?", [today(args), job_id])
        for job_id, _, _ in blocked_ids:
            con.execute(
                "UPDATE jobs SET status='triaged_out', note='blocked company (board-dedup)', "
                "last_seen=? WHERE job_id=?", [today(args), job_id])
        for job_id, _, _, _ in multi_ids:
            con.execute(
                "UPDATE jobs SET status='triaged_out', note='multi-applied company (board-dedup)', "
                "last_seen=? WHERE job_id=?", [today(args), job_id])
        con.commit()
    verb = "would drop" if args.dry_run else "dropped"
    print(f"board-dedup: {len(rows)} seen row(s) vs {len(history)} history row(s) "
          f"+ {len(blocked)} blocked company(ies) — "
          f"{verb} {len(dup_ids)} duplicate(s), {len(blocked_ids)} blocked, "
          f"{len(multi_ids)} multi-applied")
    for job_id, company, title in dup_ids:
        print(f"  ✂ [{job_id}] {company} — {title}")
    for job_id, company, title in blocked_ids:
        print(f"  🚫 [{job_id}] {company} — {title}  (blocked list)")
    for job_id, company, title, n_live in multi_ids:
        print(f"  ✋ [{job_id}] {company} — {title}  (already {n_live} live application(s) at this company; resurrect only if clearly better fit)")
    # de-duplicate warnings per job_id (a company can have several rejected rows)
    seen_warn = set()
    for job_id, company, title, b_status in warns:
        if job_id in seen_warn or job_id in {d[0] for d in dup_ids}:
            continue
        seen_warn.add(job_id)
        print(f"  ⚠ [{job_id}] {company} — {title}  (company has rejection history: {b_status}; different role → analyze allowed)")


def op_digest(args):
    """One-glance disposition of the WHOLE ledger run — every posting, one line,
    grouped: analyzed ≥6 (with 📍 + apply link) → analyzed <6 → still-'seen'
    (not yet analyzed; the pool to pick extra analyses from) → triaged_out
    (with reason). This is the end-of-run display: the candidate decides in ONE
    pass instead of apply → ask for more → apply again."""
    con = connect(args.db)
    rows = _rows_to_dicts(con.execute(
        "SELECT job_id, company, title, card_loc, metros, score, status, note, "
        "apply_type, apply_url, view_url FROM jobs ORDER BY "
        "CASE status WHEN 'analyzed' THEN 0 WHEN 'applied' THEN 1 WHEN 'seen' THEN 2 "
        "WHEN 'skipped' THEN 3 ELSE 4 END, score DESC NULLS LAST, company"))
    hi = [r for r in rows if r["status"] == "analyzed" and (r["score"] or 0) >= 6]
    ap = [r for r in rows if r["status"] == "applied"]
    lo = [r for r in rows if r["status"] == "analyzed" and (r["score"] or 0) < 6]
    sn = [r for r in rows if r["status"] == "seen"]
    sk = [r for r in rows if r["status"] == "skipped"]
    to = [r for r in rows if r["status"] == "triaged_out"]

    def line(r, mark):
        loc = r["card_loc"] or r["metros"]
        s = f"  {mark} [{r['job_id']}] {r['company']} — {r['title']}  📍{loc}"
        if r["score"] is not None:
            s += f"  ⭐{r['score']:g}"
        return s

    print(f"📊 台账全量处置（{len(rows)} 条）")
    if ap:
        # count only — the candidate knows what he applied to; the digest's job
        # is the decision list (>=6 待投), not an application-history replay
        print(f"\n✅ 已投（{len(ap)}）— 明细略")
    if hi:
        print(f"\n⭐ 已分析 ≥6，待投（{len(hi)}）")
        for r in hi:
            print(line(r, "⭐"))
            print(f"       apply: {best_url(r)}")
    if lo:
        print(f"\n❌ 已分析 <6，不入榜（{len(lo)}）")
        for r in lo:
            print(line(r, "❌"))
    if sn:
        print(f"\n👀 未分析（{len(sn)}）— 想补分析的从这里点名")
        for r in sn:
            print(line(r, "•"))
    if sk:
        print(f"\n⏭ 主动跳过（{len(sk)}）")
        for r in sk:
            print(line(r, "⏭"))
    if to:
        reasons = {}
        for r in to:
            reasons.setdefault(r["note"] or "(no note)", []).append(r)
        print(f"\n🗑 已剔除（{len(to)}）")
        for note, rs in sorted(reasons.items(), key=lambda kv: -len(kv[1])):
            names = "、".join(f"{r['company']}" for r in rs)
            print(f"  {len(rs)} × {note}: {names}")


def op_mark(args):
    if args.status not in STATUSES:
        die(f"--status must be one of {STATUSES}")
    if args.apply_type and args.apply_type not in APPLY_TYPES:
        die(f"--apply-type must be one of {APPLY_TYPES}")
    con = connect(args.db)
    sets, params = ["status=?"], [args.status]
    if args.score is not None:
        sets.append("score=?")
        params.append(args.score)
    if args.apply_type:
        sets.append("apply_type=?")
        params.append(args.apply_type)
    if args.apply_url:
        sets.append("apply_url=?")
        params.append(args.apply_url)
    if args.note:
        sets.append("note=?")
        params.append(args.note)
    if getattr(args, "posted", None):
        sets.append("posted=?")
        params.append(args.posted)
    sets.append("last_seen=?")
    params.append(today(args))
    params.append(args.job_id)
    cur = con.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE job_id=?", params)
    con.commit()
    if cur.rowcount == 0:
        die(f"no job with job_id={args.job_id} (ingest it first)")
    extra = f", score={args.score}" if args.score is not None else ""
    print(f"marked {args.job_id}: status={args.status}{extra}")


def op_filter(args):
    con = connect(args.db)
    q = ("SELECT job_id, company, title, score, status, metros, posted, referral, "
         "apply_type, apply_url, view_url FROM jobs WHERE 1=1")
    params = []
    if args.status:
        q += " AND status=?"
        params.append(args.status)
    if args.metro:
        q += " AND (','||metros||',') LIKE ?"
        params.append(f"%,{args.metro},%")
    if args.referral:
        q += " AND referral=1"
    if args.min_score is not None:
        q += " AND score IS NOT NULL AND score >= ?"
        params.append(args.min_score)
    q += " ORDER BY (score IS NULL), score DESC, posted DESC, company"
    rows = _rows_to_dicts(con.execute(q, params))
    if args.json:
        for r in rows:
            r["apply_link"] = best_url(r)
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        print("no matches")
        return
    for r in rows:
        sc = "—" if r["score"] is None else f"{r['score']:.1f}"
        tag = " ⭐REF" if r.get("referral") else ""
        print(f"  [{sc}]{tag} {r['company']} — {r['title']}  "
              f"({r['status']}, {r['metros']}, posted {r['posted'] or '?'})")
        print(f"       apply: {best_url(r)}")


def op_reflag(args):
    """Re-scan the referral flag on every row against the current referral-companies.md
    (run after editing the list so already-ingested rows pick up added/removed companies)."""
    names = referral_names(args.referral_companies or DEFAULT_REFERRAL)
    con = connect(args.db)
    n = 0
    for jid, company in con.execute("SELECT job_id, company FROM jobs").fetchall():
        con.execute("UPDATE jobs SET referral=? WHERE job_id=?",
                    (1 if is_referral(company, names) else 0, jid))
        n += 1
    con.commit()
    total = con.execute("SELECT COUNT(*) FROM jobs WHERE referral=1").fetchone()[0]
    print(f"reflagged {n} row(s) against {len(names)} referral company(ies) — {total} flagged referral")


def op_stats(args):
    con = connect(args.db)
    total = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    by_status = con.execute(
        "SELECT status, COUNT(*) FROM jobs GROUP BY status ORDER BY 2 DESC").fetchall()
    print(f"ledger: {total} posting(s) total")
    print("  by status: " + ", ".join(f"{s}={n}" for s, n in by_status))
    # metros is a comma-set; expand it
    counts = {}
    for (metros,) in con.execute("SELECT metros FROM jobs"):
        for m in (metros or "").split(","):
            if m:
                counts[m] = counts.get(m, 0) + 1
    if counts:
        print("  by metro:  " + ", ".join(
            f"{m}={n}" for m, n in sorted(counts.items(), key=lambda kv: -kv[1])))


def op_list(args):
    con = connect(args.db)
    rows = _rows_to_dicts(con.execute("SELECT * FROM jobs ORDER BY last_seen DESC, company"))
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        print("ledger is empty")
        return
    for r in rows:
        sc = "—" if r["score"] is None else f"{r['score']:.1f}"
        print(f"  {r['status']:12} [{sc:>4}] {r['company']} — {r['title']}  "
              f"({r['metros']}, seen {r['first_seen']})")


def main():
    p = argparse.ArgumentParser(description="LinkedIn 'seen jobs' ledger (SQLite).")
    p.add_argument("--db", default=DEFAULT_DB, help=f"ledger path (default {DEFAULT_DB})")
    sub = p.add_subparsers(dest="op", required=True)

    ing = sub.add_parser("ingest", help="upsert the snippet's JSON array")
    ing.add_argument("--metro", required=True, help="which search surfaced these (nyc/sanjose/seattle/dallas/remote/referral-<company>/...)")
    ing.add_argument("-i", "--input", default="-", help="JSON file, or - for stdin (default)")
    ing.add_argument("--date", help="override 'today' (YYYY-MM-DD)")
    ing.add_argument("--referral-companies", help=f"referral list file (default {DEFAULT_REFERRAL})")
    ing.add_argument("--exclude-referral", action="store_true",
                     help="skip referral-list companies (use in the REGULAR flow; the referral track has its own ledger)")
    ing.set_defaults(fn=op_ingest)

    td = sub.add_parser("todo", help="postings still needing triage/analysis")
    td.add_argument("--metro")
    td.add_argument("--json", action="store_true")
    td.set_defaults(fn=op_todo)

    bd = sub.add_parser("board-dedup",
                        help="auto-triage 'seen' rows already on the scoreboard/pending; warn on rejected companies")
    bd.add_argument("--dry-run", action="store_true", help="report only, don't mark")
    bd.set_defaults(fn=op_board_dedup)

    dg = sub.add_parser("digest", help="one-glance disposition of every posting, grouped by status")
    dg.set_defaults(fn=op_digest)

    mk = sub.add_parser("mark", help="update one posting's disposition")
    mk.add_argument("--job-id", required=True)
    mk.add_argument("--status", required=True, help=f"one of {STATUSES}")
    mk.add_argument("--score", type=float)
    mk.add_argument("--apply-type", help=f"one of {APPLY_TYPES}")
    mk.add_argument("--apply-url")
    mk.add_argument("--note")
    mk.add_argument("--posted", help="posting date YYYY-MM-DD (set at analysis time)")
    mk.add_argument("--date")
    mk.set_defaults(fn=op_mark)

    fl = sub.add_parser("filter", help="query the ledger")
    fl.add_argument("--metro")
    fl.add_argument("--status")
    fl.add_argument("--min-score", type=float)
    fl.add_argument("--referral", action="store_true", help="only referral-list companies")
    fl.add_argument("--json", action="store_true")
    fl.set_defaults(fn=op_filter)

    rf = sub.add_parser("reflag", help="re-apply the referral flag to all rows from the current list")
    rf.add_argument("--referral-companies", help=f"referral list file (default {DEFAULT_REFERRAL})")
    rf.set_defaults(fn=op_reflag)

    st = sub.add_parser("stats", help="counts by status and metro")
    st.set_defaults(fn=op_stats)

    ls = sub.add_parser("list", help="dump the whole ledger")
    ls.add_argument("--json", action="store_true")
    ls.set_defaults(fn=op_list)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
