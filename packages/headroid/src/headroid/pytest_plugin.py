# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""pytest plugin: `device` and `page` fixtures, the `headroid` marker and failure artifacts.

Loaded automatically once headroid is installed (entry point pytest11 "headroid").
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from .adb import AdbError, list_devices
from .device import Device

ARTIFACTS_DIR = "headroid-artifacts"
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
        help="package the `page` fixture launches when the test has no @pytest.mark.headroid(app=...)",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "headroid(app): package name the `page` fixture launches on a hidden display"
    )


def _no_device_reason(serial: str | None) -> str | None:
    """Why no device can be used, or None when one can."""
    try:
        devices = list_devices(os.environ.get("ADB", "adb"))
    except AdbError as e:
        return f"headroid: {e}"
    ready = [d["serial"] for d in devices if d["state"] == "device"]
    if serial is not None:
        if serial not in ready:
            return f"headroid: device {serial} is not attached and authorised (adb devices: {ready or 'none'})"
        return None
    if not ready:
        return "headroid: no Android device attached (adb devices lists none in the 'device' state)"
    if len(ready) > 1:
        return f"headroid: several devices attached ({', '.join(ready)}); pass --headroid-serial"
    return None


def _open_device(serial: str | None) -> Device:
    """Connects to the phone, or skips the test with the reason when there is none."""
    reason = _no_device_reason(serial)
    if reason:
        pytest.skip(reason)
    return Device.connect(serial=serial)


@pytest.fixture(scope="session")
def device(request):
    """A headroid Device for the whole session (closed at the end)."""
    dev = _open_device(request.config.getoption("--headroid-serial"))
    yield dev
    dev.close()


@pytest.fixture
def page(request, device):
    """A hidden display with the app from @pytest.mark.headroid(app=...) or --headroid-app; closed after the
    test. On failure its screenshot and UI tree are saved under headroid-artifacts/<test id>/."""
    marker = request.node.get_closest_marker("headroid")
    app = (marker.kwargs.get("app") if marker else None) or request.config.getoption(
        "--headroid-app"
    )
    if not app:
        pytest.fail(
            'headroid: no app for the `page` fixture: add @pytest.mark.headroid(app="com.your.app") '
            "or pass --headroid-app",
            pytrace=False,
        )
    p = device.new_page(app)
    request.node.stash[_PAGE] = p
    yield p
    p.close()


def _artifact_dir(config, nodeid: str) -> Path:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", nodeid).strip("_")[:150] or "test"
    return Path(config.rootpath) / ARTIFACTS_DIR / name


def _save_artifacts(page, folder: Path) -> list[tuple[str, str]]:
    folder.mkdir(parents=True, exist_ok=True)
    saved = []
    shot = folder / "screenshot.png"
    tree = folder / "tree.json"
    try:
        page.screenshot(str(shot))
        saved.append(("headroid_screenshot", str(shot)))
    except Exception as e:  # noqa: BLE001 - never hide the test's own failure
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
    saved = _save_artifacts(page, _artifact_dir(item.config, item.nodeid))
    report.user_properties.extend(saved)
    report.sections.append(("headroid artifacts", "\n".join(f"{k}: {v}" for k, v in saved)))
