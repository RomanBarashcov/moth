Fixes <TICKET-URL>

## 🧭 Blackbox
**Verdict:** ✅ fixed | ⚠️ partially fixed | 🙋 needs human input
**Confidence:** high / medium / low — <why, one line>
**Reached:** intake ✓ env ✓ reproduce ✓ fix ✓ evidence ✓

### Needs human input
- [ ] <question or approval, or "none">

### How it was reproduced
1. <3–5 concrete steps>

### Proof
- Red → green: `<test command>`
- Re-run it yourself: `npx playwright test bugs/<TICKET-ID>.spec.ts --headed`

#### Before / after
<!-- Output of `collect-evidence.sh markdown`; images live on the never-merged evidence branch. Non-UI bugs: red/green output or request/response diff instead. -->
| | Before (base) | After (fix) |
|---|---|---|
| `<test>` | ![before](<BASE>/before-<test>.png?raw=true) | ![after](<BASE>/after-<test>.png?raw=true) |
| recording | ![before](<BASE>/before-<test>.gif?raw=true) | ![after](<BASE>/after-<test>.gif?raw=true) |

### Root cause
<one or two sentences>

<details><summary>Full Blackbox</summary>

<!-- templates/blackbox.md, filled in -->

</details>
