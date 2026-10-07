---
name: moth-stats
description: Use when asked how well Moth's independent judge works ("moth stats", "is the judge worth it", "how often does the verifier catch bugs"). Reads .moth/metrics.jsonl and reports catches, misses and PR outcomes.
---

# Moth: judge stats

Show what the independent judge adds, from `.moth/metrics.jsonl` (one line per `moth-fix` or `moth-retest` run).

## Steps

1. Run from the project root:
   ```bash
   python3 <this skill's dir>/scripts/judge-stats.py .moth/metrics.jsonl --gh
   ```
   `--gh` checks each PR's state with `gh pr view`. If the output says "PR outcomes unavailable", tell the user why (e.g. run `gh auth login`).
2. Exit code 2 means there's no log or no usable lines yet. Tell the user to run `/moth:moth-fix` on a ticket first.
3. Show the output as is. Then add **one** line that reads it for the user, for example:
   - "The judge caught 3 of 12 fixes that your tests passed; 2 of those were merged after the second round."
   - "No misses so far, but 4 runs is too few to trust the rates."

## What the numbers mean

- **Catch**: the fixer's own tests were green, but the judge said "not satisfied" in round 1. The judge saw something the tests didn't.
- **Confirmed catch**: a catch that later passed the judge, and its PR was merged. A human accepted the fix the judge pushed for.
- **Miss**: the judge passed a fix, but a later retest of the same ticket was broken, or the PR was closed without merging.

High catches with few misses: the judge earns its cost. Near-zero catches over many runs: the fixer's tests already cover it, and the judge is mostly cost.

## Hard rules

- Read only. Never edit `.moth/metrics.jsonl`.
