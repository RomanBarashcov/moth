#!/usr/bin/env python3
"""Usage:
  satisfaction.py <playwright-report.json> [--min 0.9]

Scores a Playwright JSON report (`--reporter=json`) as satisfaction: the
fraction of trajectories (one per test result, so repeats and retries each
count) that pass. Tests must be titled `S<n> [v<k>] <title>` (scenario n,
variation k); other titles are grouped under `other` with a warning.
Skipped results are excluded.

Prints a markdown summary. The run fails if the overall score or any single
scenario is below --min (default 0.9).

Exit codes: 0 all good, 1 below min, 2 unreadable file or no usable results.
"""
import argparse
import json
import math
import re
import sys

TITLE = re.compile(r"^S(\d+) \[v(\d+)\] (.+)$")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
FAILED = {"failed", "timedOut", "interrupted"}
MAX_ERRORS = 5
ERROR_WIDTH = 120


def walk_specs(suites):
    for suite in suites or []:
        yield from suite.get("specs") or []
        yield from walk_specs(suite.get("suites"))


def first_error_line(result):
    error = result.get("error") or next(iter(result.get("errors") or []), None) or {}
    text = ANSI.sub("", error.get("message") or error.get("value") or "")
    line = next((l.strip() for l in text.splitlines() if l.strip()), result.get("status", ""))
    return line if len(line) <= ERROR_WIDTH else line[: ERROR_WIDTH - 1] + "…"


def trajectories(report):
    """Yields (scenario, variation, name, passed, project, error, title) per non-skipped result."""
    for spec in walk_specs(report.get("suites")):
        title = spec.get("title", "")
        match = TITLE.match(title)
        if match:
            scenario, variation, name = f"S{match[1]}", f"v{match[2]}", match[3]
        else:
            print(f"warning: title does not match 'S<n> [v<k>] <title>': {title!r}", file=sys.stderr)
            scenario, variation, name = "other", "", ""
        for test in spec.get("tests") or []:
            for result in test.get("results") or []:
                status = result.get("status")
                if status == "passed":
                    yield scenario, variation, name, True, test.get("projectName", ""), None, title
                elif status in FAILED:
                    yield scenario, variation, name, False, test.get("projectName", ""), first_error_line(result), title


def score(ok, total):
    return ok / total if total else 0.0


def fmt(value):
    # floor so 0.899 never prints as 0.90 next to a 0.90 floor
    return f"{math.floor(value * 100) / 100:.2f}"


def sort_key(name):
    return (1, 0) if name == "other" else (0, int(name[1:]))


def summarize(report, minimum):
    scenarios = {}
    failures = []
    for scenario, variation, name, passed, project, error, title in trajectories(report):
        s = scenarios.setdefault(scenario, {"name": name, "ok": 0, "total": 0, "vars": {}})
        v = s["vars"].setdefault(variation, [0, 0])
        s["total"] += 1
        v[1] += 1
        if passed:
            s["ok"] += 1
            v[0] += 1
        else:
            failures.append((title, project, error))

    total = sum(s["total"] for s in scenarios.values())
    if not total:
        return None, 2
    ok = sum(s["ok"] for s in scenarios.values())
    overall = score(ok, total)
    below = [k for k, s in scenarios.items() if score(s["ok"], s["total"]) < minimum]
    good = overall >= minimum and not below

    lines = [
        f"**Satisfaction: {fmt(overall)} ({ok}/{total})** — min {minimum:.2f} {'✅' if good else '❌'}",
        "",
        "| Scenario | Satisfied | Variations | Flaky |",
        "|---|---|---|---|",
    ]
    for key in sorted(scenarios, key=sort_key):
        s = scenarios[key]
        variations = " · ".join(
            f"{v} {p}/{t}" if v else f"{p}/{t}"
            for v, (p, t) in sorted(s["vars"].items(), key=lambda kv: int(kv[0][1:] or 0))
        )
        flaky = any(0 < p < t for p, t in s["vars"].values())
        label = f"{key} {s['name']}".strip()
        lines.append(f"| {label} | {s['ok']}/{s['total']} | {variations} | {'yes' if flaky else 'no'} |")

    if below:
        lines += ["", "Below min: " + ", ".join(
            f"{k} ({fmt(score(scenarios[k]['ok'], scenarios[k]['total']))})"
            for k in sorted(below, key=sort_key))]
    if failures:
        lines += ["", f"Failing trajectories ({len(failures)}):"]
        for title, project, error in failures[:MAX_ERRORS]:
            where = f" ({project})" if project else ""
            lines.append(f"- {title}{where}: {error}")
        if len(failures) > MAX_ERRORS:
            lines.append(f"- … and {len(failures) - MAX_ERRORS} more")
    return "\n".join(lines), 0 if good else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Score a Playwright JSON report as satisfaction.")
    parser.add_argument("report")
    parser.add_argument("--min", type=float, default=0.9, dest="minimum")
    args = parser.parse_args(argv)
    if not 0 <= args.minimum <= 1:
        parser.error("--min must be between 0 and 1")
    try:
        with open(args.report, encoding="utf-8") as f:
            report = json.load(f)
        if not isinstance(report, dict):
            raise ValueError("top level is not an object")
    except (OSError, ValueError) as e:
        print(f"error: cannot read {args.report}: {e}", file=sys.stderr)
        return 2
    text, code = summarize(report, args.minimum)
    if text is None:
        print(f"error: no usable results in {args.report}", file=sys.stderr)
        return 2
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
