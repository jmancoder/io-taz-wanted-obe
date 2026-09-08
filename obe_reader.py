from __future__ import annotations
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import NamedTuple

from mathutils import Matrix
import numpy as np
import numpy.typing as npt

from .binary_reader import BinaryReader


class MeshPrim(NamedTuple):
    prim_type: int
    flags: int
    vertex_count: int
    prim_count: int


class SkinPrim(NamedTuple):
    prim_type: int
    flags: int
    vertex_count: int
    matrix_count: int
    tri_count: int
    matrix_palette: npt.NDArray


class Key3(NamedTuple):
    frame: int
    value: tuple[float, float, float]


class Key4(NamedTuple):
    frame: int
    value: tuple[float, float, float, float]


class Track3(NamedTuple):
    keys: list[Key3]


class Track4(NamedTuple):
    keys: list[Key4]


@dataclass
class PrimBatch:
    prim_count: int
    tex_0_crc: int
    tex_1_crc: int
    flags: int
    primitives: list[SkinPrim | MeshPrim]


@dataclass
class Node:
    crc: int
    parent: Node | None
    child_nodes: list[Node]
    position_track: Track3
    scale_track: Track3
    rotation_track: Track4


@dataclass
class BoneNode(Node):
    inverse_transform: Matrix
    matrix_index: int


@dataclass
class MeshNode(Node):
    vertices: npt.NDArray
    prim_batches: list[PrimBatch]
    solid_batch_count: int
    color_key_batch_count: int
    alpha_batch_count: int
    first_color_key_prim: int
    first_alpha_prim: int
    first_color_key_vert: int
    first_alpha_key_vert: int
    sv_vertex_off: int
    sv_face_off: int
    sv_edge_off: int
    sv_face_count: int
    sv_edge_flags_off: int
    sv_edge_count: int
    sv_vertex_count: int
    mesh_flags: int


class AnimSegment(NamedTuple):
    crc: int
    start_frame: int
    end_frame: int
    ticks_per_frame: int


class Actor(NamedTuple):
    crc: int
    vertices: npt.NDArray
    prim_batches: list[PrimBatch]
    root_nodes: list[Node]
    anim_segments: list[AnimSegment]


def read_mesh_prim(bs: BinaryReader) -> MeshPrim:
    prim_type = bs.read_uint8()
    flags = bs.read_uint8()
    vertex_count = bs.read_uint16()
    draw_count = bs.read_uint16()
    bs.read_uint16()
    return MeshPrim(prim_type, flags, vertex_count, draw_count)


def read_prim_batch(bs: BinaryReader) -> PrimBatch:
    prim_count = bs.read_uint32()
    tex_0_crc = bs.read_uint32()
    tex_1_crc = bs.read_uint32()
    flags = bs.read_uint32()
    return PrimBatch(prim_count, tex_0_crc, tex_1_crc, flags, [])


def read_skin_prim(bs: BinaryReader) -> SkinPrim:
    prim_type = bs.read_uint8()
    flags = bs.read_uint8()
    vertex_count = bs.read_uint16()
    matrix_count = bs.read_uint8()
    bs.seek(1, 1)
    tri_count = bs.read_uint16()
    matrix_palette = np.frombuffer(bs.getbuffer(), np.uint8, 12, bs.tell())
    bs.seek(matrix_palette.nbytes, 1)
    return SkinPrim(
        prim_type, flags, vertex_count, matrix_count, tri_count, matrix_palette
    )


def read_key_3(bs: BinaryReader) -> Key3:
    frame = bs.read_uint16()
    value = bs.read_vec3H_quant()
    return Key3(frame, value)


def read_key_4(bs: BinaryReader) -> Key4:
    frame = bs.read_uint16()
    value = bs.read_vec4H_quant()
    return Key4(frame, value)


def read_track_3(bs: BinaryReader) -> Track3:
    key_type = bs.read_uint16()
    key_count = bs.read_uint16()
    key_off = bs.read_uint32()
    quant_base = bs.read_vec3f()
    quant_scale = bs.read_vec3f()
    track_end_off = bs.tell()

    # Read keyframes and return to track end
    bs.seek(key_off)
    keys = [read_key_3(bs) for _ in range(key_count)]
    bs.seek(track_end_off)
    return Track3(keys)


