"""建筑套件 · 核心：单位与坐标、几何小工具、可动部件、施工阶段标记、导出（Blender 里 import）。

坐标约定（评审 2026-10-22 定的"四视图为准，Pixal3D 成品辅助"：尺寸全按拉齐后的四视图量，单位 = 四视图像素）：
  P(E, S, U)：E = 正视图向右、S = 朝正面相机、U = 离地高度。1 像素 = K = 0.01 Blender 单位（四视图约 70.6 像素 / 米）。
  Blender 里 x = −E、y = S、z = U；导出 glTF 后是 (−E, U, −S)，和 Pixal3D 的 GLB 一个朝向（预览时绕 Y 转 180° 正面朝相机）。
  范围参数一律 (min, max) 像素。box / cylinder / blob / arch_panel / brace 直接按世界坐标出顶点（物体原点 = 世界原点），
  只有可动部件（make_part）把原点挪到转轴。
"""
from __future__ import annotations

import math
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

K = 0.01                                               # 1 四视图像素 = 0.01 Blender 单位

# 当前生效的 UV 改写 f(ob)：new_obj / reuv 先按 box_uv 投，这里不为 None 时再交给它改（projection.projected 设）
uv_override = None

GLTF_KW = dict(export_format='GLB', export_apply=True, export_yup=True, export_extras=True)
STAGES = ('foundation', 'frame', 'done')               # 施工阶段（05-model-review-tools/review_page/viewer3d.js 的 STAGE_ORDER）


def P(E, S, U):
    """四视图像素坐标 → Blender 坐标（x = −E、y = S、z = U，× K）。"""
    return Vector((-E * K, S * K, U * K))


def reset_scene():
    """清空场景（read_factory_settings use_empty）+ 清掉材质缓存。每栋房子开搭前调一次。"""
    from . import materials
    bpy.ops.wm.read_factory_settings(use_empty=True)
    materials.reset_cache()


# ---------------- 几何小工具 ----------------
def tile_of(m):
    """材质的平铺尺寸（像素）：平铺贴图材质带 'tile'（一张贴图覆盖多少四视图像素，materials.ext_mat 写），其余按 32×32。"""
    t = m.get('tile') if m is not None else None
    return tuple(t) if t else (32, 32)


def new_obj(name, bm, m):
    """bmesh → 网格物体（挂到当前集合），材质 m（一个或列表，列表时面默认用第 0 个），按第一个材质的平铺投 UV。"""
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    if isinstance(m, list):
        for x in m:
            me.materials.append(x)
    else:
        me.materials.append(m)
    m0 = m[0] if isinstance(m, list) else m
    box_uv(ob, *tile_of(m0))
    if uv_override is not None:
        uv_override(ob)
    return ob


def reuv(ob, m):
    """布尔这类操作之后重做 UV（布尔会把切刀的 UV / 材质带进来）：清掉所有 UV 层，按 m 的平铺重投；投影模式下再投一次。"""
    me = ob.data
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    box_uv(ob, *tile_of(m))
    if uv_override is not None:
        uv_override(ob)


def box_uv(ob, tu=32, tv=32):
    """按面朝向投 UV：竖面 (水平, 高度)、水平面 (x, y)；每 tu × tv 像素一张贴图（竖条纹理就竖着走）。"""
    me = ob.data
    uvl = me.uv_layers.new(name='UV')
    for poly in me.polygons:
        n = poly.normal
        for li in poly.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co / K
            if abs(n.z) > max(abs(n.x), abs(n.y)):
                uv = (v.x, v.y)
            elif abs(n.x) > abs(n.y):
                uv = (v.y, v.z)
            else:
                uv = (v.x, v.z)
            uvl.data[li].uv = (uv[0] / tu, uv[1] / tv)


def box(name, E, S, U, m, bevel=0.0, seg=2):
    """长方体。E / S / U 各是 (min, max) 像素；bevel = 圆角像素（自动限到最短边的 0.49 倍），seg = 圆角段数。"""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    lo, hi = P(E[1], S[0], U[0]), P(E[0], S[1], U[1])   # x = −E，所以 E 的 max 对应 x 的 min
    c, s = (lo + hi) / 2, hi - lo
    for v in bm.verts:
        v.co = Vector((c.x + v.co.x * abs(s.x), c.y + v.co.y * abs(s.y), c.z + v.co.z * abs(s.z)))
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=bm.edges[:] + bm.verts[:], offset=min(bevel * K, min(abs(s.x), abs(s.y), abs(s.z)) * 0.49),
                        segments=seg, affect='EDGES', profile=0.5)
    return new_obj(name, bm, m)


