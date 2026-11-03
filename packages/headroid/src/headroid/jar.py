# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""Finds the device-server jar: argument, env, wheel bundle, then a source checkout build."""

from __future__ import annotations

import os
from importlib import resources
from pathlib import Path

ENV_VAR = "HEADROID_SERVER_JAR"
JAR_NAME = "headroid-server.jar"
BUILD_HINT = (
    "build it with `cd device-server && ./gradlew :server:headroidJar` "
    f"or point {ENV_VAR} at an existing {JAR_NAME}"
)


def _bundled() -> Path | None:
    try:
        res = resources.files("headroid").joinpath("_server", JAR_NAME)
        with resources.as_file(res) as p:
            return Path(p) if Path(p).is_file() else None
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        return None


def _source_checkout() -> Path:
    repo = Path(__file__).resolve().parents[4]
    return repo / "device-server" / "server" / "build" / "headroid" / JAR_NAME


def resolve_jar(jar: str | None = None) -> str:
    """Returns the jar path. Order: jar argument, HEADROID_SERVER_JAR, wheel bundle, source build."""
    if jar:
        return str(jar)
    env = os.environ.get(ENV_VAR)
    if env:
        return env
    bundled = _bundled()
    if bundled is not None:
        return str(bundled)
    built = _source_checkout()
    if built.is_file():
        return str(built)
    raise FileNotFoundError(f"headroid server jar not found: {BUILD_HINT}")
