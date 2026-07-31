#!/usr/bin/env python3
"""batch_summary.py — deterministic end-of-batch chart for analyzed jobs.

Sibling to scoreboard.py / status_report.py. After a batch of job analyses, the main
agent calls this with the analysis files (or company names); it parses each file's
standard template and prints ONE fixed-format Chinese chart:

    ① <公司/岗位> ⭐<总分>
       适配 <分> ｜ <履历适配度一句(截断)>
       薪资 <分> ｜ 披露 <区间> → 争取 <目标>
       风险 <分> ｜ <公司/风险一句(截断)>

plus a "未入榜 (<6)" one-liner section. The chat display never drifts because the
LLM relays this output verbatim instead of drawing its own table.

Usage:
    python3 batch_summary.py Spotify Snowflake-IAM TheTradeDesk
    python3 batch_summary.py job-analyses/Spotify.md ... [--min-score 6] [--width 46]

Names are fuzzy-matched against job-analyses/*.md (case-insensitive substring).
"""
import argparse
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
DIR = os.path.join(ROOT, 'job-analyses')

CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'


def resolve(token):
    if os.path.isfile(token):
        return token
    cands = [p for p in glob.glob(os.path.join(DIR, '*.md'))
             if not os.path.basename(p).startswith('_')]
    exact = [p for p in cands
             if os.path.splitext(os.path.basename(p))[0].lower() == token.lower()]
    if exact:
        return exact[0]
    sub = [p for p in cands if token.lower() in os.path.basename(p).lower()]
    if len(sub) == 1:
        return sub[0]
    if len(sub) > 1:
        # newest match wins, but note the ambiguity on stderr
        sub.sort(key=os.path.getmtime, reverse=True)
        print(f"⚠️ '{token}' 匹配到多个文件，用最新的 {os.path.basename(sub[0])}",
              file=sys.stderr)
        return sub[0]
    return None


def clip(s, width):
    s = re.sub(r'\s+', ' ', s).strip(' ;；,，')
    return s if len(s) <= width else s[:width - 1] + '…'


def parse(path):
    text = open(path, encoding='utf-8').read()
    def grab(pattern):
        m = re.search(pattern, text)
        return m.groups() if m else None
    d = {'file': os.path.basename(path), 'name': os.path.splitext(os.path.basename(path))[0],
         'text': text.strip()}
    g = grab(r'⭐\s*推荐分[：:]\s*([\d.]+)\s*/\s*10\s*[—-]+\s*(.+)')
    d['score'], d['verdict'] = (float(g[0]), g[1].strip()) if g else (None, '')
    for key, label in (('fit', '履历适配度'), ('pay', '薪资性价比'), ('risk', r'公司/风险')):
        g = grab(rf'-\s*{label}[：:]\s*([\d.]+)\s*/\s*10\s*[—-]+\s*(.+)')
        d[key], d[key + '_note'] = (float(g[0]), g[1].strip()) if g else (None, '⚠️未解析')
    # 💰 block, parsed structurally (analyzer phrasing varies: "已披露：…", "Base $X已披露", …):
    # bullet 1 that isn't 目标/vs = the disclosed line; the 目标 bullet = the ask.
    block = []
    lines = text.splitlines()
    for i, l in enumerate(lines):
        if '建议目标年薪' in l:
            for follow in lines[i + 1:]:
                s = follow.strip()
                if not s or re.match(r'^\d+\.\s', s):
                    break
                if s.startswith('-'):
                    block.append(s.lstrip('- ').strip())
            break
    d['disclosed'] = next((b for b in block
                           if not b.startswith('目标') and not b.startswith('vs')), '未披露')
    d['ask'] = next((b for b in block if b.startswith('目标')), '')
    return d


# A money token INCLUDING its range tail — analyzers often write ranges (comma or
# K notation) where the second half carries no dollar sign of its own.
MONEY_RE = re.compile(r'\$\s*[\d][\d,.]*\s*[KkMm]?(?:\s*[–—-]\s*\$?[\d][\d,.]*\s*[KkMm]?)?')


def money_span(s, fallback_width=26):
    """Compress a salary sentence to its FIRST money range (base-band style)."""
    if '未披露' in s:
        return '未披露'
    amts = [re.sub(r'\s+', '', a) for a in MONEY_RE.findall(s)]
    if not amts:
        return clip(s, fallback_width) or '—'
    ranged = next((a for a in amts if re.search(r'[–—-]', a)), None)
    if ranged:
        return ranged
    return f"{amts[0]}–{amts[1]}" if len(amts) >= 2 else amts[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('names', nargs='+', help='company names or analysis file paths')
    ap.add_argument('--min-score', type=float, default=6.0)
    ap.add_argument('--width', type=int, default=60, help='max chars per note cell')
    ap.add_argument('--full', action='store_true',
                    help='also print each ≥min-score job\'s FULL analysis (verbatim from its '
                         'file, highest score first) before the chart — the complete '
                         'end-of-batch display in one deterministic call')
    args = ap.parse_args()

    jobs, missing = [], []
    for token in args.names:
        p = resolve(token)
        (jobs.append(parse(p)) if p else missing.append(token))

    jobs.sort(key=lambda d: -(d['score'] or 0))
    kept = [d for d in jobs if (d['score'] or 0) >= args.min_score]
    low = [d for d in jobs if (d['score'] or 0) < args.min_score]

    if args.full:
        for d in kept:
            print(f"{'━' * 30}\n▍{d['name']}\n")
            print(d['text'])
            print()
        if low:
            print('━' * 30)
            for d in low:
                reason = clip(d['fit_note'] if d['fit_note'] != '⚠️未解析' else d['verdict'],
                              args.width + 14)
                print(f"❌ {d['name']} {d['score']}/10 — {reason}（未入榜，不展开）")
            print()
        print('━' * 30)

    def cell(s, width):
        return clip(s, width).replace('|', '/')

    def num(v):
        return f"{v:g}" if v is not None else '?'

    print(f"📋 本批 {len(jobs)} 个分析汇总（按分排序）\n")
    print("| 公司 | ⭐ | 适配 | 薪资（披露 → 争取） | 风险 |")
    print("|---|---|---|---|---|")
    for d in kept:
        pay = f"{num(d['pay'])} · {money_span(d['disclosed'])} → 争 {money_span(d['ask'])}"
        print(f"| {d['name']} | **{num(d['score'])}** "
              f"| {num(d['fit'])} · {cell(d['fit_note'], args.width)} "
              f"| {cell(pay, args.width + 20)} "
              f"| {num(d['risk'])} · {cell(d['risk_note'], args.width)} |")
    if low:
        print(f"\n—— 未入榜（<{args.min_score:g}）——")
        for d in low:
            reason = clip(d['fit_note'] if d['fit_note'] != '⚠️未解析' else d['verdict'],
                          args.width + 14)
            print(f"❌ {d['name']} {d['score']}/10 — {reason}")
    if missing:
        print(f"\n⚠️ 找不到分析文件：{', '.join(missing)}（跳过件请主代理自行补一行原因）")


if __name__ == '__main__':
    main()
