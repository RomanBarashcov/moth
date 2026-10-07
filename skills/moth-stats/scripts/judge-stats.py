#!/usr/bin/env python3
"""Usage:
  judge-stats.py [.moth/metrics.jsonl] [--gh]

Measures what the independent judge adds, from the one-line-per-run log that
moth-fix and moth-retest append to .moth/metrics.jsonl (in time order).

  catch      the fixer's own tests were green, but the judge's first real
             verdict (inconclusive rounds skipped) was "not satisfied".
  confirmed  a catch that later passed the judge and whose PR was merged
             (needs --gh). Rate is over PRs that are merged or closed.
  miss       the judge passed a fix, and a retest of the same ticket logged
             AFTER it came back broken; or (--gh) its PR was closed unmerged.

--gh looks up each PR's state with `gh pr view`. If every lookup fails, the
PR lines say so instead of showing zeros.

Exit codes: 0 printed a summary, 2 no log or no usable lines.
"""
import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

SATISFIED, NOT_SATISFIED, INCONCLUSIVE = "satisfied", "not-satisfied", "inconclusive"
FINAL = ("MERGED", "CLOSED")


def valid(record):
    if not isinstance(record, dict) or not isinstance(record.get("ticket"), str):
        return False
    if record.get("kind") == "retest":
        return True
    if record.get("kind") != "fix":
        return False
    rounds, prs = record.get("rounds", []), record.get("prs", [])
    return (isinstance(rounds, list) and all(isinstance(r, dict) for r in rounds)
            and isinstance(prs, list) and all(isinstance(p, str) for p in prs))


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
        if not valid(record):
            print(f"warning: line {n} is not a fix or retest record, skipped", file=sys.stderr)
            continue
        record["_order"] = n
        records.append(record)
    return records


def gh_state(url):
    """Returns (state, error); state is MERGED, CLOSED or OPEN."""
    try:
        out = subprocess.run(["gh", "pr", "view", url, "--json", "state", "-q", ".state"],
                             capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        return None, "gh is not installed"
    except subprocess.TimeoutExpired:
        return None, "gh timed out"
    if out.returncode != 0:
        return None, (out.stderr.strip().splitlines() or ["gh failed"])[0]
    return out.stdout.strip() or None, None


def lookup_all(urls, lookup):
    """Looks up each unique URL once, in parallel."""
    unique = sorted(set(urls))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(zip(unique, pool.map(lookup, unique)))
    states = {url: state for url, (state, _) in results.items()}
    errors = [err for _, err in results.values() if err]
    return states, errors


def outcome(prs, states):
    """MERGED if any PR merged, CLOSED if all closed, OPEN otherwise; None if unknown."""
    known = [states.get(url) for url in prs]
    known = [s for s in known if s]
    if not known or len(known) < len(prs) and "MERGED" not in known:
        return None
    if "MERGED" in known:
        return "MERGED"
    if all(s == "CLOSED" for s in known):
        return "CLOSED"
    return "OPEN"


def first_verdict(rounds):
    for r in rounds:
        if r.get("verdict") in (SATISFIED, NOT_SATISFIED):
            return r.get("verdict"), r
    return None, None


def pct(part, whole):
    return f"{part}/{whole} ({part * 100 // whole}%)" if whole else "0/0"


def summarize(records, lookup=None):
    fixes = [r for r in records if r["kind"] == "fix" and first_verdict(r.get("rounds", []))[0]]
    retests = [r for r in records if r["kind"] == "retest"]
    lines = ["## Judge stats", ""]
    if not fixes and not retests:
        lines.append("No runs with a judge verdict yet.")
        return "\n".join(lines)

    if fixes:
        green = [r for r in fixes if r.get("own_tests_green")]
        catches = [r for r in green if first_verdict(r["rounds"])[0] == NOT_SATISFIED]
        caught_then_passed = []
        for r in catches:
            _, first = first_verdict(r["rounds"])
            later = r["rounds"][r["rounds"].index(first) + 1:]
            if any(x.get("verdict") == SATISFIED for x in later):
                caught_then_passed.append(r)
        passed = [r for r in fixes if r["rounds"][-1].get("verdict") == SATISFIED]
        misses = [r for r in passed if any(
            t["ticket"] == r["ticket"] and t["_order"] > r["_order"] and t.get("verdict") == "broken"
            for t in retests)]
        rounds = {}
        for r in fixes:
            rounds[len(r["rounds"])] = rounds.get(len(r["rounds"]), 0) + 1

        lines += [
            "**What the judge caught**",
            f"- Fix runs judged: {len(fixes)}",
            f"- Catches (own tests green, judge said no first): {pct(len(catches), len(green))}",
            f"- Catches fixed in a later round: {pct(len(caught_then_passed), len(catches))}",
            "- Rounds: " + ", ".join(f"{k} round{'s' if k > 1 else ''} × {v}" for k, v in sorted(rounds.items())),
            "",
            "**Did the judge get it right**",
            f"- Judge passed, a later retest broke (miss): {pct(len(misses), len(passed))}",
        ]

        if lookup:
            urls = [url for r in fixes for url in r.get("prs", [])]
            states, errors = lookup_all(urls, lookup)
            if urls and not any(states.values()):
                lines.append(f"- PR outcomes unavailable: {errors[0] if errors else 'no PR state found'}")
            else:
                final = {id(r): outcome(r.get("prs", []), states) for r in fixes}
                settled = lambda rs: [r for r in rs if final[id(r)] in FINAL]
                confirmed = [r for r in settled(caught_then_passed) if final[id(r)] == "MERGED"]
                closed = [r for r in settled(passed) if final[id(r)] == "CLOSED"]
                lines += [
                    f"- Catches confirmed by a merged PR: {pct(len(confirmed), len(settled(caught_then_passed)))}",
                    f"- Judge passed, PR closed unmerged (possible miss): {pct(len(closed), len(settled(passed)))}",
                    f"- PRs merged or closed so far: {len(settled(fixes))}/{len(fixes)}",
                ]
                if errors:
                    print(f"warning: {len(errors)} PR lookup(s) failed: {errors[0]}", file=sys.stderr)
        else:
            lines.append("- PR outcomes: run with `--gh` to check merged / closed")

    if retests:
        green_retests = [r for r in retests if r.get("own_tests_green")]
        retest_catches = [r for r in green_retests if r.get("judge") == NOT_SATISFIED]
        lines += [
            "",
            "**Retests**",
            f"- Retests: {len(retests)}, broken: {sum(r.get('verdict') == 'broken' for r in retests)}",
            f"- Tests green but judge said no: {pct(len(retest_catches), len(green_retests))}",
        ]

    if len(fixes) < 10:
        lines += ["", f"_Only {len(fixes)} judged fix run(s): too few to trust the rates yet._"]
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
    print(summarize(records, gh_state if args.gh else None))


if __name__ == "__main__":
    main()