def read_track_4(bs: BinaryReader) -> Track4:
    key_type = bs.read_uint32()
    key_count = bs.read_uint32()
    key_off = bs.read_uint32()
    bs.seek(4, 1)
    quant_base = bs.read_vec4f()
    quant_scale = bs.read_vec4f()
    track_end_off = bs.tell()

    # Read keyframes and return to track end
    bs.seek(key_off)
    keys = [read_key_4(bs) for _ in range(key_count)]
    bs.seek(track_end_off)
    return Track4(keys)


def read_node(
    bs: BinaryReader, sibling_nodes: list[Node], parent_node: Node | None = None
) -> None:
    start_node_off = bs.tell()
    cur_node_off = start_node_off
    while True:
        # Read animation tracks
        position_track = read_track_3(bs)
        scale_track = read_track_3(bs)
        rotation_track = read_track_4(bs)

        # Read node header
        bs.seek(cur_node_off + 0xE0)
        next_node_off = bs.read_uint32()
        prev_node_off = bs.read_uint32()
        parent_node_off = bs.read_uint32()
        child_node_off = bs.read_uint32()
        node_type = bs.read_uint8()
        flags = bs.read_uint8()
        bs.seek(2, 1)
        crc = bs.read_uint32()
        anim_event_off = bs.read_uint32()
        anim_event_count = bs.read_uint32()

        # Read node type-specific fields
        bs.seek(cur_node_off + 0x70)
        if node_type == 1:
            # Read bone node
            inverse_transform = bs.read_matrix_4x4()
            matrix_idx = bs.read_int32()
            bs.seek(12, 1)
            node = BoneNode(
                crc,
                parent_node,
                [],
                position_track,
                scale_track,
                rotation_track,
                inverse_transform,
                matrix_idx,
            )
        elif node_type == 2:
            # Read mesh node
            vert_count = bs.read_uint32()
            vert_off = bs.read_uint32()
            prim_batch_count = bs.read_uint32()
            prim_batch_off = bs.read_uint32()
            prim_off = bs.read_uint32()
            solid_batch_count = bs.read_uint32()
            color_key_batch_count = bs.read_uint32()
            alpha_batch_count = bs.read_uint32()
            first_color_key_prim = bs.read_int32()
            first_alpha_prim = bs.read_int32()
            first_color_key_vert = bs.read_int32()
            first_alpha_key_vert = bs.read_int32()
            sv_vert_off = bs.read_uint32()
            sv_face_off = bs.read_uint32()
            sv_edge_off = bs.read_uint32()
            sv_face_count = bs.read_uint32()
            sv_edge_flags_off = bs.read_uint32()
            sv_edge_count = bs.read_uint32()
            sv_vert_count = bs.read_uint32()
            mesh_flags = bs.read_uint32()

            # Read vertices
            bs.seek(vert_off)
            vertex_dtype = np.dtype(
                [
                    ("position", np.float32, 3),
                    ("normal", np.float32, 3),
                    ("diffuse", np.uint8, 4),
                    ("uvs", np.float32, (1, 2)),
                ]
            )
            vertices = np.frombuffer(
                bs.getbuffer(), vertex_dtype, vert_count, bs.tell()
            )

            # Read primitive batches
            bs.seek(prim_batch_off)
            prim_batches = [read_prim_batch(bs) for _ in range(prim_batch_count)]
            bs.seek(prim_off)
            for prim_batch in prim_batches:
                prim_batch.primitives = [
                    read_mesh_prim(bs) for _ in range(prim_batch.prim_count)
                ]

            node = MeshNode(
                crc,
                parent_node,
                [],
                position_track,
                scale_track,
                rotation_track,
                vertices,
                prim_batches,
                solid_batch_count,
                color_key_batch_count,
                alpha_batch_count,
                first_color_key_prim,
                first_alpha_prim,
                first_color_key_vert,
                first_alpha_key_vert,
                sv_vert_off,
                sv_face_off,
                sv_edge_off,
                sv_face_count,
                sv_edge_flags_off,
                sv_edge_count,
                sv_vert_count,
                mesh_flags,
            )
        else:
            node = Node(
                crc, parent_node, [], position_track, scale_track, rotation_track
            )
            logging.error(f"Unimplemented node type {node_type}")

        # Read child nodes
        sibling_nodes.append(node)
        if child_node_off != 0:
            bs.seek(child_node_off)
            read_node(bs, node.child_nodes)

        # Skip to next sibling node
        cur_node_off = next_node_off
        if cur_node_off == start_node_off:
            break
        bs.seek(cur_node_off)


