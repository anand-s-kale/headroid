# Research (2026-10-29)

These reports decided whether headroid was worth building. Four AI agents did the research, and they disagreed in
places. **Start with [SUMMARY.md](SUMMARY.md)**: it records which claims held up, and which were wrong after checking
against source code.

| Report | Author | Question |
|---|---|---|
| [IDEA.md](IDEA.md) | owner | The original brief |
| [FEASIBILITY-claude.md](FEASIBILITY-claude.md) | Claude Opus | Can Android do this without root? (AOSP and scrcpy internals, 1-hour PoC) |
| [VIABILITY-codex.md](VIABILITY-codex.md) | OpenAI Codex | Go / no-go, risks, who would use it |
| [PRIOR-ART-claude.md](PRIOR-ART-claude.md) | Claude Sonnet | Does it already exist on GitHub? |
| [REVIEW-gemini.md](REVIEW-gemini.md) | Gemini (Antigravity) | Cross-review of the three reports |
| [TECHNIQUES.md](TECHNIQUES.md) | Claude Sonnet | Clean-room notes: ideas from related projects, no code |

Known corrections:
- PRIOR-ART says Appium has no display-id support. It does (`currentDisplayId`, Android 11+).
- REVIEW says the PoC `scrcpy --no-window --no-audio` command exits with "nothing to do". It doesn't, because control stays enabled.

**Nothing in these reports has been verified on a physical device yet.** That is milestone M0.
