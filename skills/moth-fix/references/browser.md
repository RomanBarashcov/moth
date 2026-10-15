# Browser: which tool for what

Two jobs, two kinds of tool. Don't mix them up.

## Proof: specs, screenshots, video

Always `npx playwright test`. It is the only proof that can be re-run: the verifier repeats it, the reviewer runs it with `--headed`. It needs the npm package, not the Playwright MCP.

- **The repo has a `playwright_config`:** run from that config's folder, as the skill says.
- **A UI repo without Playwright:** don't add Playwright to the repo. Use one shared install, so the fixer, the verifier and retests run the same version and it is downloaded once:
  ```bash
  PW="${XDG_CACHE_HOME:-$HOME/.cache}/moth/playwright"
  [ -d "$PW/node_modules/@playwright/test" ] || { mkdir -p "$PW" && cd "$PW" && npm init -y >/dev/null && npm i -D @playwright/test && npx playwright install chromium; }
  ln -sfn "$PW/node_modules" "$SCRATCH/node_modules"
  cd "$SCRATCH"
  ```
  Write `$SCRATCH/playwright.config.ts` with `use: { baseURL: '<local app URL>', video: 'on', screenshot: 'on', trace: 'on' }`, put the spec next to it, and run `npx playwright test` from `$SCRATCH`. The spec is never committed, so paste it into the PR's "Reproduce it yourself" block.

## Looking around and reading logs

To explore the app, read console errors or watch network requests, use the tool named in `browser.mcp` in `system.yaml` (`builtin` is Claude's built-in browser). If it is `auto`, unset or not available, take the first one you have:

1. **Playwright MCP**: navigate, page snapshot, console messages, network requests.
2. **Chrome DevTools MCP**: console logs, network requests with status and body.
3. **Claude in Chrome**, or Claude's built-in browser. Load its skill first. Claude in Chrome drives the user's real browser with their sign-ins: work in a new tab and stay on local or staging URLs, never a prod admin page.

None of them? Use `curl` for pages and APIs, plus the read-only log MCPs, and note "no browser tool" in the Blackbox.

The same rules apply with every tool:
- On `local`, click freely.
- On staging and prod, only look: never submit a form, save, delete, pay or send anything.
- A screenshot from these tools is a note for you, not proof. Proof comes from the spec.
