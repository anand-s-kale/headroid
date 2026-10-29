# ADR 0001: License under Apache-2.0

Date: 2026-10-29 · Status: accepted

## Context
headroid builds on scrcpy-server (Apache-2.0) and sits next to Appium, Playwright, Maestro and Shizuku, all Apache-2.0.
We want companies and individuals to use and contribute freely, and we want protection against patent claims.

## Decision
Apache License 2.0 for all original code, with a `NOTICE` file for attributions and DCO sign-off for contributions.

## Alternatives
- **MIT:** simpler, but no explicit patent grant. Code adapted from scrcpy would still carry Apache-2.0 terms.
- **GPL-3.0 / AGPL:** would keep forks open, but discourages adoption in company test pipelines.
- Code without a licence, or under a non-commercial licence (Mua, PhoneAgent, android-virtual-screen), cannot be
  included under any of these. See [CLEAN-ROOM.md](../CLEAN-ROOM.md).

## Consequences
Derived scrcpy files keep their headers and state their changes. Anyone may fork headroid, including commercially.
