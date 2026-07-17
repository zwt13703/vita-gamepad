from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator

import usb.core
import usb.util

from vitapad.protocol import PACKET_SIZE

SONY_VENDOR_ID = 0x054C

try:
    import libusb_package

    USB_BACKEND = libusb_package.get_libusb1_backend()
except (ImportError, OSError):
    USB_BACKEND = None


def _find_vita() -> tuple[object, object, tuple[int | None, int | None]] | None:
    for device in usb.core.find(
        find_all=True, idVendor=SONY_VENDOR_ID, backend=USB_BACKEND
    ):
        try:
            product = usb.util.get_string(device, device.iProduct) or ""
        except (ValueError, usb.core.USBError):
            product = ""
        if "Vita" not in product and "Type D" not in product:
            continue
        try:
            device.set_configuration()
        except usb.core.USBError:
            # It may already have the desired configuration.
            pass
        configuration = device.get_active_configuration()
        for interface in configuration:
            for endpoint in interface:
                if (
                    usb.util.endpoint_direction(endpoint.bEndpointAddress)
                    == usb.util.ENDPOINT_IN
                    and usb.util.endpoint_type(endpoint.bmAttributes)
                    == usb.util.ENDPOINT_TYPE_BULK
                ):
                    return device, endpoint, (device.bus, device.address)
    return None


def iter_usb_packets(
    stop: threading.Event, log: Callable[[str], None]
) -> Iterator[bytes]:
    connected_device: tuple[int | None, int | None] | None = None
    pending = bytearray()
    while not stop.is_set():
        found = _find_vita()
        if found is None:
            if connected_device is not None:
                log("PSVita USB 已断开；等待重新连接...")
                connected_device = None
            stop.wait(1.0)
            continue
        _device, endpoint, device_key = found
        if connected_device != device_key:
            connected_device = device_key
            pending.clear()
            log("已检测到 PSVita USB 数据通道")
        try:
            chunk = bytes(endpoint.read(max(PACKET_SIZE, endpoint.wMaxPacketSize), 250))
        except usb.core.USBTimeoutError:
            continue
        except usb.core.USBError:
            connected_device = None
            time.sleep(0.2)
            continue
        pending.extend(chunk)
        while len(pending) >= PACKET_SIZE:
            yield bytes(pending[:PACKET_SIZE])
            del pending[:PACKET_SIZE]
