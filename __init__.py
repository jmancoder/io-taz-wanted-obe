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
from bpy.props import CollectionProperty, PointerProperty, StringProperty
from bpy.types import (
    Context,
    Operator,
    OperatorFileListElement,
    Panel,
    PropertyGroup,
    Scene,
)

from . import obe_reader, obe_importer, pc_extractor, texture_reader


class TazWantedSettings(PropertyGroup):
    pc_output_dir: StringProperty(
        name="PC Output Folder",
        description="Output folder to extract the PC archive(s) to.",
        subtype="DIR_PATH",
    )
    manifest_path: StringProperty(
        name="Manifest Path",
        description="Path to the manifest.json of the package"
        "you are importing from. Used to locate dependencies.",
        subtype="FILE_PATH",
    )


class ExtractPCArchives(Operator, ImportHelper):
    """Extract one or more PC archives to the chosen output folder."""

    bl_idname = "extract_archive.taz_wanted_pc"
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
        settings = context.scene.taz_wanted_settings
        if not settings.pc_output_dir:
            self.report({"ERROR"}, "No output folder selected")
            return {"CANCELLED"}
        output_dir = Path(settings.pc_output_dir)

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


class ImportBMP(Operator, ImportHelper):
    """Load one or more BMP files from Taz: Wanted."""

    bl_idname = "import_image.taz_wanted_bmp"
    bl_label = "Import BMP"
    filename_ext = ".bmp"

    filter_glob: StringProperty(
        default="*.bmp",
        options={"HIDDEN"},
    )
    directory: StringProperty(subtype="DIR_PATH", options={"SKIP_SAVE", "HIDDEN"})
    files: CollectionProperty(
        type=OperatorFileListElement, options={"SKIP_SAVE", "HIDDEN"}
    )

    def execute(self, context):
        for file in self.files:
            input_path = Path(self.directory) / file.name
            texture = texture_reader.read_bmp(input_path)
            image = bpy.data.images.new(file.name, texture.width, texture.height)
            image.pixels = texture.pixels

        self.report(
            {"INFO"},
            f"Imported {len(self.files)} image{"" if len(self.files) == 1 else "s"}",
        )
        return {"FINISHED"}


class ImportOBE(Operator, ImportHelper):
    """Load one or more OBE files from Taz: Wanted."""

    bl_idname = "import_scene.obe"
    bl_label = "Import OBE"
    filename_ext = ".obe"

    filter_glob: StringProperty(
        default="*.obe",
        options={"HIDDEN"},
        maxlen=255,
    )
    directory: StringProperty(subtype="DIR_PATH", options={"SKIP_SAVE", "HIDDEN"})
    files: CollectionProperty(
        type=OperatorFileListElement, options={"SKIP_SAVE", "HIDDEN"}
    )

    def execute(self, context: Context):
        actor_count = 0
        for file in self.files:
            input_path = Path(self.directory) / file.name
            resource = obe_reader.read_obe(input_path)
            if type(resource) is obe_reader.Actor:
                obe_importer.import_actor(context, resource)
                actor_count += 1

        self.report(
            {"INFO"},
            f"Imported {actor_count} actor{"" if actor_count == 1 else "s"}",
        )
        return {"FINISHED"}


class TAZ_WANTED_PT_panel(Panel):
    bl_label = "Taz: Wanted"
    bl_idname = "TAZ_WANTED_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Taz: Wanted"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.taz_wanted_settings
        layout.prop(settings, "pc_output_dir", text="Output Folder")
        layout.operator(
            "extract_archive.taz_wanted_pc",
            text="Extract PC Archives",
            icon="EXPORT",
        )
        layout.separator(type="LINE")
        layout.prop(settings, "manifest_path", text="Manifest Path")
        layout.operator(
            "import_image.taz_wanted_bmp",
            text="Import BMP",
            icon="FILE_IMAGE",
        )
        layout.operator(
            "import_scene.obe",
            text="Import OBE",
            icon="FILE_3D",
        )


classes = (
    TazWantedSettings,
    ExtractPCArchives,
    ImportBMP,
    ImportOBE,
    TAZ_WANTED_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    Scene.taz_wanted_settings = PointerProperty(type=TazWantedSettings)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del Scene.taz_wanted_settings


if __name__ == "__main__":
    register()
