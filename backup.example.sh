#!/bin/zsh
# backup.example.sh — back up your gitignored personal data OUTSIDE git.
#
# This workspace keeps personal data (profile.local.md, job-scoreboard.md,
# job-analyses/, application-kit.md, …) out of git by design — which also means
# git is NOT backing it up. This script mirrors the whole workspace, including
# those gitignored files, into a cloud-synced folder.
#
# The one rule that makes this safe: a LIVE git repo must not sit inside a
# cloud-synced folder (iCloud/Dropbox/OneDrive touching .git mid-operation
# causes corruption — and on macOS, repos under ~/Desktop or ~/Documents also
# hit random "Operation not permitted" failures from per-app privacy grants).
# So the live repo lives in a plain folder like ~/dev, and only rsync COPIES
# land in the synced destination.
#
# Setup:
#   1. cp backup.example.sh ~/backup.sh && chmod +x ~/backup.sh
#      (run the copy from outside the repo; this file is just the template)
#   2. Edit SRC_ROOT / REPOS / DEST below.
#   3. Schedule it daily: launchd (macOS), cron, or a systemd timer.
#
# .git is excluded — commits are already backed up on your git remote.
# No --delete: files you remove locally stay recoverable in the mirror.

set -euo pipefail

# Parent dir holding your repo(s), and which of them to back up:
SRC_ROOT="$HOME/dev"
REPOS=(my-jobhunt-workspace)   # e.g. (jobhunt leetcode side-project)

# Destination — any cloud-synced folder works:
DEST="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Backup/dev-mirror"   # iCloud (macOS)
# DEST="$HOME/Dropbox/Backup/dev-mirror"

mkdir -p "$DEST"

# If you use the dual-repo model (pgit.sh — a local-only personal git layer),
# take a version snapshot before mirroring; the .personal-git history rides
# along into the cloud mirror as off-site disaster recovery.
# "$SRC_ROOT/<your-workspace>/pgit.sh" snapshot || true

for repo in "${REPOS[@]}"; do
  src="$SRC_ROOT/$repo"
  [ -d "$src" ] || continue
  rsync -a \
    --exclude '.git' \
    --exclude '__pycache__/' \
    --exclude '.DS_Store' \
    --exclude 'node_modules/' \
    "$src/" "$DEST/$repo/"
done

# The script itself lives outside the repos — keep a copy of it in the mirror
# too, so the whole recovery story is self-contained.
rsync -a "$0" "$DEST/"

echo "$(date '+%Y-%m-%d %H:%M:%S') backup ok" >> "$SRC_ROOT/.backup.log"
