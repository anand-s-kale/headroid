# Contributing to headroid

Thanks for helping. headroid is early, so the most valuable contributions right now are:

1. **Device reports:** run the M0 experiment on your phone and file a [device report](../../issues/new?template=device_report.yml).
2. **Research corrections:** if something in [docs/research](docs/research/) is wrong, open an issue with a source.
3. **Code** for the milestones in the [roadmap](docs/ROADMAP.md). Comment on an issue before starting large work.

## Ground rules

- **Clean room.** Read [docs/CLEAN-ROOM.md](docs/CLEAN-ROOM.md). Never paste, translate or paraphrase code from
  projects without a compatible licence. Code adapted from Apache-2.0 / MIT / BSD projects keeps its original header
  and is listed in [NOTICE](NOTICE).
- **Sign your commits (DCO).** Add `Signed-off-by: Your Name <email>` with `git commit -s`. It certifies that you
  wrote the change or have the right to submit it under Apache-2.0 ([developercertificate.org](https://developercertificate.org/)).
- **One topic per pull request.** Describe what changed, how you tested it, and on which device and Android version.
- **Be honest about verification.** "Tested on Pixel 8, Android 15" or "not tested on a device" are both fine.
  Unverified claims are not.
- **Respect privacy.** Never commit screenshots, logs or traces that show personal data from your phone.

## Development setup

Nothing to build yet. Tooling (JDK 17 + Android SDK for `device-server/`, Python 3.12+ with `uv` for `packages/` and
`integrations/`) will be documented here when M1 starts.

## Reusing code from other projects

Read [ADR 0003](docs/adr/0003-compose-open-source-stack.md). Apache-2.0 / MIT / BSD code (scrcpy, ARTEMIS, mobile-use,
uiautomator2…) is welcome: keep its copyright header, add a "modified for headroid" line, and update `NOTICE`.

## Commit style

[Conventional Commits](https://www.conventionalcommits.org/): `feat(server): ...`, `fix(sdk): ...`, `docs: ...`.

## Code of conduct

Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md).
