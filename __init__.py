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
from bpy.props import StringProperty
from bpy.types import Operator, Context

from . import obe_reader
from . import obe_importer


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


def register():
    bpy.utils.register_class(ImportOBE)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(ImportOBE)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()
