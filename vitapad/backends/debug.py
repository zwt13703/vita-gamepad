from __future__ import annotations

import time

from vitapad.protocol import InputState


class DebugGamepad:
    name = "debug"

    def __init__(self) -> None:
        self._last_print = 0.0

    def update(self, state: InputState) -> None:
        now = time.monotonic()
        if now - self._last_print >= 0.1:
            print(
                f"\rseq={state.sequence:<10} buttons=0x{state.buttons:04x} "
                f"L=({state.lx:3},{state.ly:3}) R=({state.rx:3},{state.ry:3}) "
                f"LT={state.lt:3} RT={state.rt:3}",
                end="",
                flush=True,
            )
            self._last_print = now

    def close(self) -> None:
        print()

