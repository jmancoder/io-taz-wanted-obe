from io import BytesIO
import struct
from typing import Literal

from mathutils import Matrix


class BinaryReader(BytesIO):
    def __init__(self, data: bytes, big_endian=False) -> None:
        super().__init__(data)

        self.endian_symbol: Literal["<", ">"]
        self.byte_order: Literal["little", "big"]
        if big_endian:
            self.endian_symbol = ">"
            self.byte_order = "big"
        else:
            self.endian_symbol = "<"
            self.byte_order = "little"

    def read_uint8(self) -> int:
        return int.from_bytes(self.read(1), signed=False, byteorder=self.byte_order)

    def read_int8(self) -> int:
        return int.from_bytes(self.read(1), signed=True, byteorder=self.byte_order)

    def read_uint16(self) -> int:
        return int.from_bytes(self.read(2), signed=False, byteorder=self.byte_order)

    def read_int16(self) -> int:
        return int.from_bytes(self.read(2), signed=True, byteorder=self.byte_order)

    def read_uint32(self) -> int:
        return int.from_bytes(self.read(4), signed=False, byteorder=self.byte_order)

    def read_int32(self) -> int:
        return int.from_bytes(self.read(4), signed=True, byteorder=self.byte_order)

    def read_vec3H_quant(self) -> tuple[float, float, float]:
        x, y, z = struct.unpack(self.endian_symbol + "3H", self.read(6))
        return (x / 0xFFFF, y / 0xFFFF, z / 0xFFFF)

    def read_vec4H_quant(self) -> tuple[float, float, float, float]:
        x, y, z, w = struct.unpack(self.endian_symbol + "4H", self.read(8))
        return (x / 0xFFFF, y / 0xFFFF, z / 0xFFFF, w / 0xFFFF)

    def read_float(self) -> float:
        return struct.unpack(self.endian_symbol + "f", self.read(4))[0]

    def read_vec2f(self) -> tuple[float, float]:
        return struct.unpack(self.endian_symbol + "2f", self.read(8))

    def read_vec3f(self) -> tuple[float, float, float]:
        return struct.unpack(self.endian_symbol + "3f", self.read(12))

    def read_vec4f(self) -> tuple[float, float, float, float]:
        return struct.unpack(self.endian_symbol + "4f", self.read(16))

    def read_matrix_4x4(self) -> Matrix:
        return Matrix([self.read_vec4f() for _ in range(4)])
