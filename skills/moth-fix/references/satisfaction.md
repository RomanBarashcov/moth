# Satisfaction

A fix is not proven by one green run. It is proven by **satisfaction**: the fraction of trajectories that satisfy the ticket. A trajectory is one run of one test — one scenario, one variation, one browser, one repeat.

## Why trajectories, not one run

One pass can be luck: a race that went the right way, a warm cache. One fail can be noise. Many runs of the same intent, with small changes, show whether the fix holds or only held once.

## How the count multiplies

- **Scenario** `S<n>`: one acceptance criterion from the ticket.
- **Variation** `v<k>`: the same scenario with other inputs (other user, locale, empty vs full cart).
- **Repeat**: `--repeat-each <R>` runs every variation R times.

Trajectories per scenario = variations × repeats × browsers, e.g. 3 × 3 × 1 = 9. Retries add more; each counts. Titles must be exactly `S<n> [v<k>] <title>`; anything else is scored under `other`.

Score it with `scripts/satisfaction.py <report.json> --min 0.9`. Exit 0 ok, 1 below min, 2 no usable results.

## Reading the table

- **Satisfaction** line: passing / total trajectories, and ✅ or ❌ against the floor.
- **Satisfied**: the same per scenario. Skipped runs are not counted.
- **Variations**: the split per variation. `v2 0/3` means the fix misses that case.
- **Flaky**: yes if one variation both passed and failed in the same browser. Always failing in one browser and passing in another is a browser-specific bug, not flake.
- **Below min**: scenarios under the floor. One broken scenario fails the run even when the overall score is fine.

## Defaults

`satisfaction_repeats: 3` and `min_satisfaction: 0.9` (system.yaml guardrails), with 2–4 variations per scenario.

## On flaky

Do not raise repeats until it passes, and do not lower the floor. Flaky means something is not deterministic: a missing wait in the test, or a race in the fix. Read the failing trajectories' errors, fix the cause, run again. If the flake is in the product and not in the fix, say so in the PR.
