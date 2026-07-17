from __future__ import annotations

import ipaddress
import socket
import threading
import time
from collections.abc import Callable
from contextlib import suppress

from vitapad.backends import GamepadBackend
from vitapad.mapping import MappingManager
from vitapad.protocol import (
    DISCOVERY_MAGIC,
    InputState,
    VITA_DISCOVERY_MAGIC,
    decode_packet,
    sequence_is_newer,
)

try:
    import psutil
except ImportError:  # Keep source checkouts usable before dependencies are installed.
    psutil = None


class Receiver:
    def __init__(
        self,
        backend: GamepadBackend,
        bind: str = "0.0.0.0",
        port: int = 5000,
        discovery_port: int = 5001,
        allow: str | None = None,
        timeout_ms: int = 300,
        log: Callable[[str], None] = print,
        on_input: Callable[[InputState], None] | None = None,
        mapping: MappingManager | None = None,
    ) -> None:
        self.backend = backend
        self.bind = bind
        self.port = port
        self.discovery_port = discovery_port
        self.allow = allow
        self.timeout = timeout_ms / 1000.0
        self.log = log
        self.on_input = on_input
        self.mapping = mapping
        self._stop = threading.Event()
        self._last_packet = 0.0
        self._connected_address: str | None = None
        self._last_sequence: int | None = None
        self._neutral_sent = True
        self._input_lock = threading.Lock()

    def _discovery_targets(self) -> tuple[str, ...]:
        targets = {"255.255.255.255"}
        if psutil is not None:
            for addresses in psutil.net_if_addrs().values():
                for address in addresses:
                    if (
                        address.family == socket.AF_INET
                        and address.netmask
                        and not address.address.startswith("127.")
                        and not address.address.startswith("169.254.")
                    ):
                        try:
                            network = ipaddress.IPv4Interface(
                                f"{address.address}/{address.netmask}"
                            ).network
                        except ValueError:
                            continue
                        targets.add(str(network.broadcast_address))
        return tuple(sorted(targets))

    def _run_discovery(self) -> None:
        targets = self._discovery_targets()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as beacon:
            beacon.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            beacon.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                beacon.bind((self.bind, self.discovery_port))
            except OSError as exc:
                self.log(
                    f"无法监听自动发现端口 {self.discovery_port}: {exc}"
                )
                return
            beacon.settimeout(0.2)
            next_broadcast = 0.0
            while not self._stop.is_set():
                now = time.monotonic()
                if now >= next_broadcast:
                    for target in targets:
                        with suppress(OSError):
                            beacon.sendto(
                                DISCOVERY_MAGIC, (target, self.discovery_port)
                            )
                    next_broadcast = now + 1.0
                try:
                    data, address = beacon.recvfrom(64)
                except socket.timeout:
                    continue
                except OSError:
                    if self._stop.is_set():
                        break
                    continue
                if data == VITA_DISCOVERY_MAGIC:
                    # A unicast answer works even when Windows chose the wrong
                    # interface for its limited broadcast.
                    with suppress(OSError):
                        beacon.sendto(DISCOVERY_MAGIC, address)

    def run(self) -> None:
        discovery = threading.Thread(
            target=self._run_discovery, name="discovery", daemon=True
        )
        discovery.start()
        usb = threading.Thread(
            target=self._receive_usb, name="usb-receiver", daemon=True
        )
        usb.start()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as listener:
            listener.bind((self.bind, self.port))
            listener.settimeout(0.05)
            self.log(
                f"正在监听 Wi-Fi {self.bind}:{self.port}，后端: {self.backend.name}\n"
                f"发现目标: {', '.join(self._discovery_targets())}\n"
                "等待 PSVita（Wi-Fi 或 USB）..."
            )
            try:
                while not self._stop.is_set():
                    self._receive_once(listener)
                    self._apply_failsafe()
            finally:
                self._stop.set()
                discovery.join(timeout=1.2)
                usb.join(timeout=1.2)
                if self.on_input is not None:
                    self.on_input(InputState.neutral())
                self.backend.close()

    def _receive_once(self, listener: socket.socket) -> None:
        try:
            data, address = listener.recvfrom(256)
        except socket.timeout:
            return
        if self.allow and address[0] != self.allow:
            return
        self._handle_packet(data, address[0])

    def _handle_packet(self, data: bytes, source: str) -> None:
        try:
            state = decode_packet(data)
        except ValueError:
            return
        with self._input_lock:
            if self._connected_address != source:
                self._connected_address = source
                self._last_sequence = None
                self.log(f"已连接 PSVita: {source}")
            if self._last_sequence is not None and not sequence_is_newer(
                state.sequence, self._last_sequence
            ):
                return
            self._last_sequence = state.sequence
            self._last_packet = time.monotonic()
            self._neutral_sent = False
            output_state = self.mapping.apply(state) if self.mapping else state
            self.backend.update(output_state)
            if self.on_input is not None:
                self.on_input(output_state)

    def _receive_usb(self) -> None:
        try:
            from vitapad.usb_transport import iter_usb_packets
        except ImportError:
            self.log(
                'USB 支持未安装；如需数据线模式，请运行 pip install -e ".[usb]"'
            )
            return
        try:
            self.log("USB 监听已就绪；等待 PS Vita Type D 设备...")
            for packet in iter_usb_packets(self._stop, self.log):
                self._handle_packet(packet, "USB")
        except Exception as exc:
            if not self._stop.is_set():
                self.log(f"USB 接收已停止: {exc}")

    def _apply_failsafe(self) -> None:
        with self._input_lock:
            if (
                not self._neutral_sent
                and time.monotonic() - self._last_packet >= self.timeout
            ):
                self.backend.update(InputState.neutral())
                if self.mapping is not None:
                    self.mapping.reset()
                if self.on_input is not None:
                    self.on_input(InputState.neutral())
                self._neutral_sent = True
                self.log("连接超时，已释放全部按键；等待重连...")

    def stop(self) -> None:
        self._stop.set()

    @property
    def connected_address(self) -> str | None:
        if self._neutral_sent:
            return None
        return self._connected_address
