# Capability matrix

What actually works, per device, **without root**. Entries move from *expected* to *verified* only with a device report.
Add yours with the [device report issue form](../../../issues/new?template=device_report.yml).

Legend: ✅ works · ⚠️ works with caveats · ❌ does not work · ❔ untested

## Expected (from research, not yet verified)

| Capability | A10–12 | A13 | A14–16 | Source |
|---|---|---|---|---|
| Create hidden virtual display (shell uid) | ✅ | ✅ | ✅ | scrcpy `--new-display` |
| Trusted display (`ADD_TRUSTED_DISPLAY`) | ❌ | ✅ | ⚠️ (A15 QPR regression reported) | AOSP shell manifest; scrcpy #5523 |
| Launch any exported activity on it | ✅ | ✅ | ✅ | `am start --display N` |
| Input only on the hidden display | ✅ | ✅ | ✅ | `input -d N` |
| User keeps focus while agent taps | ❌ | ❌ | ⚠️ | `STEAL_TOP_FOCUS_DISABLED` |
| Hide keyboard on test display | ❌ | ✅ | ✅ | display IME policy |
| Frame capture | ✅ | ✅ | ✅ | own ImageReader |
| Per-display UI tree | ⚠️ (A11+) | ✅ | ✅ | UiAutomation windows on all displays |
| `FLAG_SECURE` content | ❌ | ❌ | ❌ | secure displays need root |
| Isolated audio / notifications | ❌ | ❌ | ❌ | shared system services |
| Runs with screen off / locked | ❔ | ❔ | ❔ | to test |

## Verified devices

| Device | Android / skin | Date | Reporter | Results |
|---|---|---|---|---|
| _none yet_ | | | | |
