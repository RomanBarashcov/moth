---
name: moth-fix
description: Use when asked to fix a bug ticket end-to-end ("moth fix ACME-123", a ticket labeled `moth`). Runs intake → env → reproduce → fix → evidence → independent verification → PR in a project with Moth set up, always ending with a Blackbox report in the PR or on the ticket.
---

# Moth: fix a bug ticket

You take one bug ticket and drive it to a PR **autonomously**. A human only reviews the PR. Every run ends with a Blackbox report, **whether it succeeded or failed**: in the PR description, or as a ticket comment when it stops. That's where people look, so that's where it goes. Nothing stays on disk except one knowledge note per fixed bug.

## Preconditions

- Run from the project root. Moth's config lives in its git-ignored `.moth/` folder; `knowledge/` below means `.moth/knowledge/`. If `.moth/system.yaml` or `.moth/guard.json` is missing, stop and tell the user to run `/moth:moth-init`.
- Put every scratch file (test output, Playwright media) in `SCRATCH=$(mktemp -d "${TMPDIR:-/tmp}/moth-<TICKET-ID>.XXXXXX")`, never in the project. It is deleted when the run ends.
- Keep the Blackbox (`templates/blackbox.md`) as notes during the run. Don't write it to a file.
- Read `.moth/system.yaml` first. Repo paths in it are relative to the project root. It is the only source of truth for repos, environments, MCP servers, tracker and guardrails. Never guess a command that is not in it.
- If a value you need is `TODO`, stop with `missing-config` and name the exact key in the Blackbox.

## Pipeline

Track the stages: `intake → env → reproduce → fix → evidence → verify → pr → review`.
When any stage fails, jump to **Stop** and do not continue.

### 1. Intake
1. Fetch the ticket through the tracker MCP named in `system.yaml` (`tracker.mcp`).
   - If you were asked to pick a ticket yourself, first drop the ones already fixed: `git log --all --oneline -i --grep "<TICKET-ID>\b"` in each repo. If commits exist, comment "already fixed in <sha>" on the ticket, record it in the Blackbox, and pick another.
2. Read `knowledge/INDEX.md`. Open only the records whose one-line description matches this bug's area or symptom.
3. Write down in the Blackbox, in 1–3 lines each:
   - **Expected behaviour**, taken from the ticket.
   - **Actual behaviour**, taken from the ticket.
   - The **suspected services**, taken from the `system.yaml` repo map.
4. Stop with `vague-ticket` if expected vs actual can't be stated. Before stopping, comment the clarifying questions on the ticket and set the `needs-info` label.
5. Spawn the `moth-scenario-writer` agent with the ticket ID and the project root (plus the app URL if a local stack is already up). Do it now, before you reproduce or read any code.
   - When the ticket is thin, it observes the app and read-only errors/logs to fill in steps and data. It never reads code.
   - It writes holdout scenarios to `.moth/scenarios/<TICKET-ID>/scenarios.md` and returns one line.
   - `vague-ticket: <question>`: stop as in step 4, and put its question on the ticket.
   - **Never read `.moth/scenarios/`.** Not now, not later. Scenarios you have seen can't check your fix.

### 2. Env
1. For each suspected repo, create a git worktree on branch `moth/<TICKET-ID>`.
2. Start the local stack using the `run` commands from `system.yaml`.
3. Only touch the `local` environment. **Staging and prod are read-only.** Use only the read-only sources listed under `environments.<name>.read_only`.

### 3. Reproduce
1. Write the failing test **from the expected behaviour, before reading the suspected code.** This guards against a self-confirming test.
   - Use the lowest level that shows the bug: unit, integration or e2e.
   - For UI-visible bugs, **always** also write a Playwright spec at `<repo>/<playwright_dir>/bugs/<TICKET-ID>.spec.ts`, with video, trace and screenshot enabled.
2. Run the test and confirm it fails **for the reason in the ticket**, not for a setup error.
3. When you get stuck, gather evidence from logs, metrics and data (read-only). If the superpowers `systematic-debugging` skill is available, use it.
4. Stop after `guardrails.reproduce_attempts` failed attempts. Stop with one category from `templates/blackbox.md`.

### 4. Fix
1. Make the smallest change that turns the red test green. Follow the TDD skill if it is available.
2. Run each touched repo's full test command from `system.yaml`.
3. Mark the PR as **draft** if the fix:
   - touches more than `guardrails.max_files` files,
   - touches a DB migration,
   - or touches a public API.
4. Record any **sibling bugs** you notice. Do not fix them, because they are out of scope.

