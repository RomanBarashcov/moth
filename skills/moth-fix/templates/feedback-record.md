---
id: FB-<NNN>
date: <YYYY-MM-DD>
source: user | reviewer | ci:<check-name> | security-review | ticket-comment | agent
raised_in: runs/<TICKET-ID>/blackbox.md#<stage>
area: intake | env | reproduce | fix | evidence | pr | record | guard | init | config
status: proposed | accepted | implemented | rejected | deferred
---

## Problem
<What happened, observably. Quote the error, the check or the comment. One to three lines.>

## Motivation
<Why it matters: what it cost in this run (turns, a wrong PR, a blocked push) and what it would keep costing.>

## Proposal
<What was suggested. Quote a human verbatim (names → roles). If you are the source, say "agent".>

## Decision
<Who decided what, and why. Leave "pending" while status is proposed.>

## Output
<What changed in Moth because of it: plugin files, config keys, commits. "none yet" while not implemented.>

## Verification
<How we know it works: a test (e.g. `hooks/test_guard.py`), a later run that exercised it, or "not yet verified".>
