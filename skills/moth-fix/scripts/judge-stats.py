#!/usr/bin/env python3
"""Usage:
  judge-stats.py [.moth/metrics.jsonl] [--gh]

Measures what the independent judge adds, from the one-line-per-run log that
moth-fix and moth-retest append to .moth/metrics.jsonl.

  catch      the fixer's own tests were green, but the judge said "not
             satisfied" in round 1. The judge saw something the tests missed.
  confirmed  a catch that later passed the judge and whose PR was merged
             (needs --gh): a human accepted the fix the judge pushed for.
  miss       the judge passed a fix, but a later retest of the same ticket
             came back broken, or its PR was closed without merging (--gh).

--gh looks up each PR's state with `gh pr view`. Without it, PR outcomes
are left out.

Exit codes: 0 printed a summary, 2 no log or no usable lines.
"""
import argparse
import json
import subprocess
import sys

NOT_SATISFIED = "not-satisfied"
SATISFIED = "satisfied"


def load(path):
    try:
        with open(path) as f:
            lines = f.readlines()
    except OSError as err:
        print(f"Can't read {path}: {err}", file=sys.stderr)
        sys.exit(2)
    records = []
    for n, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            print(f"warning: line {n} is not JSON, skipped", file=sys.stderr)
            continue
        if isinstance(record, dict) and record.get("kind") in ("fix", "retest"):
            records.append(record)
    return records


def pr_state(url):
    try:
        out = subprocess.run(["gh", "pr", "view", url, "--json", "state", "-q", ".state"],
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def outcome(prs, lookup):
    """MERGED if any PR merged, CLOSED if all closed, OPEN otherwise; None if unknown."""
    states = [lookup(url) for url in prs]
    states = [s for s in states if s]
    if not states:
        return None
    if "MERGED" in states:
        return "MERGED"
    if all(s == "CLOSED" for s in states):
        return "CLOSED"
    return "OPEN"


def pct(part, whole):
    return f"{part}/{whole} ({part * 100 // whole}%)" if whole else "0/0"


def summarize(records, lookup=None):
    fixes = [r for r in records if r["kind"] == "fix" and r.get("rounds")]
    retests = [r for r in records if r["kind"] == "retest"]
    green = [r for r in fixes if r.get("own_tests_green")]
    catches = [r for r in green if r["rounds"][0].get("verdict") == NOT_SATISFIED]
    caught_then_passed = [r for r in catches if any(x.get("verdict") == SATISFIED for x in r["rounds"][1:])]
    passed = [r for r in fixes if r["rounds"][-1].get("verdict") == SATISFIED]
    rounds = {}
    for r in fixes:
        rounds[len(r["rounds"])] = rounds.get(len(r["rounds"]), 0) + 1

    broken_later = {r["ticket"] for r in retests if r.get("verdict") == "broken"}
    misses = [r for r in passed if r["ticket"] in broken_later]

    lines = ["## Judge stats", ""]
    if not fixes and not retests:
        lines.append("No runs with a judge verdict yet.")
        return "\n".join(lines)

    lines += [
        "**What the judge caught**",
        f"- Fix runs judged: {len(fixes)}",
        f"- Catches (own tests green, judge said no in round 1): {pct(len(catches), len(green))}",
        f"- Catches fixed in a later round: {pct(len(caught_then_passed), len(catches))}",
        "- Rounds: " + ", ".join(f"{k} round{'s' if k > 1 else ''} × {v}" for k, v in sorted(rounds.items())),
        "",
        "**Did the judge get it right**",
        f"- Judge passed, retest later broken (miss): {pct(len(misses), len(passed))}",
    ]

    if lookup:
        states = {id(r): outcome(r.get("prs") or [], lookup) for r in fixes}
        known = [r for r in fixes if states[id(r)] in ("MERGED", "CLOSED")]
        confirmed = [r for r in caught_then_passed if states[id(r)] == "MERGED"]
        closed_after_pass = [r for r in passed if states[id(r)] == "CLOSED"]
        lines += [
            f"- Catches confirmed by a merged PR: {pct(len(confirmed), len(caught_then_passed))}",
            f"- Judge passed, PR closed unmerged (possible miss): {pct(len(closed_after_pass), len(passed))}",
            f"- PRs with a final state: {len(known)}/{len(fixes)}",
        ]
    else:
        lines.append("- PR outcomes: run with `--gh` to check merged / closed")

    if retests:
        retest_catches = [r for r in retests if r.get("own_tests_green") and r.get("judge") == NOT_SATISFIED]
        lines += [
            "",
            "**Retests**",
            f"- Retests: {len(retests)}, broken: {sum(r.get('verdict') == 'broken' for r in retests)}",
            f"- Tests green but judge said no: {pct(len(retest_catches), sum(bool(r.get('own_tests_green')) for r in retests))}",
        ]

    if len(fixes) < 10:
        lines += ["", f"_Only {len(fixes)} judged run(s): too few to trust the rates yet._"]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("path", nargs="?", default=".moth/metrics.jsonl")
    parser.add_argument("--gh", action="store_true")
    parser.add_argument("-h", "--help", action="store_true")
    args = parser.parse_args()
    if args.help:
        print(__doc__)
        return
    records = load(args.path)
    if not records:
        print(f"No usable runs in {args.path}.", file=sys.stderr)
        sys.exit(2)
    print(summarize(records, pr_state if args.gh else None))


if __name__ == "__main__":
    main()
