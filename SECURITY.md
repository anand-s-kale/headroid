# Security policy

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Use GitHub's private
[Report a vulnerability](../../security/advisories/new) form. We aim to reply within 7 days.

## Scope

headroid controls a phone through ADB and a shell-uid server, which can read the screen, inject input and launch apps.
Relevant reports include:

- the device server accepting connections from anything other than the adb-forwarded host;
- the device server leaving a display, process or forwarded port behind after the host disconnects;
- captures, traces or logs leaking content from the owner's physical display or other apps;
- anything that lets headroid gain privileges beyond the shell user.

## Responsible use

- Only use headroid on devices you own or are explicitly authorised to test.
- Turn off Wireless debugging when you are not testing, and only pair on networks you trust.
- Treat traces and screenshots as sensitive: they may contain personal data.
- headroid is a testing tool. It must not be used to automate other people's accounts, bypass app protections
  (for example `FLAG_SECURE`), or evade bot detection.
