#!/usr/bin/env python3
import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys

DEFAULT_WRITE_VERBS = [
    "create", "update", "delete", "write", "insert", "upsert", "set", "put",
    "patch", "remove", "drop", "truncate", "execute", "exec", "run", "publish",
    "produce", "send", "merge", "flush", "del", "expire", "rename", "alter",
]

PROTECTED_BRANCHES = {"main", "master"}
OPERATOR_CHARS = set(";&|()\n")
REDIRECTS = {"<", ">", ">>", "<<", "<<<", ">&", "<&", "&>", "&>>", ">|"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
WRAPPERS = {"sudo", "doas", "env", "command", "builtin", "exec", "nohup", "time", "nice", "xargs"}
WRAPPER_OPTS_WITH_VALUE = {"-u", "-g", "-C", "-n", "-I", "-L", "-P", "-s"}
GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env", "--super-prefix"}
PUSH_OPTS_WITH_VALUE = {"-o", "--push-option", "--receive-pack", "--exec", "--repo"}
GH_OPTS_WITH_VALUE = {"-R", "--repo", "--hostname"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
HEREDOC = re.compile(
    r"<<-?\s*(?P<q>['\"]?)(?P<tag>\w+)(?P=q)(?P<rest>[^\n]*)\n(?P<body>.*?)\n[ \t]*(?P=tag)[ \t]*(?=\n|$)",
    re.DOTALL,
)
MAX_DEPTH = 5
BRACE = re.compile(r"\{([^{}]*,[^{}]*)\}")
# Plugin agents arrive as "<plugin>:<agent>"; a bare name could be any user or project agent.
HOLDOUT_AGENTS = {"moth:moth-scenario-writer", "moth:moth-verifier"}
# The holdout check stops accidental reads (a project-wide grep, a cat of the folder) and the
# common evasions. It is not a sandbox: an interpreter one-liner that builds the path at run
# time (python -c "open('.mo'+'th/...')") still gets through. The skills forbid that outright.
HOLDOUT_SAFE = re.compile(r"/(system\.yaml|guard\.json|knowledge(/[^*?\[]*)?)", re.IGNORECASE)
MOTH_REF = re.compile(r"\.moth([^\s'\";|&()<>`]*)", re.IGNORECASE)
ALWAYS_RECURSIVE = {"find", "tree", "du", "rsync", "tar", "zip", "rgrep", "ack"}
RECURSIVE_FLAGS = {"grep": "rR", "egrep": "rR", "fgrep": "rR", "ls": "R", "cp": "rRa", "scp": "r"}
UNIGNORE_READERS = {"rg", "ag", "ack"}
PATTERN_FIRST = {"grep", "egrep", "fgrep", "rgrep", "rg", "ag", "ack"}
holdout_dir = None  # set in main() when the caller may not see the holdout scenarios
SENSITIVE_VERBS = {"push", "merge"}
UNVERIFIABLE = re.compile(r"[$`{}*?\[~]")
GIT_BUILTINS = {
    "add", "am", "apply", "bisect", "blame", "branch", "cat-file", "checkout", "cherry-pick",
    "clean", "clone", "commit", "commit-tree", "config", "describe", "diff", "fetch",
    "for-each-ref", "format-patch", "gc", "grep", "hash-object", "help", "init", "log",
    "ls-files", "ls-remote", "ls-tree", "merge", "merge-base", "mv", "notes", "pull", "read-tree",
    "rebase", "reflog", "remote", "reset", "restore", "rev-list", "rev-parse", "revert", "rm",
    "shortlog", "show", "stash", "status", "submodule", "switch", "symbolic-ref", "tag",
    "update-index", "version", "worktree", "write-tree",
}


class Denied(Exception):
    pass


def program(word):
    return os.path.basename(word).lower()


def drop_data_heredocs(command):
    def replace(match):
        line_start = command.rfind("\n", 0, match.start()) + 1
        feeder = strip_wrappers(command[line_start:match.start()].split())
        runs_body = bool(feeder) and program(feeder[0]) in SHELLS
        body = f"\n{match.group('body')}" if runs_body else ""
        return f"{match.group('rest')}{body}\n"

    return HEREDOC.sub(replace, command)


def tokenize(command):
    text = drop_data_heredocs(command.replace("\\\n", "")).replace("`", "\n")
    try:
        return _lex(text)
    except ValueError:
        tokens = []
        for line in text.split("\n"):
            try:
                tokens.extend(_lex(line))
            except ValueError:
                tokens.extend(line.split())
            tokens.append("\n")
        return tokens


def _lex(text):
    lexer = shlex.shlex(text, posix=True, punctuation_chars=";&|()<>\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def simple_commands(tokens):
    words, skip_next = [], False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if set(token) <= OPERATOR_CHARS:
            if words:
                yield words
            words = []
        elif token in REDIRECTS:
            skip_next = True
        else:
            words.append(token)
    if words:
        yield words


def strip_wrappers(words):
    while words:
        if ASSIGNMENT.match(words[0]):
            words = words[1:]
        elif program(words[0]) in WRAPPERS:
            words = words[1:]
            while words and words[0].startswith("-"):
                takes_value = words[0] in WRAPPER_OPTS_WITH_VALUE
                words = words[2:] if takes_value else words[1:]
        else:
            return words
    return words


def current_branch(cwd):
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "symbolic-ref", "--short", "-q", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def normalize_branch(ref):
    return ref.removeprefix("refs/heads/")


def check_push(args, cwd):
    positional, i = [], 0
    while i < len(args):
        arg = args[i]
        if arg in PUSH_OPTS_WITH_VALUE:
            i += 2
            continue
        if arg.startswith("--"):
            name = arg.split("=")[0]
            if name in ("--force", "--force-with-lease"):
                raise Denied("force push is not allowed")
            if name in ("--mirror", "--all", "--branches"):
                raise Denied(f"`git push {name}` would push main/master")
        elif arg.startswith("-") and len(arg) > 1:
            if "f" in arg[1:]:
                raise Denied("force push is not allowed")
        else:
            positional.append(arg)
        i += 1

    if any(UNVERIFIABLE.search(p) for p in positional):
        raise Denied("push target uses shell expansion ($, {}, *, ~); name the branch literally")

    refspecs = positional[1:]
    if any(r.startswith("+") for r in refspecs):
        raise Denied("force push is not allowed")

    targets = []
    if not refspecs:
        targets.append(None)
    for refspec in refspecs:
        src, _, dst = refspec.lstrip("+").partition(":")
        target = dst if dst else src
        targets.append(None if target in ("HEAD", "@") else target)

    for target in targets:
        if target is None:
            target = current_branch(cwd)
            if target is None:
                raise Denied("cannot determine the branch this push targets; name it explicitly")
        if normalize_branch(target) in PROTECTED_BRANCHES:
            raise Denied("pushing to main/master is not allowed")


def git_alias(cwd, name):
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "config", "--get", f"alias.{name}"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def check_git(words, cwd, depth):
    inline_aliases, i = {}, 1
    while i < len(words) and words[i].startswith("-"):
        opt = words[i]
        if opt in GIT_OPTS_WITH_VALUE:
            value = words[i + 1] if i + 1 < len(words) else ""
            if opt == "-C":
                cwd = os.path.join(cwd, value)
            elif opt == "-c" and value.startswith("alias."):
                name, _, expansion = value[len("alias."):].partition("=")
                inline_aliases[name] = expansion
            i += 2
        else:
            i += 1
    if i >= len(words):
        return
    sub, rest = words[i], words[i + 1:]
    if UNVERIFIABLE.search(sub):
        raise Denied("git subcommand uses shell expansion; name it literally")
    if sub == "push":
        check_push(rest, cwd)
        return
    if sub in GIT_BUILTINS:
        return
    alias = inline_aliases.get(sub) or git_alias(cwd, sub)
    if not alias:
        return
    if depth >= MAX_DEPTH:
        raise Denied("git alias nests too deeply to check")
    if alias.startswith("!"):
        check_command(" ".join([alias[1:], *map(shlex.quote, rest)]), cwd, depth + 1)
    else:
        check_git(["git", *shlex.split(alias), *rest], cwd, depth + 1)


def check_gh(words):
    rest, i = [], 1
    while i < len(words):
        if words[i] in GH_OPTS_WITH_VALUE:
            i += 2
            continue
        rest.append(words[i])
        i += 1
    if rest[:2] == ["pr", "merge"]:
        raise Denied("merging is a human decision")
    if rest[:1] == ["api"] and any(re.search(r"pulls/\d+/merge\b", w) for w in rest):
        raise Denied("merging is a human decision")


def check_holdout_text(text):
    for match in MOTH_REF.finditer(text):
        suffix = match.group(1)
        if ".." in suffix or "\\" in suffix or not HOLDOUT_SAFE.fullmatch(suffix):
            raise Denied(".moth/ holds the holdout scenarios; only system.yaml, guard.json and knowledge/ are open to you")


def expand_braces(word, limit=64):
    words = [word]
    while any(BRACE.search(w) for w in words) and len(words) < limit:
        expanded = []
        for w in words:
            m = BRACE.search(w)
            if not m:
                expanded.append(w)
                continue
            expanded += [w[:m.start()] + alt + w[m.end():] for alt in m.group(1).split(",")]
        words = expanded
    return words


def may_expand_to_moth(word):
    """True if a glob or brace word could expand to a .moth path (.mo*, .{moth,x}, {.moth,x}).

    Like the shell, a wildcard never matches the leading dot, so only parts that start
    with a literal "." can reach .moth; src/**/*.go stays allowed.
    """
    if not re.search(r"[*?\[{]", word):
        return False
    for candidate in expand_braces(word.casefold()):
        for part in candidate.split("/"):
            if part.startswith(".") and fnmatch.fnmatchcase(".moth", part):
                return True
    return False


def inside(path, directory):
    # casefold: macOS and Windows file systems ignore case, so .MOTH/Scenarios is the same folder
    path = os.path.realpath(path).casefold()
    directory = os.path.realpath(directory).casefold()
    return path == directory or path.startswith(directory + os.sep)


def reads_recursively(name, args):
    if name in ALWAYS_RECURSIVE:
        return True
    options = [a for a in args if a.startswith("-")]
    if name in UNIGNORE_READERS:
        return any(a in ("-u", "-uu", "-uuu", "--hidden", "-.") or a.startswith("--no-ignore") for a in options)
    flags = RECURSIVE_FLAGS.get(name, "")
    return any(a in ("--recursive", "--dereference-recursive", "--archive")
               or (not a.startswith("--") and any(f in a[1:] for f in flags)) for a in options)


def check_holdout_words(name, args, cwd):
    if name == "git" and "grep" in args and any(a in ("--no-index", "--no-exclude-standard", "--untracked") for a in args):
        raise Denied("git grep over untracked/ignored files would read .moth/scenarios/; search tracked files only")
    if not reads_recursively(name, args):
        return
    if name == "find":
        targets = []
        for a in args:
            if a.startswith(("-", "(", "!")):
                break
            targets.append(a)
    else:
        targets = [a for a in args if not a.startswith("-")]
    if name in PATTERN_FIRST and targets and not any(a in ("-e", "-f", "--regexp", "--file") for a in args):
        targets = targets[1:]
    for target in targets or ["."]:
        base = os.path.join(cwd, os.path.expanduser(target.split("*")[0].split("?")[0].split("[")[0] or "."))
        if inside(holdout_dir, base):
            raise Denied(f"'{name}' would read .moth/scenarios/ recursively; narrow the path or exclude .moth")


def check_simple(words, cwd, depth):
    words = strip_wrappers(words)
    if not words:
        return cwd
    name = program(words[0])
    if holdout_dir:
        # words are already unquoted, so .mo''th and .mo\\th show up as .moth here
        for word in words:
            check_holdout_text(word)
            if may_expand_to_moth(word):
                raise Denied("this glob or quoting could expand to .moth/; name the path literally")
        check_holdout_words(name, words[1:], cwd)
    if UNVERIFIABLE.search(name) and any(w.lower() in SENSITIVE_VERBS for w in words[1:]):
        raise Denied("command name uses shell expansion; name the program literally")

    if name == "cd" and len(words) > 1:
        return os.path.join(cwd, os.path.expanduser(words[1]))
    if name == "eval":
        check_command(" ".join(words[1:]), cwd, depth + 1)
    elif name in SHELLS:
        for j, word in enumerate(words[1:-1], start=1):
            if re.fullmatch(r"-[a-zA-Z]*c[a-zA-Z]*", word):
                check_command(words[j + 1], cwd, depth + 1)
                break
    elif name == "git":
        check_git(words, cwd, depth)
    elif name == "gh":
        check_gh(words)
    return cwd


def check_command(command, cwd, depth=0):
    if depth > MAX_DEPTH:
        raise Denied("command nests shells too deeply to check")
    for words in simple_commands(tokenize(command)):
        cwd = check_simple(words, cwd, depth)


def find_guard(project_dir):
    """Finds .moth/guard.json in project_dir or a parent, up to the git top level.

    moth-init puts .moth/ at the git top level, but Claude Code may be started
    in a subdirectory of the repo (CLAUDE_PROJECT_DIR is then that subdirectory).
    """
    directory = os.path.abspath(project_dir)
    while True:
        path = os.path.join(directory, ".moth", "guard.json")
        if os.path.isfile(path):
            return path
        parent = os.path.dirname(directory)
        if os.path.exists(os.path.join(directory, ".git")) or parent == directory:
            return None
        directory = parent


def load_guard(project_dir):
    path = find_guard(project_dir)
    if path is None:
        return None
    with open(path) as f:
        guard = json.load(f)
    if not isinstance(guard, dict):
        raise ValueError("guard.json must contain a JSON object")
    return guard


def deny(reason):
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"Moth guardrail: {reason}",
        }
    }, sys.stdout)
    sys.exit(0)


