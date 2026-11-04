# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""Which Android keys headroid sends to a hidden display, and key names for Page.press."""

from __future__ import annotations

# The keys headroid sends: editing and navigation keys that act on the focused window of the hidden display.
# Everything else is refused: many keys act on the whole phone or its main screen whatever display the event
# names (HOME, POWER, volume, calls, media, camera, assistant, app-launch keys, Recents, settings, ...).
ALLOWED_KEYS = {
    4: "BACK",
    19: "DPAD_UP",
    20: "DPAD_DOWN",
    21: "DPAD_LEFT",
    22: "DPAD_RIGHT",
    23: "DPAD_CENTER",
    61: "TAB",
    62: "SPACE",
    66: "ENTER",
    67: "DEL",
    82: "MENU",
    111: "ESCAPE",
    112: "FORWARD_DEL",
    122: "MOVE_HOME",
    123: "MOVE_END",
}
# Printable keys: 0-9, A-Z, comma, period, ` - = [ ] \ ; ' / @, plus.
PRINTABLE_KEYS = frozenset([*range(7, 17), *range(29, 57), *range(68, 78), 81])

# Names of refused keys, for the error message.
REFUSED_KEY_NAMES = {
    3: "HOME",
    5: "CALL",
    6: "ENDCALL",
    24: "VOLUME_UP",
    25: "VOLUME_DOWN",
    26: "POWER",
    27: "CAMERA",
    79: "HEADSETHOOK",
    83: "NOTIFICATION",
    84: "SEARCH",
    85: "MEDIA_PLAY_PAUSE",
    91: "MUTE",
    120: "SYSRQ",
    164: "VOLUME_MUTE",
    176: "SETTINGS",
    187: "APP_SWITCH",
    219: "ASSIST",
    223: "SLEEP",
    224: "WAKEUP",
    231: "VOICE_ASSIST",
    284: "ALL_APPS",
}

_NAMES = {
    **{name: code for code, name in ALLOWED_KEYS.items()},
    **{name: code for code, name in REFUSED_KEY_NAMES.items()},
    **{chr(ord("A") + i): 29 + i for i in range(26)},
    **{str(i): 7 + i for i in range(10)},
    "DELETE": 67,
    "BACKSPACE": 67,
    "ESC": 111,
    "RETURN": 66,
}


def key_allowed(code: int) -> bool:
    return code in ALLOWED_KEYS or code in PRINTABLE_KEYS


def press_code(key: str | int) -> int:
    """KEYCODE number for a name like "BACK", "enter", "KEYCODE_TAB" or "A" (or a number). Raises ValueError
    for an unknown name and PermissionError for a key that would act on the whole phone."""
    if isinstance(key, int):
        code = key
    else:
        name = str(key).strip().upper().removeprefix("KEYCODE_")
        if name in _NAMES:
            code = _NAMES[name]
        elif name.isdigit():
            code = int(name)
        else:
            known = ", ".join(sorted(ALLOWED_KEYS.values()))
            raise ValueError(
                f"unknown key {key!r}: use one of {known}, a letter, a digit or a KEYCODE_* number"
            )
    if not key_allowed(code):
        name = REFUSED_KEY_NAMES.get(code, str(code))
        raise PermissionError(
            f"KEYCODE_{name} acts on the whole phone or its main screen (display 0), not on the hidden "
            "display; headroid does not send it."
        )
    return code