### 5. Evidence
1. For UI bugs, run the Playwright spec twice, each with its own `--output` dir:
   - **before**: on the base commit, with the fix stashed (`git stash push -u -- <fix paths>`), `--output $SCRATCH/before`,
   - **after**: on the fix commit, `--output $SCRATCH/after`.
   The spec must record `video: 'on'` and `screenshot: 'on'` so passing tests keep media too.
2. Collect and publish the media with `scripts/collect-evidence.sh` (in this skill's directory):
   ```bash
   collect-evidence.sh collect $SCRATCH/before $SCRATCH/after $SCRATCH/evidence
   BASE=$(collect-evidence.sh publish <service-repo> $SCRATCH/evidence <ID> "<evidence.branch>")
   collect-evidence.sh markdown $SCRATCH/evidence "$BASE"   # paste into the PR body
   ```
   `publish` commits to the orphan branch `evidence.branch` from `system.yaml` (default `moth-evidence`) through a temporary index. It never touches the working tree or the fix branch, and that branch is never merged. Its URLs are pinned to the evidence commit, so the PR keeps rendering after the fix branch is deleted.
3. **Look at the after screenshot** before using it. It must show the fixed behaviour (e.g. the success toast), not a blank or loading page. If it doesn't, add an explicit `page.screenshot()` at the moment that proves the fix and re-run.
4. For non-UI bugs, capture red and green test output, plus a request/response or log diff, and paste the short version into the PR body.

### 6. Verify
1. Spawn the `moth-verifier` agent. Give it only:
   - the ticket ID and the project root,
   - each fix worktree path and its fix commit SHA (commit first; the tree must be clean),
   - the running local stack,
   - the path of this skill's `scripts/` directory.
   Never send it the diff, your tests or your theory of the bug.
2. It returns an **Independent verification** block: verdict, satisfaction score, and for each scenario its title, Then line and a judge note. That's all you get. You never see the scenarios' variations or its test code.
3. ✅ **satisfied**: go to PR.
4. ❌ **not satisfied**, or a score below `guardrails.min_satisfaction`: go back to **4. Fix** with the failing titles and Then lines, then redo Evidence and Verify.
   - At most 2 rounds back to Fix. If the verifier still isn't satisfied, open a **draft** PR and say so under "Needs human input".
5. ⚠️ **inconclusive**: fix the cause if it's yours (stack down, uncommitted fix) and run the verifier once more. Still inconclusive? Open a draft PR and say why.
6. **Never edit, delete or regenerate the scenarios** to get a pass.

### 7. PR
1. Open one PR per touched repo with `gh pr create` (draft when step 4 or 6 says so). Pass the body with `--body-file`, never inline.
2. Build the PR description from `templates/pr-blackbox-summary.md`, including the evidence table from step 5, the Independent verification block from step 6, and the full Blackbox in its collapsed `<details>` block. A UI fix PR without before/after images is incomplete.
3. **Never commit Moth files to the fix branch.** That covers the knowledge record and the media. `.moth/` is git-ignored; never `git add -f` it. Media goes only to the evidence branch.
4. Comment on the ticket with the PR links.
5. Run the repo's quality checks on the PR (`gh pr checks`). If a check fails and its details aren't readable (for example, a private code-quality project and no API token), ask the user for the finding text instead of guessing fixes.

### 8. Record and clean up
1. If the run was fixed or partially fixed:
   - write `knowledge/<TICKET-ID>-<slug>.md` from `templates/knowledge-record.md`,
   - add one line to `knowledge/INDEX.md`.
   Don't commit them.
2. `rm -rf "$SCRATCH"`. The proof now lives in the PR and on the evidence branch.

## Stop

Use Stop for any failure, and for hitting a guardrail limit (`guardrails.max_turns`, `guardrails.timeout_minutes`).

1. Fill in the Blackbox:
   - `reached_stage`,
   - `stop_category`,
   - `verdict`,
   - what you tried,
   - **where the workflow was invalid** (the gap in process, config or skill, not in the code),
   - a suggested improvement to Moth, if any.
2. Comment the filled Blackbox on the ticket: what you checked, your hypotheses, and where the workflow was invalid. Attach the key test output inline.
3. `rm -rf "$SCRATCH"`.
4. **A failure that leaves no trail is a bug in Moth.**

## Hard rules

- No writes to staging or prod. No force push. No merge.
- Never weaken or delete an existing test to get green.
- Don't fix anything the ticket doesn't describe. Log it as a sibling bug instead.
- Never read, edit or delete `.moth/scenarios/`. Only the scenario writer and the verifier touch it.
- Never mark a fix done on your own tests alone. The verifier judges it, not you.
