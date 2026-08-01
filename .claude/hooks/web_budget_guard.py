#!/usr/bin/env python3
"""PreToolUse hook: hard budget on WebSearch/WebFetch calls per agent session.

Why: LLM-side "budget" instructions are soft — a runaway research agent can loop on
searches for half an hour. This hook counts web calls per session id (each subagent
carries its own id) and DENIES calls beyond the cap, telling the agent to wrap up
with what it has. Deterministic, harness-enforced, zero tokens.

Cap: WEB_BUDGET_MAX env var, default 40 — far above a normal analyzer run (~10–20)
but a hard stop for loops. Counters live in the system temp dir and expire after 24h,
so every new session starts fresh.
"""
import json
import os
import sys
import tempfile
import time

MAX = int(os.environ.get("WEB_BUDGET_MAX", "40"))
DIR = os.path.join(tempfile.gettempdir(), "claude-web-budget")


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return  # malformed input -> never block
    sid = str(payload.get("session_id") or "unknown")[:64]
    os.makedirs(DIR, exist_ok=True)
    now = time.time()
    # prune stale counters (>24h) so the dir never grows unbounded
    for f in os.listdir(DIR):
        p = os.path.join(DIR, f)
        try:
            if now - os.path.getmtime(p) > 86400:
                os.remove(p)
        except OSError:
            pass
    path = os.path.join(DIR, sid)
    try:
        count = int(open(path).read().strip() or 0)
    except (OSError, ValueError):
        count = 0
    count += 1
    try:
        with open(path, "w") as f:
            f.write(str(count))
    except OSError:
        return  # can't track -> never block
    if count > MAX:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"Web budget exhausted for this agent session ({count - 1}/{MAX} "
                    f"WebSearch/WebFetch calls used). STOP searching — synthesize and "
                    f"return your findings from what you already gathered, and state "
                    f"honestly which areas you could not cover."),
            }
        }))


if __name__ == "__main__":
    main()
