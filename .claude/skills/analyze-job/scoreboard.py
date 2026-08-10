#!/usr/bin/env python3
"""Deterministic scoreboard operations for the job-hunt workflow.

Replaces the old `scoreboard-keeper` LLM subagent: mechanical work (sort, renumber,
dedup, merge) is done by code — exact, fast, atomic, no races, no hallucination.
The LLM (job-analyzer) still does the *thinking* (research + scoring); this only
does the *bookkeeping*.

Files (resolved relative to this script's location):
  <root>/job-scoreboard.md          the ranked master table
  <root>/job-analyses/_pending.md   append-only staging buffer

Row shape (9 cells):
  | 排名 | **公司** | 岗位 (地点) | 状态 | **推荐分** | 适配 | 薪资 | 风险 | 一句话 |

Ops:
  append   --rows-file F | (stdin)     append row line(s) to _pending.md (drops 推荐分 < 6)
  flush    [--date YYYY-MM-DD]         merge _pending -> board, re-sort, renumber, clear buffer (drops 推荐分 < 6)
  status   --company C --role R --set S   set one posting's 状态 (board or pending)
  refresh  --row "<full row>"          replace one existing posting's row (matched by 公司+岗位)
  prune    [--min N] [--date ...]      remove board rows scoring < N (default 6) — clear sub-cutoff jobs
  check                                read-only: duplicates / sort / count sanity

Cutoff rule: a job scoring below MIN_SCORE (6) is below the candidate's bar and is NOT
tracked on the board — append/flush drop it, prune clears any that predate the rule.

Identity of a posting = 公司 + 岗位 (never 公司 alone) — same company's different roles coexist.
"""
import argparse
import datetime
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(os.path.join(__file__, "..", "..", "..")))
BOARD = os.path.join(ROOT, "job-scoreboard.md")
PENDING = os.path.join(ROOT, "job-analyses", "_pending.md")
STATE = os.path.join(ROOT, ".board-state.json")  # tiny sidecar: last merge time + counts (gitignored)
MERGE_LOG = os.path.join(ROOT, ".merge-log.md")  # append-only audit log: who flushed & when (gitignored)

SCORE_RE = re.compile(r"\*\*([0-9]+(?:\.[0-9]+)?)\*\*")

MIN_SCORE = 6.0  # 推荐分 < 6 = below the candidate's bar -> never boarded (append/flush drop it, prune clears it)

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.readlines()

def write_atomic(path, lines):
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.writelines(lines)
        os.replace(tmp, path)  # atomic on same filesystem
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise

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
    return re.sub(r"\s+", " ", s.replace("*", "").strip().lower())

def company_cell(l):
    return norm(cells(l)[2])

def role_cell(l):
    return norm(cells(l)[3])

def key(l):
    return (company_cell(l), role_cell(l))

def renumber_and_sort(lines):
    """Re-sort data rows by 推荐分 desc (stable) and renumber 排名 (ties share a rank)."""
    idx = [i for i, l in enumerate(lines) if is_row(l)]
    rows = sorted((lines[i] for i in idx), key=score_of, reverse=True)
    for slot, l in zip(idx, rows):
        lines[slot] = l
    prev_s = None
    prev_r = 0
    for pos, i in enumerate(idx):
        s = score_of(lines[i])
        r = pos + 1 if (prev_s is None or s != prev_s) else prev_r
        prev_s, prev_r = s, r
        c = cells(lines[i])
        c[1] = f" {r} "
        lines[i] = "|".join(c)
    return len(idx)

def set_count(lines, total):
    return [re.sub(r"（\d+\s*个岗位）", f"（{total} 个岗位）", l) if "结论速览" in l else l
            for l in lines]

def update_date(lines, date):
    if not date:
        return lines
    return [re.sub(r"(_更新于\s*)\d{4}-\d{2}-\d{2}(_)", rf"\g<1>{date}\g<2>", l)
            if "更新于" in l else l for l in lines]

