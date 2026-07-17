import socket
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from vitapad.gui import DashboardController
from vitapad.protocol import Buttons, InputState


class FakeBackend:
    name = "fake gamepad"

    def __init__(self) -> None:
        self.states: list[InputState] = []
        self.closed = False

    def update(self, state: InputState) -> None:
        self.states.append(state)

    def close(self) -> None:
        self.closed = True


def unused_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class DashboardControllerTests(unittest.TestCase):
    def test_start_pause_and_logs(self) -> None:
        backend = FakeBackend()
        controller = DashboardController(
            backend_name="debug",
            bind="127.0.0.1",
            port=unused_udp_port(),
            discovery_port=unused_udp_port(),
            allow=None,
            timeout_ms=100,
        )
        with patch("vitapad.gui.create_backend", return_value=backend):
            started, _ = controller.start()
            self.assertTrue(started)
            deadline = time.monotonic() + 1
            while (
                controller.status()["status"] != "running"
                and time.monotonic() < deadline
            ):
                time.sleep(0.01)
            self.assertEqual(controller.status()["status"], "running")
            paused, _ = controller.pause()
            self.assertTrue(paused)
            deadline = time.monotonic() + 2
            while (
                controller.status()["status"] != "paused"
                and time.monotonic() < deadline
            ):
                time.sleep(0.01)
        self.assertEqual(controller.status()["status"], "paused")
        self.assertTrue(backend.closed)
        messages = [entry["message"] for entry in controller.logs_after(0)]
        self.assertTrue(any("服务已开启" in message for message in messages))
        self.assertTrue(any("正在暂停" in message for message in messages))

    def test_live_input_subscription(self) -> None:
        controller = DashboardController(
            backend_name="debug",
            bind="127.0.0.1",
            port=unused_udp_port(),
            discovery_port=unused_udp_port(),
            allow=None,
            timeout_ms=100,
        )
        subscriber = controller.subscribe()
        self.assertEqual(subscriber.get_nowait(), InputState.neutral())
        state = InputState(
            sequence=42,
            buttons=Buttons.LEFT | Buttons.A,
            lx=0,
            ry=255,
            lt=128,
        )
        controller.handle_input(state)
        self.assertEqual(subscriber.get_nowait(), state)
        self.assertEqual(controller.status()["input"]["buttons"], state.buttons)
        controller.unsubscribe(subscriber)

    def test_mapping_settings_are_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            controller = DashboardController(
                backend_name="debug",
                bind="127.0.0.1",
                port=unused_udp_port(),
                discovery_port=unused_udp_port(),
                allow=None,
                timeout_ms=100,
                config_path=str(path),
            )
            settings = controller.settings()
            settings["bindings"]["a"]["target"] = "b"
            settings["bindings"]["a"]["turbo"] = True
            settings["bindings"]["a"]["frequency"] = 12
            controller.update_settings(settings)
            restored = DashboardController(
                backend_name="debug",
                bind="127.0.0.1",
                port=unused_udp_port(),
                discovery_port=unused_udp_port(),
                allow=None,
                timeout_ms=100,
                config_path=str(path),
            )
            binding = restored.settings()["bindings"]["a"]
            self.assertEqual(binding["target"], "b")
            self.assertTrue(binding["turbo"])
            self.assertEqual(binding["frequency"], 12.0)


if __name__ == "__main__":
    unittest.main()
