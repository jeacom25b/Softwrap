import bpy
import bmesh

from .springs import SpringEngine

from mathutils.geometry import intersect_line_plane
from mathutils import Matrix, Vector
from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d, location_3d_to_region_2d
from .utils import DummyObj
from .multifile import register_class
from .interface import get_settings
from .draw_3d import DrawCallback, MULTIPLY_BLEND

draw = DrawCallback()
draw.blend_mode = MULTIPLY_BLEND
draw.line_width = 2
draw.point_size = 10
draw.draw_on_top = True


def get_mouse_ray(context, event, mat=Matrix.Identity(4)):
    region = context.region
    r3d = context.space_data.region_3d
    co = event.mouse_region_x, event.mouse_region_y
    origin = mat @ region_2d_to_origin_3d(region, r3d, co)
    vec = region_2d_to_vector_3d(region, r3d, co)
    vec.rotate(mat)
    return origin, vec


def mouse_raycast(obj, context, event):
    mat = obj.matrix_world.inverted()
    origin, vec = get_mouse_ray(context, event, mat)
    return obj.ray_cast(origin, vec)


def global_to_screen(co, context):
    region = context.region
    r3d = context.space_data.region_3d
    return location_3d_to_region_2d(region, r3d, co)


class CurrEngine:
    engine = None
    source_bm = None
    target_bm = None
    mouse_pin = None

    @classmethod
    def init(cls):
        settings = get_settings(bpy.context)
        if not settings.source_mesh:
            return False
        cls.source_bm = bmesh.new()
        cls.source_bm.from_mesh(settings.source_mesh.data)

        if settings.target_mesh:
            cls.target_bm = bmesh.new()
            cls.target_bm.from_mesh(settings.target_mesh.data)
            bmesh.ops.transform(cls.target_bm, matrix=settings.target_mesh.matrix_world, verts=cls.target_bm.verts)
            bmesh.ops.transform(cls.target_bm, matrix=settings.source_mesh.matrix_world.inverted(),
                                verts=cls.target_bm.verts)
        else:
            cls.target_bm = None

        cls.engine = SpringEngine(cls.source_bm, cls.target_bm, settings.max_springs, settings.x_mirror, 6)
        draw.setup_handler()

    @classmethod
    def remove(cls, context):
        cls.engine = None
        if cls.source_bm:
            cls.source_bm.free()
            cls.source_bm = None
        if cls.target_bm:
            cls.target_bm.free()
            cls.target_bm = None
        draw.remove_handler()

    @classmethod
    def mouse_pin_set(cls, context, event, mode="GRAB"):
        settings = get_settings(context)
        result, location, normal, index = mouse_raycast(settings.source_mesh, context, event)
        if result:
            vert = min(cls.engine.bm.faces[index].verts, key=lambda v: (v.co - location).length_squared)
            if mode == "GRAB":
                cls.mouse_pin = DummyObj(co=location,
                                         normal=context.space_data.region_3d.view_rotation @ Vector((0, 0, 1)),
                                         vert_index=vert.index,
                                         d=vert.co - location)
                return True
            elif mode == "PINS":
                if settings.source_mesh.get("pins", None):
                    pinl = settings.source_mesh["pins"]
                else:
                    pinl = []
                co = settings.source_mesh.matrix_world @ vert.co
                r = sum(e.calc_length() for e in vert.link_edges) / len(vert.link_edges)
                ob = bpy.data.objects.new(name="_pin", object_data=None)
                ob.location = co
                ob.empty_display_type = "SPHERE"
                ob.empty_display_size = r / 2
                ob["vert_index"] = vert.index
                ob["stiffness"] = settings.pin_stiffness
                ob["factor"] = settings.pin_force
                ob["twisty"] = True
                for nob in context.scene.objects:
                    nob.select_set(False)
                context.view_layer.active_layer_collection.collection.objects.link(ob)
                ob.select_set(True)
                context.view_layer.objects.active = ob
                pinl.append(ob.name)
                settings.source_mesh["pins"] = pinl
                return True

    @classmethod
    def mouse_pin_remove(cls):
        cls.mouse_pin = None

    @classmethod
    def pins_update(cls, context, event):
        settings = get_settings(context)
        cls.engine.clear_pins()
        mat = settings.source_mesh.matrix_world.inverted()
        if settings.source_mesh.get("pins", None):
            pins = list(settings.source_mesh["pins"])
            for ob_name in pins:
                if ob_name in context.scene.objects:
                    ob = context.scene.objects[ob_name]
                    co = mat @ ob.location
                    cls.engine.add_pin(co, ob["vert_index"], ob["stiffness"], ob["factor"], twisty=ob["twisty"],
                                       x_mirr=settings.x_mirror)
                else:
                    print("remove", ob_name)
                    pins.remove(ob_name)
            settings.source_mesh["pins"] = pins
        if cls.mouse_pin:
            origin, vec = get_mouse_ray(context, event, mat)
            origin += cls.mouse_pin.d
            hit2 = intersect_line_plane(origin, origin + vec, cls.mouse_pin.co, cls.mouse_pin.normal)
            cls.engine.add_pin(hit2, cls.mouse_pin.vert_index, settings.stiffness // 2, twisty=True,
                               x_mirr=settings.x_mirror)

    @classmethod
    def draw(cls, context):
        settings = get_settings(context)
        draw.clear_data()
        mat = settings.source_mesh.matrix_world
        for i, pin in enumerate(cls.engine.pins):
            vert = cls.engine.bm.verts[pin.vert_index]
            co1 = mat @ Vector(pin.co)
            co2 = mat @ vert.co
            draw.add_line(co1, co2, color1=(1, 0, 0, 1))
            draw.add_point(co1, color=(1, 0, 0, 1))
            draw.add_point(co2, color=(0, 1, 1, 1))

        draw.update_batch()

    @classmethod
    def step(cls):
        settings = get_settings(bpy.context)

        cls.engine.sizing = settings.scale

        if settings.drag < 1:
            cls.engine.movement_step(drag=1 - settings.drag)

        for i in range(settings.iterations):
            cls.engine.springs_force_apply(stiffness=settings.stiffness,
                                           springs=settings.quality,
                                           factor=settings.tension)
            cls.engine.pins_apply()
        if settings.smoothing > 0:
            cls.engine.smooth(factor=settings.smoothing)

        if settings.target_attraction > 0 and cls.target_bm:
            cls.engine.target_attract(factor=settings.target_attraction)

        if settings.x_mirror:
            cls.engine.x_mirror_apply()

        cls.engine.back_to_bm()
        if settings.source_mesh.mode == "OBJECT":
            cls.engine.bm.to_mesh(settings.source_mesh.data)

