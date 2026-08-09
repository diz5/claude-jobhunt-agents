#!/usr/bin/env python3
"""Deterministic bookkeeping for the application-prep pipeline.

Sibling to `scoreboard.py`: the LLM (application-drafter) does the *thinking*
(reading the JD, drafting human answers); this script does the *mechanics* —
picking which roles to apply to and scaffolding a per-job application packet.
Exact, atomic, no hallucination.

Files (resolved relative to this script's location, project ROOT):
  <root>/job-scoreboard.md                 the ranked master table (read-only here)
  <root>/applications/<slug>/packet.json   per-job machine-fillable packet
  <root>/applications/<slug>/answers.md     human-readable answers (for review)
  <root>/applications/<slug>/run.log        append-only pipeline log
  <root>/applications/identity.json         shared applicant identity (optional, gitignored)

The `applications/` tree holds personal data and is gitignored.

Ops:
  queue    [--min-score N] [--status S] [--json]   list board roles to apply to, ranked
  init     --company C --role R [--url U] [--ats A] [--location L]
                                                   scaffold applications/<slug>/ packet
  list     [--json]                                list all packets and their state

Apply-state (mirrors the scoreboard 状态 column, extended):
  未投 -> 排队中 -> 草稿就绪 -> 已投 MM-DD
Board status changes are NOT made here — the application-prep skill routes those
through scoreboard.py so the board stays single-writer.
"""
import argparse
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(os.path.join(__file__, "..", "..", "..")))
BOARD = os.path.join(ROOT, "job-scoreboard.md")
APPS = os.path.join(ROOT, "applications")
IDENTITY = os.path.join(APPS, "identity.json")

SCORE_RE = re.compile(r"\*\*([0-9]+(?:\.[0-9]+)?)\*\*")

# Default identity skeleton written into a packet when applications/identity.json is absent.
IDENTITY_SKELETON = {
    "first_name": "", "last_name": "", "full_name": "",
    "email": "", "phone": "", "location": "",
    "linkedin": "", "github": "", "website": "",
    "work_authorized": True, "requires_sponsorship": False,
}


# ---------- io helpers (atomic, mirrors scoreboard.py) ----------

def read_lines(path):
    with open(path, encoding="utf-8") as f:
        return f.readlines()

