from dataclasses import dataclass
import logging

import bpy
from bpy.types import Context, EditBone, Object
import numpy.typing as npt

from . import obe_reader


@dataclass
class ActorContext:
    armature_obj: Object
    bone_map: dict[int, EditBone]
    object_map: dict[int, Object]


def fan_positions_to_triangles(
    positions: npt.NDArray, start_idx: int
) -> list[tuple[int, int, int]]:
    triangles: list[tuple[int, int, int]] = []
    for i in range(1, len(positions) - 1):
        triangles.append((start_idx, start_idx + i, start_idx + i + 1))
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


def import_mesh(
    context: Context,
    actor_context: ActorContext,
    name: str,
    vertices: npt.NDArray,
    prim_batches: list[obe_reader.PrimBatch],
) -> Object:
    # Create empty object if vertices cannot be read
    if len(vertices) == 0 or "position" not in vertices.dtype.names:
        empty_obj = bpy.data.objects.new(name, None)
        context.collection.objects.link(empty_obj)
        return empty_obj

    triangles: list[tuple[int, int, int]] = []
    poly_group_lengths: list[int] = []
    start_vert = 0
    for prim_batch in prim_batches:
        tri_start_len = len(triangles)
        for prim in prim_batch.primitives:
            # Remap bone indices using matrix palette
            prim_vertices = vertices[start_vert : start_vert + prim.vertex_count]
            if type(prim) is obe_reader.SkinPrim:
                prim_vertices["indices"] = prim.matrix_palette[
                    prim_vertices["indices"] // 3
                ]

            # Convert primitive to triangles
            prim_positions = prim_vertices["position"]
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
        poly_group_lengths.append(len(triangles) - tri_start_len)

    # Import geometry
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(
        vertices["position"],
        [],
        triangles,
    )

    # Create and assign materials before mesh validation so polygons match triangles
    start_poly = 0
    mat_names: list[str] = []
    for prim_batch, poly_group_len in zip(prim_batches, poly_group_lengths):
        mat_name = str(prim_batch.tex_0_crc)
        if mat_name not in mat_names:
            mesh.materials.append(bpy.data.materials.new(mat_name))
            mat_names.append(mat_name)
        for i in range(poly_group_len):
            mesh.polygons[start_poly + i].material_index = mat_names.index(mat_name)
        start_poly += poly_group_len

    mesh.validate()
    mesh.update()

    # Create mesh object
    mesh_obj = bpy.data.objects.new(name, mesh)
    context.collection.objects.link(mesh_obj)

    # Import vertex UV layers
    for i in range(vertices.dtype["uvs"].shape[0]):
        uv_layer = mesh.uv_layers.new(name=f"UV{i}")
        for loop in mesh.loops:
            uv = vertices[loop.vertex_index]["uvs"][i]
            uv_layer.data[loop.index].uv = (uv[0], 1.0 - uv[1])

    # Import vertex normals
    mesh.normals_split_custom_set_from_vertices(vertices["normal"])

    # Import vertex colors
    vertex_color_attr = mesh.color_attributes.new(
        name="vertex_color",
        type="BYTE_COLOR",
        domain="POINT",
    )
    vertex_color_attr.data.foreach_set(
        "color",
        vertices["diffuse"].flatten(),
    )

    # Import vertex groups if present
    if "weights" not in vertices.dtype.names or "indices" not in vertices.dtype.names:
        return mesh_obj
    vertex_groups = [
        mesh_obj.vertex_groups.new(name=bone.name)
        for bone in actor_context.bone_map.values()
    ]
    for i, (raw_weights, indices) in enumerate(
        zip(vertices["weights"], vertices["indices"])
    ):
        weights: list[float] = raw_weights.tolist()
        weights.append(1.0 - sum(weights))
        for index, weight in zip(indices, weights):
            vertex_groups[int(index)].add([i], weight, "ADD")
    return mesh_obj


def import_node(
    context: Context,
    actor_context: ActorContext,
    node: obe_reader.Node,
) -> None:
    if type(node) is obe_reader.BoneNode:
        edit_bone = actor_context.armature_obj.data.edit_bones.new(str(node.crc))
        edit_bone.length = 25.0
        edit_bone.matrix = node.inverse_transform.inverted()
        if node.parent is not None:
            if type(node.parent) is obe_reader.BoneNode:
                edit_bone.parent = actor_context.bone_map[node.parent.matrix_index]
            else:
                logging.warning("Parenting bones to non-bone nodes is unimplemented.")
        actor_context.bone_map[node.matrix_index] = edit_bone
    elif type(node) is obe_reader.MeshNode:
        mesh_obj = import_mesh(
            context, actor_context, str(node.crc), node.vertices, node.prim_batches
        )
        if node.parent is None:
            mesh_obj.parent = actor_context.armature_obj
        else:
            mesh_obj.parent = actor_context.object_map[node.parent.crc]
        actor_context.object_map[node.crc] = mesh_obj

    # Import child nodes
    for child_node in node.child_nodes:
        import_node(context, actor_context, child_node)


def import_actor(context: Context, actor: obe_reader.Actor) -> None:
    # Import skin mesh
    actor_name = str(actor.crc)
    armature = bpy.data.armatures.new(actor_name)
    armature_obj = bpy.data.objects.new(actor_name, armature)
    context.collection.objects.link(armature_obj)
    armature_obj.scale *= 0.01
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode="EDIT")

    # Import nodes
    actor_context = ActorContext(armature_obj, {}, {})
    for root_node in actor.root_nodes:
        import_node(context, actor_context, root_node)

    # Import skin mesh if present
    if len(actor.vertices) == 0:
        return
    skin_mesh_obj = import_mesh(
        context, actor_context, actor_name, actor.vertices, actor.prim_batches
    )
    bpy.ops.object.mode_set(mode="OBJECT")
    skin_mesh_obj.parent = armature_obj
    modifier = skin_mesh_obj.modifiers.new("Armature", "ARMATURE")
    modifier.object = armature_obj
