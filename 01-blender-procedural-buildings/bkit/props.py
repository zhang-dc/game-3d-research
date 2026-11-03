"""营地级这类小件用的通用零件（2026-10-22 起）：圆木、绑绳圈、石块、有厚度的布面、平滑着色。

坐标同 core：P(E, S, U)，单位 = 建模单位（营地级按厘米建：1 单位 = 1 厘米，K = 0.01 → Blender 1 = 1 米）。
曲面一律平滑着色（smooth）：茅草房那轮全是平直着色导出，打光一块块的棱面（render_lit 近看看得出来）。
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from .core import K, P, new_obj


def smooth(ob, angle: float | None = None):
    """平滑着色。angle（度）给了就按角度：两面夹角大于它的边保持硬边（木板、石台这种有棱的）。"""
    me = ob.data
    for poly in me.polygons:
        poly.use_smooth = True
    if angle is not None:
        try:
            me.set_sharp_from_angle(angle=math.radians(angle))
        except AttributeError:                         # 老版本 Blender
            me.use_auto_smooth = True
            me.auto_smooth_angle = math.radians(angle)
    return ob


def _frame(d: Vector):
    """沿 d 方向的正交基 (u, v, d)。"""
    d = d.normalized()
    up = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    u = d.cross(up).normalized()
    v = d.cross(u).normalized()
    return u, v, d


def log(name, a, b, r, m, cap=None, seg=12, bevel=0.25, taper=0.0, tile=None):
    """两点之间的圆木：a、b = (E, S, U)，r = 半径（单位）。侧面 UV 绕一圈 = u、沿木头 = v（竖纹贴图顺着木头走），
    端面用 cap 材质（给了的话）按圆盘贴满一张图（年轮）。bevel = 端口倒圆占半径的比例；taper = 末端收细比例。
    tile = (u 一圈铺几张, 每张沿木头覆盖多少单位)，不给按 m['tile'] 第二维（或 32）算。"""
    pa, pb = P(*a), P(*b)
    L = (pb - pa).length
    u, v, d = _frame(pb - pa)
    bm = bmesh.new()
    rings = []
    rb = r * bevel * K                                 # 端口倒圆的长度（Blender 单位）
    # 截面圈：两头各一圈收小一点（倒圆），中间两圈全粗
    long_ = L > 2 * rb
    zs = [0.0, rb * 0.6, L - rb * 0.6, L] if long_ else [0.0, L]
    rs = [r * (1 - bevel * 0.5), r, r * (1 - taper), r * (1 - taper) * (1 - bevel * 0.5)] if long_ else [r, r * (1 - taper)]
    for z, rr in zip(zs, rs):
        ring = []
        for i in range(seg):
            t = 2 * math.pi * i / seg
            ring.append(bm.verts.new(pa + d * z + (u * math.cos(t) + v * math.sin(t)) * rr * K))
        rings.append(ring)
    side = []
    for j in range(len(rings) - 1):
        for i in range(seg):
            f = bm.faces.new((rings[j][i], rings[j][(i + 1) % seg], rings[j + 1][(i + 1) % seg], rings[j + 1][i]))
            side.append(f)
    caps = [bm.faces.new(list(reversed(rings[0]))), bm.faces.new(rings[-1])]
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    mats = [m] + ([cap] if cap is not None else [])
    for f in caps:
        f.material_index = 1 if cap is not None else 0
    ob = new_obj(name, bm, mats)
    # 重投 UV：侧面圆柱展开，端面圆盘
    me = ob.data
    uvl = me.uv_layers['UV']
    if tile is None:
        t_ = m.get('tile') if hasattr(m, 'get') else None
        tile = (1, t_[1] if t_ else 32)
    tu, tv = tile
    for poly in me.polygons:
        cos = [me.vertices[me.loops[li].vertex_index].co for li in poly.loop_indices]
        if poly.material_index == 1 or abs(poly.normal.dot(d)) > 0.9:   # 端面
            c = sum(cos, Vector()) / len(cos)
            for li, co in zip(poly.loop_indices, cos):
                q = co - c
                uvl.data[li].uv = (0.5 + q.dot(u) / (2 * r * K), 0.5 + q.dot(v) / (2 * r * K))
            continue
        ts = []
        for co in cos:
            q = co - pa
            ts.append(math.atan2(q.dot(v), q.dot(u)) / (2 * math.pi) % 1.0)
        if max(ts) - min(ts) > 0.5:                    # 跨 0 / 1 接缝的那一圈面
            ts = [t + 1 if t < 0.5 else t for t in ts]
        for li, co, t in zip(poly.loop_indices, cos, ts):
            uvl.data[li].uv = (t * tu, (co - pa).dot(d) / K / tv)
    smooth(ob)
    for poly in me.polygons:                           # 端面保持平的
        if abs(poly.normal.dot(d)) > 0.9:
            poly.use_smooth = False
    return ob


def rope_ring(name, c, axis, r, thick, m, seg=14, tube=6):
    """绑绳圈：绕 axis 方向、中心 c = (E, S, U)、半径 r（到绳子中线）、绳粗 thick（单位）的圆环。"""
    pc = P(*c)
    ax = Vector((-axis[0], axis[1], axis[2])).normalized()     # (E, S, U) 方向 → Blender
    u, v, d = _frame(ax)
    bm = bmesh.new()
    rings = []
    for i in range(seg):
        t = 2 * math.pi * i / seg
        cen = pc + (u * math.cos(t) + v * math.sin(t)) * r * K
        rad = (u * math.cos(t) + v * math.sin(t))
        ring = []
        for j in range(tube):
            s = 2 * math.pi * j / tube
            ring.append(bm.verts.new(cen + (rad * math.cos(s) + d * math.sin(s)) * thick / 2 * K))
        rings.append(ring)
    for i in range(seg):
        for j in range(tube):
            bm.faces.new((rings[i][j], rings[(i + 1) % seg][j], rings[(i + 1) % seg][(j + 1) % tube], rings[i][(j + 1) % tube]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return smooth(new_obj(name, bm, m))


def stone(name, c, rx, ry, rz, m, sub=2, lump=0.10, seed=0, flat_bottom=True):
    """圆鼓鼓的石块：压扁的球 + 低频起伏（lump = 半径的比例），底面压平贴地。c = (E, S, U) 是石块底面中心。"""
    rng = random.Random(seed)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1)
    ph = [rng.uniform(0, 6.28) for _ in range(6)]
    o = P(c[0], c[1], c[2] + rz)
    for vt in bm.verts:
        x, y, z = vt.co
        n = 1 + lump * (0.6 * math.sin(2.1 * x + ph[0]) * math.sin(1.7 * y + ph[1])
                        + 0.4 * math.sin(2.9 * z + ph[2]) * math.cos(1.3 * x + ph[3]))
        zz = z * n
        if flat_bottom and zz < -0.55:
            zz = -0.55 - (zz + 0.55) * 0.15
        vt.co = Vector((x * n * rx * K, y * n * ry * K, (zz + 0.0) * rz * K)) + o
    ob = new_obj(name, bm, m)
    # 底面贴地：整体抬到最低点 = c[2]
    zmin = min(vv.co.z for vv in ob.data.vertices)
    for vv in ob.data.vertices:
        vv.co.z += c[2] * K - zmin
    return smooth(ob)


def panel(name, pts, thick, m, normal_out=None):
    """有厚度的多边形布面 / 板：pts = [(E, S, U), …]（同一平面，逆时针看正面），沿面法线挤出 thick（单位），两面都在。
    normal_out = (E, S, U) 方向，给了就让正面朝它（帐篷布朝外）。"""
    bm = bmesh.new()
    vs = [bm.verts.new(P(*p)) for p in pts]
    f = bm.faces.new(vs)
    f.normal_update()
    nrm = f.normal.copy()
    if normal_out is not None:
        want = Vector((-normal_out[0], normal_out[1], normal_out[2]))
        if nrm.dot(want) < 0:
            f.normal_flip()
            nrm = -nrm
    ext = bmesh.ops.extrude_face_region(bm, geom=[f], use_keep_orig=True)
    bmesh.ops.translate(bm, verts=[x for x in ext['geom'] if isinstance(x, bmesh.types.BMVert)], vec=-nrm * thick * K)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return new_obj(name, bm, m)


def export_stage_glbs(out, stages, kw=None):
    """按施工阶段各出一个 GLB（= 做到这一阶段的样子，规格："每栋按阶段 2–4 个模型"）：<out 去掉 .glb>_stage<k>_<阶段 id>.glb。
    物体按 extras.stage（core.tag）归阶段：stage 序号 ≤ k 的显示；only_stage 只在那一阶段显示；没标阶段的算最后一阶段。
    在 core.export 之后调（它导出组装版和部件）；这里只按选择导出，不改场景。返回写出的文件列表。"""
    from pathlib import Path
    out = Path(out)
    kw = kw or dict(export_format='GLB', export_apply=True, export_yup=True, export_extras=True)
    files = []
    for k, sid in enumerate(stages):
        bpy.ops.object.select_all(action='DESELECT')
        for ob in bpy.data.objects:
            if ob.type != 'MESH':
                continue
            st, only = ob.get('stage'), ob.get('only_stage')
            if only is not None:
                ob.select_set(only == sid)
            else:
                idx = stages.index(st) if st in stages else len(stages) - 1
                ob.select_set(idx <= k)
        p = out.with_name(f'{out.stem}_stage{k}_{sid}.glb')
        bpy.ops.export_scene.gltf(filepath=str(p), use_selection=True, **kw)
        files.append(p)
    bpy.ops.object.select_all(action='DESELECT')
    print(f'[stages] {len(files)} 个阶段 GLB → {out.parent}')
    return files


def to_meters(units_per_m):
    """整个场景换成真实米数（导出前调）：建模单位 × K → 米，乘 1 / (units_per_m · K)。
    茅草房按四视图像素建（K = 0.01、四视图每米 70.6 像素）→ ×1.4164；营地级按厘米建（units_per_m = 100）→ ×1，不动。
    预览器按实际尺寸显示（用户反馈："应该按模型的实际尺寸来显示啊"）。
    网格数据和物体位置一起缩（部件的网格在转轴局部坐标、位置 = 转轴，一起缩还是对的）。返回倍数。"""
    f = 1.0 / (units_per_m * K)
    if abs(f - 1.0) < 1e-9:
        return 1.0
    S = Matrix.Scale(f, 4)
    for ob in bpy.data.objects:
        if ob.type == 'MESH':
            ob.data.transform(S)
        ob.location = ob.location * f
    return f
