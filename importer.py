import bpy
from bpy.types import Context, Object

import numpy as np
import numpy.typing as npt

from . import reader


def fan_positions_to_triangles(
    positions: npt.NDArray, start_idx: int
) -> list[tuple[int, int, int]]:
    triangles: list[tuple[int, int, int]] = []
    a = positions[0]
    for i in range(1, len(positions) - 1):
        b = positions[i]
        c = positions[i + 1]
        triangles.append((0, start_idx + i, start_idx + i + 1))
    return triangles


def strip_positions_to_triangles(
    positions: npt.NDArray, start_idx: int
) -> list[tuple[int, int, int]]:
    triangles: list[tuple[int, int, int]] = []
    for i in range(len(positions) - 2):
        if i % 2:
            triangles.append(
                (
                    start_idx + i + 1,
                    start_idx + i,
                    start_idx + i + 2,
                )
            )
        else:
            triangles.append(
                (
                    start_idx + i,
                    start_idx + i + 1,
                    start_idx + i + 2,
                )
            )
    return triangles


def import_scene(context: Context, actor: reader.Actor) -> None:
    if len(actor.vertices) == 0 or "position" not in actor.vertices.dtype.names:
        return

    # Convert primitives to triangles
    triangles: list[tuple[int, int, int]] = []
    start_vert = 0
    for prim_group in actor.prim_groups:
        for prim in prim_group:
            prim_positions = actor.vertices["position"][
                start_vert : start_vert + prim.vertex_count
            ]
            if prim.prim_type == 4:
                # Triangle list
                triangles.extend(
                    [
                        (start_vert + i, start_vert + i + 1, start_vert + i + 2)
                        for i in range(0, prim.vertex_count, 3)
                    ]
                )
            elif prim.prim_type == 5:
                # Triangle strip
                triangles.extend(
                    strip_positions_to_triangles(
                        prim_positions,
                        start_vert,
                    )
                )
            elif prim.prim_type == 6:
                # Triangle fan
                triangles.extend(
                    fan_positions_to_triangles(
                        prim_positions,
                        start_vert,
                    )
                )
            else:
                raise NotImplementedError(
                    f"Unimplemented primitive type {prim.prim_type}"
                )
            start_vert += prim.vertex_count

    # Import geometry
    print(actor.vertices.dtype)
    mesh = bpy.data.meshes.new("Mesh")
    mesh.from_pydata(
        actor.vertices["position"],
        [],
        triangles,
    )
    mesh.validate()
    mesh.update()

    # Create mesh object
    mesh_obj = bpy.data.objects.new("Mesh", mesh)
    context.collection.objects.link(mesh_obj)

    # Import vertex UV layers
    for i in range(2):
        uv_field = f"uv_{i}"
        if uv_field not in actor.vertices.dtype.names:
            continue
        uv_data = actor.vertices[uv_field]
        uv_layer = mesh.uv_layers.new(name=f"UV{i}")
        for loop in mesh.loops:
            uv = uv_data[loop.vertex_index]
            uv_layer.data[loop.index].uv = (uv[0], 1.0 - uv[1])

    # Import vertex normals
    if "normal" in actor.vertices.dtype.names:
        mesh.normals_split_custom_set_from_vertices(actor.vertices["normal"])

    # Import vertex colors
    if "color" in actor.vertices.dtype.names:
        vertex_color_attr = mesh.color_attributes.new(
            name="vertex_color",
            type="BYTE_COLOR",
            domain="POINT",
        )
        vertex_color_attr.data.foreach_set(
            "color",
            actor.vertices["color"].flatten(),
        )
