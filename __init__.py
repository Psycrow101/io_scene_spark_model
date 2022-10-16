import bpy
from bpy.props import (
        BoolProperty,
        StringProperty,
)
from bpy_extras.io_utils import (
        ImportHelper,
        orientation_helper,
        axis_conversion,
)

bl_info = {
    "name": "Spark Model",
    "author": "Psycrow",
    "version": (0, 1, 0),
    "blender": (2, 81, 0),
    "location": "File > Import-Export",
    "description": "Import / Export Spark Model (.model)",
    "warning": "",
    "wiki_url": "",
    "support": 'COMMUNITY',
    "category": "Import-Export"
}

if "bpy" in locals():
    import importlib
    if "import_spark_model" in locals():
        importlib.reload(import_spark_model)


@orientation_helper(axis_forward='-Z', axis_up='Y')
class ImportSparkModel(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.spark_model"
    bl_label = "Import Spark Model"
    bl_options = {'PRESET', 'UNDO'}

    filter_glob: StringProperty(default="*.model", options={'HIDDEN'})
    filename_ext = ".model"

    game_directory: StringProperty(
        name="Game directory",
        description="For example C:/Steam/steamapps/common/Natural Selection 2/ns2",
        maxlen=1024,
    )

    import_actions: BoolProperty(
        name="Import actions",
        description="Load actions and link them to loaded model armature",
        default=True,
    )

    import_cameras: BoolProperty(
        name="Import cameras",
        description="Load cameras and make them children of the corresponding bones",
        default=True,
    )

    import_attach_points: BoolProperty(
        name="Import attach points",
        description="Load attach points and make them children of the corresponding bones",
        default=True,
    )

    def execute(self, context):
        from . import import_spark_model

        keywords = self.as_keywords(ignore=("axis_forward",
                                            "axis_up",
                                            "filter_glob",
                                            ))

        keywords["global_matrix"] = axis_conversion(from_forward=self.axis_forward,
                                                    from_up=self.axis_up,
                                                    ).to_4x4()

        return import_spark_model.load(context, **keywords)


def menu_func_import(self, context):
    self.layout.operator(ImportSparkModel.bl_idname,
                         text="Spark Model (.model)")


classes = (
    ImportSparkModel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