def read_anim_segment(bs: BinaryReader) -> AnimSegment:
    crc = bs.read_uint32()
    start_frame = bs.read_uint32()
    end_frame = bs.read_uint32()
    ticks_per_frame = bs.read_uint32()
    context = bs.read_uint32()
    name_off = bs.read_uint32()
    bs.seek(8, 1)
    return AnimSegment(crc, start_frame, end_frame, ticks_per_frame)


def read_actor(bs: BinaryReader, crc: int) -> Actor:
    # Read skin info
    bs.seek(0x20)
    vertex_count = bs.read_uint16()
    prim_batch_count = bs.read_uint16()
    vertex_off = bs.read_uint32()
    prim_batch_off = bs.read_uint32()
    prim_off = bs.read_uint32()
    bones_per_vertex = bs.read_uint8()
    bs.seek(3, 1)
    skin_flags = bs.read_uint32()

    # Read actor info
    bs.seek(0x60)
    root_node_off = bs.read_uint32()
    flags = bs.read_uint32()
    last_frame = bs.read_uint32()
    max_prim_verts = bs.read_uint32()
    max_total_prim_verts = bs.read_uint32()
    anim_segment_off = bs.read_uint32()
    anim_segment_count = bs.read_uint32()
    max_radius = bs.read_float()
    bounds = [bs.read_float() for _ in range(6)]
    matrix_pal_size = bs.read_uint8()
    vertex_type = bs.read_uint8()
    bs.seek(2, 1)

    # Read skin vertices
    bs.seek(vertex_off)
    vertex_dtype_fields = [
        ("position", np.float32, 3),
        ("weights", np.float32, 3),
        ("indices", np.uint8, 4),
        ("normal", np.float32, 3),
        ("diffuse", np.uint8, 4),
    ]
    match vertex_type:
        case 0 | 8:
            uv_count = 1
        case 1 | 9:
            uv_count = 2
        case 2 | 10:
            uv_count = 3
        case 3 | 11:
            uv_count = 4
        case _:
            uv_count = 0
            vertex_dtype_fields = []
    if uv_count > 0:
        vertex_dtype_fields.append(("uvs", np.float32, (uv_count, 2)))
    vertex_dtype = np.dtype(vertex_dtype_fields)
    vertices = np.frombuffer(bs.getbuffer(), vertex_dtype, vertex_count, bs.tell())
    bs.seek(vertices.nbytes, 1)

    # Read skin primitive batches
    bs.seek(prim_batch_off)
    prim_batches = [read_prim_batch(bs) for _ in range(prim_batch_count)]
    bs.seek(prim_off)
    for prim_batch in prim_batches:
        prim_batch.primitives = [
            read_skin_prim(bs) for _ in range(prim_batch.prim_count)
        ]

    # Read nodes
    bs.seek(root_node_off)
    root_nodes: list[Node] = []
    read_node(bs, root_nodes)

    # Read anim segments
    bs.seek(anim_segment_off)
    anim_segments = [read_anim_segment(bs) for _ in range(anim_segment_count)]
    return Actor(crc, vertices, prim_batches, root_nodes, anim_segments)


def read_obe(input_path: Path) -> Actor | None:
    with open(input_path, "rb") as f:
        bs = BinaryReader(f.read())

    bs.seek(0x6)
    res_type = bs.read_uint8()
    bs.seek(0xC)
    crc = bs.read_uint32()
    if res_type == 1:
        return read_actor(bs, crc)
    else:
        raise NotImplementedError(f"Unimplemented resource type {res_type}")
