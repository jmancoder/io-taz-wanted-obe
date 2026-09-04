from __future__ import annotations
from dataclasses import dataclass
from io import BufferedReader
from typing import NamedTuple

from mathutils import Matrix
import numpy as np
import numpy.typing as npt

from .binary_reader import BinaryReader

FVF_LIST = [
    0x0000115C,
    0x0000125C,
    0x0000135C,
    0x0000145C,
    0x00000000,
    0x00000000,
    0x00000000,
    0x00000000,
    0x0000115C,
    0x0000125C,
    0x0000135C,
    0x0000145C,
]


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
    draw_count: int


@dataclass
class PrimBatch:
    prim_count: int
    tex_0_crc: int
    tex_1_crc: int
    flags: int
    primitives: list[SkinPrim | MeshPrim]


@dataclass
class Node:
    child_nodes: list[Node]


@dataclass
class BoneNode(Node):
    transform: Matrix
    matrix_palette_index: int


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


class Actor(NamedTuple):
    vertices: npt.NDArray
    prim_batches: list[PrimBatch]
    root_nodes: list[Node]


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
    bs.read_uint8()
    draw_count = bs.read_uint16()
    matrix_indexes = [bs.read_uint8() for _ in range(12)]
    return SkinPrim(prim_type, flags, vertex_count, matrix_count, draw_count)


def read_node(bs: BinaryReader, nodes: list[Node]) -> None:
    start_node_off = bs.tell()
    cur_node_off = start_node_off
    while True:
        bs.seek(cur_node_off + 0xE0)
        next_node_off = bs.read_uint32()
        prev_node_off = bs.read_uint32()
        parent_node_off = bs.read_uint32()
        child_node_off = bs.read_uint32()
        node_type = bs.read_uint8()
        flags = bs.read_uint8()

        bs.seek(cur_node_off + 0x70)
        if node_type == 1:
            # Read bone node
            transform = bs.read_matrix_4x4()
            matrix_pal_idx = bs.read_int32()
            bs.seek(44, 1)
            node = BoneNode([], transform, matrix_pal_idx)
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
                    ("uv", np.float32, 2),
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
                [],
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
            node = Node([])
            print(f"WARNING: Unimplemented node type {node_type}")

        # Read child nodes
        nodes.append(node)
        if child_node_off != 0:
            bs.seek(child_node_off)
            read_node(bs, node.child_nodes)

        # Skip to next sibling node
        cur_node_off = next_node_off
        if cur_node_off == start_node_off:
            break


def fvf_to_dtype(fvf: int) -> npt.DTypeLike:
    XYZ = 0x02
    XYZRHW = 0x04
    NORMAL = 0x10
    PSIZE = 0x20
    DIFFUSE = 0x40
    SPECULAR = 0x80
    TEX_MASK = 0xF00

    fields = []

    pos = fvf & 0x400E
    if pos == XYZ:
        fields.append(("position", "<f4", 3))
    elif pos == XYZRHW:
        fields.append(("position", "<f4", 4))
    elif 0x06 <= pos <= 0x0E:
        n = (pos - 0x06) // 2 + 1
        fields += [("position", "<f4", 3), ("weights", "<f4", n)]

    if fvf & NORMAL:
        fields.append(("normal", "<f4", 3))
    if fvf & PSIZE:
        fields.append(("point_size", "<f4"))
    if fvf & DIFFUSE:
        fields.append(("diffuse", "<u1", 4))
    if fvf & SPECULAR:
        fields.append(("specular", "<u1", 4))

    for i in range((fvf & TEX_MASK) >> 8):
        fields.append((f"uv_{i}", "<f4", 2))

    return np.dtype(fields)


def read_actor(f: BufferedReader) -> Actor:
    bs = BinaryReader(f.read())

    # Read header
    sig = bs.read_uint32()
    version = bs.read_uint32()
    if version != 0x10000:
        print(f"Warning: version {hex(version)} is untested")
    bs.seek(0x20)
    vertex_count = bs.read_uint16()
    prim_batch_count = bs.read_uint16()
    vertex_off = bs.read_uint32()
    prim_batch_off = bs.read_uint32()
    prim_off = bs.read_uint32()
    bs.seek(0x60)
    root_node_off = bs.read_uint32()
    bs.seek(0x99)
    fvf_idx = bs.read_uint8()

    # Read skin vertices
    bs.seek(vertex_off)
    vertex_dtype = fvf_to_dtype(FVF_LIST[fvf_idx])
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
    return Actor(vertices, prim_batches, root_nodes)
