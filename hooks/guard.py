#!/usr/bin/env python3
import json
import os
import re
import sys

DEFAULT_WRITE_VERBS = [
    "create", "update", "delete", "write", "insert", "upsert", "set", "put",
    "patch", "remove", "drop", "truncate", "execute", "exec", "run", "publish",
    "produce", "send", "merge", "flush", "del", "expire", "rename", "alter",
]

PROTECTED_BRANCHES = {"main", "master"}
FORCE_FLAGS = {"--force", "--force-with-lease", "-f"}
SEGMENT_SPLIT = re.compile(r"&&|\|\||[;|\n]")
COMMAND_PREFIX = r"^\s*(?:\S+=\S+\s+)*"
GIT_PUSH = re.compile(COMMAND_PREFIX + r"git(?:\s+-C\s+\S+)?\s+push\b(.*)$")
GH_PR_MERGE = re.compile(COMMAND_PREFIX + r"gh\s+pr\s+merge\b")


def segments(command):
    return SEGMENT_SPLIT.split(command)


def git_push_args(command):
    for segment in segments(command):
        match = GIT_PUSH.match(segment)
        if match:
            yield match.group(1).split()


def pushes_protected_branch(args):
    refspecs = [a for a in args if not a.startswith("-")][1:]
    for refspec in refspecs:
        target = refspec.lstrip("+").split(":")[-1]
        if target.removeprefix("refs/heads/") in PROTECTED_BRANCHES:
            return True
    return False


def check_git_push(command):
    for args in git_push_args(command):
        if any(a.split("=")[0] in FORCE_FLAGS or a.startswith("+") for a in args):
            deny("force push is not allowed")
        if pushes_protected_branch(args):
            deny("pushing to main/master is not allowed")


def load_guard(project_dir):
    path = os.path.join(project_dir, ".moth", "guard.json")
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        return json.load(f)


def deny(reason):
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"Moth guardrail: {reason}",
        }
    }, sys.stdout)
    sys.exit(0)


def check_bash(command, guard):
    check_git_push(command)
    if any(GH_PR_MERGE.match(segment) for segment in segments(command)):
        deny("merging is a human decision")
    for rule in guard.get("bash_deny", []):
        if re.search(rule["pattern"], command):
            deny(rule.get("reason", f"command matches denied pattern {rule['pattern']}"))


def mcp_server_matches(tool_name, server):
    escaped = re.escape(server)
    return re.match(rf"^mcp__({escaped}|plugin_.+_{escaped})__", tool_name) is not None


def check_mcp(tool_name, guard):
    verbs = guard.get("write_verbs", DEFAULT_WRITE_VERBS)
    action = tool_name.rsplit("__", 1)[-1].lower()
    is_write = any(re.search(rf"(^|[_-]){re.escape(v)}([_-]|$)", action) for v in verbs)
    if not is_write:
        return
    for server in guard.get("read_only_mcp", []):
        if mcp_server_matches(tool_name, server):
            deny(f"MCP server '{server}' is read-only (staging/prod); '{action}' looks like a write")


def main():
    payload = json.load(sys.stdin)
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    guard = load_guard(project_dir)
    if guard is None:
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    if tool_name == "Bash":
        check_bash(tool_input.get("command", ""), guard)
    elif tool_name.startswith("mcp__"):
        check_mcp(tool_name, guard)
    sys.exit(0)


if __name__ == "__main__":
    main()