def write_atomic(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise

def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def dump_json(path, obj):
    write_atomic(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


# ---------- board row parsing (mirrors scoreboard.py) ----------

def cells(l):
    return l.split("|")

def is_row(l):
    if not l.startswith("|"):
        return False
    c = cells(l)
    return len(c) >= 10 and SCORE_RE.search(c[5]) is not None

def score_of(l):
    return float(SCORE_RE.search(cells(l)[5]).group(1))

def norm(s):
    return re.sub(r"\s+", " ", s.replace("*", "").strip())

def company_of(l):
    return norm(cells(l)[2])

def role_of(l):
    return norm(cells(l)[3])

def status_of(l):
    return norm(cells(l)[4])

def blurb_of(l):
    return norm(cells(l)[9])


# ---------- slug ----------

def slugify(*parts):
    s = " ".join(p for p in parts if p)
    s = s.lower()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)  # drop punctuation, keep word chars
    s = re.sub(r"[\s_]+", "-", s.strip())
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "job"

def packet_dir(slug):
    return os.path.join(APPS, slug)


# ---------- ops ----------

def op_queue(args):
    if not os.path.exists(BOARD):
        print(f"no board at {BOARD}", file=sys.stderr)
        sys.exit(1)
    rows = [l for l in read_lines(BOARD) if is_row(l)]
    want_status = norm(args.status) if args.status else None
    picked = []
    for l in rows:
        if score_of(l) < args.min_score:
            continue
        if want_status is not None and status_of(l) != want_status:
            continue
        picked.append({
            "company": company_of(l),
            "role": role_of(l),
            "status": status_of(l),
            "score": score_of(l),
            "blurb": blurb_of(l),
            "slug": slugify(company_of(l), role_of(l)),
        })
    picked.sort(key=lambda r: r["score"], reverse=True)
    if args.json:
        print(json.dumps(picked, ensure_ascii=False, indent=2))
        return
    if not picked:
        print(f"queue empty (status={args.status or 'any'}, min-score={args.min_score})")
        return
    print(f"{len(picked)} role(s) to apply — status={args.status or 'any'}, 推荐分>={args.min_score}:")
    for i, r in enumerate(picked, 1):
        print(f"  {i}. [{r['score']}] {r['company']} — {r['role']}  ({r['status']})")
        print(f"      slug: {r['slug']}  ·  {r['blurb']}")

def op_init(args):
    slug = args.slug or slugify(args.company, args.role)
    d = packet_dir(slug)
    packet_path = os.path.join(d, "packet.json")
    if os.path.exists(packet_path) and not args.force:
        print(f"packet already exists: {os.path.relpath(packet_path, ROOT)} (use --force to overwrite)")
        return
    identity = load_json(IDENTITY, default=dict(IDENTITY_SKELETON))
    # ensure all skeleton keys present even if identity.json is partial
    for k, v in IDENTITY_SKELETON.items():
        identity.setdefault(k, v)
    packet = {
        "company": args.company,
        "role": args.role,
        "location": args.location or "",
        "ats": args.ats or "",
        "url": args.url or "",
        "resume": args.resume or "",
        "state": "排队中",
        "identity": identity,
        "questions": [],                        # [{id,label,type,answer,required}] filled by the drafter
    }
    dump_json(packet_path, packet)
    # human-readable answer sheet stub
    write_atomic(os.path.join(d, "answers.md"),
                 f"# {args.company} — {args.role}\n\n"
                 f"_申请回答（草稿，提交前复核）_\n\n"
                 f"- 岗位链接：{args.url or '（待填）'}\n- ATS：{args.ats or '（待识别）'}\n\n"
                 f"## 表单问题与回答\n\n_（application-drafter 填充）_\n")
    log(slug, f"init packet · ats={args.ats or '?'} · url={args.url or '?'}")
    print(f"created {os.path.relpath(d, ROOT)}/  (slug: {slug})")

def op_list(args):
    if not os.path.isdir(APPS):
        print("no applications/ yet")
        return
    items = []
    for name in sorted(os.listdir(APPS)):
        p = os.path.join(APPS, name, "packet.json")
        pk = load_json(p)
        if pk is None:
            continue
        n_q = len(pk.get("questions", []))
        n_ans = sum(1 for q in pk.get("questions", []) if (q.get("answer") or "").strip())
        items.append({"slug": name, "company": pk.get("company", ""), "role": pk.get("role", ""),
                      "state": pk.get("state", ""), "answered": f"{n_ans}/{n_q}"})
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return
    if not items:
        print("no packets in applications/")
        return
    for it in items:
        print(f"  {it['state']:14} {it['company']} — {it['role']}  "
              f"(answers {it['answered']}, slug={it['slug']})")


def log(slug, msg):
    """Append a line to a packet's run.log. Timestamp is prepended by the caller/skill
    (this script has no clock access in some harnesses); here we log the event only."""
    path = os.path.join(packet_dir(slug), "run.log")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(msg.rstrip() + "\n")


def main():
    p = argparse.ArgumentParser(description="Deterministic application-prep bookkeeping.")
    sub = p.add_subparsers(dest="op", required=True)

    q = sub.add_parser("queue")
    q.add_argument("--min-score", type=float, default=6.0)
    q.add_argument("--status", default="未投", help="board 状态 to filter (default 未投; '' = any)")
    q.add_argument("--json", action="store_true")
    q.set_defaults(fn=op_queue)

    i = sub.add_parser("init")
    i.add_argument("--company", required=True)
    i.add_argument("--role", required=True)
    i.add_argument("--url", default="")
    i.add_argument("--ats", default="", help="greenhouse|lever|ashby|workday|... (optional hint)")
    i.add_argument("--location", default="")
    i.add_argument("--resume", default="")
    i.add_argument("--slug", default="")
    i.add_argument("--force", action="store_true")
    i.set_defaults(fn=op_init)

    ls = sub.add_parser("list")
    ls.add_argument("--json", action="store_true")
    ls.set_defaults(fn=op_list)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
