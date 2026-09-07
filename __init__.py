bl_info = {
    "name": "ADDON_NAME",
    "author": "AUTHOR_NAME",
    "description": "",
    "blender": (2, 80, 0),
    "version": (0, 0, 1),
    "location": "File > Import",
    "category": "Import-Export",
}


from pathlib import Path

import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from bpy.types import Operator, Context

from . import obe_reader
from . import obe_importer


class IMPORT_OT_obe(Operator, ImportHelper):
    """Load a Taz Wanted OBE file."""

    bl_idname = "import_scene.obe"
    bl_label = "Import OBE"
    filename_ext = ".obe"

    filter_glob: StringProperty(
        default="*.obe",
        options={"HIDDEN"},
        maxlen=255,
    )

    def execute(self, context: Context):
        mp_path = Path(self.filepath)
        with open(mp_path, "rb") as f:
            actor = obe_reader.read_obe(f)

        importer = obe_importer.OBEImporter(context)
        if type(actor) is obe_reader.Actor:
            importer.import_actor(actor)

        return {"FINISHED"}


def menu_func_import(self, context):
    self.layout.operator(IMPORT_OT_obe.bl_idname, text="Taz Wanted Model (.obe)")


def register():
    bpy.utils.register_class(IMPORT_OT_obe)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(IMPORT_OT_obe)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()
