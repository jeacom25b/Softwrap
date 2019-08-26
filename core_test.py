import bpy
import bmesh
from mathutils import Vector
from . import softwrap_core
from . springs import n_ring
from . multifile import register_class
from mathutils.kdtree import KDTree
import os

here = os.path.dirname(os.path.abspath(__file__))
profile_file = os.path.join(here, "profile.prof")

test = "BVH"

@register_class
class Operator(bpy.types.Operator):
    bl_idname = "object.core_test"
    bl_label = "core test"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        bm = bmesh.new()
        bm.from_mesh(context.active_object.data)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.verts.ensure_lookup_table()
        bm1 = bmesh.new()


        p = tuple(context.scene.cursor.location)
        pts = [tuple(vert.co) for vert in bm.verts]
        faces = [tuple(vert.index for vert in face.verts) for face in bm.faces]

        if test == "GEOM":
            if len(context.active_object.data.vertices) is not 3:
                self.report({"INFO"}, message="Cancelled")
                return {"CANCELLED"}

            tri = [tuple(v.co) for v in bm.verts]
            result = softwrap_core.test_barycentric(tri, p)
            self.report(type={"INFO"}, message=str(result))

        elif test == "MESH":

            newpts = softwrap_core.mesh_test(pts, faces, p)
            for pt in newpts:
                bm1.verts.new(pt)
            bpy.ops.object.duplicate()
            bm1.to_mesh(context.active_object.data)

        elif test == "BVH":
            import cProfile
            import pstats

            if 0:
                cProfile.runctx("for box in softwrap_core.test_bvh(pts, faces, p): continue",
                                 globals=globals(), locals=locals(), filename=profile_file)
                print("read stats")
                s = pstats.Stats(profile_file)
                print("print_stats stats")
                s.strip_dirs().sort_stats("time").print_stats()
            else:
                for b in softwrap_core.test_bvh(pts, faces, p):
                    nnn = bm1.verts.new((b["-x"], b["-y"], b["-z"]))
                    nnp = bm1.verts.new((b["-x"], b["-y"], b["+z"]))
                    npn = bm1.verts.new((b["-x"], b["+y"], b["-z"]))
                    npp = bm1.verts.new((b["-x"], b["+y"], b["+z"]))
                    pnn = bm1.verts.new((b["+x"], b["-y"], b["-z"]))
                    pnp = bm1.verts.new((b["+x"], b["-y"], b["+z"]))
                    ppn = bm1.verts.new((b["+x"], b["+y"], b["-z"]))
                    ppp = bm1.verts.new((b["+x"], b["+y"], b["+z"]))
                    co = bm1.verts.new((b["co"][0], b["co"][1], b["co"][2]))

                    bm1.edges.new((npn, nnn))
                    bm1.edges.new((nnn, nnp))
                    bm1.edges.new((nnp, npp))
                    bm1.edges.new((npp, npn))
                    bm1.edges.new((ppn, npn))
                    bm1.edges.new((npp, ppp))
                    bm1.edges.new((ppp, ppn))
                    bm1.edges.new((pnn, ppn))
                    bm1.edges.new((ppp, pnp))
                    bm1.edges.new((pnp, pnn))
                    bm1.edges.new((nnn, pnn))
                    bm1.edges.new((pnp, nnp))

                bpy.ops.object.duplicate()
                bm1.to_mesh(context.active_object.data)

        elif test == "LIST":
            softwrap_core.test_linked_list()

        elif test == "RNG":
            for co in softwrap_core.test_rng(900000):
                bm1.verts.new(co)
            bm1.to_mesh(context.active_object.data)

        return {"CANCELLED"}

@register_class
class Operator(bpy.types.Operator):
    bl_idname = "softwrap_core.test_engine"
    bl_label = "test engine"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        self.ob = context.active_object.data
        self.bm = bmesh.new()
        self.bm.from_mesh(self.ob)
        self.bm.verts.ensure_lookup_table()

        links = []
        for vert in self.bm.verts:
            l = []
            links.append(l)
            for v in n_ring(vert, 100):
                l.append(v.index)

        immediate_edges = [len(vert.link_edges) for vert in self.bm.verts]

        bmesh.ops.triangulate(self.bm, faces=self.bm.faces)
        self.bm.verts.ensure_lookup_table()

        co = [tuple(v.co) for v in self.bm.verts]
        t = [tuple(v.index for v in f.verts) for f in self.bm.faces]

        kd = KDTree(len(self.bm.verts))
        for vert in self.bm.verts:
            kd.insert(vert.co, vert.index)
        kd.balance()

        x_mirr_table = [kd.find((vert.co[0] * -1, vert.co[1], vert.co[2]))[1] for vert in self.bm.verts]

        self.engine = softwrap_core.ShapeEngine(co, t, links, co, t, immediate_edges, x_mirr_table)
        self.engine.random_co()


        self.engine.add_pin(co=(10, 0, 0), vert_index=0, stiffness=50, twisty=False, x_mirr=True)

        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        self.engine.springs_force_apply(factor=0.2, springs=100, stiffness=100)
        self.engine.smooth(factor=0.5)
        self.engine.target_attract(factor=1)
        self.engine.movement_step(0.5)
        self.engine.x_mirror_apply()
        # self.engine.pins_apply()

        for co, vert in zip(self.engine.co, self.ob.vertices):
            vert.co = co

        context.area.tag_redraw()
        if event.type in {"ESC"}:
            return {"CANCELLED"}

        return {"PASS_THROUGH"}
