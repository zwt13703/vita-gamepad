import unittest

from vitapad.protocol import (
    Buttons,
    InputState,
    PACKET_SIZE,
    decode_packet,
    encode_packet,
    sequence_is_newer,
)


class ProtocolTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        state = InputState(
            sequence=123456,
            buttons=Buttons.A | Buttons.UP,
            lx=1,
            ly=2,
            rx=253,
            ry=254,
            lt=17,
            rt=240,
        )
        encoded = encode_packet(state)
        self.assertEqual(len(encoded), PACKET_SIZE)
        self.assertEqual(decode_packet(encoded), state)

    def test_rejects_bad_packets(self) -> None:
        with self.assertRaises(ValueError):
            decode_packet(b"")
        packet = bytearray(encode_packet(InputState()))
        packet[0] = 0
        with self.assertRaises(ValueError):
            decode_packet(packet)

    def test_sequence_comparison_wraps(self) -> None:
        self.assertTrue(sequence_is_newer(11, 10))
        self.assertFalse(sequence_is_newer(10, 10))
        self.assertFalse(sequence_is_newer(9, 10))
        self.assertTrue(sequence_is_newer(0, 0xFFFFFFFF))

    def test_axis_validation(self) -> None:
        with self.assertRaises(ValueError):
            encode_packet(InputState(lx=256))


if __name__ == "__main__":
    unittest.main()

