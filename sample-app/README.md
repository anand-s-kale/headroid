# headroid sample app

A small native Android app (Kotlin, framework widgets only, no AndroidX) used as headroid's own test target and demo.
Package `dev.headroid.sample`, minSdk 26, target 35, version 0.1.0. Every control has a resource-id
(`dev.headroid.sample:id/<name>`) and a content description. Interesting events are logged to logcat with tag
`HeadroidSample`.

Login: `demo@headroid.dev` / `headroid`

## Screens

| Activity | Resource-ids | Behaviour |
|---|---|---|
| `MainActivity` | `nav_login`, `nav_form`, `nav_list`, `nav_checkout`, `nav_effects`, `nav_crash`, `nav_secure`, `nav_timer` | One button per screen |
| `LoginActivity` | `login_email`, `login_password`, `login_submit`, `login_error` | Valid credentials open `FormActivity`; otherwise `login_error` shows "Invalid email or password" |
| `FormActivity` | `form_name`, `form_phone`, `form_notes`, `form_newsletter`, `form_plan` (`plan_free`, `plan_pro`), `form_submit`, `form_result` | Submit shows "Saved: <name>" |
| `ListActivity` | `list_items`, `list_selected` | 200 items; tap shows "Selected: Item N" |
| `CheckoutActivity` | `checkout_step`, `checkout_cart`, `checkout_address`, `checkout_address_input`, `checkout_pay`, `checkout_done`, `checkout_next`, `checkout_back` | Three steps then "Order placed"; Next disabled on step 2 until the address is non-empty |
| `EffectsActivity` | `effects_sound`, `effects_vibrate`, `effects_toast`, `effects_dialog`, `effects_dialog_result`, `effects_notification`, `effects_permission`, `effects_permission_result` | Beep (300 ms), vibrate (300 ms), toast, dialog (OK/Cancel), notification (channel `sample`), camera permission request |
| `CrashActivity` | `crash_now`, `anr_now` | Throws `IllegalStateException("headroid sample crash")`; blocks the main thread for 20 s |
| `SecureActivity` | `secure_text` | `FLAG_SECURE` set |
| `TimerActivity` | `timer_value`, `timer_started_at` | Seconds since start, updated every second; logs every 10 s |

## Build

Requires JDK 17 and the Android SDK (put `sdk.dir=...` in `sample-app/local.properties`, which is gitignored).

```
cd sample-app
./gradlew :app:assembleDebug :app:lintDebug
```

The APK is `app/build/outputs/apk/debug/app-debug.apk`. CI (`.github/workflows/sample-app.yml`) builds it on every push,
uploads it as the `headroid-sample-debug` artifact, and attaches it to releases on `v*` tags.

Licensed under Apache-2.0.
