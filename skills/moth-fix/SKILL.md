---
name: moth-fix
description: Use when asked to fix a bug ticket end-to-end ("moth fix ACME-123", a ticket labeled `moth`). Runs intake → env → reproduce → fix → evidence → PR inside a Moth workspace, always writing a Blackbox run log.
---

# Moth: fix a bug ticket

You take one bug ticket and drive it to a PR **autonomously**. A human only reviews the PR. Every run ends with a Blackbox, **whether it succeeded or failed**.

## Preconditions

- The current directory is a **Moth workspace**: it contains `system.yaml`, `runs/` and `knowledge/`. If `system.yaml` or `.moth/guard.json` is missing, stop and tell the user to run `/moth:moth-init`.
- Read `system.yaml` first. It is the only source of truth for repos, environments, MCP servers, tracker and guardrails. Never guess a command that is not in it.
- If a value you need is `TODO`, stop with `missing-config` and name the exact key in the Blackbox.

## Pipeline

Track the stages: `intake → env → reproduce → fix → evidence → pr → review`.
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
   - **before**: on the base commit, with the fix stashed (`git stash push -u -- <fix paths>`), `--output runs/<TICKET-ID>/media/before`,
   - **after**: on the fix commit, `--output runs/<TICKET-ID>/media/after`.
   The spec must record `video: 'on'` and `screenshot: 'on'` so passing tests keep media too.
2. Collect and publish the media with `scripts/collect-evidence.sh` (in this skill's directory):
   ```bash
   collect-evidence.sh collect runs/<ID>/media/before runs/<ID>/media/after runs/<ID>/evidence
   BASE=$(collect-evidence.sh publish <service-repo> runs/<ID>/evidence <ID> "<evidence.branch>")
   collect-evidence.sh markdown runs/<ID>/evidence "$BASE"   # paste into the PR body
   ```
   `publish` commits to the orphan branch `evidence.branch` from `system.yaml` (default `moth-evidence`) through a temporary index. It never touches the working tree or the fix branch, and that branch is never merged. Its URLs are pinned to the evidence commit, so the PR keeps rendering after the fix branch is deleted.
3. **Look at the after screenshot** before using it. It must show the fixed behaviour (e.g. the success toast), not a blank or loading page. If it doesn't, add an explicit `page.screenshot()` at the moment that proves the fix and re-run.
4. For non-UI bugs, capture red and green test output, plus a request/response or log diff, and paste the short version into the PR body.

### 6. PR
1. Open one PR per touched repo with `gh pr create` (draft when step 4 says so). Pass the body with `--body-file`, never inline.
2. Build the PR description from `templates/pr-blackbox-summary.md`, including the evidence table from step 5. A UI fix PR without before/after images is incomplete.
3. **Never commit Moth files to the fix branch.** That covers the Blackbox, the knowledge record and the media. Media goes only to the evidence branch.
4. Comment on the ticket with the PR links.
5. Run the repo's quality checks on the PR (`gh pr checks`). If a check fails and its details aren't readable (for example, a private code-quality project and no API token), ask the user for the finding text instead of guessing fixes.

### 7. Record
1. Write `runs/<TICKET-ID>/blackbox.md` from `templates/blackbox.md`.
2. If the run was fixed or partially fixed:
   - write `knowledge/<TICKET-ID>-<slug>.md` from `templates/knowledge-record.md`,
   - add one line to `knowledge/INDEX.md`.
3. Make sure every improvement raised during the run has a feedback record (see **Feedback chain**), and list their IDs in the Blackbox under "Suggested improvement".
4. Commit these to the workspace repo (never to a service repo).

## Feedback chain

Moth improves through the proposals people and checks make while it works. Record each one **when it is raised**, not at the end of the run, so the reasoning isn't lost.

**What counts:** any proposal to change *how Moth works*: its process, skills, config, guard or templates. It can come from:
- the user, mid-run ("add the screenshots to the PR"),
- a PR reviewer or a ticket comment,
- a CI or quality check (`ci:<check-name>`),
- a security review,
- you, when you hit a gap ("guard blocked a legitimate push").

A product-code fix requested in review is *not* feedback by itself. Record it only if it reveals a workflow gap (e.g. "no security pass before the PR").

**How:**
1. Take the next free number from `feedback/INDEX.md` and write `feedback/FB-<NNN>-<slug>.md` from `templates/feedback-record.md`: problem, motivation, proposal (quote humans verbatim, names → roles), decision, output, verification.
2. Add one row to `feedback/INDEX.md`: `| FB-NNN | date | source | area | status | one-line problem → output |`.
3. When the proposal is implemented later, update `status`, **Output** (files, commits) and **Verification** in the same record. Don't open a new one.
4. If two proposals conflict (e.g. "store media in the repo" → "don't merge media into code"), keep both records and link the later one to the earlier one in **Decision**. The chain of decisions is the point.

## Stop

Use Stop for any failure, and for hitting a guardrail limit (`guardrails.max_turns`, `guardrails.timeout_minutes`).

1. Fill in the Blackbox:
   - `reached_stage`,
   - `stop_category`,
   - `verdict`,
   - what you tried,
   - **where the workflow was invalid** (the gap in process, config or skill, not in the code),
   - a suggested improvement.
2. Comment on the ticket: what you checked, your hypotheses, and the link to the Blackbox.
3. **A failure that leaves no trail is a bug in Moth.**

## Hard rules

- No writes to staging or prod. No force push. No merge.
- Never weaken or delete an existing test to get green.
- Don't fix anything the ticket doesn't describe. Log it as a sibling bug instead.
