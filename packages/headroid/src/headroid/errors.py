# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""Exceptions raised by the Page / Locator API."""

from __future__ import annotations

import builtins


class TimeoutError(builtins.TimeoutError):
    """A Page or Locator wait ran out of time. Catching the built-in TimeoutError also catches it."""
