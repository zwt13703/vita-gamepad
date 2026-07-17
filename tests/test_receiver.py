import socket
import threading
import time
import unittest

from vitapad.protocol import Buttons, InputState, encode_packet
from vitapad.receiver import Receiver


class FakeBackend:
    name = "fake"

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


class ReceiverTests(unittest.TestCase):
    def test_receive_and_failsafe(self) -> None:
        backend = FakeBackend()
        input_events: list[InputState] = []
        port = unused_udp_port()
        receiver = Receiver(
            backend,
            bind="127.0.0.1",
            port=port,
            discovery_port=unused_udp_port(),
            timeout_ms=50,
            on_input=input_events.append,
        )
        thread = threading.Thread(target=receiver.run)
        thread.start()
        try:
            state = InputState(sequence=7, buttons=Buttons.A, lx=200)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                # Give the receiver thread time to bind.
                time.sleep(0.02)
                sender.sendto(encode_packet(state), ("127.0.0.1", port))
            deadline = time.monotonic() + 1.0
            while len(backend.states) < 2 and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(backend.states[0], state)
            self.assertEqual(backend.states[1], InputState.neutral())
            self.assertEqual(input_events[0], state)
            self.assertEqual(input_events[1], InputState.neutral())
        finally:
            receiver.stop()
            thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertTrue(backend.closed)

    def test_rejects_old_sequence(self) -> None:
        backend = FakeBackend()
        receiver = Receiver(backend)
        receiver._connected_address = "127.0.0.1"
        receiver._last_sequence = 20
        listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            listener.bind(("127.0.0.1", 0))
            listener.settimeout(1)
            sender.sendto(
                encode_packet(InputState(sequence=19, buttons=Buttons.B)),
                listener.getsockname(),
            )
            receiver._receive_once(listener)
        finally:
            listener.close()
            sender.close()
        self.assertEqual(backend.states, [])


if __name__ == "__main__":
    unittest.main()
