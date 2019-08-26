bl_info = {
    "name": "SoftWrap",
    "description": "dynamics for retopology",
    "author": "Jean Da Costa Machado",
    "version": (0, 0, 1),
    "blender": (2, 80, 0),
    "wiki_url": "",
    "category": "Mesh",
    "location": "3D view > Proprties > SoftWrap",
    "warning": "This is an alpha version."}

from . multifile import register, unregister, add_module, import_modules

add_module("interface")
add_module("draw_3d")
add_module("utils")
add_module("springs")
add_module("manager")
# add_module("core_test")
import_modules()
