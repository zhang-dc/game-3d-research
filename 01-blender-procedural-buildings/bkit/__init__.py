"""建筑套件 bkit：Blender 程序建模建筑时复用的材质库 + 组件库（Blender 自带的 Python 里 import）。
用户 2026-10-22："最好形成可以复用的材质和组件，方便建模时复用"。第一个用它的是茅草房 blender_house/house_s5.py（s5 定稿）。

    import random, sys
    sys.path.insert(0, '<repo>/01-blender-procedural-buildings')
    from bkit import core, materials, components as C
    core.reset_scene(); random.seed(7)
    M = materials.load('toy_clay')                         # 材质库：lib/materials/toy_clay/materials.json
    C.base(M); C.walls(M); C.roof(M, TIERS, band=materials.band(), geo=True); C.door(M); C.steps(M) …
    C.roughen()                                            # 几何质感（最后调）
    core.export('/…/out.glb')                              # 组装版 + <名>_parts/（本体 + 可动部件）

  core        单位与坐标（K、P(E, S, U)）、box / cylinder / blob / arch_panel / brace、make_part（可动部件）、tag（施工阶段）、export
  materials   材质库：load(style) → M 字典、band()（茅草带）、mat / ext_mat / tex_image（自己加材质）
  components  base 石基、walls + timber_frame 墙和木构架、roof 茅草屋顶、chimney、window、door、steps、dormer、lantern、barrel、roughen
  projection  四视图直投（不推荐，侧面会拉丝；只为复现 PROJ=1）
坐标：E = 正视图向右、S = 朝正面、U = 离地，单位 = 四视图像素（1 像素 = 0.01 Blender 单位）；Blender (−E, S, U)，glTF (−E, U, −S)。
"""
from . import components, core, materials, projection
from .core import (K, P, arch_panel, blob, box, box_uv, brace, created_since, cylinder, export, export_parts, make_part, new_obj,
                   reset_scene, snapshot, tag)
from .materials import band, load

__all__ = ['components', 'core', 'materials', 'projection', 'K', 'P', 'arch_panel', 'blob', 'box', 'box_uv', 'brace', 'created_since',
           'cylinder', 'export', 'export_parts', 'make_part', 'new_obj', 'reset_scene', 'snapshot', 'tag', 'band', 'load']
