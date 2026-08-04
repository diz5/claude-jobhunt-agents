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
import sqlite3
import sys

ROOT = os.path.dirname(os.path.abspath(os.path.join(__file__, "..", "..", "..")))
DEFAULT_DB = os.path.join(ROOT, ".linkedin-seen.db")

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
    return con


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
    new = seen = bad = 0
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
        cur = con.execute("SELECT metros FROM jobs WHERE job_id=?", (jid,)).fetchone()
        if cur is None:
            con.execute(
                "INSERT INTO jobs (job_id, company, title, card_loc, metros, view_url, "
                "status, first_seen, last_seen) VALUES (?,?,?,?,?,?, 'seen', ?, ?)",
                (jid, company, title, loc, args.metro or "", view, day, day))
            new += 1
        else:
            con.execute(
                "UPDATE jobs SET metros=?, last_seen=?, "
                "company  = CASE WHEN company=''  THEN ? ELSE company  END, "
                "title    = CASE WHEN title=''    THEN ? ELSE title    END, "
                "card_loc = CASE WHEN card_loc='' THEN ? ELSE card_loc END, "
                "view_url = CASE WHEN view_url='' THEN ? ELSE view_url END "
                "WHERE job_id=?",
                (merge_metros(cur[0], args.metro), day, company, title, loc, view, jid))
            seen += 1
    con.commit()
    msg = f"metro={args.metro or '-'}: {new + seen} card(s) — {new} new, {seen} already seen"
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
    q = ("SELECT job_id, company, title, score, status, metros, apply_type, apply_url, view_url "
         "FROM jobs WHERE 1=1")
    params = []
    if args.status:
        q += " AND status=?"
        params.append(args.status)
    if args.metro:
        q += " AND (','||metros||',') LIKE ?"
        params.append(f"%,{args.metro},%")
    if args.min_score is not None:
        q += " AND score IS NOT NULL AND score >= ?"
        params.append(args.min_score)
    q += " ORDER BY (score IS NULL), score DESC, company"
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
        print(f"  [{sc}] {r['company']} — {r['title']}  ({r['status']}, {r['metros']})")
        print(f"       apply: {best_url(r)}")


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
    ing.add_argument("--metro", required=True, help="which search surfaced these (nyc/sanjose/seattle/dallas/remote/...)")
    ing.add_argument("-i", "--input", default="-", help="JSON file, or - for stdin (default)")
    ing.add_argument("--date", help="override 'today' (YYYY-MM-DD)")
    ing.set_defaults(fn=op_ingest)

    td = sub.add_parser("todo", help="postings still needing triage/analysis")
    td.add_argument("--metro")
    td.add_argument("--json", action="store_true")
    td.set_defaults(fn=op_todo)

    mk = sub.add_parser("mark", help="update one posting's disposition")
    mk.add_argument("--job-id", required=True)
    mk.add_argument("--status", required=True, help=f"one of {STATUSES}")
    mk.add_argument("--score", type=float)
    mk.add_argument("--apply-type", help=f"one of {APPLY_TYPES}")
    mk.add_argument("--apply-url")
    mk.add_argument("--note")
    mk.add_argument("--date")
    mk.set_defaults(fn=op_mark)

    fl = sub.add_parser("filter", help="query the ledger")
    fl.add_argument("--metro")
    fl.add_argument("--status")
    fl.add_argument("--min-score", type=float)
    fl.add_argument("--json", action="store_true")
    fl.set_defaults(fn=op_filter)

    st = sub.add_parser("stats", help="counts by status and metro")
    st.set_defaults(fn=op_stats)

    ls = sub.add_parser("list", help="dump the whole ledger")
    ls.add_argument("--json", action="store_true")
    ls.set_defaults(fn=op_list)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