def board_counts():
    """(#rows on the board, #rows staged in _pending) — cheap, for the state marker."""
    board = read(BOARD) if os.path.exists(BOARD) else []
    pend = read(PENDING) if os.path.exists(PENDING) else []
    return sum(1 for l in board if is_row(l)), sum(1 for l in pend if is_row(l))

def stamp_state(last_op):
    """Write .board-state.json after any mutation so a running session can compare a
    timestamp/count and know the board moved (e.g. another session flushed) — see the
    Refresh mode in SKILL.md. Best-effort: never let a state-write failure break the op."""
    try:
        rows, pending = board_counts()
        state = {"last_updated": datetime.datetime.now().isoformat(timespec="seconds"),
                 "last_op": last_op, "rows": rows, "pending_rows": pending}
        write_atomic(STATE, [json.dumps(state, ensure_ascii=False, indent=2) + "\n"])
    except Exception as e:
        print(f"(warning: could not write {os.path.basename(STATE)}: {e})", file=sys.stderr)

def log_merge(session_id, merged, skipped, low, total):
    """Append ONE line to .merge-log.md recording which session ran this flush and when.

    Answers 'which session merged the board, and when' for future audits. Uses a plain
    append (not the atomic read-modify-write the board uses) so concurrent sessions can
    each log without clobbering each other's lines. The session id comes from the
    CLAUDE_CODE_SESSION_ID env var Claude Code sets — it's the reliable, always-available
    identifier, so it's all we log (no session name).
    Best-effort: a logging failure must never break the merge itself.
    """
    try:
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        sid = session_id or os.environ.get("CLAUDE_CODE_SESSION_ID") or "unknown"
        line = (f"- {ts} · {sid} · merged {len(merged)}, "
                f"dup {len(skipped)}, <cutoff {len(low)}, board total {total}\n")
        header_needed = not os.path.exists(MERGE_LOG)
        with open(MERGE_LOG, "a", encoding="utf-8") as f:
            if header_needed:
                f.write("# 合并日志 (merge audit log) — append-only; 哪个 session 在何时把 _pending 合并进 board\n")
                f.write("# 每行: - <时间> · <session id> · merged N, dup N, <cutoff N, board total N\n\n")
            f.write(line)
    except Exception as e:
        print(f"(warning: could not write {os.path.basename(MERGE_LOG)}: {e})", file=sys.stderr)

# ---------- ops ----------

def op_append(args):
    if args.rows_file:
        new = read(args.rows_file)
    else:
        new = sys.stdin.readlines()
    new = [l if l.endswith("\n") else l + "\n" for l in new if l.strip().startswith("|")]
    if not new:
        print("no valid row lines to append")
        return
    kept, low = [], []
    for l in new:
        if is_row(l) and score_of(l) < MIN_SCORE:
            low.append(cells(l)[2].replace("*", "").strip())
        else:
            kept.append(l)
    if not kept:
        print(f"nothing appended — all {len(low)} row(s) below cutoff {MIN_SCORE}: {low}")
        return
    pend = read(PENDING)
    write_atomic(PENDING, pend + kept)
    stamp_state("append")
    msg = f"appended {len(kept)} row(s) to _pending.md"
    if low:
        msg += f"; skipped {len(low)} below {MIN_SCORE}: {low}"
    print(msg)

