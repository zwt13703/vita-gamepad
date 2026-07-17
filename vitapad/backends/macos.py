from __future__ import annotations

import ctypes
import ctypes.util
import struct

from vitapad.protocol import Buttons, InputState

# Report 1: 16 buttons, 8-way hat, four 16-bit axes and two 8-bit triggers.
REPORT_DESCRIPTOR = bytes(
    [
        0x05, 0x01, 0x09, 0x05, 0xA1, 0x01, 0x85, 0x01,
        0x05, 0x09, 0x19, 0x01, 0x29, 0x10, 0x15, 0x00,
        0x25, 0x01, 0x75, 0x01, 0x95, 0x10, 0x81, 0x02,
        0x05, 0x01, 0x09, 0x39, 0x15, 0x00, 0x25, 0x07,
        0x35, 0x00, 0x46, 0x3B, 0x01, 0x65, 0x14, 0x75,
        0x04, 0x95, 0x01, 0x81, 0x42, 0x65, 0x00, 0x75,
        0x04, 0x95, 0x01, 0x81, 0x03, 0x09, 0x30, 0x09,
        0x31, 0x09, 0x33, 0x09, 0x34, 0x15, 0x00, 0x26,
        0xFF, 0xFF, 0x75, 0x10, 0x95, 0x04, 0x81, 0x02,
        0x09, 0x32, 0x09, 0x35, 0x15, 0x00, 0x26, 0xFF,
        0x00, 0x75, 0x08, 0x95, 0x02, 0x81, 0x02, 0xC0,
    ]
)

BUTTON_ORDER = (
    Buttons.A, Buttons.B, Buttons.X, Buttons.Y,
    Buttons.LB, Buttons.RB, Buttons.BACK, Buttons.START,
    Buttons.L3, Buttons.R3,
)


def _hat(buttons: int) -> int:
    up, down = bool(buttons & Buttons.UP), bool(buttons & Buttons.DOWN)
    left, right = bool(buttons & Buttons.LEFT), bool(buttons & Buttons.RIGHT)
    if up and right:
        return 1
    if right and down:
        return 3
    if down and left:
        return 5
    if left and up:
        return 7
    if up and not down:
        return 0
    if right and not left:
        return 2
    if down and not up:
        return 4
    if left and not right:
        return 6
    return 8


class MacOSGamepad:
    name = "Generic HID gamepad (IOHIDUserDevice)"

    def __init__(self) -> None:
        cf_path = ctypes.util.find_library("CoreFoundation")
        io_path = ctypes.util.find_library("IOKit")
        if not cf_path or not io_path:
            raise RuntimeError("找不到 macOS CoreFoundation/IOKit")
        self._cf = ctypes.CDLL(cf_path)
        self._io = ctypes.CDLL(io_path)
        self._configure_functions()
        properties = self._create_properties()
        self._device = self._io.IOHIDUserDeviceCreate(None, properties)
        self._cf.CFRelease(properties)
        if not self._device:
            raise RuntimeError(
                "无法创建 macOS 虚拟 HID 手柄；请尝试使用 sudo 运行"
            )

    def _configure_functions(self) -> None:
        self._cf.CFStringCreateWithCString.restype = ctypes.c_void_p
        self._cf.CFStringCreateWithCString.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32
        ]
        self._cf.CFDataCreate.restype = ctypes.c_void_p
        self._cf.CFDataCreate.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint8), ctypes.c_long
        ]
        self._cf.CFNumberCreate.restype = ctypes.c_void_p
        self._cf.CFNumberCreate.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p
        ]
        self._cf.CFDictionaryCreateMutable.restype = ctypes.c_void_p
        self._cf.CFDictionaryCreateMutable.argtypes = [
            ctypes.c_void_p, ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p
        ]
        self._cf.CFDictionarySetValue.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
        ]
        self._cf.CFRelease.argtypes = [ctypes.c_void_p]
        self._io.IOHIDUserDeviceCreate.restype = ctypes.c_void_p
        self._io.IOHIDUserDeviceCreate.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self._io.IOHIDUserDeviceHandleReport.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint8), ctypes.c_long
        ]
        self._io.IOHIDUserDeviceHandleReport.restype = ctypes.c_int
        self._dictionary_key_callbacks = ctypes.c_byte.in_dll(
            self._cf, "kCFTypeDictionaryKeyCallBacks"
        )
        self._dictionary_value_callbacks = ctypes.c_byte.in_dll(
            self._cf, "kCFTypeDictionaryValueCallBacks"
        )

    def _string(self, value: str) -> int:
        # kCFStringEncodingUTF8
        return self._cf.CFStringCreateWithCString(None, value.encode(), 0x08000100)

    def _create_properties(self) -> int:
        dictionary = self._cf.CFDictionaryCreateMutable(
            None,
            0,
            ctypes.byref(self._dictionary_key_callbacks),
            ctypes.byref(self._dictionary_value_callbacks),
        )
        retained: list[int] = []

        def put_number(key: str, value: int) -> None:
            key_ref = self._string(key)
            raw = ctypes.c_int(value)
            value_ref = self._cf.CFNumberCreate(None, 9, ctypes.byref(raw))
            self._cf.CFDictionarySetValue(dictionary, key_ref, value_ref)
            retained.extend((key_ref, value_ref))

        def put_string(key: str, value: str) -> None:
            key_ref, value_ref = self._string(key), self._string(value)
            self._cf.CFDictionarySetValue(dictionary, key_ref, value_ref)
            retained.extend((key_ref, value_ref))

        descriptor_array = (ctypes.c_uint8 * len(REPORT_DESCRIPTOR)).from_buffer_copy(
            REPORT_DESCRIPTOR
        )
        descriptor = self._cf.CFDataCreate(
            None, descriptor_array, len(REPORT_DESCRIPTOR)
        )
        descriptor_key = self._string("ReportDescriptor")
        self._cf.CFDictionarySetValue(dictionary, descriptor_key, descriptor)
        retained.extend((descriptor_key, descriptor))
        put_number("VendorID", 0x054C)
        put_number("ProductID", 0x09CC)
        put_number("VersionNumber", 0x0100)
        put_number("PrimaryUsagePage", 0x01)
        put_number("PrimaryUsage", 0x05)
        put_string("Manufacturer", "Vita Gamepad")
        put_string("Product", "PS Vita Network Gamepad")
        for item in retained:
            self._cf.CFRelease(item)
        return dictionary

    def update(self, state: InputState) -> None:
        hid_buttons = 0
        for index, mask in enumerate(BUTTON_ORDER):
            if state.buttons & mask:
                hid_buttons |= 1 << index
        report = struct.pack(
            "<BHBHHHHBB",
            1,
            hid_buttons,
            _hat(state.buttons),
            state.lx * 257,
            state.ly * 257,
            state.rx * 257,
            state.ry * 257,
            state.lt,
            state.rt,
        )
        buffer = (ctypes.c_uint8 * len(report)).from_buffer_copy(report)
        result = self._io.IOHIDUserDeviceHandleReport(
            self._device, buffer, len(report)
        )
        if result != 0:
            raise RuntimeError(f"IOHIDUserDeviceHandleReport 失败: 0x{result:08x}")

    def close(self) -> None:
        if self._device:
            self.update(InputState.neutral())
            self._cf.CFRelease(self._device)
            self._device = None
