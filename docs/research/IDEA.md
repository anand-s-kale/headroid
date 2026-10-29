# Idea: Headless Android app testing on a physical phone, driven by AI agents

Goal: a Playwright-like, open-source "headless" automation framework for native Android apps on the owner's REAL phone,
so AI agents can launch / navigate / tap / swipe / type / screenshot / inspect UI / run test scenarios / write bug reports
in the BACKGROUND while the owner keeps using the same phone normally (WhatsApp, YouTube, Instagram) on the main screen.

Requirements:
- Physical Android phone (no emulator, no cloud device farm), connected via Wireless ADB (Android 11+ wireless debugging).
- App under test runs on a separate, invisible/off-screen VIRTUAL DISPLAY; physical display stays the owner's.
- Independent input: injected taps/swipes/keys/text go only to the virtual display, never to the physical touchscreen.
- Keyboard/IME focus, activity lifecycle (onPause/onStop when not "visible"), screenshots of the virtual display, UI hierarchy
  (UiAutomator/accessibility) per display.
- Determine what works on NON-ROOTED devices via the adb shell user (uid 2000) vs. what needs root / privileged perms / system mods.
- Fork/combine open source: scrcpy (it already has --new-display / virtual display support), ADB, UiAutomator2, Appium, etc.
- Initial targets: React Native + native Android apps; Flutter later.
Architecture: AI Agent -> Automation Controller -> Wireless ADB -> on-device service (app_process, like scrcpy-server)
  -> isolated VirtualDisplay -> app under test.