def cylinder(name, c, r, U, m, seg=16, bulge=0.0):
    """竖圆柱：c = (E, S) 圆心，r = 半径像素，U = (底, 顶)。bulge > 0 时中间鼓（木桶：0.10 = 中间半径大 10%）。"""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r * K, radius2=r * K, depth=(U[1] - U[0]) * K)
    if bulge:
        bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if abs((e.verts[0].co - e.verts[1].co).z) > 1e-4], cuts=4)
        h2 = (U[1] - U[0]) * K / 2
        for v in bm.verts:
            k = 1 + bulge * (1 - (v.co.z / h2) ** 2)
            v.co.x *= k
            v.co.y *= k
    o = P(c[0], c[1], (U[0] + U[1]) / 2)
    for v in bm.verts:
        v.co += o
    return new_obj(name, bm, m)


def blob(name, c, rx, ry, rz, m, sub=2):
    """压扁的球（叶丛、花、茅草拱罩的圆鼓块）：c = (E, S, U) 球心，rx / ry / rz = 沿 Blender x / y / z 的半径像素。"""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1)
    o = P(*c)
    for v in bm.verts:
        v.co = Vector((v.co.x * rx * K, v.co.y * ry * K, v.co.z * rz * K)) + o
    return new_obj(name, bm, m)


