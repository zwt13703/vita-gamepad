from __future__ import annotations

import sys
from typing import Protocol

from vitapad.protocol import InputState


class GamepadBackend(Protocol):
    name: str

    def update(self, state: InputState) -> None: ...

    def close(self) -> None: ...


def create_backend(name: str) -> GamepadBackend:
    selected = name
    if selected == "auto":
        selected = "windows" if sys.platform == "win32" else "macos" if sys.platform == "darwin" else "debug"
    if selected == "windows":
        from .windows import WindowsGamepad

        return WindowsGamepad()
    if selected == "macos":
        from .macos import MacOSGamepad

        return MacOSGamepad()
    if selected == "debug":
        from .debug import DebugGamepad

        return DebugGamepad()
    raise ValueError(f"unknown backend: {name}")

