import logging

import bpy
from bpy.types import Armature, Context, EditBone, Object
import numpy.typing as npt

from . import reader


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


class OBEImporter:
    def __init__(self, context: Context) -> None:
        self.context = context
        self.armature_obj: Object
        self.bone_map: dict[int, EditBone] = {}
        self.object_map: dict[int, Object] = {}

    def import_mesh(
        self,
        name: str,
        vertices: npt.NDArray,
        prim_batches: list[reader.PrimBatch],
    ) -> Object:
        # Create empty object if vertices cannot be read
        if len(vertices) == 0 or "position" not in vertices.dtype.names:
            empty_obj = bpy.data.objects.new(name, None)
            self.context.collection.objects.link(empty_obj)
            return empty_obj

        # Convert primitives to triangles
        triangles: list[tuple[int, int, int]] = []
        poly_group_lengths: list[int] = []
        start_vert = 0
        for prim_batch in prim_batches:
            tri_start_len = len(triangles)
            for prim in prim_batch.primitives:
                prim_positions = vertices["position"][
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
            poly_group_lengths.append(len(triangles) - tri_start_len)

        # Import geometry
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(
            vertices["position"],
            [],
            triangles,
        )

        # Create and assign materials
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

        # Delay mesh validation so polygons match triangles
        mesh.validate()
        mesh.update()

        # Create mesh object
        mesh_obj = bpy.data.objects.new(name, mesh)
        self.context.collection.objects.link(mesh_obj)

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

        if (
            "weights" not in vertices.dtype.names
            or "indices" not in vertices.dtype.names
        ):
            return mesh_obj

        # Import vertex groups
        # vertex_groups = [
        #     mesh_obj.vertex_groups.new(name=str(crc)) for crc in self.bone_crcs
        # ]
        # for i, (raw_weights, indices) in enumerate(
        #     zip(vertices["weights"], vertices["indices"])
        # ):
        #     weights: list[float] = raw_weights.tolist()
        #     weights.append(1.0 - sum(weights))
        #     for idx, weight in zip(indices, weights):
        #         vertex_groups[int(idx)].add([i], weight, "ADD")
        return mesh_obj

    def import_node(self, node: reader.Node) -> None:
        if type(node) is reader.BoneNode:
            edit_bone = self.armature_obj.data.edit_bones.new(str(node.crc))
            edit_bone.length = 20.0
            edit_bone.matrix = node.inverse_transform.inverted()
            if node.parent is not None:
                edit_bone.parent = self.bone_map[node.parent.crc]
            self.bone_map[node.crc] = edit_bone
        elif type(node) is reader.MeshNode:
            mesh_obj = self.import_mesh(str(node.crc), node.vertices, node.prim_batches)
            if node.parent is None:
                mesh_obj.parent = self.armature_obj
            else:
                mesh_obj.parent = self.object_map[node.parent.crc]
            self.object_map[node.crc] = mesh_obj

        # Import child nodes
        for child_node in node.child_nodes:
            self.import_node(child_node)

    def import_actor(self, actor: reader.Actor) -> None:
        # Import skin mesh
        actor_name = str(actor.crc)
        armature = bpy.data.armatures.new(actor_name)
        self.armature_obj = bpy.data.objects.new(actor_name, armature)
        self.context.collection.objects.link(self.armature_obj)
        self.armature_obj.scale *= 0.01
        bpy.context.view_layer.objects.active = self.armature_obj
        bpy.ops.object.mode_set(mode="EDIT")

        # Import nodes
        for root_node in actor.root_nodes:
            self.import_node(root_node)

        # Import skin mesh
        bpy.ops.object.mode_set(mode="OBJECT")
        skin_mesh_obj = self.import_mesh(actor_name, actor.vertices, actor.prim_batches)
        skin_mesh_obj.parent = self.armature_obj
