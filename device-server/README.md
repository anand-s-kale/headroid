# device-server

On-device server started with `app_process` over adb (no root, no app install). It is a fork of
[scrcpy-server](https://github.com/Genymobile/scrcpy/tree/master/server) **v4.1** (Apache-2.0, see
[`LICENSE-scrcpy`](LICENSE-scrcpy) and [NOTICE](../NOTICE)). Design: [design §6.1](../docs/superpowers/specs/2026-10-30-headroid-design.md),
tasks and wire protocol: [implementation plan](../docs/superpowers/plans/2026-10-30-headroid-implementation.md).

## Layout

| Path | What |
|---|---|
| `server/src/main/java/com/genymobile/scrcpy/` | Upstream scrcpy-server v4.1, unchanged except lines marked `headroid:` |
| `server/src/main/java/dev/headroid/server/` | headroid's server: JSON-RPC, hidden displays, input, screenshots, UI tree, teardown |
| `server/src/test/java/dev/headroid/server/` | JVM unit tests for the parts that do not need a phone |

Changes to upstream files (all marked `headroid:`):

- `video/NewDisplayCapture.java`: on Android 14+, adds `VIRTUAL_DISPLAY_FLAG_STEAL_TOP_FOCUS_DISABLED` (`1 << 16`) to
  `--new-display`, so input injected into the hidden display never takes focus or the keyboard from the user
  (verified in [M0](../docs/m0/RESULTS.md); this was `patches/0001-steal-top-focus-disabled.diff`).
- `build.gradle`: application id `dev.headroid.server`, `minSdk 29`, version `0.1.0`, `headroidJar` task.

The upstream scrcpy entry point (`com.genymobile.scrcpy.Server`) still works with a scrcpy 4.1 client, which is
handy to watch a hidden display while debugging. Unused upstream parts (audio, camera, UHID) are stripped later
(plan Task 1.11).

## Build

Needs JDK 17 and the Android SDK (platform 36). `local.properties`: `sdk.dir=C:/path/to/Android/Sdk` (forward slashes
on Windows too).

```sh
./gradlew :server:headroidJar :server:testDebugUnitTest
# -> server/build/headroid/headroid-server.jar
```

GitHub Actions builds the same jar on every push to `device-server/**` (artifact `headroid-server`).

## Run (by hand)

```sh
adb -s <serial> push server/build/headroid/headroid-server.jar /data/local/tmp/headroid-server.jar
adb -s <serial> shell CLASSPATH=/data/local/tmp/headroid-server.jar app_process / dev.headroid.server.HeadroidServer socket=headroid
adb -s <serial> forward tcp:27183 localabstract:headroid
```

Then send newline-delimited JSON-RPC 2.0 to `127.0.0.1:27183`, for example
`{"jsonrpc":"2.0","id":1,"method":"server.info"}`. The Python host in [`packages/headroid`](../packages/headroid) does
all of this for you.

Server arguments: `socket=<name>` (default `headroid`), `grace_ms=<n>` (teardown delay after the host disconnects,
default 15000), `log=verbose|debug|info|warn|error`.