def op_flush(args):
    pend = read(PENDING)
    pend_rows = [l for l in pend if is_row(l)]
    if not pend_rows:
        print("暂存区为空，无需合并")
        return
    board = read(BOARD)
    existing = {key(l) for l in board if is_row(l)}
    merged, skipped, low = [], [], []
    seen = set()
    for l in pend_rows:
        if score_of(l) < MIN_SCORE:              # below the candidate's bar -> never boarded
            low.append(cells(l)[2].replace("*", "").strip())
            continue
        k = key(l)
        if k in existing or k in seen:          # exact same 公司+岗位 already there -> dup
            skipped.append(cells(l)[2].replace("*", "").strip())
            continue
        seen.add(k)
        merged.append(l if l.endswith("\n") else l + "\n")
    last = max(i for i, l in enumerate(board) if is_row(l))
    for l in reversed(merged):
        board.insert(last + 1, l)
    total = renumber_and_sort(board)
    board = set_count(board, total)
    board = update_date(board, args.date)
    write_atomic(BOARD, board)
    # clear pending -> keep only the non-row (comment header) lines
    write_atomic(PENDING, [l for l in pend if not is_row(l)])
    stamp_state("flush")
    log_merge(os.environ.get("CLAUDE_CODE_SESSION_ID"), merged, skipped, low, total)
    msg = f"merged {len(merged)}; board total = {total}"
    if skipped:
        msg += f"; skipped dup: {skipped}"
    if low:
        msg += f"; skipped <{MIN_SCORE}: {low}"
    print(msg)

def _find(lines, company, role):
    c, r = norm(company), norm(role)
    return [i for i, l in enumerate(lines)
            if is_row(l) and c in company_cell(l) and r in role_cell(l)]

STATUS_DATE_KEYS = ("已投", "已拒", "已挂", "面试", "Offer")
CHANNEL_TAGS = {"cold": "冷投", "referral": "内推", "recruiter": "猎头", "inbound": "对方主动",
                "autosearch": "自动搜岗"}

def op_status(args):
    val = args.set.strip()
    # Data discipline: every status change carries a date (needed for time-to-response
    # analytics later). Auto-stamp today unless the value already carries MM-DD.
    if any(k in val for k in STATUS_DATE_KEYS) and not re.search(r"\d{2}-\d{2}", val):
        val = f"{val} {args.date or datetime.date.today().strftime('%m-%d')}"
    if getattr(args, "channel", None):
        tag = CHANNEL_TAGS.get(args.channel, args.channel)
        if tag not in val:
            val = f"{val}·{tag}"
    for path in (BOARD, PENDING):
        lines = read(path)
        hits = _find(lines, args.company, args.role)
        if len(hits) == 1:
            c = cells(lines[hits[0]])
            c[4] = f" {val} "
            lines[hits[0]] = "|".join(c)
            if path == BOARD:
                lines = update_date(lines, args.date)
            write_atomic(path, lines)
            stamp_state("status")
            print(f"set 状态 = {val} for {args.company} / {args.role}  (in {os.path.basename(path)})")
            return
        if len(hits) > 1:
            print(f"AMBIGUOUS — {len(hits)} rows match in {os.path.basename(path)}; refine 岗位:")
            for i in hits:
                print("   " + cells(lines[i])[2].strip() + " | " + cells(lines[i])[3].strip())
            return
    print(f"NOT FOUND: {args.company} / {args.role} (neither board nor pending)")

def op_refresh(args):
    row = args.row if args.row.endswith("\n") else args.row + "\n"
    company, role = cells(row)[2], cells(row)[3]
    board = read(BOARD)
    hits = _find(board, company, role)
    if len(hits) != 1:
        print(f"refresh needs exactly one match; got {len(hits)} for {company.strip()} / {role.strip()}")
        return
    i = hits[0]
    old_status = cells(board[i])[4]
    c = cells(row)
    c[4] = old_status  # preserve existing 状态
    board[i] = "|".join(c)
    total = renumber_and_sort(board)
    board = set_count(board, total)
    board = update_date(board, args.date)
    write_atomic(BOARD, board)
    stamp_state("refresh")
    print(f"refreshed {company.strip()} / {role.strip()} (状态 preserved)")

