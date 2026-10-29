# Instructions for AI coding agents

This repo is built with several agents (Claude Code, OpenAI Codex, Google Antigravity/Gemini). All of them read this file.

## Hard rules

1. **Clean room.** Follow [docs/CLEAN-ROOM.md](docs/CLEAN-ROOM.md). Do not fetch, paste, translate or paraphrase code
   from unlicensed or non-commercial projects (Mua, PhoneAgent, android-virtual-screen). Use
   [docs/research/TECHNIQUES.md](docs/research/TECHNIQUES.md), AOSP and permissively licensed sources instead.
   Keep the original licence header on any adapted Apache-2.0 / MIT code and add it to `NOTICE`.
2. **Phone safety.** The test phone may be the owner's personal phone. Check what is in the foreground
   (`adb shell dumpsys window | grep mCurrentFocus`) before acting. Never touch display 0 except for setup the owner
   asked for. Never open, read or screenshot the owner's personal apps.
3. **Honest verification.** Say exactly what ran, on which device and Android version. Mark anything else UNVERIFIED.
4. **One agent per branch/worktree.** Branches: `claude/<topic>`, `codex/<topic>`, `agy/<topic>`. Only the lead merges.
5. Reviews are read-only: report findings, do not edit.

## Layout

- `device-server/`: Java, runs on the phone via `app_process` (derived from scrcpy-server, Apache-2.0)
- `packages/`: Python host SDK, CLI, test runner, MCP server
- `integrations/`: drivers that run ARTEMIS / mobile-use on the hidden display
- How third-party code is mixed in (adapt / depend / integrate) and attributed: [docs/adr/0003](docs/adr/0003-compose-open-source-stack.md)
- `docs/`: architecture, roadmap, capability matrix, ADRs, research
