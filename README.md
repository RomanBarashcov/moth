<p align="center">
  <img src="assets/moth-matrix.svg" alt="Moth: a moth drawn in falling green matrix glyphs" width="100%">
</p>

# Moth

**Give it a bug ticket. Get back a PR with a fix and proof.**

A Claude Code plugin. It reproduces the bug, writes a failing test, fixes it, and opens a PR with before/after screenshots.

## Start in 3 steps (~10 min)

1. Make a workspace folder next to your code:
   ```bash
   mkdir acme-moth && cd acme-moth
   ```
2. Start Claude Code with the plugin and set up the workspace:
   ```bash
   claude --plugin-dir /path/to/moth
   > /moth:moth-init
   ```
   It finds your repos, commands and tools. It asks only what it can't find.
3. Fix one ticket:
   ```bash
   > /moth:moth-fix ACME-123
   ```

Config example: [`examples/system.yaml`](examples/system.yaml).

## What you get in the PR

- 🔴→🟢 **A test** that fails before the fix and passes after it.
- 🎭 **A Playwright spec** you can re-run: `npx playwright test bugs/ACME-123.spec.ts --headed`.
- 🖼️ **Before/after screenshots and GIFs** in the description.
- 🧭 **A short report:** verdict, confidence, what a human needs to check.
- 🔗 **A comment on the ticket** with the PR link.

You review. You merge. Moth never merges.

## How a run goes

```
ticket → reproduce → red test → fix → green test → screenshots → PR
```

| Step | What Moth does |
|---|---|
| 1. Intake | Reads the ticket. Skips it if git already has a fix. Asks on the ticket if it's too vague. |
| 2. Reproduce | Writes a failing test from the ticket, before reading the code. Stops after 3 tries. |
| 3. Fix | Makes the smallest change that turns the test green. Runs all tests. |
| 4. Proof | Runs the Playwright spec on the old code and the new code. Puts both in the PR. |
| 5. Record | Writes a run log, a knowledge note, and any improvement ideas. |

## Safety rules

Enforced by a hook (`hooks/guard.py`), not by trust:

- ❌ No push to `main`/`master`. No force push. No merge.
- ❌ No writes to staging or prod. Read-only logs and errors only.
- 📝 Draft PR if the fix touches more than 10 files, a migration, or a public API.
- ⏱️ Stops after ~45 min or 3 failed reproduce tries, and comments what it found.
- 🔒 If the hook itself breaks, it blocks the command.

Test the hook: `python3 -m unittest discover -s hooks`

## Where things live

```
moth/          ← this repo: the plugin, the same for every project
acme-moth/     ← your workspace, one per project
  system.yaml    repos, commands, tools, rules
  runs/          a log for every run, success or failure
  knowledge/     one note per fixed bug
  feedback/      every idea for improving Moth
```

Screenshots go to a separate `moth-evidence` branch. It is never merged, so no images end up in your code.

## Plugins that help

`moth-init` checks for these and gives install commands:

- `linear` or `atlassian`: read tickets
- `playwright`: screenshots and videos
- `superpowers`: TDD and debugging
- Sentry, Axiom or Grafana MCP: read-only logs and errors
- `ffmpeg`: GIFs in PRs (optional)

## Improving Moth: the feedback chain

Every idea to improve Moth gets one file in `feedback/`. Ideas can come from you, a reviewer, a CI check, or Moth itself.

Each file answers 6 questions:

1. What went wrong?
2. Why does it matter?
3. What was proposed?
4. What was decided?
5. What changed?
6. How do we know it works?

Open `feedback/INDEX.md` to see all ideas and their status.

## Why it exists

AI writes code from the code it sees. If that code has bugs, AI copies them. Moth breaks the loop: every bug gets a test, a fix and a note, so the next session sees the right pattern.

> **The name:** in 1947, engineers found a moth stuck in the Harvard Mark II computer. They taped it into the logbook as the *"first actual case of bug being found"*. Every Moth run is logged too.

## What's next

| Phase | What | Status |
|---|---|---|
| 1 | Ticket → PR | ✅ now |
| 1.5 | Run unattended from a label queue (`claude -p`) | next |
| 2 | Hunt bugs on a schedule, file tickets itself | later |
| 3 | CLI and UI for teams | later |

## License

[MIT](LICENSE)
