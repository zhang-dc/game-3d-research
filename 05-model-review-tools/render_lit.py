"""打光渲染（Blender Cycles，正交相机 + 太阳光）：看接缝、漏光、穿模这类不打光对照图里看不出来的问题。

    blender -b --factory-startup --python render_lit.py -- <模型.glb> <out.png> <yaw> <pitch> [缩放 = 正交宽度米数] [中心 x,y,z（glTF 坐标）] [分辨率]
yaw / pitch 同 compare.py（yaw 0 = 正面，90 = 右侧；pitch 俯角）。光从游戏的固定方向来（左上前方）。
"""
import math
import sys

import bpy
from mathutils import Vector

a = sys.argv[sys.argv.index('--') + 1:]
glb, out, yaw, pitch = a[0], a[1], float(a[2]), float(a[3])
width = float(a[4]) if len(a) > 4 else 6.0
center = [float(x) for x in a[5].split(',')] if len(a) > 5 and a[5] else None   # 空字符串 = 包围盒中心
res = int(a[6]) if len(a) > 6 else 900

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
objs = [o for o in bpy.data.objects if o.type == 'MESH']
lo = Vector([min((o.matrix_world @ Vector(c))[i] for o in objs for c in o.bound_box) for i in range(3)])
hi = Vector([max((o.matrix_world @ Vector(c))[i] for o in objs for c in o.bound_box) for i in range(3)])
if center is None:
    c = (lo + hi) / 2
else:  # glTF (x, y, z) → Blender (x, −z, y)
    c = Vector((center[0], -center[2], center[1]))

# 模型坐标：glTF (−E, U, −S) 导入 Blender 后是 (−E, S, U)；yaw 0 从 +S（Blender +y）看
t, p = math.radians(yaw), math.radians(pitch)
d = Vector((-math.sin(t) * math.cos(p), math.cos(t) * math.cos(p), math.sin(p)))   # 从中心指向相机
cam_d = bpy.data.cameras.new('cam')
cam_d.type = 'ORTHO'
cam_d.ortho_scale = width
cam = bpy.data.objects.new('cam', cam_d)
bpy.context.collection.objects.link(cam)
cam.location = c + d * 30
cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
sc = bpy.context.scene
sc.camera = cam
sun_d = bpy.data.lights.new('sun', 'SUN')
sun_d.energy = 3.0
sun = bpy.data.objects.new('sun', sun_d)
bpy.context.collection.objects.link(sun)
L = Vector((-0.45, 0.55, 0.70)).normalized()     # 光从左（−x = +E 反方向…）上方、偏正面来
sun.rotation_euler = (-L).to_track_quat('-Z', 'Y').to_euler()
world = bpy.data.worlds.new('w')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.55, 0.58, 0.62, 1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.6
sc.world = world
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = 24
sc.cycles.use_denoising = False
sc.render.resolution_x = sc.render.resolution_y = res
sc.render.film_transparent = True
sc.view_settings.view_transform = 'Standard'
# TEXMODE（环境变量，比较贴图方式用）：不设 / closest = 最近邻（同预览器）；linear = 平滑采样；flat = 去掉贴图、换成贴图平均色
import os
import numpy as np
TEXMODE = os.environ.get('TEXMODE', 'closest')
for m in bpy.data.materials:
    if not m.use_nodes:
        continue
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != 'TEX_IMAGE':
            continue
        if TEXMODE == 'flat' and n.image is not None:
            px = np.array(n.image.pixels[:]).reshape(-1, 4)[:, :3].mean(0)
            if n.image.colorspace_settings.name == 'sRGB':   # pixels 是 sRGB 值，填进线性槽要先转
                px = np.where(px <= 0.04045, px / 12.92, ((px + 0.055) / 1.055) ** 2.4)
            for l in list(n.outputs['Color'].links):
                to = l.to_socket
                if to.node.type == 'BSDF_PRINCIPLED':
                    nt.links.remove(l)
                    to.default_value = (*px, 1)
                elif to.node.type == 'MIX' or to.node.type == 'MIX_RGB' or to.node.type == 'VECT_MATH' or True:
                    rgb = nt.nodes.new('ShaderNodeRGB'); rgb.outputs[0].default_value = (*px, 1)
                    nt.links.remove(l); nt.links.new(rgb.outputs[0], to)
        else:
            n.interpolation = 'Linear' if TEXMODE == 'linear' else 'Closest'
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
print('[lit]', out)
