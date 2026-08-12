#!/bin/sh
# pgit — git wrapper for the PERSONAL data layer of this workspace.
#
# Two git layers share this working directory (dotfiles bare-repo pattern):
#   .git           the public toolkit repo (origin = GitHub) — tracks tooling only
#   .personal-git  the personal layer — tracks ONLY the personal paths listed
#                  below and has NO remote, so personal data physically cannot
#                  be pushed anywhere.
#
# Why force-add: the shared root .gitignore excludes all personal files (so the
# PUBLIC repo can never take them), and git cannot re-include files under an
# excluded directory. The personal layer therefore adds its files with -f,
# scoped strictly to the whitelist below — tooling files are never touched.
#
# Usage:
#   ./pgit.sh snapshot          # stage whitelist + commit "snapshot <date>" (no-op when clean)
#   ./pgit.sh log --oneline     # any other git command passes through
#   ./pgit.sh diff / status / checkout -- <file> ...

ROOT="$(cd "$(dirname "$0")" && pwd)"
PGIT="git --git-dir=$ROOT/.personal-git --work-tree=$ROOT"

# ── PERSONAL WHITELIST — the explicit audit list of personal data here ──
# (paths relative to the repo root; directories are included recursively)
PERSONAL_PATHS="
profile.local.md
IDEAS.local.md
dev-log.local.md
cmu-self-study.local.md
inbox.job-hun-sanjose.local.md
.secrets.local
job-scoreboard.md
job-analyses
application-kit.md
.board-state.json
.status-history.json
.merge-log.md
interview-prep
applications
.linkedin-seen.db
.linkedin-referral.db
referral-companies.md
referral-queue.md
blocked-companies.md
resumes
session-helper
.claude/settings.local.json
.claude/skills/pipeline-chart
"

# noise never worth versioning (unstaged again after every add)
NOISE="*.db-wal *.db-shm .DS_Store */.DS_Store job-scoreboard.md.bak* __pycache__"

if [ "$1" = "snapshot" ]; then
    for p in $PERSONAL_PATHS; do
        [ -e "$ROOT/$p" ] && $PGIT add -Af -- "$p"
    done
    # shellcheck disable=SC2086
    $PGIT rm -r --cached -q --ignore-unmatch -- $NOISE 2>/dev/null
    if $PGIT diff --cached --quiet 2>/dev/null && $PGIT rev-parse -q --verify HEAD >/dev/null; then
        echo "pgit: nothing new to snapshot"
    else
        $PGIT commit -q -m "snapshot $(date +%F' '%H:%M)"
        echo "pgit: committed snapshot $(date +%F' '%H:%M) — $($PGIT ls-files | wc -l | tr -d ' ') file(s) tracked"
    fi
    exit 0
fi

exec $PGIT "$@"
