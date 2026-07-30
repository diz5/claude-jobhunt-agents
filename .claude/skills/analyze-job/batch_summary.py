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


def first_amounts(s, width):
    """Salary text: cut citations/parens, keep the money part readable."""
    s = re.sub(r'（[^）]*来源[^）]*）|（[^）]*\[[^）]*）', '', s)  # drop source parens
    s = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', s)              # md links → text
    return clip(s, width)


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
    g = grab(r'-\s*(已披露[：:].+|未披露.+)')
    d['disclosed'] = g[0].strip() if g else '⚠️未解析'
    g = grab(r'-\s*(目标\s*base.+)')
    d['ask'] = g[0].strip() if g else '⚠️未解析'
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('names', nargs='+', help='company names or analysis file paths')
    ap.add_argument('--min-score', type=float, default=6.0)
    ap.add_argument('--width', type=int, default=46, help='max chars per note line')
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

    print(f"📋 本批 {len(jobs)} 个分析汇总（按分排序）")
    for i, d in enumerate(kept):
        tag = CIRCLED[i] if i < len(CIRCLED) else f'({i + 1})'
        print(f"\n{tag} {d['name']} ⭐{d['score']}")
        print(f"   适配 {d['fit']} ｜ {clip(d['fit_note'], args.width)}")
        disclosed = first_amounts(re.sub(r'^已披露[：:]\s*', '', d['disclosed']), args.width + 14)
        ask = first_amounts(re.sub(r'^目标\s*', '', d['ask']), args.width + 14)
        print(f"   薪资 {d['pay']} ｜ 披露 {disclosed}")
        print(f"          → 争取 {ask}")
        print(f"   风险 {d['risk']} ｜ {clip(d['risk_note'], args.width)}")
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
