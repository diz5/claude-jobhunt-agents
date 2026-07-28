#!/usr/bin/env python3
"""status_report.py — deterministic job-hunt status snapshot from the scoreboard.

Sibling to scoreboard.py: parses job-scoreboard.md (+ the _pending.md buffer) and prints
a compact funnel report — totals, live interviews, score bands, top unapplied targets,
recent applications — plus the delta vs the previous run (kept in .status-history.json).

Usage:  python3 .claude/skills/analyze-job/status_report.py [--top N] [--min-score S]

No LLM judgment here: exact counts, one screen, safe to run any time.
"""
import argparse
import datetime as dt
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
BOARD = os.path.join(ROOT, 'job-scoreboard.md')
PENDING = os.path.join(ROOT, 'job-analyses', '_pending.md')
HISTORY = os.path.join(ROOT, '.status-history.json')

STATUS_ORDER = [  # first match wins
    ('offer', re.compile(r'Offer', re.I)),
    ('interview', re.compile(r'面试')),
    ('dead', re.compile(r'已拒|已挂|拒|挂')),
    ('applied', re.compile(r'已投')),
    ('notyet', re.compile(r'未投')),
]


def cells_of(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]


def parse_board(path):
    """Return (rows, columns) where rows = dicts with company/role/score/status."""
    if not os.path.exists(path):
        return [], {}
    header, idx = None, {}
    rows = []
    for line in open(path, encoding='utf-8'):
        if not line.lstrip().startswith('|'):
            continue
        cs = cells_of(line)
        if header is None:
            if any('公司' in c for c in cs):
                header = cs
                for key, names in (('company', ('公司',)), ('role', ('岗位', '职位')),
                                   ('score', ('推荐分', '评分')), ('status', ('状态',))):
                    idx[key] = next((i for i, c in enumerate(header)
                                     if any(n in c for n in names)), None)
            continue
        if not cs or not re.fullmatch(r'\d+', cs[0]):
            continue  # separator rows, notes, anything that isn't a ranked entry
        def get(key):
            i = idx.get(key)
            return cs[i] if i is not None and i < len(cs) else ''
        m = re.search(r'\d+(?:\.\d+)?', get('score'))
        score = float(m.group()) if m else None
        status_raw = get('status')
        bucket = next((b for b, rx in STATUS_ORDER if rx.search(status_raw)), 'other')
        rows.append({'company': get('company').strip('*'), 'role': get('role'),
                     'score': score, 'status': status_raw, 'bucket': bucket})
    return rows, idx


def count_pending():
    if not os.path.exists(PENDING):
        return 0
    n = 0
    for line in open(PENDING, encoding='utf-8'):
        if line.lstrip().startswith('|'):
            cs = cells_of(line)
            if cs and re.search(r'\d', ''.join(cs)) and not any('公司' in c for c in cs) \
                    and not set(''.join(cs)) <= set('-: '):
                n += 1
    return n


def recent_days(status, days=7):
    m = re.search(r'(\d{2})-(\d{2})', status)
    if not m:
        return False
    today = dt.date.today()
    try:
        d = dt.date(today.year, int(m.group(1)), int(m.group(2)))
    except ValueError:
        return False
    if d > today:
        d = d.replace(year=today.year - 1)
    return (today - d).days <= days


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=10, help='max unapplied targets to list')
    ap.add_argument('--min-score', type=float, default=7.5, help='min score for the target list')
    args = ap.parse_args()

    rows, _ = parse_board(BOARD)
    counts = {b: sum(1 for r in rows if r['bucket'] == b)
              for b in ('offer', 'interview', 'dead', 'applied', 'notyet', 'other')}
    total = len(rows)
    pending = count_pending()

    # delta vs previous run
    hist = []
    if os.path.exists(HISTORY):
        try:
            hist = json.load(open(HISTORY))
        except Exception:
            hist = []
    prev = hist[-1] if hist else None

    def delta(key, cur):
        if not prev or key not in prev:
            return ''
        d = cur - prev[key]
        return f" ({'+' if d >= 0 else ''}{d} vs {prev['date']})" if d else ''

    applied_all = counts['applied'] + counts['interview'] + counts['offer']
    print(f"📊 在册 {total}{delta('total', total)} · 暂存待并 {pending}")
    print(f"   已投(含面试/offer) {applied_all}{delta('applied_all', applied_all)}"
          f" · 面试中 {counts['interview']}{delta('interview', counts['interview'])}"
          f" · Offer {counts['offer']}"
          f" · 已关闭 {counts['dead']}{delta('dead', counts['dead'])}"
          f" · 未投 {counts['notyet']}{delta('notyet', counts['notyet'])}")

    bands = {'8+': 0, '7-7.9': 0, '6-6.9': 0, '<6': 0}
    for r in rows:
        s = r['score'] or 0
        bands['8+' if s >= 8 else '7-7.9' if s >= 7 else '6-6.9' if s >= 6 else '<6'] += 1
    print(f"   分布 ≥8: {bands['8+']} · 7档: {bands['7-7.9']} · 6档: {bands['6-6.9']} · <6: {bands['<6']}")

    live = sorted((r for r in rows if r['bucket'] in ('interview', 'offer')),
                  key=lambda r: -(r['score'] or 0))
    if live:
        print(f"\n🎯 面试/Offer ({len(live)}):")
        for r in live:
            print(f"   {r['score'] or '?'}  {r['company']} — {r['role'][:48]}")

    targets = sorted((r for r in rows if r['bucket'] == 'notyet'
                      and (r['score'] or 0) >= args.min_score),
                     key=lambda r: -(r['score'] or 0))[:args.top]
    if targets:
        print(f"\n📌 未投 ≥{args.min_score} (top {len(targets)}):")
        for r in targets:
            print(f"   {r['score']}  {r['company']} — {r['role'][:48]}")

    fresh = [r for r in rows if r['bucket'] == 'applied' and recent_days(r['status'])]
    print(f"\n🕐 近 7 天新投 {len(fresh)}:"
          + (' ' + '、'.join(r['company'] for r in fresh[:12]) if fresh else ' —'))

    # append snapshot (best-effort)
    try:
        hist.append({'date': dt.date.today().isoformat(), 'total': total,
                     'applied_all': applied_all, 'interview': counts['interview'],
                     'dead': counts['dead'], 'notyet': counts['notyet']})
        json.dump(hist[-100:], open(HISTORY, 'w'), ensure_ascii=False)
    except Exception:
        pass


if __name__ == '__main__':
    main()
