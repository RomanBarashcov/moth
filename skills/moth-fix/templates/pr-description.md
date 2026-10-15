Fixes <TICKET-URL>

<!--
The reader skims. Shape it so they can act from the first lines:
- Line 1 under the title is what the reviewer does, with a time in minutes.
- Checks are numbered, one action each, at most 3.
- {a | b | c} means: write exactly one of them. Never leave the choices in.
- One fact per line. No preamble, no recap, no "let me know".
-->

## {✅ Fixed | ⚠️ Partly fixed | 🙋 Needs your input}: <the bug, in the user's words>

**Your review (~<N> min):**
1. <one concrete check, e.g. "Open /cart with no items: the empty-cart text shows">
2. <optional second check>
<!-- Nothing risky? Write a single line: "1. Nothing special: merge when CI is green." -->

**Was:** <what the user saw>
**Now:** <what the user sees>

| | |
|---|---|
| Own tests | 🔴 → 🟢 `<test name>` |
| Judge | {✅ satisfied · <score> | ❌ not satisfied · <score> | ❌ <score>, below <min_satisfaction> | ⚠️ inconclusive · <reason>} |
| Confidence | {high | medium | low}: <why, a few words> |

### Before / after
<!-- Output of `collect-evidence.sh markdown`; images live on the never-merged evidence branch. Non-UI bugs: red/green output or request/response diff instead. -->
| | Before (base) | After (fix) |
|---|---|---|
| `<test>` | ![before](<BASE>/before-<test>.png?raw=true) | ![after](<BASE>/after-<test>.png?raw=true) |
| recording | ![before](<BASE>/before-<test>.gif?raw=true) | ![after](<BASE>/after-<test>.gif?raw=true) |

### Why it broke
<one or two sentences: the root cause and the change that fixes it>

<details><summary>🧪 Independent check: <verdict>, <satisfaction></summary>

<!-- The block returned by the moth-verifier agent, pasted as is (format: agents/moth-verifier.md). Holdout scenarios were written from the ticket only, by an agent that never saw the code; the fixer never saw them. -->

</details>

<details><summary>🔁 Reproduce it yourself</summary>

1. <3–5 concrete steps>

- Red → green: `<test command>`
- Playwright: `cd <dir of playwright_config> && npx playwright test bugs/<TICKET-ID> --headed`

</details>

<details><summary>🧭 Run log (Blackbox)</summary>

<!-- templates/blackbox.md, filled in: timeline, what was tried, sibling bugs, workflow gaps. For debugging Moth, not for reviewing the fix. -->

</details>
