# Moth

A Claude Code plugin that takes a bug ticket from Linear or Jira, reproduces it, fixes it test-first and opens a PR with re-runnable proof. Every run leaves a **Blackbox**: a log of where the workflow succeeded or broke.

The name comes from the moth taped into the Harvard Mark II logbook in 1947 as the "first actual case of bug being found".

## How it fits together

```
moth/                 ← this repo: the generic plugin
acme-moth/            ← one workspace per system (not in this repo)
  system.yaml         ← repos, environments, MCP servers, tracker, guardrails
  repos/              ← service repos
  runs/<ID>/          ← Blackbox for every run, success or failure
  knowledge/          ← INDEX.md + one record per fixed bug
  feedback/           ← INDEX.md + FB-NNN records: every proposal to improve Moth (problem → motivation → decision → output)
```

- Fix PRs go to the service repos.
- Moth's own files (Blackbox, knowledge, raw media) stay in the workspace.
- Before/after screenshots and GIFs for the PR description go to an orphan `moth-evidence` branch in the service repo. It shares no history with the code and is never merged, and the PR links to a pinned commit on it (`skills/moth-fix/scripts/collect-evidence.sh`).

## Try it locally

```bash
mkdir acme-moth && cd acme-moth
claude --plugin-dir /path/to/moth
> /moth:moth-init          # detects repos, MCPs, boards; asks only what it cannot detect
> /moth:moth-fix ACME-123  # fix one ticket
```

The config shape is in [`examples/system.yaml`](examples/system.yaml).

## Guardrails

The `hooks/guard.py` `PreToolUse` hook is active only inside a workspace that has `.moth/guard.json`. Everywhere else it does nothing. It denies:
- force pushes, pushes to main/master and `gh pr merge`. These are checked per sub-command, so `git push origin moth/X && gh pr create --base main` is allowed. Cases are in `hooks/test_guard.py`;
- write-like tools (`create`, `update`, `delete`, `execute`...) on MCP servers listed as staging/prod read-only;
- the extra regexes in `guardrails.bash_deny`.

It is the second line of defence. Use read-only credentials for prod data first.

## Recommended plugins

`moth-init` checks for these and suggests install commands:
- `linear` or `atlassian` (tracker)
- `playwright` (evidence)
- `superpowers` (TDD and debugging)
- Sentry, Axiom and Grafana MCPs (read-only diagnostics)

## Status

v0.1: the `moth-init` and `moth-fix` skills plus the guard hook, run interactively. There is no harness yet.
