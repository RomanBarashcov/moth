---
name: <TICKET-ID>-<slug>
description: <one line: symptom + root cause, written so a future search matches it>
area: <domain area, e.g. checkout>
services: [service-a]
tags: []
prs: []
blackbox: runs/<TICKET-ID>/blackbox.md
---

## How it was found
<ticket source, reporter, symptom>

## How it was reproduced
1.

## Root cause
<what was wrong and why it shipped>

## Fix
<what changed, and why this fix over alternatives>

## Conclusion
<the lesson: the pattern to avoid or the check to add>

## Sibling bugs
- <related issues noticed, with ticket links if filed>
