# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""headroid: host-side SDK for the headroid device server."""

from .adb import Adb, AdbError
from .device import Device, Display
from .errors import TimeoutError
from .expect import expect
from .locator import Locator
from .page import Page
from .rpc import RpcClient, RpcError
from .server import ServerProcess

__version__ = "0.1.0a4"
__all__ = [
    "Adb",
    "AdbError",
    "Device",
    "Display",
    "Locator",
    "Page",
    "RpcClient",
    "RpcError",
    "ServerProcess",
    "TimeoutError",
    "__version__",
    "expect",
]
