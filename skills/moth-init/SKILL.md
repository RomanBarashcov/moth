---
name: moth-init
description: Use to set up or extend Moth in a project ("moth init", "add a board / repo to Moth", "sync Moth guardrails"). Creates a git-ignored .moth/ folder in the project, discovers repos, commands, MCP servers and tracker boards automatically, asks only for what it cannot detect, and writes .moth/system.yaml + .moth/guard.json.
---

# Moth: init a project

The goal is a working `.moth/system.yaml` with **as few questions as possible**. Detect first, ask second, and leave a `TODO` for anything still unknown.

## Modes

| Invocation | What it does |
|---|---|
| `moth-init` | Creates `.moth/` in the current project, or resumes it if `.moth/system.yaml` exists |
| `moth-init --add-repo <path>` | Detects one more repo (e.g. `../other-service`) and appends it |
| `moth-init --add-board` | Lists tracker boards and appends the chosen one |
| `moth-init --sync` | Regenerates `.moth/guard.json` from `.moth/system.yaml`, then reports the gaps |

**Never overwrite** a value marked `# confirmed`. Re-running init only adds new values or refines `# inferred` ones.

## Step 0: The `.moth/` folder

Moth lives in one folder at the project root (the git top level of the current directory):

```
<project>/
  .gitignore     ← contains the line `.moth/`
  .moth/
    system.yaml    repos, commands, tools, rules
    guard.json     generated from system.yaml, read by the guard hook
    runs/          a Blackbox for every run
    knowledge/     one note per fixed bug
    feedback/      every idea for improving Moth
```

1. Create `.moth/` at the project root. Don't ask.
2. If `.gitignore` doesn't already ignore `.moth/`, append the line `.moth/` to it. Don't touch anything else in `.gitignore`, and don't commit it: tell the user to commit that one line.
3. Run `git check-ignore -q .moth/system.yaml`. If it isn't ignored, stop and say why.

`.moth/` is never committed, so Moth files can't leak into a fix branch.

## Step 1: Detect (no questions yet)

### Repos
The project itself is the first repo, with `path: .`. Add every extra repo path the user gave (e.g. `../web-app` for a multi-repo system). Paths in `system.yaml` are relative to the project root, not to `.moth/`. For each repo:
- **Language**: from `go.mod`, `package.json`, `pyproject.toml`, `Cargo.toml`, `pom.xml` / `build.gradle`.
- **`run` / `test` / `test_one` / `e2e`**: from Makefile targets (`make -qp` or by reading the `Makefile`), `package.json` scripts, `justfile`, `Taskfile.yml`. Prefer the targets named `run`, `dev`, `test`, `test:run`, `test:e2e`.
- **`playwright_dir`**: from the `testDir` in `playwright.config.*`.
- **Local stack**: from `docker-compose*.yml` / `compose*.yaml`, plus the seed and migrate targets.

### Links between services
- Read the service names in the compose files, the URLs in `.env.example`, and the queue and topic names.
- Write these down as `links`, marked `# inferred`.

### MCP servers and plugins
Run `claude mcp list` and read the enabled plugins. Classify each server:
- **tracker**: Linear, Jira / Atlassian
- **errors**: Sentry
- **logs and metrics**: Axiom, Grafana, Datadog
- **data**: Postgres, Redis, Kafka
- **browser**: Playwright, Chrome DevTools

### Boards
If a tracker MCP is available, list its teams and projects (boards).

## Step 2: Ask only what is missing

Ask **one question at a time**, each with a recommended default. Typical questions:
1. "Which board(s) should Moth watch?" Show the boards you detected.
2. "Which label queues a ticket for Moth?" Default: `moth`.
3. "Which MCP gives staging/prod logs? errors? metrics?" Show the servers you detected.
4. "Any commands that must never run here?" Seed the list with prod DB hosts and `kubectl` prod contexts.

Skip a question when Step 1 already answered it with high confidence. Mark that value `# inferred` and show it in the summary.

If the user doesn't know an answer, write `TODO: <what is missing>` and move on. A later `moth-fix` run that hits it will stop with `missing-config`, and its Blackbox will say exactly what to fill in.

## Step 3: Gap report

For each pipeline stage, show whether a capability exists. When one is missing, give the exact install command. **Do not install anything yourself.**

| Stage | Needed | Suggest if missing |
|---|---|---|
| intake | tracker MCP | `claude plugin install linear@claude-plugins-official` / `atlassian@claude-plugins-official` |
| reproduce | errors / logs (optional) | Sentry, Axiom, Grafana (`--disable-write`) MCP |
| evidence | browser automation | `claude plugin install playwright@claude-plugins-official` |
| evidence | `ffmpeg` for GIFs in the PR (optional) | `brew install ffmpeg` |
| evidence | push access to an orphan `evidence.branch` (default `moth-evidence`) in each service repo | branch protection that blocks new branches → ask the repo admin, or set `evidence.branch` to an allowed name |
| fix / debug | TDD + debugging skills (optional) | `claude plugin install superpowers@claude-plugins-official` |
| pr | `gh` CLI, authenticated | `gh auth login` |

For data stores (Postgres, Redis, Kafka), recommend **read-only credentials** (a read-only DB role or a replica). The guard hook is the second line of defence, not the first.

## Step 4: Write

1. Write `.moth/system.yaml`. Use `examples/system.yaml` in this plugin as the shape, and mark every value `# inferred`, `# confirmed` or `TODO`.
2. Generate `.moth/guard.json` from `.moth/system.yaml`:
   ```json
   {
     "read_only_mcp": ["<every MCP named under environments.staging/prod.read_only>"],
     "bash_deny": [{ "pattern": "<regex>", "reason": "<why>" }]
   }
   ```
   The Moth `PreToolUse` hook reads this file. Writes through a read-only MCP, force pushes, pushes to main/master and `gh pr merge` are then denied.
3. Create `.moth/runs/` and `.moth/knowledge/INDEX.md` if they are missing. `INDEX.md` starts with a `# Knowledge index` header and nothing else.
4. Create `.moth/feedback/INDEX.md` if it is missing:
   ```markdown
   # Feedback chain

   | ID | Date | Source | Area | Status | Problem → Output |
   |---|---|---|---|---|---|
   ```
5. Ask before creating the queue label in the tracker. The label is visible to the whole team.

## Step 5: Verify and summarize

1. Run one fast `test_one` (or `test`) command for each repo. Report pass, fail, or the command not being found.
2. Show:
   - every value marked `# inferred`, for the user to confirm,
   - every `TODO`,
   - the gap report,
   - whether `.gitignore` was changed (the user commits that one line),
   - the exact next command: `/moth:moth-fix <TICKET-ID>`.