def arch_panel(name, E, U, S, m, arch=True, seg=10):
    """拱形板：正视轮廓 = 矩形 + 上面半圆（arch=False 只要矩形），沿 S 从 S[0] 挤到 S[1]。
    挤出时保留原面当背面——评审 2026-10-22："门没有建模背面"（之前挤出把原面删了，门板 / 老虎窗窗框背面是空的）。"""
    e0, e1 = E
    w = (e1 - e0) / 2
    ec = (e0 + e1) / 2
    top = U[1] - (w if arch else 0)
    pts = [(e0, U[0]), (e1, U[0]), (e1, top)]
    if arch:
        pts +=[(ec + w * math.cos(a), top + w * math.sin(a)) for a in np.linspace(0, math.pi, seg)[1:-1]]
    pts += [(e0, top)]
    bm = bmesh.new()
    vs = [bm.verts.new(P(e, S[0], u)) for e, u in pts]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f], use_keep_orig=True)
    d = (S[1] - S[0]) * K
    bmesh.ops.translate(bm, verts=[v for v in ext['geom'] if isinstance(v, bmesh.types.BMVert)], vec=Vector((0, d, 0)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return new_obj(name, bm, m)


def brace(name, a, b, w, m, overlap=6):
    """斜撑 / 任意两点之间的方木：a、b = 两端中心 (E, S, U)，w = 截面边长像素；两头各多伸 overlap 像素，插进柱子和梁里不留缝。"""
    pa, pb = P(*a), P(*b)
    d = pb - pa
    ext = d.normalized() * overlap * K
    pa, pb = pa - ext, pb + ext
    d = pb - pa
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    L = d.length
    for v in bm.verts:
        v.co = Vector((v.co.x * w * K, v.co.y * w * K, v.co.z * L))
    rot = Vector((0, 0, 1)).rotation_difference(d.normalized())
    bmesh.ops.rotate(bm, verts=bm.verts[:], matrix=rot.to_matrix())
    bmesh.ops.translate(bm, verts=bm.verts[:], vec=(pa + pb) / 2)
    return new_obj(name, bm, m)


def boolean_cut(ob, cutter, solver='EXACT'):
    """ob 减去 cutter（布尔 DIFFERENCE，应用后删掉 cutter）。之后记得 reuv(ob, 材质)：布尔会把切刀的 UV / 材质带进来。"""
    mod = ob.modifiers.new('hole', 'BOOLEAN')
    mod.operation, mod.object, mod.solver = 'DIFFERENCE', cutter, solver
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter)


# ---------------- 物体集合 / 可动部件 / 施工阶段 ----------------
def snapshot():
    """当前所有物体（之后用 created_since 取这之后新建的）。"""
    return set(bpy.data.objects)


def created_since(before):
    """snapshot() 之后新建的物体，按名字排序（结果和 set 遍历顺序无关）。"""
    return sorted(set(bpy.data.objects) - before, key=lambda o: o.name)


def make_part(pid, objs, hinge, d, n, angle):
    """会动的部件单独成件——评审 2026-10-22："门应该单独建模""可活动的部件都应该单独建模"。
    objs 合成一个物体 part.<pid>，原点放转轴 hinge（Blender 坐标，用 P() 给），绕竖直轴开 0 → ±angle 度；
    方向由"门扇朝向 d、屋外方向 n"（Blender xy 平面里的二维向量）定：绕 +z 转正角时 d 往 z×d 走，(z×d)·n > 0 取正。
    extras：axis = 'z'、range = [0, ±angle]、stage = 'done'（预览器 / 引擎的部件约定，见 05-model-review-tools/review_page/viewer3d.js）。
    合并顺序按名字排（第一个当活动物体）：合出来的网格和 set 遍历顺序无关，每次构建一样。"""
    objs = sorted(objs, key=lambda o: o.name)
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = f'part.{pid}'
    ob.data.transform(Matrix.Translation(-hinge))
    ob.location = hinge
    sign = 1.0 if (-d[1] * n[0] + d[0] * n[1]) > 0 else -1.0
    ob['axis'] = 'z'
    ob['range'] = [0.0, sign * angle]
    ob['stage'] = 'done'
    return ob


def tag(objs, stage=None, only_stage=None):
    """施工阶段标记（写进 glTF extras，预览器的阶段切换用；茅草房不调用）：
    stage = 从哪个阶段起出现；only_stage = 只在这个阶段出现（脚手架这类）。
    阶段名默认 'foundation' | 'frame' | 'done'；每栋自己的阶段（每栋 2–4 个阶段，如帐篷 poles / cover）随便起 id，
    导出时 export(..., stages=[按顺序的 id], stage_names={id: 中文名})。约定见 05-model-review-tools/review_page/viewer3d.js 顶部。
    注意 make_part 给部件写的是 stage = 'done'，用自定义阶段时记得给部件重新 tag。返回 objs。"""
    for s in (stage, only_stage):
        if s is not None and (not isinstance(s, str) or not s):
            raise ValueError(f'阶段名要是非空字符串，收到 {s!r}')
    for o in objs:
        if stage is not None:
            o['stage'] = stage
        if only_stage is not None:
            o['only_stage'] = only_stage
    return objs


# ---------------- 导出 ----------------
def export(out, label='house', stages=None, stage_names=None):
    """整栋导出：<out>（组装版，含 part.* 节点，给预览页点开关）+ <名>_parts/（export_parts）。打印 [label] 件数 / 面数。
    stages：这栋自己的施工阶段顺序（不给 = 预览器默认 foundation → frame → done）；给了就加一个空节点 stage_order，
    extras.stages = 顺序、extras.stage_names = {id: 中文名}（预览器读它，见 05-model-review-tools/review_page/viewer3d.js），组装版和 body.glb 里都有，导完删掉。
    物体上写的阶段名不在顺序里时打印提醒（预览器里这种件每个阶段都显示）。"""
    order = None
    if stages:
        order = bpy.data.objects.new('stage_order', None)
        bpy.context.collection.objects.link(order)
        order['stages'] = list(stages)
        order['stage_names'] = dict(stage_names or {})
    known = list(stages) if stages else list(STAGES)
    used = {o[k] for o in bpy.data.objects for k in ('stage', 'only_stage') if k in o.keys()}
    if used - set(known):
        print(f'[{label}] 提醒：阶段名 {sorted(used - set(known))} 不在阶段顺序 {known} 里（预览器里这些件每个阶段都显示）')
    n = sum(len(o.data.polygons) for o in bpy.data.objects if o.type == 'MESH')
    kw = dict(GLTF_KW)
    bpy.ops.export_scene.gltf(filepath=str(out), **kw)
    print(f'[{label}] {len(bpy.data.objects)} 件 {n} 面 → {out}')
    export_parts(Path(out), kw)
    if order is not None:
        bpy.data.objects.remove(order)


def export_parts(out: Path, kw=None):
    """本体 + 部件分开出：<名>_parts/body.glb（静态部分 + 挂点 mount.<部件>，extras 写部件文件、转轴、开合角）
    和 <名>_parts/<部件>.glb（原点 = 转轴）。"""
    kw = dict(GLTF_KW) if kw is None else kw
    d = out.parent / f'{out.stem}_parts'
    d.mkdir(exist_ok=True)
    parts = [o for o in bpy.data.objects if o.name.startswith('part.')]
    for o in parts:
        loc = o.location.copy()
        o.location = (0, 0, 0)
        bpy.ops.object.select_all(action='DESELECT')
        o.select_set(True)
        pid = o.name[5:]
        bpy.ops.export_scene.gltf(filepath=str(d / f'{pid}.glb'), use_selection=True, **kw)
        o.location = loc
    mounts = []
    for o in parts:
        e = bpy.data.objects.new(f'mount.{o.name[5:]}', None)
        bpy.context.collection.objects.link(e)
        e.location = o.location
        e['part'] = f'{o.name[5:]}.glb'
        e['axis'] = o['axis']
        e['range'] = list(o['range'])
        mounts.append(e)
    bpy.ops.object.select_all(action='DESELECT')
    for o in bpy.data.objects:
        o.select_set(not o.name.startswith('part.'))
    bpy.ops.export_scene.gltf(filepath=str(d / 'body.glb'), use_selection=True, **kw)
    for e in mounts:
        bpy.data.objects.remove(e)
    print(f'[parts] 本体 + {len(parts)} 个部件 → {d}')
