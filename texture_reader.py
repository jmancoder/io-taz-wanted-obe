import logging
from pathlib import Path
from typing import NamedTuple

import numpy as np
import numpy.typing as npt

from .binary_reader import BinaryReader


class Texture(NamedTuple):
    width: int
    height: int
    pixels: npt.NDArray


def read_argb8888(bs: BinaryReader, width: int, height: int) -> npt.NDArray:
    argb = np.frombuffer(
        bs.getbuffer(), np.uint8, width * height * 4, bs.tell()
    ).reshape(-1, 4)
    bs.seek(argb.nbytes, 1)
    pixels = argb[:, [1, 2, 3, 0]].astype(np.float32) / 255.0
    return pixels.ravel()


def read_bmp(input_path: Path) -> Texture:
    with open(input_path, "rb") as f:
        bs = BinaryReader(f.read())

    # Read header
    width = bs.read_uint32()
    height = bs.read_uint32()
    format_id = bs.read_uint32()
    flags = bs.read_uint16()
    mip_count = bs.read_uint8()
    frame_count = bs.read_uint8()
    group_id = bs.read_uint16()
    bs.seek(2, 1)
    anim_duration = bs.read_int32()
    alpha_blend_mode = bs.read_uint8()
    bs.seek(3, 1)
    frame_delays = [bs.read_int32() for _ in range(frame_count)]

    # Read pixels
    match format_id:
        case 1:
            # ARGB8888
            pixels = read_argb8888(bs, width, height)
        case 3:
            # ARGB1555
            argb = np.frombuffer(bs.getbuffer(), np.uint16, width * height, bs.tell())
            a = (argb >> 15) & 1
            r = (argb >> 10) & 0x1F
            g = (argb >> 5) & 0x1F
            b = argb & 0x1F
            pixels = np.stack((r, g, b, a), axis=1).astype(np.float32)
            pixels[:, :3] /= 31.0
            pixels[:, 3] /= 1.0
            pixels = pixels.ravel()
        case 5:
            # PAL8
            palette = read_argb8888(bs, width, height)
            indices = np.frombuffer(bs.getbuffer(), np.uint8, width * height, bs.tell())
            bs.seek(indices.nbytes, 1)
            pixels = palette[indices].astype(np.float32) / 255.0
            pixels = pixels.ravel()
        case 7:
            # PAL4
            palette = read_argb8888(bs, width, height)
            data = np.frombuffer(
                bs.getbuffer(), np.uint8, (width * height + 1) // 2, bs.tell()
            )
            bs.seek(data.nbytes, 1)
            indices = np.empty(width * height, np.uint8)
            indices[0::2] = data >> 4
            indices[1::2] = data & 0xF
            pixels = palette[indices].astype(np.float32) / 255.0
            pixels = pixels.ravel()
        case 9:
            # ARGB4444
            argb = np.frombuffer(bs.getbuffer(), np.uint16, width * height, bs.tell())
            bs.seek(argb.nbytes, 1)
            a = (argb >> 12) & 0xF
            r = (argb >> 8) & 0xF
            g = (argb >> 4) & 0xF
            b = argb & 0xF
            pixels = np.stack((r, g, b, a), axis=1).astype(np.float32) / 15.0
            pixels = pixels.ravel()
        case _:
            logging.error(
                f"{input_path.stem} uses unimplemented texture format {format_id}"
            )
            pixels = np.tile([0.0, 0.0, 0.0, 1.0], width * height)
    return Texture(width, height, pixels)
