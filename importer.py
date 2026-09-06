import bpy
from bpy.types import Context, Object
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


def import_mesh(
    context: Context, vertices: npt.NDArray, prim_batches: list[reader.PrimBatch]
) -> Object | None:
    if len(vertices) == 0 or "position" not in vertices.dtype.names:
        return None

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
    mesh = bpy.data.meshes.new("Mesh")
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
    mesh_obj = bpy.data.objects.new("Mesh", mesh)
    context.collection.objects.link(mesh_obj)

    # Import vertex UV layers
    for i in range(2):
        uv_field = f"uv_{i}"
        if uv_field not in vertices.dtype.names:
            continue
        uv_data = vertices[uv_field]
        uv_layer = mesh.uv_layers.new(name=f"UV{i}")
        for loop in mesh.loops:
            uv = uv_data[loop.vertex_index]
            uv_layer.data[loop.index].uv = (uv[0], 1.0 - uv[1])

    # Import vertex normals
    if "normal" in vertices.dtype.names:
        mesh.normals_split_custom_set_from_vertices(vertices["normal"])

    # Import vertex colors
    if "diffuse" in vertices.dtype.names:
        vertex_color_attr = mesh.color_attributes.new(
            name="vertex_color",
            type="BYTE_COLOR",
            domain="POINT",
        )
        vertex_color_attr.data.foreach_set(
            "color",
            vertices["diffuse"].flatten(),
        )

    return mesh_obj


def import_node(context: Context, node: reader.Node) -> None:
    if type(node) is reader.MeshNode:
        mesh_obj = import_mesh(context, node.vertices, node.prim_batches)
        if mesh_obj is not None:
            mesh_obj.scale *= 0.01

    # Import child nodes
    for child_node in node.child_nodes:
        import_node(context, child_node)


def import_actor(context: Context, actor: reader.Actor) -> None:
    # Import skin mesh
    skin_mesh_obj = import_mesh(context, actor.vertices, actor.prim_batches)
    if skin_mesh_obj is not None:
        skin_mesh_obj.scale *= 0.01

    # Import nodes
    for root_node in actor.root_nodes:
        import_node(context, root_node)
