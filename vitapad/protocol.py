from __future__ import annotations

from dataclasses import dataclass
import struct

MAGIC = b"VGPD"
VERSION = 1
PACKET_SIZE = 20
DISCOVERY_MAGIC = b"VGPD_HOST_V1"
VITA_DISCOVERY_MAGIC = b"VGPD_VITA_V1"
PACKET_STRUCT = struct.Struct("!4sBBHIH6B")


class Buttons:
    A = 1 << 0
    B = 1 << 1
    X = 1 << 2
    Y = 1 << 3
    LB = 1 << 4
    RB = 1 << 5
    BACK = 1 << 6
    START = 1 << 7
    L3 = 1 << 8
    R3 = 1 << 9
    UP = 1 << 10
    DOWN = 1 << 11
    LEFT = 1 << 12
    RIGHT = 1 << 13


@dataclass(frozen=True, slots=True)
class InputState:
    sequence: int = 0
    buttons: int = 0
    lx: int = 128
    ly: int = 128
    rx: int = 128
    ry: int = 128
    lt: int = 0
    rt: int = 0
    flags: int = 0

    @classmethod
    def neutral(cls) -> "InputState":
        return cls()


def decode_packet(data: bytes) -> InputState:
    if len(data) != PACKET_SIZE:
        raise ValueError(f"invalid packet size: {len(data)}")
    magic, version, flags, size, sequence, buttons, *axes = PACKET_STRUCT.unpack(data)
    if magic != MAGIC:
        raise ValueError("invalid packet magic")
    if version != VERSION:
        raise ValueError(f"unsupported protocol version: {version}")
    if size != PACKET_SIZE:
        raise ValueError(f"invalid declared packet size: {size}")
    return InputState(sequence, buttons, *axes, flags)


def encode_packet(state: InputState) -> bytes:
    values = (state.lx, state.ly, state.rx, state.ry, state.lt, state.rt)
    if any(not 0 <= value <= 255 for value in values):
        raise ValueError("axis and trigger values must be between 0 and 255")
    return PACKET_STRUCT.pack(
        MAGIC,
        VERSION,
        state.flags,
        PACKET_SIZE,
        state.sequence & 0xFFFFFFFF,
        state.buttons & 0xFFFF,
        *values,
    )


def sequence_is_newer(candidate: int, previous: int) -> bool:
    """Compare wrapping unsigned 32-bit sequence numbers."""
    difference = (candidate - previous) & 0xFFFFFFFF
    return 0 < difference < 0x80000000

