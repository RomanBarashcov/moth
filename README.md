<p align="center">
  <img src="assets/moth-matrix.svg" alt="Moth: a moth drawn in falling green matrix glyphs" width="100%">
</p>

# Moth

**A Claude Code plugin that takes a bug ticket, reproduces it, fixes it test-first and opens a PR with proof you can re-run.**

Every run, whether it succeeds or fails, leaves a **Blackbox**: a log of where the workflow worked and where it broke. Every fix leaves a searchable **knowledge record**, so the next bug of the same kind is found faster.

> On 9 September 1947, operators of the Harvard Mark II found a moth stuck in a relay and taped it into the logbook as the *"first actual case of bug being found"*. The first bug ever was recorded in a log. Every Moth run is too.

## Why

Most projects have no bug-hunting automation. Code is written by hand without a repeatable workflow. When one engineer ships buggy code, the next engineer working with AI can ship more of it, because each AI session builds its context from the code that already exists, bugs included.

Moth automates the workflow a careful engineer follows by hand:

1. **Investigate.** Decide whether a feature really works, capture video and screenshots, and put the context into the ticket.
2. **Reproduce.** Trace the bug through logs, metrics, queues and caches, and look for the sibling bugs that live next to it.
3. **Fix.** Write a failing test first, then the smallest fix, then a PR with proof for the team to review.

## What a Moth PR contains

| | |
|---|---|
| 🔴→🟢 | A test that fails before the fix and passes after it (unit, integration or e2e, whichever is lowest and still shows the bug). |
| 🎭 | A Playwright spec you can re-run: `npx playwright test bugs/ACME-123.spec.ts --headed`. |
| 🖼️ | **Before/after screenshots and GIFs** in the description for UI bugs. For backend bugs, red/green output and a request/response or log diff. |
| 🧭 | A Blackbox summary: verdict, confidence, stages reached, a "needs human input" checklist and how the bug was reproduced. |
| 🔗 | A comment on the ticket linking the PR, plus a knowledge record in the workspace. |

Media is published to an orphan `moth-evidence` branch in the service repo. It shares no history with the code and is never merged; the PR links to a pinned commit on it.

## How it works

```
ticket ─▶ intake ─▶ env ─▶ reproduce ─▶ fix ─▶ evidence ─▶ PR ─▶ record
            │                   │                                 │
            ├ skip already-     ├ red test written from the       ├ Blackbox (always)
            │ fixed tickets     │ ticket, before reading code     ├ knowledge record
            └ vague? ask on     └ 3 attempts, then stop           └ feedback chain
              the ticket          with a category
```

Moth is two layers:

```
moth/                 ← this repo: the generic plugin, the same for every system
  skills/               moth-init, moth-fix (+ templates, evidence script)
  hooks/                guard.py: PreToolUse guardrails

acme-moth/            ← one workspace per system (not in this repo)
  system.yaml           repos, commands, environments, MCP servers, tracker, guardrails
  runs/<ID>/            Blackbox for every run, success or failure
  knowledge/            INDEX.md + one record per fixed bug (progressive disclosure)
  feedback/             INDEX.md + FB-NNN: every proposal to improve Moth
```

The plugin knows nothing about any concrete project; everything specific lives in the workspace's `system.yaml`. A new system means a new `<name>-moth/` workspace, and the plugin stays the same.

- **Reproduction** runs locally, in a git worktree per bug, against the local stack.
- **Staging and prod are read-only**: logs, metrics and errors only, through MCP servers marked read-only.
- **Knowledge** lives in the workspace, not in a service repo, because cross-service bugs are the valuable ones. The agent reads `knowledge/INDEX.md` before it investigates.

## Quick start

```bash
mkdir acme-moth && cd acme-moth
claude --plugin-dir /path/to/moth
> /moth:moth-init          # detects repos, commands, MCP servers, boards; asks only what it can't detect
> /moth:moth-fix ACME-123  # fix one ticket end to end
```

The config shape is in [`examples/system.yaml`](examples/system.yaml). `moth-init` checks for these plugins and suggests install commands:
- `linear` or `atlassian` (tracker)
- `playwright` (evidence)
- `superpowers` (TDD and debugging)
- Sentry, Axiom or Grafana MCPs (read-only diagnostics)
- `ffmpeg` (GIFs in PRs, optional)

## Guardrails

| Limit | Default | On hit |
|---|---|---|
| Effort per bug | max turns + ~45 min | stop, comment findings on the ticket |
| Can't reproduce | 3 attempts | comment hypotheses + `needs-info` label |
| Fix touches > 10 files, a migration or a public API | — | open the PR as **draft** |
| Staging / prod | read-only | denied by the guard hook |
| Git | no force push, no push to main/master, no merge | humans merge |

`hooks/guard.py` enforces these as a `PreToolUse` hook, only inside a workspace that has `.moth/guard.json`. It parses each shell command with `shlex`, unwraps `sudo`/`env`/`bash -c`/`eval`/`$(…)`, resolves the current branch for a bare `git push`, and **fails closed**: a broken `guard.json` or an internal error denies the command. Cases are in [`hooks/test_guard.py`](hooks/test_guard.py) (`python3 -m unittest discover -s hooks`).

It is the second line of defence. Use read-only credentials for prod data first.

## The feedback chain

Moth improves through the proposals people and checks make while it works: the user mid-run, a PR reviewer, a CI check, a security review, or Moth itself when it hits a gap. Each proposal becomes an `FB-NNN` record with its **problem, motivation, proposal, decision, output and verification**, linked to the run where it came up. Reading `feedback/INDEX.md` shows what was proposed, what was decided and what changed in the plugin.

A failure that leaves no trail is a bug in Moth.

## Roadmap

- **Phase 1, ticket → PR** (now): fully autonomous up to the PR; a human only reviews.
- **Harness**: a script over `claude -p` (`--output-format stream-json`, `--max-turns`, `--resume`) to process the `moth` label queue unattended.
- **Phase 2, autonomous hunting**: on a schedule, explore the app like a user, record video and file tickets that feed Phase 1.
- **Phase 3, product**: CLI and UI for engineers, a webhook listener for instant intake.

## Key decisions

| Decision | Instead of |
|---|---|
| Plugin + per-system workspace; knowledge in the workspace | knowledge per service repo or only in the tracker |
| Fully autonomous to the PR; humans review and merge | a checkpoint after the red test |
| Local isolated repro + read-only staging/prod diagnostics | shared staging only |
| Playwright now, browser MCP for exploratory hunting later | AppleScript / computer-use |
| A Blackbox for every run, success or failure | knowledge records only (failures lost) |
| Guardrails in a hook, not in skill text | rules the model could talk itself out of |
| Evidence on a never-merged branch, shown in the PR | media committed to the code |

## Status

v0.2: `moth-init`, `moth-fix`, the evidence script and the guard hook, run interactively in Claude Code. The `claude -p` harness is next.

## License

[MIT](LICENSE)
