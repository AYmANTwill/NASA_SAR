#!/usr/bin/env python3
"""PreToolUse hook for the Bash tool: Claude Code must never write git history.

Claude Code sends the pending tool call as JSON on stdin. Exit code 2 blocks the
call and the stderr text is shown to Claude as the reason. Exit code 0 lets it run.
Humans commit by hand; this hook only stops Claude.
"""
import json
import re
import sys

GIT_OPTS = r"(?:\s+(?:-C\s+\S+|-c\s+\S+|--[\w-]+(?:=\S+)?|-\w+))*"
BLOCKED = [
    # anything that creates, moves, rewrites or publishes commits
    (rf"\bgit{GIT_OPTS}\s+(commit|commit-tree|merge|rebase|cherry-pick|revert|am|pull|push|tag|"
     r"update-ref|filter-branch|filter-repo|replace|notes)\b", "writes git history"),
    (rf"\bgit{GIT_OPTS}\s+reset\b[^;&|\n]*--(hard|soft|merge|keep)\b", "moves HEAD / discards work"),
    (rf"\bgit{GIT_OPTS}\s+clean\b[^;&|\n]*\s-\w*f", "deletes untracked files"),
    (rf"\bgit{GIT_OPTS}\s+(branch|checkout|switch)\b[^;&|\n]*\s-(D|B|C)\b", "force-overwrites a branch"),
    (r"\bgh\s+pr\s+(merge|create)\b", "creates or merges a pull request"),
    (r"\bgh\s+repo\s+sync\b", "rewrites a branch"),
]

def main() -> int:
    raw = sys.stdin.read()
    try:
        cmd = json.loads(raw).get("tool_input", {}).get("command", "") or ""
    except Exception:
        cmd = raw  # unreadable input: still scan the raw text, never crash open
    for pattern, why in BLOCKED:
        m = re.search(pattern, cmd)
        if m:
            sys.stderr.write(
                f"BLOCKED by project policy (.claude/hooks/guard_git.py): `{m.group(0).strip()}` {why}.\n"
                "In this repository only humans commit, push, merge or rewrite history.\n"
                "Do not retry or work around this. Stop and give the user the exact command "
                "to run themselves (for commits: an explicit `git add <files>` list and a commit message).\n"
            )
            return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
