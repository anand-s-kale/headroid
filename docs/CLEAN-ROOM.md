# Clean-room policy

headroid is licensed under Apache-2.0. Every line in this repository must be ours, or come from a source whose licence
lets us reuse it. This page explains how we learn from other projects without copying them.

## Why

Code on GitHub is not automatically open source. When a repository has **no licence**, the author keeps all rights by
default: you may read it, but you may not copy, translate, or closely paraphrase it. A **non-commercial** licence
(e.g. PolyForm Noncommercial) is incompatible with Apache-2.0. Ideas, techniques, Android API facts and protocol
behaviour are not protected, so we can learn those and write our own implementation.

## Source categories

| Category | Examples | What we may do |
|---|---|---|
| **Reusable** (Apache-2.0, MIT, BSD) | scrcpy, Shizuku, Appium, uiautomator2, ClosePaw, Ruto-GLM, lamda client, AOSP | Copy or adapt code **with attribution**: keep the original copyright header, note the changes, add to [NOTICE](../NOTICE) |
| **Read-only** (no licence) | Mua, PhoneAgent | Read to understand ideas. **Never** copy, translate or paraphrase code |
| **Read-only** (non-commercial / incompatible) | android-virtual-screen (PolyForm NC) | Same as above |
| **Facts** | Android docs, AOSP flag values, `adb`/`am`/`input` commands | Use freely |

## Process

1. **Reader:** studies a read-only project and writes plain-language notes in [`docs/research/TECHNIQUES.md`](research/TECHNIQUES.md):
   behaviour, approach, Android APIs used, pitfalls. **No code, no copied identifiers, no copied comments or strings.**
2. **Implementer:** writes headroid code from those notes, Android documentation, AOSP source and reusable projects.
   While writing a component, the implementer does not open read-only sources for that component.
3. **Review:** pull requests that touch areas covered by read-only projects state in the PR template that no read-only
   code was used. Reviewers reject anything that looks transliterated.
4. **Attribution:** code adapted from a reusable project keeps its licence header, and the PR adds it to `NOTICE`.

When we wanted something a read-only project has, we prefer to ask its author to add a permissive licence.

AI agents working in this repo follow the same rules (see [AGENTS.md](../AGENTS.md)).
