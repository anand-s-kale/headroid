# ADR 0002: Device server derived from scrcpy-server, TypeScript host

Date: 2026-10-29 · Status: proposed (confirm after M0). Host language superseded by [ADR 0003](0003-compose-open-source-stack.md): Python-first.

## Context
A non-root process must create a hidden virtual display, launch apps on it, inject input to it, capture it and read
its UI tree. scrcpy-server already does the first three as the shell user via `app_process` on Android 10–16, and it
is actively maintained. The alternatives are an installed app using Shizuku (extra install and pairing on the phone)
or Appium/UiAutomator2 (built around the main display, and heavy).

## Decision
- Device side: a Java server derived from scrcpy-server and started over adb. We add JSON-RPC, a focus guard
  (`STEAL_TOP_FOCUS_DISABLED`), IME policy `HIDE`, ImageReader capture and a per-display UiAutomation tree.
- Host side: TypeScript (SDK, runner, MCP server), because Playwright's API and the MCP SDKs are TypeScript-first.
  A Python client can follow.

## Consequences
We track scrcpy upstream for Android version fixes. Shell permissions may shrink in future Android releases
(see the Android 15 QPR trusted-display report). `headroid doctor` must detect that and say so clearly.
