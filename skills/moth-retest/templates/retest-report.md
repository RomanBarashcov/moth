# Retest ACME-123: ✅ works | ❌ broken | ⚠️ inconclusive

**Expected behaviour:** <from the ticket, one line>
**Retested on:** `<repo>@<short sha>` (<branch or PR>), local stack. One line per repo.

## Checks
| Check | Command | Result |
|---|---|---|
| Regression test | `<test_one command>` | ✅ pass / ❌ fail / ⚠️ flaky (n/3) |
| Playwright spec | `npx playwright test bugs/<TICKET-ID>.spec.ts` | |
| Full suite `<repo>` | `<test command>` | <passed>/<total> |
| Independent verification | `moth-verifier` | ✅ satisfied / ❌ not satisfied / ⚠️ inconclusive |

## Proof
<!-- Output of `collect-evidence.sh markdown`. Non-UI bugs: passing test output instead. -->
| | Now |
|---|---|
| `<test>` | ![now](<BASE>/after-<test>.png?raw=true) |
| recording | ![now](<BASE>/after-<test>.gif?raw=true) |

## Independent verification
<!-- The block returned by the moth-verifier agent, pasted here as is (its format is defined in agents/moth-verifier.md). -->

## If broken
- Failing check: <name>
- First error: `<quoted line>`
- Next step: `/moth:moth-fix <TICKET-ID>`

## Notes
- Spec written just for this retest (not in the repo): yes / no
- Holdout scenarios written just for this retest: yes / no
- Gaps in the fix's proof (e.g. no regression test): <one line>, or `none`
