# device-server

On-device server started with `app_process` over adb (no root, no app install). It is derived from
[scrcpy-server](https://github.com/Genymobile/scrcpy/tree/master/server) (Apache-2.0); see [NOTICE](../NOTICE).
Design: [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).

## Current state (M0)

The full server fork starts in M1. For now headroid ships a patch against scrcpy v4.1:

| Patch | What it does |
|---|---|
| [`0001-steal-top-focus-disabled.diff`](patches/0001-steal-top-focus-disabled.diff) | On Android 14+, adds `VIRTUAL_DISPLAY_FLAG_STEAL_TOP_FOCUS_DISABLED` (`1 << 16`) to `--new-display`, so input injected into the hidden display never takes focus or the keyboard from the user. Verified in [M0](../docs/m0/RESULTS.md). |

The patch modifies `server/src/main/java/com/genymobile/scrcpy/video/NewDisplayCapture.java`
(Copyright (C) Genymobile / Romain Vimont, Apache-2.0). The changed lines are marked `headroid:`.

## Build the patched server

Needs JDK 17 and the Android SDK (platform 36). On Windows, clone to a short path to avoid long-path errors.

```sh
git clone --depth 1 --branch v4.1 https://github.com/Genymobile/scrcpy.git
cd scrcpy
git apply ../headroid/device-server/patches/0001-steal-top-focus-disabled.diff
echo "sdk.dir=/path/to/Android/Sdk" > local.properties   # forward slashes on Windows too
./gradlew :server:assembleRelease
```

Use it with an installed scrcpy 4.1 client (the versions must match):

```sh
SCRCPY_SERVER_PATH=server/build/outputs/apk/release/server-release-unsigned.apk \
  scrcpy --new-display=1080x2400/420 --start-app=<package> --no-vd-system-decorations \
         --display-ime-policy=hide --no-audio --no-window --no-playback --record=run.mp4
```
