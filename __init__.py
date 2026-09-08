bl_info = {
    "name": "ADDON_NAME",
    "author": "AUTHOR_NAME",
    "description": "",
    "version": (0, 1, 0),
    "blender": (2, 80, 0),
    "location": "File > Import-Export",
    "warning": "",
    "category": "Import-Export",
}


from pathlib import Path

import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, CollectionProperty, PointerProperty
from bpy.types import (
    Operator,
    Context,
    OperatorFileListElement,
    PropertyGroup,
    Panel,
    Scene,
)

from . import obe_reader, obe_importer, pc_extractor


class PCExtractSettings(PropertyGroup):
    output_dir: StringProperty(subtype="DIR_PATH")


class ExtractPCArchives(Operator, ImportHelper):
    bl_idname = "extract_archive.pc"
    bl_label = "Extract PC"
    filename_ext = ".pc"

    filter_glob: StringProperty(
        default="*.pc",
        options={"HIDDEN"},
    )
    directory: StringProperty(subtype="DIR_PATH", options={"SKIP_SAVE", "HIDDEN"})
    files: CollectionProperty(
        type=OperatorFileListElement, options={"SKIP_SAVE", "HIDDEN"}
    )

    def execute(self, context):
        settings = context.scene.pc_extract_settings
        if not settings.output_dir:
            self.report({"ERROR"}, "No output folder selected")
            return {"CANCELLED"}
        output_dir = Path(settings.output_dir)

        output_file_count = 0
        for file in self.files:
            input_path = Path(self.directory) / file.name
            output_file_count += pc_extractor.extract_pc(input_path, output_dir)
        self.report(
            {"INFO"},
            f"Extracted {output_file_count} files from {len(self.files)} archive"
            f"{"" if len(self.files) == 1 else "s"}",
        )

        return {"FINISHED"}


class PC_PT_panel(Panel):
    bl_label = "PC Extractor"
    bl_idname = "PC_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "PC Extractor"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.pc_extract_settings
        layout.prop(settings, "output_dir", text="Output Folder")
        layout.operator(
            "extract_archive.pc",
            text="Extract PC Archives",
            icon="EXPORT",
        )


class ImportOBE(Operator, ImportHelper):
    """Load a Taz: Wanted OBE file."""

    bl_idname = "import_scene.obe"
    bl_label = "Import OBE"
    filename_ext = ".obe"

    filter_glob: StringProperty(
        default="*.obe",
        options={"HIDDEN"},
        maxlen=255,
    )

    def execute(self, context: Context):
        resource = obe_reader.read_obe(Path(self.filepath))

        if type(resource) is obe_reader.Actor:
            obe_importer.import_actor(context, resource)
        return {"FINISHED"}


def menu_func_import(self, context):
    self.layout.operator(ImportOBE.bl_idname, text="Taz: Wanted Model (.obe)")


classes = (
    PCExtractSettings,
    ExtractPCArchives,
    PC_PT_panel,
    ImportOBE,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    Scene.pc_extract_settings = PointerProperty(type=PCExtractSettings)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del Scene.pc_extract_settings
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()
