#!/usr/bin/env python3
"""Publish guard — fail if any git-TRACKED file contains personal/sensitive data.

Run before committing/pushing a public repo. It scans only files git actually
tracks (i.e. what would go public), for:
  - generic PII shapes (home paths, emails, salary figures, immigration status)
  - user-specific literal tokens read from a gitignored `.secrets.local`
    (so THIS committed script never contains the real secrets)
It also checks that `.gitignore` covers the required local-only paths.

Exit 0 = safe to publish. Non-zero = something leaks (or .gitignore is incomplete).

Design note: mechanical scan = code; a `publish-guard` agent wraps this and adds a
fuzzy judgment pass for anything the patterns miss.
"""
import os
import re
import subprocess
import sys

REQUIRED_IGNORES = [
    "profile.local.md", ".secrets.local", "job-scoreboard.md", "job-analyses/",
    "application-kit.md", "applications/", ".linkedin-seen.db", "referral-companies.md",
    ".claude/settings.local.json", "*.pdf", "*.docx",
]

GENERIC_PATTERNS = [
    (re.compile(r"/Users/[A-Za-z0-9._-]+"), "absolute home path"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "email address"),
    (re.compile(r"\$\s?1?\d{2},\d{3}\b"), "salary figure"),
    (re.compile(r"\$\s?\d{2,3}\s?[Kk]\b"), "salary figure (K)"),
    (re.compile(r"green\s*card|绿卡", re.I), "immigration status"),
]

TEXT_EXT = (".md", ".py", ".json", ".txt", ".html", ".yml", ".yaml", ".sh", ".js", ".ts")
SELF = os.path.basename(__file__)


def tracked_files(root):
    r = subprocess.run(["git", "-C", root, "ls-files"], capture_output=True, text=True)
    return [f for f in r.stdout.splitlines() if f]


def load_secret_tokens(root):
    p = os.path.join(root, ".secrets.local")
    toks = []
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            t = line.strip()
            if t and not t.startswith("#"):
                toks.append(t)
    return toks


def missing_ignores(root):
    """Which REQUIRED_IGNORES are NOT actually ignored — checked with real git semantics
    (git check-ignore), so a glob like *.local.md correctly covers profile.local.md."""
    probes = {"*.pdf": "sample.pdf", "*.docx": "sample.docx"}
    missing = []
    for e in REQUIRED_IGNORES:
        if e in probes:
            probe = probes[e]
        elif e.endswith("/"):
            # A dir-only pattern (`foo/`) only matches via git check-ignore when the dir
            # exists on disk; probe a child path so it verifies even in a clean checkout.
            probe = e + "__probe__"
        else:
            probe = e
        rc = subprocess.run(["git", "-C", root, "check-ignore", "-q", probe]).returncode
        if rc != 0:  # 0 = ignored, 1 = NOT ignored
            missing.append(e)
    return missing


def is_example(f):
    return ".example." in f or f.startswith("examples/") or f.endswith("profile.example.md")


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    files = tracked_files(root)
    if not files:
        print("no git-tracked files yet — run `git add` first, then re-run.")
        return 0

    tokens = load_secret_tokens(root)
    token_pats = [(re.compile(re.escape(t), re.I), f"secret token: {t}") for t in tokens]

    findings = []
    for f in files:
        if f == SELF or is_example(f):
            continue
        if f.endswith((".pdf", ".docx", ".doc")):
            findings.append((f, 0, "tracked resume/binary doc — should be gitignored"))
            continue
        if not f.endswith(TEXT_EXT):
            continue
        try:
            lines = open(os.path.join(root, f), encoding="utf-8", errors="ignore").readlines()
        except Exception:
            continue
        for i, l in enumerate(lines, 1):
            for rx, why in GENERIC_PATTERNS + token_pats:
                m = rx.search(l)
                if not m:
                    continue
                if why == "email address" and m.group(0).lower().endswith(
                    ("example.com", "example.org", "example.net")):
                    continue  # fictional sample email is fine
                findings.append((f, i, why))

    missing = missing_ignores(root)

    print(f"scanned {len(files)} tracked files · secret tokens loaded: {len(tokens)}")
    if missing:
        print("❌ .gitignore missing entries:", missing)
    if findings:
        print(f"❌ {len(findings)} potential leak(s):")
        for f, i, why in findings[:60]:
            print(f"   {f}:{i}  {why}")
    if not findings and not missing:
        print("✅ PASS — no personal data in tracked files; .gitignore covers all secrets.")
        return 0
    print("\n⛔ NOT safe to publish yet — fix the above, re-run.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
