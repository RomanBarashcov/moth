Fixes <TICKET-URL>

<!--
Written in layers, most important first. A reviewer who reads only the top 4 lines must know:
what broke, what changed, what to check, and how sure Moth is. Every line ≤ 1 sentence.
-->

## ✅ Fixed | ⚠️ Partly fixed | 🙋 Needs your input: <the bug, in the user's words>

**Was:** <what the user saw>
**Now:** <what the user sees>
**Check before merging:** <1–3 concrete things, e.g. "the empty-cart copy with product", or "nothing special">
**Confidence:** high / medium / low · tests 🔴→🟢 · judge ✅ <satisfaction> · <why, a few words>

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
