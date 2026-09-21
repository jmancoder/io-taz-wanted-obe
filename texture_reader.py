import logging
from pathlib import Path
from typing import NamedTuple

import numpy as np
import numpy.typing as npt

from .binary_reader import BinaryReader


class Texture(NamedTuple):
    width: int
    height: int
    pixels: npt.NDArray[np.float32]


def read_bmp(input_path: Path) -> Texture:
    with open(input_path, "rb") as f:
        bs = BinaryReader(f.read())

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

    match format_id:
        case 1:
            # ARGB8888
            argb = np.frombuffer(
                bs.getbuffer(),
                dtype="<u4",
                count=width * height,
                offset=bs.tell(),
            ).reshape(height, width)

            pixels = (
                np.stack(
                    (
                        (argb >> 16) & 0xFF,
                        (argb >> 8) & 0xFF,
                        argb & 0xFF,
                        argb >> 24,
                    ),
                    axis=-1,
                ).astype(np.float32)
                / 255.0
            )
            pixels = pixels[::-1].ravel()
        case 3:
            # ARGB1555
            argb = np.frombuffer(
                bs.getbuffer(),
                dtype="<u2",
                count=width * height,
                offset=bs.tell(),
            ).reshape(height, width)

            pixels = np.stack(
                (
                    (argb >> 10) & 0x1F,
                    (argb >> 5) & 0x1F,
                    argb & 0x1F,
                    argb >> 15,
                ),
                axis=-1,
            ).astype(np.float32)
            pixels[..., :3] /= 31.0
            pixels = pixels[::-1].ravel()
        case 5:
            # PAL8
            palette = np.frombuffer(
                bs.getbuffer(), dtype=np.uint8, count=256 * 4, offset=bs.tell()
            ).reshape(256, 4)
            bs.seek(palette.nbytes, 1)

            indices = np.frombuffer(
                bs.getbuffer(),
                dtype=np.uint8,
                count=width * height,
                offset=bs.tell(),
            ).reshape(height, width)
            bs.seek(indices.nbytes, 1)

            pixels = palette[indices].astype(np.float32) / 255.0
            pixels = pixels[::-1].ravel()
        case 7:
            # PAL4
            palette = np.frombuffer(
                bs.getbuffer(), dtype=np.uint8, count=16 * 4, offset=bs.tell()
            ).reshape(16, 4)
            bs.seek(palette.nbytes, 1)

            raw_indices = np.frombuffer(
                bs.getbuffer(),
                dtype=np.uint8,
                count=(width * height + 1) // 2,
                offset=bs.tell(),
            )
            bs.seek(raw_indices.nbytes, 1)

            indices = np.empty(width * height, dtype=np.uint8)
            indices[0::2] = raw_indices & 0x0F
            indices[1::2] = raw_indices >> 4

            pixels = palette[indices].reshape(height, width, 4)
            pixels = pixels[::-1].astype(np.float32) / 255.0
            pixels = pixels.ravel()
        case 9:
            # ARGB4444
            argb = np.frombuffer(
                bs.getbuffer(),
                dtype="<u2",
                count=width * height,
                offset=bs.tell(),
            ).reshape(height, width)

            pixels = (
                np.stack(
                    (
                        (argb >> 8) & 0x0F,
                        (argb >> 4) & 0x0F,
                        argb & 0x0F,
                        argb >> 12,
                    ),
                    axis=-1,
                ).astype(np.float32)
                / 15.0
            )
            pixels = pixels[::-1].ravel()
        case _:
            logging.error(
                "%s uses unimplemented texture format %d",
                input_path.stem,
                format_id,
            )
            pixels = np.tile(
                np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32),
                width * height,
            )
    return Texture(width, height, pixels)