def op_remove(args):
    board = read(BOARD)
    hits = _find(board, args.company, args.role)
    if not hits:
        # fall back to the staging buffer — a row analyzed this session may not be merged yet
        pend = read(PENDING) if os.path.exists(PENDING) else []
        phits = _find(pend, args.company, args.role)
        if phits:
            for i in sorted(phits, reverse=True):
                del pend[i]
            write_atomic(PENDING, pend)
            stamp_state("remove")
            print(f"removed {len(phits)} row(s) for {args.company} / {args.role} from _pending.md")
            return
        print(f"NOT FOUND: {args.company} / {args.role}")
        return
    for i in sorted(hits, reverse=True):
        del board[i]
    total = renumber_and_sort(board)
    board = set_count(board, total)
    board = update_date(board, args.date)
    write_atomic(BOARD, board)
    stamp_state("remove")
    print(f"removed {len(hits)} row(s) for {args.company} / {args.role}; board total = {total}")

def op_prune(args):
    thr = args.min if args.min is not None else MIN_SCORE
    board = read(BOARD)
    victims = [i for i, l in enumerate(board) if is_row(l) and score_of(l) < thr]
    if not victims:
        print(f"no rows below {thr} — nothing to prune")
        return
    names = [f"{cells(board[i])[2].replace('*','').strip()} ({score_of(board[i])})" for i in victims]
    for i in sorted(victims, reverse=True):
        del board[i]
    total = renumber_and_sort(board)
    board = set_count(board, total)
    board = update_date(board, args.date)
    write_atomic(BOARD, board)
    stamp_state("prune")
    print(f"pruned {len(victims)} row(s) below {thr}; board total = {total}")
    print("  removed: " + ", ".join(names))

def op_state(args):
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as f:
            sys.stdout.write(f.read())
    else:
        rows, pending = board_counts()
        print(json.dumps({"last_updated": None, "last_op": None,
                          "rows": rows, "pending_rows": pending}, ensure_ascii=False))

def op_check(args):
    board = read(BOARD)
    rows = [l for l in board if is_row(l)]
    # duplicates by 公司+岗位
    seen, dups = set(), []
    for l in rows:
        k = key(l)
        if k in seen:
            dups.append(f"{cells(l)[2].strip()} | {cells(l)[3].strip()}")
        seen.add(k)
    # sort check
    bad = []
    prev = None
    for l in rows:
        s = score_of(l)
        if prev is not None and s > prev + 1e-9:
            bad.append(s)
        prev = s
    # count line
    m = re.search(r"结论速览（(\d+)\s*个岗位）", "".join(board))
    stated = int(m.group(1)) if m else None
    print(f"rows = {len(rows)}")
    print(f"结论速览 count = {stated}  {'OK' if stated == len(rows) else '❌ MISMATCH'}")
    print(f"duplicates (公司+岗位) = {dups if dups else 'none'}")
    print(f"sort = {'OK (non-increasing)' if not bad else '❌ out of order'}")

def main():
    p = argparse.ArgumentParser(description="Deterministic scoreboard bookkeeping.")
    sub = p.add_subparsers(dest="op", required=True)

    a = sub.add_parser("append"); a.add_argument("--rows-file"); a.set_defaults(fn=op_append)
    f = sub.add_parser("flush"); f.add_argument("--date"); f.set_defaults(fn=op_flush)
    s = sub.add_parser("status")
    s.add_argument("--company", required=True); s.add_argument("--role", required=True)
    s.add_argument("--set", required=True); s.add_argument("--date")
    s.add_argument("--channel", choices=list(CHANNEL_TAGS)); s.set_defaults(fn=op_status)
    r = sub.add_parser("refresh")
    r.add_argument("--row", required=True); r.add_argument("--date"); r.set_defaults(fn=op_refresh)
    rm = sub.add_parser("remove")
    rm.add_argument("--company", required=True); rm.add_argument("--role", required=True)
    rm.add_argument("--date"); rm.set_defaults(fn=op_remove)
    pr = sub.add_parser("prune"); pr.add_argument("--min", type=float)
    pr.add_argument("--date"); pr.set_defaults(fn=op_prune)
    st = sub.add_parser("state"); st.set_defaults(fn=op_state)
    c = sub.add_parser("check"); c.set_defaults(fn=op_check)

    args = p.parse_args()
    args.fn(args)

if __name__ == "__main__":
    main()
