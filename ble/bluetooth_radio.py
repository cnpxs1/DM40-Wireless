"""Check whether Bluetooth is enabled on Windows (adapter PnP status OK)."""

from __future__ import annotations

import contextlib
import subprocess
import sys

# Matched by name so this module keeps working where bleak is absent.
_BT_OFF_EXC_NAME = "BleakBluetoothNotAvailableError"

_BT_OFF_ERROR_MARKERS = (
    "bluetooth radio is not powered",
    "bluetooth is powered off",
    "radio is not powered",
    "radio not available",
    "no bluetooth adapter",
    "bluetooth unavailable",
    "bluetooth is turned off",
    "device is not available",
    "bleakbluetoothnotavailable",
)

_PS_CHECK = r"""
$adapter = Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue |
    Where-Object { $_.FriendlyName -match 'Bluetooth' } |
    Select-Object -First 1
if (-not $adapter) { exit 2 }
if ($adapter.Status -eq 'OK') { exit 0 }
exit 1
"""


def exception_indicates_bt_off(exc: BaseException) -> bool:
    if _BT_OFF_EXC_NAME in (cls.__name__ for cls in type(exc).__mro__):
        return True
    msg = str(exc).lower()
    return any(marker in msg for marker in _BT_OFF_ERROR_MARKERS)


def is_bluetooth_enabled() -> bool | None:
    """True = on, False = off, None = unknown (other OS / error)."""
    if sys.platform != "win32":
        return None
    with contextlib.suppress(Exception):    # any failure is "unknown", not fatal
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", _PS_CHECK],
            capture_output=True,
            timeout=8,
            creationflags=flags,
        )
        if proc.returncode == 0:
            return True
        if proc.returncode == 1:
            return False
    return None
