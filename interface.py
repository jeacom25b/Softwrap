import bpy
from .multifile import register_class, register_function, unregister_function


@register_class
class SoftWrapSettings(bpy.types.PropertyGroup):
    is_running: bpy.props.BoolProperty(
        default=False, options={"SKIP_SAVE", "HIDDEN"})
    pause: bpy.props.BoolProperty(
        name="Pause", default=False, options={"SKIP_SAVE"})
    enable_interaction: bpy.props.BoolProperty(name="Enable", default=True)
    interact_mouse: bpy.props.EnumProperty(name="Interaction",
                                           items=(("LEFTMOUSE", "Left Mouse", "To avoid conflicts with selection, "
                                                                              "choose the side not assigned as selection"),
                                                  ("RIGHTMOUSE", "Right Mouse", "To avoid conflicts with selection, "
                                                                                "choose the side not assigned as selection")),
                                           default="LEFTMOUSE",
                                           description="To avoid conflicts with selection, "
                                                       "choose the side not assigned as selection")

    max_springs: bpy.props.IntProperty(name="Max Springs", min=4, default=300)
    x_mirror: bpy.props.BoolProperty(name="X Mirror", default=False)
    source_mesh: bpy.props.PointerProperty(
        type=bpy.types.Object, name="Source Mesh")
    target_mesh: bpy.props.PointerProperty(
        type=bpy.types.Object, name="Target Mesh")

    stiffness: bpy.props.IntProperty(name="Stiffness", min=4, default=100)
    drag: bpy.props.FloatProperty(name="Drag", min=0, max=1, default=0.2)
    smoothing: bpy.props.FloatProperty(
        name="Smooth", min=0, max=5, default=0)
    tension: bpy.props.FloatProperty(name="Tension", min=0, max=1, default=0.99)
    iterations: bpy.props.IntProperty(name="Iterations", min=1, default=2)
    quality: bpy.props.IntProperty(name="Quality", min=4, default=25)

    target_attraction: bpy.props.FloatProperty(
        name="Target Forcce", min=0, max=1, default=0.5)
    scale: bpy.props.FloatProperty(name="Scale", min=0, default=1, step=0.01)

    pin_stiffness: bpy.props.IntProperty(
        name="Pin Stiffness", min=0, default=30)
    pin_force: bpy.props.FloatProperty(
        name="Pin Force", min=0, max=1, default=1)


def get_settings(context):
    return context.scene.softwrap_settings


@register_class
class SoftWrapPanel(bpy.types.Panel):
    bl_idname = "SOFTWRAP_PT_softwrap_panel"
    bl_label = "Softwrap"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SoftWrap"

    def draw(self, context):
        layout = self.layout
        settings = get_settings(context)

        if settings.is_running:
            layout.label(text="Shift + Click to add pin.")
        layout.label(text="Interaction")
        col = layout.column(align=True)
        col.prop(settings, "enable_interaction",
                 text="Enable (Shift + Space)", toggle=True)
        row = col.row(align=True)
        row.prop(settings, "interact_mouse", expand=True)

        layout.separator()
        layout.label(text="Initialization")

        if settings.is_running:
            layout.operator("softwrap.main", text="Stop")
            layout.prop(settings, "pause", text="Pause (Space)", toggle=True)
        else:
            layout.operator("softwrap.main", text="Start")

        layout.prop(settings, "max_springs")
        layout.prop(settings, "x_mirror")

        layout.separator()
        layout.prop(settings, "source_mesh")
        layout.prop(settings, "target_mesh")

        layout.separator()
        layout.label(text="Dynamics")
        layout.prop(settings, "stiffness")
        layout.prop(settings, "drag", slider=True)
        layout.prop(settings, "smoothing", slider=True)
        layout.prop(settings, "tension")
        layout.prop(settings, "iterations")
        layout.prop(settings, "quality")

        layout.separator()
        layout.label(text="Retopo")
        layout.prop(settings, "target_attraction", slider=True)
        layout.prop(settings, "scale")

        ob = context.active_object
        pin_selected = ob and\
            ob.get("vert_index", None) != None and\
            ob.get("stiffness", None) != None and\
            ob.get("factor", None) != None and\
            ob.get("twisty", None) != None

        layout.label(text="Pins")
        layout.prop(settings, "pin_stiffness")
        layout.prop(settings, "pin_force")

        if pin_selected:
            layout.label(text="Selected Pin")
            box = layout.box()
            box.prop(ob, '["stiffness"]')
            box.prop(ob, '["factor"]')
            box.prop(ob, '["twisty"]', toggle=True)
        else:
            layout.label(text="No pin selected")


@register_function
def register():
    bpy.types.Scene.softwrap_settings = bpy.props.PointerProperty(
        type=SoftWrapSettings)


@unregister_function
def unregister():
    del bpy.types.Scene.softwrap_settings
