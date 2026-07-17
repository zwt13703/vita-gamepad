from __future__ import annotations

import socket
import threading
import time

from vitapad.backends import GamepadBackend
from vitapad.protocol import (
    DISCOVERY_MAGIC,
    InputState,
    decode_packet,
    sequence_is_newer,
)


class Receiver:
    def __init__(
        self,
        backend: GamepadBackend,
        bind: str = "0.0.0.0",
        port: int = 5000,
        discovery_port: int = 5001,
        allow: str | None = None,
        timeout_ms: int = 300,
    ) -> None:
        self.backend = backend
        self.bind = bind
        self.port = port
        self.discovery_port = discovery_port
        self.allow = allow
        self.timeout = timeout_ms / 1000.0
        self._stop = threading.Event()
        self._last_packet = 0.0
        self._connected_address: str | None = None
        self._last_sequence: int | None = None
        self._neutral_sent = True

    def _broadcast_discovery(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as beacon:
            beacon.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            while not self._stop.wait(1.0):
                try:
                    beacon.sendto(
                        DISCOVERY_MAGIC, ("255.255.255.255", self.discovery_port)
                    )
                except OSError:
                    # Interfaces can disappear during sleep/network changes.
                    pass

    def run(self) -> None:
        discovery = threading.Thread(
            target=self._broadcast_discovery, name="discovery", daemon=True
        )
        discovery.start()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as listener:
            listener.bind((self.bind, self.port))
            listener.settimeout(0.05)
            print(
                f"正在监听 {self.bind}:{self.port}，后端: {self.backend.name}\n"
                "等待 PSVita（Ctrl+C 退出）..."
            )
            try:
                while not self._stop.is_set():
                    self._receive_once(listener)
                    self._apply_failsafe()
            finally:
                self._stop.set()
                discovery.join(timeout=1.2)
                self.backend.close()

    def _receive_once(self, listener: socket.socket) -> None:
        try:
            data, address = listener.recvfrom(256)
        except socket.timeout:
            return
        if self.allow and address[0] != self.allow:
            return
        try:
            state = decode_packet(data)
        except ValueError:
            return
        if self._connected_address != address[0]:
            self._connected_address = address[0]
            self._last_sequence = None
            print(f"已连接 PSVita: {address[0]}")
        if self._last_sequence is not None and not sequence_is_newer(
            state.sequence, self._last_sequence
        ):
            return
        self._last_sequence = state.sequence
        self._last_packet = time.monotonic()
        self._neutral_sent = False
        self.backend.update(state)

    def _apply_failsafe(self) -> None:
        if (
            not self._neutral_sent
            and time.monotonic() - self._last_packet >= self.timeout
        ):
            self.backend.update(InputState.neutral())
            self._neutral_sent = True
            print("连接超时，已释放全部按键；等待重连...")

    def stop(self) -> None:
        self._stop.set()