def check_bash(command, guard, cwd=None):
    try:
        if holdout_dir:
            check_holdout_text(command)
            if "$'" in command:
                raise Denied("$'...' quoting can hide a .moth path; write the path literally")
        check_command(command, cwd or os.getcwd())
    except Denied as denied:
        deny(str(denied))
    for rule in guard.get("bash_deny", []):
        if re.search(rule["pattern"], command):
            deny(rule.get("reason", f"command matches denied pattern {rule['pattern']}"))


def mcp_server_matches(tool_name, server):
    escaped = re.escape(server)
    return re.match(rf"^mcp__({escaped}|plugin_.+_{escaped})__", tool_name) is not None


def check_mcp(tool_name, guard):
    verbs = guard.get("write_verbs")
    if not isinstance(verbs, list):
        verbs = DEFAULT_WRITE_VERBS
    action = tool_name.rsplit("__", 1)[-1].lower()
    is_write = any(re.search(rf"(^|[_-]){re.escape(v)}([_-]|$)", action) for v in verbs)
    if not is_write:
        return
    for server in guard.get("read_only_mcp", []):
        if mcp_server_matches(tool_name, server):
            deny(f"MCP server '{server}' is read-only (staging/prod); '{action}' looks like a write")


def holdout_allowed(payload):
    return payload.get("agent_type") in HOLDOUT_AGENTS


