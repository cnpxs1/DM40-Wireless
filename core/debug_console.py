"""Console for ``-debug`` runs of the packaged app."""

from __future__ import annotations

import sys
from typing import Any

ATTACH_PARENT_PROCESS = 0xFFFFFFFF


def open_debug_console() -> None:
    """Attach to the parent console, or create one when launched from Explorer."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32: Any = ctypes.windll.kernel32
        kernel32.AttachConsole.argtypes = [ctypes.c_uint]
        kernel32.AttachConsole.restype = ctypes.c_int
        kernel32.AllocConsole.argtypes = []
        kernel32.AllocConsole.restype = ctypes.c_int
        kernel32.SetConsoleOutputCP.argtypes = [ctypes.c_uint]
        kernel32.SetConsoleOutputCP.restype = ctypes.c_int

        if not kernel32.AttachConsole(ATTACH_PARENT_PROCESS):
            if not kernel32.AllocConsole():
                return
        kernel32.SetConsoleOutputCP(65001)
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
    except (ImportError, OSError, ValueError):
        pass
