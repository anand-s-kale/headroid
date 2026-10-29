# integrations

Adapters that make existing open-source mobile agents **headless**: they run on headroid's hidden display instead of
the phone's real screen. We plug into these agents rather than forking their logic (see
[ADR 0003](../docs/adr/0003-compose-open-source-stack.md)), and offer each adapter upstream.

| Folder | Target | Seam | Licence of target |
|---|---|---|---|
| `artemis/` (M3) | [google/artemis](https://github.com/google/artemis) | `artemis.drivers.base.BaseDeviceDriver` | Apache-2.0 |
| `mobile-use/` (M3) | [minitap-ai/mobile-use](https://github.com/minitap-ai/mobile-use) | `minitap.mobile_use.controllers` | Apache-2.0 |

Files derived from these projects keep their original copyright header plus a "modified for headroid" line, and are
listed in [NOTICE](../NOTICE).
