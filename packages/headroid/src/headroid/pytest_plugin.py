# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""pytest plugin: `headroid_device` and `headroid_page` fixtures, the `headroid` marker and failure artifacts.

Loaded automatically once headroid is installed (entry point pytest11 "headroid"). Needs pytest >= 7.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import pytest

from .adb import AdbError, list_devices
from .device import Device

ARTIFACTS_DIR = "headroid-artifacts"
_NAME_MAX = 70
_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_PAGE = pytest.StashKey["object"]()


def pytest_addoption(parser):
    group = parser.getgroup("headroid", "headroid (Android apps on a hidden display)")
    group.addoption(
        "--headroid-serial",
        default=None,
        help="adb serial of the phone (needed when several are attached)",
    )
    group.addoption(
        "--headroid-app",
        default=None,
        help="package the `headroid_page` fixture launches when the test has no "
        "@pytest.mark.headroid(app=...)",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "headroid(app): package name the `headroid_page` fixture launches on a hidden display",
    )


def _device_problem(serial: str | None) -> tuple[str, str] | None:
    """("skip" | "fail", reason) when no device can be used, else None.

    Skip: adb missing or no ready device (a machine without a phone). Fail: a usage error (several ready
    devices and no --headroid-serial, or a --headroid-serial that is not attached)."""
    try:
        devices = list_devices(os.environ.get("ADB", "adb"))
    except AdbError as e:
        return "skip", f"headroid: {e}"
    ready = [d["serial"] for d in devices if d["state"] == "device"]
    if serial is not None:
        if serial not in ready:
            listed = ", ".join(f"{d['serial']} ({d['state']})" for d in devices) or "none"
            return (
                "fail",
                f"headroid: --headroid-serial {serial} is not attached and ready (adb devices: {listed})",
            )
        return None
    if not ready:
        if devices:
            listed = ", ".join(f"{d['serial']} ({d['state']})" for d in devices)
            return "skip", (
                f"headroid: no ready Android device: {listed}; accept the USB debugging prompt on the phone, "
                "or reconnect it"
            )
        return "skip", "headroid: no Android device attached (adb devices lists none)"
    if len(ready) > 1:
        return (
            "fail",
            f"headroid: several devices attached ({', '.join(ready)}); pass --headroid-serial S",
        )
    return None


def _open_device(serial: str | None) -> Device:
    """Connects to the phone; skips (no phone) or fails (usage error) with the reason otherwise."""
    problem = _device_problem(serial)
    if problem:
        kind, reason = problem
        if kind == "skip":
            pytest.skip(reason)
        pytest.fail(reason, pytrace=False)
    return Device.connect(serial=serial)


@pytest.fixture(scope="session")
def headroid_device(request):
    """A headroid Device for the whole session (closed at the end)."""
    dev = _open_device(request.config.getoption("--headroid-serial"))
    yield dev
    dev.close()


def _marker_app(marker) -> str | None:
    if marker is None:
        return None
    if marker.args and "app" in marker.kwargs:
        raise ValueError(
            'headroid marker: give the app once, as headroid("pkg") or headroid(app="pkg")'
        )
    app = marker.args[0] if marker.args else marker.kwargs.get("app")
    extra = set(marker.kwargs) - {"app"}
    if len(marker.args) > 1 or extra or (app is not None and (not isinstance(app, str) or not app)):
        raise ValueError(
            f'headroid marker: expected headroid("pkg") or headroid(app="pkg"), got '
            f"args={marker.args!r} kwargs={marker.kwargs!r}"
        )
    return app


@pytest.fixture
def headroid_page(request, headroid_device):
    """A hidden display with the app from @pytest.mark.headroid(app=...) or --headroid-app; closed after the
    test. When the test body fails, its screenshot and UI tree are saved under headroid-artifacts/<test id>/
    in the rootdir."""
    try:
        app = _marker_app(request.node.get_closest_marker("headroid"))
    except ValueError as e:
        pytest.fail(str(e), pytrace=False)
    app = app or request.config.getoption("--headroid-app")
    if not app:
        pytest.fail(
            "headroid: no app for the `headroid_page` fixture: add "
            '@pytest.mark.headroid(app="com.your.app") or pass --headroid-app',
            pytrace=False,
        )
    p = headroid_device.new_page(app)
    request.node.stash[_PAGE] = p
    yield p
    p.close()


def _artifact_name(nodeid: str) -> str:
    """A short, unique, Windows-safe folder name for a test id."""
    digest = hashlib.sha1(nodeid.encode("utf-8")).hexdigest()[:8]
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", nodeid).strip("_")[:_NAME_MAX].rstrip(". _")
    if name.split(".")[0].upper() in _RESERVED:
        name = "_" + name
    return f"{name}-{digest}" if name else digest


def _save_artifacts(page, folder: Path) -> list[tuple[str, str]]:
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except Exception as e:  # noqa: BLE001 - never crash pytest or hide the test's own failure
        return [("headroid_artifacts_error", f"{folder}: {type(e).__name__}: {e}")]
    saved = []
    shot = folder / "screenshot.png"
    tree = folder / "tree.json"
    try:
        page.screenshot(str(shot))
        saved.append(("headroid_screenshot", str(shot)))
    except Exception as e:  # noqa: BLE001
        saved.append(("headroid_screenshot_error", f"{type(e).__name__}: {e}"))
    try:
        tree.write_text(json.dumps(page.tree(), indent=2), encoding="utf-8")
        saved.append(("headroid_tree", str(tree)))
    except Exception as e:  # noqa: BLE001
        saved.append(("headroid_tree_error", f"{type(e).__name__}: {e}"))
    return saved


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return
    page = item.stash.get(_PAGE, None)
    if page is None or getattr(page, "closed", False):
        return
    try:
        folder = Path(item.config.rootpath) / ARTIFACTS_DIR / _artifact_name(item.nodeid)
        saved = _save_artifacts(page, folder)
    except Exception as e:  # noqa: BLE001
        saved = [("headroid_artifacts_error", f"{type(e).__name__}: {e}")]
    report.user_properties.extend(saved)
    item.user_properties.extend(saved)  # junitxml writes properties from the teardown report
    report.sections.append(("headroid artifacts", "\n".join(f"{k}: {v}" for k, v in saved)))