def check_file_tool(tool_name, tool_input, cwd):
    keys = ["file_path", "notebook_path", "path", "glob"] + (["pattern"] if tool_name == "Glob" else [])
    for key in keys:
        value = tool_input.get(key)
        if not isinstance(value, str) or not value:
            continue
        if may_expand_to_moth(value):
            deny("this pattern could match .moth/; name the path literally")
        try:
            check_holdout_text(value)
        except Denied as denied:
            deny(str(denied))
        if key != "glob" and inside(os.path.join(cwd, os.path.expanduser(value)), holdout_dir):
            deny(".moth/scenarios/ is the holdout; only the scenario writer and the verifier read it")


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        payload = None
    cwd = (payload or {}).get("cwd") or os.getcwd()
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or cwd

    try:
        guard = load_guard(project_dir)
    except (OSError, ValueError) as err:
        deny(f"cannot read .moth/guard.json ({err}); fix it or run /moth:moth-init --sync")
    if guard is None:
        sys.exit(0)
    if payload is None:
        deny("unreadable hook input; denying to stay safe")

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    global holdout_dir
    if not holdout_allowed(payload):
        holdout_dir = os.path.join(os.path.dirname(os.path.dirname(find_guard(project_dir))), ".moth", "scenarios")
    try:
        if tool_name == "Bash":
            check_bash(tool_input.get("command", ""), guard, cwd)
        elif tool_name.startswith("mcp__"):
            check_mcp(tool_name, guard)
        elif holdout_dir and isinstance(tool_input, dict):
            check_file_tool(tool_name, tool_input, cwd)
    except SystemExit:
        raise
    except Exception as err:
        deny(f"guard failed ({type(err).__name__}: {err}); denying to stay safe")
    sys.exit(0)


if __name__ == "__main__":
    main()
