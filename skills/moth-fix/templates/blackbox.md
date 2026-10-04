---
ticket: ACME-123
run_id: <claude session id>
started: 2026-01-01T14:00
outcome: pr-opened | draft-pr | stopped | needs-info
reached_stage: intake | env | reproduce | fix | evidence | pr | review
stop_category: none   # or one category from the taxonomy below
verdict: fixed | partially-fixed | not-fixed | needs-human-input
confidence: high | medium | low
human_input_needed: []
prs: []
turns: 0
minutes: 0
---

## Expected vs actual
- Expected:
- Actual:

## Timeline
| Stage | Result | Turns | Notes |
|---|---|---|---|
| intake | | | |
| env | | | |
| reproduce | | | |
| fix | | | |
| evidence | | | |
| pr | | | |

## How it was reproduced
1.

## What the agent tried
-

## Sibling bugs noticed
-

## Where the workflow was invalid
- One sentence: the gap in process / config / skill, not in the code. `none` if the run was clean.

## Suggested improvement
- FB-<NNN>: <one line> (every item here has a record in `feedback/`)

## Review outcome
- (filled after human review) accepted | changes-requested | rejected — reason

<!--
Stop-category taxonomy:
intake:    vague-ticket, not-a-bug, needs-product-decision
env:       env-wont-start, missing-config, missing-secret
reproduce: missing-seed-data, needs-prod-data, third-party-dependency, race-or-timing, cannot-reproduce
fix:       limit-exceeded, touches-migration-or-api, tests-flaky
evidence:  ui-not-capturable, playwright-failed
review:    wrong-root-cause, self-confirming-test, style-or-scope
-->
