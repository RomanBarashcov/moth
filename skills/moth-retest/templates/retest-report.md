---
ticket: ACME-123
retested: 2026-01-01T14:00
verdict: works | broken | inconclusive
targets:                     # one line per repo: the exact code that was retested
  - repo: service-a
    ref: main
    sha: <commit sha>
prs: []
---

# Retest ACME-123: ✅ works | ❌ broken | ⚠️ inconclusive

**Expected behaviour:** <from the ticket, one line>
**Retested on:** `<repo>@<short sha>` (<branch or PR>), local stack

## Checks
| Check | Command | Result |
|---|---|---|
| Regression test | `<test_one command>` | ✅ pass / ❌ fail / ⚠️ flaky (n/3) |
| Playwright spec | `npx playwright test bugs/<TICKET-ID>.spec.ts` | |
| Full suite `<repo>` | `<test command>` | <passed>/<total> |

## Proof
<!-- Output of `collect-evidence.sh markdown`. Non-UI bugs: passing test output instead. -->
| | Now |
|---|---|
| `<test>` | ![now](<BASE>/after-<test>.png?raw=true) |
| recording | ![now](<BASE>/after-<test>.gif?raw=true) |

## If broken
- Failing check: <name>
- First error: `<quoted line>`
- Next step: `/moth:moth-fix <TICKET-ID>`

## Notes
- Spec written just for this retest (not in the repo): yes / no
- Gaps: FB-<NNN> <one line>, or `none`
