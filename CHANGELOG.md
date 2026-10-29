# Changelog

All notable changes are recorded here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]
### Added
- Project charter, architecture, roadmap, capability matrix, clean-room policy and research reports.
- M0 proof of concept on a POCO F6 (Android 16): GO. scrcpy-server patch adding `STEAL_TOP_FOCUS_DISABLED`
  (`device-server/patches/`), results and evidence in `docs/m0/`, first verified device in the capability matrix.
- Implementation plan for the full product (`docs/superpowers/plans/`).
- headroid sample app `dev.headroid.sample` (`sample-app/`) built by GitHub Actions with the debug APK as an artifact.
- M1 device server (`device-server/`): fork of scrcpy-server v4.1 (the M0 patch is now in tree) with JSON-RPC,
  hidden displays, per-display input, screenshots, UI tree and teardown. Unit-tested; not yet run on a device.
- Python host skeleton (`packages/headroid`) and an emulator/phone smoke script.
