from __future__ import annotations

from vitapad.protocol import Buttons, InputState

try:
    import vgamepad as vg
except ImportError as exc:
    raise RuntimeError(
        'Windows 后端需要 vgamepad，请运行: pip install -e ".[windows]"'
    ) from exc


BUTTON_MAP = (
    (Buttons.A, vg.XUSB_BUTTON.XUSB_GAMEPAD_A),
    (Buttons.B, vg.XUSB_BUTTON.XUSB_GAMEPAD_B),
    (Buttons.X, vg.XUSB_BUTTON.XUSB_GAMEPAD_X),
    (Buttons.Y, vg.XUSB_BUTTON.XUSB_GAMEPAD_Y),
    (Buttons.LB, vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER),
    (Buttons.RB, vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER),
    (Buttons.BACK, vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK),
    (Buttons.START, vg.XUSB_BUTTON.XUSB_GAMEPAD_START),
    (Buttons.L3, vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB),
    (Buttons.R3, vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB),
    (Buttons.UP, vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP),
    (Buttons.DOWN, vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN),
    (Buttons.LEFT, vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT),
    (Buttons.RIGHT, vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT),
)


def _axis(value: int, *, invert: bool = False) -> int:
    if value >= 128:
        result = round((value - 128) * 32767 / 127)
    else:
        result = round((value - 128) * 32768 / 128)
    return -result if invert else result


class WindowsGamepad:
    name = "Xbox 360 (ViGEm)"

    def __init__(self) -> None:
        try:
            self._pad = vg.VX360Gamepad()
        except Exception as exc:
            raise RuntimeError(
                "无法创建虚拟手柄，请确认已安装 ViGEmBus 驱动"
            ) from exc

    def update(self, state: InputState) -> None:
        self._pad.reset()
        for mask, button in BUTTON_MAP:
            if state.buttons & mask:
                self._pad.press_button(button=button)
        self._pad.left_joystick(
            x_value=_axis(state.lx), y_value=_axis(state.ly, invert=True)
        )
        self._pad.right_joystick(
            x_value=_axis(state.rx), y_value=_axis(state.ry, invert=True)
        )
        self._pad.left_trigger(value=state.lt)
        self._pad.right_trigger(value=state.rt)
        self._pad.update()

    def close(self) -> None:
        self.update(InputState.neutral())
        del self._pad
