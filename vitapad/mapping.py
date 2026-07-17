from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import time
from typing import Any

from vitapad.protocol import Buttons, InputState


SOURCES = (
    ("a", "×", Buttons.A),
    ("b", "○", Buttons.B),
    ("x", "□", Buttons.X),
    ("y", "△", Buttons.Y),
    ("lb", "L1", Buttons.LB),
    ("rb", "R1", Buttons.RB),
    ("back", "Select", Buttons.BACK),
    ("start", "Start", Buttons.START),
    ("l3", "L3", Buttons.L3),
    ("r3", "R3", Buttons.R3),
    ("up", "方向键上", Buttons.UP),
    ("down", "方向键下", Buttons.DOWN),
    ("left", "方向键左", Buttons.LEFT),
    ("right", "方向键右", Buttons.RIGHT),
    ("lt", "L2（后触摸左）", None),
    ("rt", "R2（后触摸右）", None),
)

TARGETS = (
    ("none", "禁用", None),
    ("a", "Xbox A", Buttons.A),
    ("b", "Xbox B", Buttons.B),
    ("x", "Xbox X", Buttons.X),
    ("y", "Xbox Y", Buttons.Y),
    ("lb", "LB", Buttons.LB),
    ("rb", "RB", Buttons.RB),
    ("back", "Back", Buttons.BACK),
    ("start", "Start", Buttons.START),
    ("l3", "左摇杆按下", Buttons.L3),
    ("r3", "右摇杆按下", Buttons.R3),
    ("up", "方向键上", Buttons.UP),
    ("down", "方向键下", Buttons.DOWN),
    ("left", "方向键左", Buttons.LEFT),
    ("right", "方向键右", Buttons.RIGHT),
    ("lt", "LT", None),
    ("rt", "RT", None),
)

SOURCE_BY_ID = {source_id: mask for source_id, _label, mask in SOURCES}
TARGET_BY_ID = {target_id: mask for target_id, _label, mask in TARGETS}
DEFAULT_BINDINGS = {
    source_id: {"target": source_id, "turbo": False, "frequency": 10}
    for source_id, _label, _mask in SOURCES
}


def default_config_path() -> Path:
    if os.name == "nt" and os.environ.get("APPDATA"):
        root = Path(os.environ["APPDATA"])
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "VitaGamepad" / "settings.json"


class MappingManager:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else default_config_path()
        self._lock = threading.RLock()
        self._bindings = {
            key: dict(value) for key, value in DEFAULT_BINDINGS.items()
        }
        self._held_since: dict[str, float] = {}
        self._load()

    def _load(self) -> None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        try:
            self.update(payload, save=False)
        except ValueError:
            return

    def describe(self) -> dict[str, Any]:
        with self._lock:
            return {
                "version": 1,
                "path": str(self.path),
                "sources": [
                    {"id": source_id, "label": label}
                    for source_id, label, _mask in SOURCES
                ],
                "targets": [
                    {"id": target_id, "label": label}
                    for target_id, label, _mask in TARGETS
                ],
                "bindings": {
                    key: dict(value) for key, value in self._bindings.items()
                },
                "defaults": {
                    key: dict(value) for key, value in DEFAULT_BINDINGS.items()
                },
            }

    def update(self, payload: dict[str, Any], *, save: bool = True) -> None:
        bindings = payload.get("bindings")
        if not isinstance(bindings, dict):
            raise ValueError("bindings 必须是对象")
        validated: dict[str, dict[str, Any]] = {}
        for source_id, _label, _mask in SOURCES:
            entry = bindings.get(source_id, DEFAULT_BINDINGS[source_id])
            if not isinstance(entry, dict):
                raise ValueError(f"{source_id} 配置无效")
            target = entry.get("target", source_id)
            if target not in TARGET_BY_ID:
                raise ValueError(f"{source_id} 的目标按键无效")
            turbo = bool(entry.get("turbo", False))
            try:
                frequency = float(entry.get("frequency", 10))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{source_id} 的连击频率无效") from exc
            if not 1 <= frequency <= 30:
                raise ValueError("连击频率必须在 1 到 30 Hz 之间")
            validated[source_id] = {
                "target": target,
                "turbo": turbo,
                "frequency": round(frequency, 2),
            }
        with self._lock:
            self._bindings = validated
            self._held_since.clear()
            if save:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.path.with_suffix(".tmp")
                temporary.write_text(
                    json.dumps(
                        {"version": 1, "bindings": self._bindings},
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                temporary.replace(self.path)

    def reset(self) -> None:
        with self._lock:
            self._held_since.clear()

    def apply(self, state: InputState, *, now: float | None = None) -> InputState:
        moment = time.monotonic() if now is None else now
        output_buttons = 0
        output_lt = 0
        output_rt = 0
        with self._lock:
            for source_id, _label, source_mask in SOURCES:
                if source_id == "lt":
                    value = state.lt
                elif source_id == "rt":
                    value = state.rt
                else:
                    value = 255 if state.buttons & int(source_mask) else 0
                entry = self._bindings[source_id]
                active = value > 0
                if not active:
                    self._held_since.pop(source_id, None)
                    continue
                if entry["turbo"]:
                    started = self._held_since.setdefault(source_id, moment)
                    half_cycles = int(
                        (moment - started) * float(entry["frequency"]) * 2
                    )
                    if half_cycles % 2:
                        continue
                target = str(entry["target"])
                if target == "none":
                    continue
                if target == "lt":
                    output_lt = max(output_lt, value)
                elif target == "rt":
                    output_rt = max(output_rt, value)
                else:
                    output_buttons |= int(TARGET_BY_ID[target])
        return InputState(
            sequence=state.sequence,
            buttons=output_buttons,
            lx=state.lx,
            ly=state.ly,
            rx=state.rx,
            ry=state.ry,
            lt=output_lt,
            rt=output_rt,
            flags=state.flags,
        )