@register_class
class SoftwrapMain(bpy.types.Operator):
    bl_idname = "softwrap.main"
    bl_label = "Softwrap"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    _timer = None

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        settings = get_settings(context)
        if CurrEngine.engine:
            settings.is_running = False
            CurrEngine.remove(context)
            return {"CANCELLED"}

        CurrEngine.init()
        context.window_manager.modal_handler_add(self)
        self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
        settings.is_running = True
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        settings = get_settings(context)

        if not CurrEngine.engine or not settings.source_mesh or \
                settings.source_mesh.name not in context.view_layer.objects:
            settings.is_running = False
            CurrEngine.remove(context)
            context.window_manager.event_timer_remove(self._timer)
            return {"FINISHED"}

        elif event.type == "SPACE" and event.value == "PRESS" and not event.ctrl:
            if event.shift:
                settings.enable_interaction = not settings.enable_interaction
            else:
                settings.pause = not settings.pause
            return {"RUNNING_MODAL"}

        elif event.type == settings.interact_mouse and event.value == "PRESS" and settings.enable_interaction:
            if event.shift:
                mode = "PINS"
            else:
                mode = "GRAB"
            if CurrEngine.mouse_pin_set(context, event, mode):
                return {"RUNNING_MODAL"}

        elif event.type == settings.interact_mouse and event.value == "RELEASE":
            CurrEngine.mouse_pin_remove()

        elif event.type == "TIMER":
            CurrEngine.pins_update(context, event)
            if not settings.pause:
                CurrEngine.step()
            CurrEngine.draw(context)
            context.area.tag_redraw()

        return {"PASS_THROUGH"}
