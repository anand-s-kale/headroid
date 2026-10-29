# packages

Host-side Python packages (`headroid/` skeleton exists, rest planned, see [ADR 0003](../docs/adr/0003-compose-open-source-stack.md)):

| Module | Purpose |
|---|---|
| `headroid` | SDK: `Device`, `Page`, `Locator`, auto-wait, screenshots (on `adbutils`) |
| `headroid.test` | pytest plugin: fixtures, `expect`, reports, traces |
| `headroid.mcp` | MCP server exposing headroid to AI agents |
| `headroid.cli` | `pair`, `doctor`, `run`, `record` |

A TypeScript client may follow; the device-server protocol is language-neutral.
