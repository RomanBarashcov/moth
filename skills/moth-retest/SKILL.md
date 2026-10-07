---
name: moth-retest
description: Use after a bug was fixed, to prove it still works ("moth retest ACME-123", "retest the fix", "show me proof the bug is gone"). Re-runs the bug's regression test and Playwright spec on the merged code (or the open PR), runs the full suites for regressions, and reports a clear verdict with fresh screenshots, in the chat and optionally on the ticket. Works for fixes made by Moth or by a human.
---

# Moth: retest a fixed bug

You take one ticket whose fix is merged or in an open PR, and show **with fresh proof** whether the ticket's expected behaviour holds now. You only observe. You never change code to make the retest pass.

## Invocation

| Invocation | What it retests |
|---|---|
| `moth-retest <TICKET-ID>` | The merged fix on the default branch; the PR head if the PR is still open |
| `moth-retest <TICKET-ID> --on <branch \| sha \| PR#>` | That exact ref |
| `moth-retest <TICKET-ID> --post` | As above, then posts the report summary on the ticket (and the PR, if open) without asking |

## Preconditions

- Same as `moth-fix`: run from the project root, `.moth/system.yaml` and `.moth/guard.json` exist (otherwise tell the user to run `/moth:moth-init`). Nothing is written to the project: scratch output goes to `SCRATCH=$(mktemp -d -t moth-retest-<TICKET-ID>)`, deleted at the end.
- Only the `local` environment. Staging and prod stay read-only, because a Playwright spec clicks buttons and writes data.
- If a value you need is `TODO`, stop with `missing-config` and name the key in the report.

Let `<STAMP>` be the current time as `YYYYMMDD-HHMM`.

## Steps

### 1. Gather what "fixed" means
1. Fetch the ticket through `tracker.mcp`. Write down **expected behaviour** in 1–3 lines.
2. Find the fix PRs in each repo: `gh pr list --state all --search "<TICKET-ID>"`. Note each PR's state and merge commit.
3. Read each PR's description. A Moth PR names its regression tests and spec under "Proof".
4. Find the proof to re-run, in this order:
   - the tests named in the PR's "Proof" section,
   - the spec `<repo>/<playwright_dir>/bugs/<TICKET-ID>.spec.ts`,
   - tests added or changed by the fix PR (`gh pr diff <PR> --name-only`).
5. If you find no fix at all, stop with `no-fix-found`.

### 2. Pick the target
1. `--on` given: use it. Otherwise a merged PR means the latest default branch (`git fetch` first), and an open PR means its head.
2. Record the exact commit SHA per repo. The report is only valid for those SHAs.
3. Create a detached worktree at that SHA for each repo, and start the local stack with the `run` commands from `system.yaml`.

### 3. Re-run the proof
1. Run each regression test with the repo's `test_one`. It must pass.
2. For UI bugs, run the spec with video and screenshots on: `--output $SCRATCH/after`.
3. **No test or spec exists** (e.g. a human fixed it without one)? Write a Playwright spec, or the lowest-level test, from the expected behaviour into the worktree only. Never commit it. Say so in the report.
4. Run the full `test` command (and `e2e` if set) of every touched repo, to catch regressions around the fix.
5. A failing test gets 2 more runs. If the results are mixed, it is **flaky**, not failed.
6. **Look at every screenshot.** It must show the expected behaviour, not a blank or loading page. If it doesn't, add a `page.screenshot()` at the moment that proves it, and re-run.

### 4. Verdict
- ✅ **works**: every regression test and spec passes, and the screenshots show the expected behaviour.
- ❌ **broken**: the bug is back, or the fix broke something nearby. Name the failing test and quote the first error line.
- ⚠️ **inconclusive**: the stack didn't start, tests are flaky, or there's no proof that can be run. Say exactly what is missing.

### 5. Report
1. Publish the media through `scripts/collect-evidence.sh` in the `moth-fix` skill directory. Use the `retest-<STAMP>` sub-path so the original fix evidence isn't touched:
   ```bash
   collect-evidence.sh collect $SCRATCH/before $SCRATCH/after $SCRATCH/evidence
   BASE=$(collect-evidence.sh publish <service-repo> $SCRATCH/evidence <TICKET-ID>/retest-<STAMP> "<evidence.branch>")
   collect-evidence.sh markdown $SCRATCH/evidence "$BASE"
   ```
   With no `before` dir, the table has a single "Now" column. For non-UI bugs, paste the passing test output instead.
2. Fill `templates/retest-report.md` and show it to the user in full. Don't save it to a file: the images live on the evidence branch, and the text goes to the ticket in step 6.

### 6. Share
1. With `--post`, or after the user says yes: comment the filled report on the ticket, and on the PR if it is still open.
2. On ❌, don't reopen the ticket or change its status. Suggest `/moth:moth-fix <TICKET-ID>`, and link this report as the starting point.

### 7. Clean up
Stop the local stack, remove the worktrees (any spec written in step 3.3 goes with them) and `rm -rf "$SCRATCH"`.

## Hard rules

- Never change product code, tests or specs in the repo to make the retest pass. Never commit or push anything except the evidence branch.
- No writes to staging or prod.
- No verdict without fresh evidence from this run. Old screenshots don't count.
