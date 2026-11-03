"""纯色 + 顶点色明暗（黏土感）组件（2026-10-23 tex_trial 方向 A，评审选定推广到所有 Blender 模型；起因"贴图很难看，没对齐的感觉"）。

做法：
  - 材质全换纯色（materials.json / veg_materials.json 的四视图取色，按 sRGB 转线性），每个材质再包一层"乘顶点色"（veg.vcol_mat）；
  - 明暗写进顶点色（shade）：朝下 / 被遮挡（半球射线）/ 凹沟（点属性 puff_k，1 = 鼓、0 = 沟）变暗，朝上稍亮；
  - 质感交给几何：茅草层一缕一缕的竖向浅槽 + 下沿每缕一个草尖（thatch_tier）、木料圆角 + 浅纹槽（bar / bar3）、
    门板 / 百叶板缝（plank_grooves）、石块之间的缝（深色砂浆芯 + 环境遮挡）、桶板槽（staved_barrel）、老虎窗茅草拱罩一整根卷（hood_roll）；
  - 曲面平滑着色（茅草层、拱罩、叶团、桶），硬折角按角度留硬边（finish）。
坐标 / 单位同 bkit.core：P(E, S, U)，茅草房按四视图像素（K = 0.01），橡树按厘米。
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))))  # -> import bkit
from bkit import materials, veg  # noqa: E402
from bkit.core import K, P, new_obj  # noqa: E402
from bkit.props import smooth  # noqa: E402


# ---------------- 材质：纯色 × 顶点色 ----------------
def color_mat(name, srgb):
    """纯色材质（sRGB 取色 → 线性，materials.mat 在 SRGB_COLORS 打开时转）再包成乘顶点色版。"""
    return veg.vcol_mat(materials.mat(name, color=list(srgb)))


def house_mats(override=None):
    """materials.json 每项 → 纯色 × 顶点色（键同 materials.load 的 M）。stone / chimney 按 simple.variants 的 factor 出三档深浅。
    override = {id: [r, g, b] sRGB} 改个别颜色。"""
    materials.SRGB_COLORS = True
    sp = materials.spec('toy_clay')
    ov = override or {}
    M = {}
    for mid, e in sp['materials'].items():
        if e['kind'] == 'band':
            continue
        c = ov.get(mid, e['color'])
        vs = e.get('simple', {}).get('variants')
        if vs:
            M[mid] = [color_mat(f'f_{v["blender"]}', [min(1, x * v['factor']) for x in c]) for v in vs]
        else:
            M[mid] = color_mat(f'f_{mid}', c)
    for mid, c in ov.items():
        if mid not in M:
            M[mid] = color_mat(f'f_{mid}', c)
    return M


# ---------------- 顶点色明暗 ----------------
_HEMI = []
for _i in range(24):
    _z = math.sqrt(1 - (_i + 0.5) / 24)
    _a = _i * math.pi * (3 - math.sqrt(5))
    _q = math.sqrt(max(0.0, 1 - _z * _z))
    _HEMI.append(Vector((_q * math.cos(_a), _q * math.sin(_a), _z)))


def _frame(n):
    up = Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((1, 0, 0))
    u = n.cross(up).normalized()
    return u, n.cross(u).normalized()


def bvh_all(objs):
    verts, polys = [], []
    for o in objs:
        mw = o.matrix_world
        off = len(verts)
        verts += [mw @ v.co for v in o.data.vertices]
        polys += [[off + i for i in p.vertices] for p in o.data.polygons]
    return BVHTree.FromPolygons(verts, polys)


def shade(objs, tree, dist=60.0, w_down=0.5, w_ao=0.8, w_crease=0.5, dark=(0.35, 0.33, 0.32), up=0.10, gamma=1.0, blur=1,
          attr='Col'):
    """顶点色明暗（同 veg.shade_verts 的算法，多一项"朝上稍亮"、射线 24 条）：
      暗度 v = w_down × 朝下程度 + w_ao × 半球被挡比例（射线长 dist 建模单位）+ w_crease × (1 − puff_k)（有这个点属性时），截 0–1，邻点平均 blur 次；
      颜色 = (1 − v^gamma × (1 − dark)) × (1 − up × (1 − 朝上程度))：正朝上 = 1，侧面 / 朝下多压 up。
    返回 {物体名: 平均暗度}。"""
    res = {}
    for o in objs:
        me = o.data
        mw = o.matrix_world
        nm = mw.to_3x3().inverted().transposed()
        kat = me.attributes.get('puff_k')
        vals, ups = [], []
        for vt in me.vertices:
            p = mw @ vt.co
            n = (nm @ vt.normal).normalized()
            u, w = _frame(n)
            org = p + n * 0.004
            hit = 0
            for h in _HEMI:
                if tree.ray_cast(org, u * h.x + w * h.y + n * h.z, dist * K)[0] is not None:
                    hit += 1
            cr = (1.0 - kat.data[vt.index].value) if kat is not None else 0.0
            v = w_down * max(0.0, -n.z) + w_ao * hit / len(_HEMI) + w_crease * cr
            vals.append(max(0.0, min(1.0, v)))
            ups.append(max(0.0, n.z))
        nb = [[] for _ in me.vertices]
        for e in me.edges:
            a, c = e.vertices
            nb[a].append(c)
            nb[c].append(a)
        for _ in range(blur):
            vals = [(vals[i] * 2 + sum(vals[j] for j in nb[i])) / (2 + len(nb[i])) for i in range(len(vals))]
        if attr in me.color_attributes:
            me.color_attributes.remove(me.color_attributes[attr])
        ca = me.color_attributes.new(attr, 'FLOAT_COLOR', 'POINT')
        for i, v in enumerate(vals):
            f = v ** gamma
            g = 1 - up * (1 - ups[i])
            ca.data[i].color = ((1 - f * (1 - dark[0])) * g, (1 - f * (1 - dark[1])) * g, (1 - f * (1 - dark[2])) * g, 1.0)
        me.color_attributes.active_color = ca
        res[o.name] = sum(vals) / max(1, len(vals))
    return res


# ---------------- 平滑着色收尾 ----------------
def finish(objs, angle=80.0, skip=()):
    """没单独处理过的网格（盒子、方木、拱形板……）：全部平滑着色、夹角 > angle 的边留硬边，再加加权法线修改器（按面积）：
    大平面的法线保持平、倒角 / 圆角那一圈是圆的（平滑着色又不把整块木头着成圆棍；导出时 export_apply 写进 GLB 法线）。
    茅草层、叶团、拱罩、桶这些曲面自己平滑过（flat_done），跳过。"""
    for o in objs:
        if o.type != 'MESH' or o.name.startswith(skip) or o.get('flat_done'):
            continue
        smooth(o, angle=angle)
        md = o.modifiers.new('wn', 'WEIGHTED_NORMAL')
        md.mode = 'FACE_AREA'
        md.weight = 50
        md.keep_sharp = True


# ---------------- 网格小工具 ----------------
def grid_box(name, E, S, U, m, cell=16):
    """长方体，每个面按 cell 像素切成格子（墙这种大面：顶点色要有顶点才能出檐下 / 墙角的渐变）。"""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    lo, hi = P(E[1], S[0], U[0]), P(E[0], S[1], U[1])
    c, s = (lo + hi) / 2, hi - lo
    for v in bm.verts:
        v.co = Vector((c.x + v.co.x * abs(s.x), c.y + v.co.y * abs(s.y), c.z + v.co.z * abs(s.z)))
    for ax in range(3):
        a0, a1 = min(lo[ax], hi[ax]), max(lo[ax], hi[ax])
        n = max(1, round((a1 - a0) / (cell * K)))
        for k in range(1, n):
            co = Vector((0, 0, 0))
            co[ax] = a0 + (a1 - a0) * k / n
            no = Vector((0, 0, 0))
            no[ax] = 1
            bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=co, plane_no=no)
    ob = new_obj(name, bm, m)
    return ob


def _rrect(hw, hd, rc, grooves, corner_seg=3):
    """圆角矩形截面（逆时针）：半宽 hw、半厚 hd、圆角 rc；grooves = {边号: [(位置 −1–1 比例, 深, 半宽), …]}，边号 0 = +x 面、1 = +y、2 = −x、3 = −y。
    返回 [(x, y)]。"""
    pts = []
    corners = [(hw - rc, hd - rc, 0), (-hw + rc, hd - rc, 90), (-hw + rc, -hd + rc, 180), (hw - rc, -hd + rc, 270)]
    # 边：+x 面（从 (hw, −hd+rc) 到 (hw, hd−rc)）在角 0 之前
    SIDES = [((hw, 0), (0, 1), (-1, 0)), ((0, hd), (-1, 0), (0, -1)), ((-hw, 0), (0, -1), (1, 0)), ((0, -hd), (1, 0), (0, 1))]

    def side(k):
        # 平底槽：槽沿 → 槽底两点 → 槽沿（槽壁陡、平滑着色时槽壁留硬边，面本身保持平）
        out = []
        (bx, by), (ax_, ay_), (nx, ny) = SIDES[k]
        L = (hd if k in (0, 2) else hw) - rc
        for pos, dep, gw in sorted(grooves.get(k, []), key=lambda g: g[0]):
            gb = max(gw * 0.3, gw - 0.45 * K)
            for t, dd in ((pos * L - gw, 0), (pos * L - gb, dep), (pos * L + gb, dep), (pos * L + gw, 0)):
                out.append((bx + ax_ * t + nx * dd, by + ay_ * t + ny * dd))
        return out
    for k, (cx, cy, a0) in enumerate(corners):
        pts += side(k)
        for j in range(corner_seg + 1):
            a = math.radians(a0 + 90 * j / corner_seg)
            pts.append((cx + rc * math.cos(a), cy + rc * math.sin(a)))
    return pts


def bar3(name, pa, pb, ax1, ax2, hw, hd, m, rc=None, grooves=None, cell=90, end=0.8, corner_seg=2):
    """方木 / 板（Blender 坐标）：从 pa 到 pb，截面沿 ax1（半宽 hw）× ax2（半厚 hd），圆角 rc（默认 min × 0.35，最多 5 像素），
    截面四边可带浅纹槽 grooves（见 _rrect）；两头倒圆（端口收进 end × rc），中间每 cell 像素一圈（顶点色渐变用）。闭合体。"""
    d = pb - pa
    L = d.length
    dn = d.normalized()
    rc = min(hw, hd) * 0.35 if rc is None else rc
    rc = max(0.3 * K, min(rc, 5 * K, hw * 0.9, hd * 0.9))
    if rc < 2.5 * K:                                    # 小圆角（窗框横档、梁头这种细料）一段倒角就够，平滑着色看着是圆的
        corner_seg = 1
    sec = _rrect(hw, hd, rc, grooves or {}, corner_seg=corner_seg)
    c = min(rc * end, L * 0.3)
    n_mid = max(0, int(L / (cell * K)))
    zs = [0.0, c] + [c + (L - 2 * c) * (k + 1) / (n_mid + 1) for k in range(n_mid)] + [L - c, L]
    sh = [c * 0.7, 0.0] + [0.0] * n_mid + [0.0, c * 0.7]
    bm = bmesh.new()
    rings = []
    for z, s in zip(zs, sh):
        ring = []
        for x, y in sec:
            # 端口收进：截面往里缩 s（按到中心的方向，圆角处近似）
            kx = max(0.05, (hw - s) / hw)
            ky = max(0.05, (hd - s) / hd)
            ring.append(bm.verts.new(pa + dn * z + ax1 * x * kx + ax2 * y * ky))
        rings.append(ring)
    n = len(sec)
    for j in range(len(rings) - 1):
        for i in range(n):
            bm.faces.new((rings[j][i], rings[j][(i + 1) % n], rings[j + 1][(i + 1) % n], rings[j + 1][i]))
    caps = [bm.faces.new(list(reversed(rings[0]))), bm.faces.new(rings[-1])]
    bmesh.ops.triangulate(bm, faces=caps, quad_method='BEAUTY', ngon_method='EAR_CLIP')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return new_obj(name, bm, m)                          # 平滑 + 加权法线在 finish 里统一做


def _grooves_for(lens, rng, every=20, dep=0.9, gw=1.5):
    """截面四边各自按边长随机放几道浅纹槽：lens = 四条边的长度（像素）。"""
    g = {}
    for k, ln in enumerate(lens):
        cnt = int(ln // every)
        if cnt <= 0:
            continue
        g[k] = [(rng.uniform(-0.6, 0.6), dep * rng.uniform(0.7, 1.2) * K, gw * K) for _ in range(min(cnt, 1))]
        # 同一边的槽别挤在一起
        g[k].sort()
        for a in range(1, len(g[k])):
            if g[k][a][0] - g[k][a - 1][0] < 0.3:
                g[k][a] = (min(0.85, g[k][a - 1][0] + 0.3), g[k][a][1], g[k][a][2])
    return g


def bar(name, E, S, U, m, rng=random, grooves=True, rc=None, axis=None, plank=None, every=20):
    """轴对齐的方木（同 core.box 的范围写法，像素）：长轴 = 最长那个方向（或 axis = 'E' / 'S' / 'U'），圆角 + 顺着长轴的浅纹槽。
    plank = (板宽像素, 面号列表)：板子（百叶、门板）在这些面上按板宽开板缝（替代随机纹槽）。"""
    lo, hi = P(E[1], S[0], U[0]), P(E[0], S[1], U[1])
    ext = [abs(hi[i] - lo[i]) for i in range(3)]
    if axis is None:
        ia = max(range(3), key=lambda i: ext[i])
    else:
        ia = {'E': 0, 'S': 1, 'U': 2}[axis]
    i1, i2 = [i for i in range(3) if i != ia]
    c = (lo + hi) / 2
    e = [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))]
    pa = c - e[ia] * ext[ia] / 2
    pb = c + e[ia] * ext[ia] / 2
    hw, hd = ext[i1] / 2, ext[i2] / 2
    rc = rc * K if rc is not None else None             # 参数是像素，bar3 要 Blender 单位
    g = {}
    if plank is not None:
        pw = plank
        faces = (1, 3) if hd <= hw else (0, 2)          # 板面 = 截面上薄的那个方向的两面
        for k in faces:
            span = 2 * (hd if k in (0, 2) else hw) / K
            n = max(1, round(span / pw))
            L = (hd if k in (0, 2) else hw) - min(rc if rc is not None else min(hw, hd) * 0.35, 5 * K)
            g[k] = []
            for j in range(1, n):
                pos_px = -span / 2 + span * j / n
                g[k].append((pos_px * K / max(L, 1e-6), 1.1 * K, 1.3 * K))
    elif grooves:
        g = _grooves_for([2 * hd / K, 2 * hw / K, 2 * hd / K, 2 * hw / K], rng, every=every)
    ax1, ax2 = e[i1], e[i2]
    if ax1.cross(ax2).dot(pb - pa) < 0:
        ax2 = -ax2
        g = {(4 - k) % 4 if k in (1, 3) else k: v for k, v in g.items()}
    return bar3(name, pa, pb, ax1, ax2, hw, hd, m, rc=rc, grooves=g)


def bar_between(name, a, b, w, m, rng=random, overlap=6, grooves=True):
    """斜撑（同 core.brace：两端中心 (E, S, U)，截面 w × w，两头多伸 overlap）：圆角 + 纹槽。"""
    pa, pb = P(*a), P(*b)
    dn = (pb - pa).normalized()
    pa, pb = pa - dn * overlap * K, pb + dn * overlap * K
    side = Vector((0, 0, 1)).cross(dn)
    if side.length < 1e-6:
        side = Vector((1, 0, 0))
    ax1 = side.normalized()
    ax2 = dn.cross(ax1).normalized()
    g = _grooves_for([w] * 4, rng) if grooves else {}
    return bar3(name, pa, pb, ax1, ax2, w * K / 2, w * K / 2, m, grooves=g)


def plank_grooves(ob, xs, axis=0, width=1.2, depth=1.3, face_axis=1):
    """平板上开竖向板缝：在 Blender 坐标 axis 方向的位置 xs（像素）处切三刀（x − width、x、x + width），
    中间那刀上、位于朝 ±face_axis 的面上的顶点往里压 depth（像素）。门板、木板这种挤出板用。"""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    no = Vector((0, 0, 0))
    no[axis] = 1
    for x in xs:
        for dx in (-width, 0.0, width):
            co = Vector((0, 0, 0))
            co[axis] = (x + dx) * K
            bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=co, plane_no=no)
    fa = [v.co[face_axis] for v in bm.verts]
    lo_, hi_ = min(fa), max(fa)
    for v in bm.verts:
        if any(abs(v.co[axis] - x * K) < 1e-6 for x in xs):
            if abs(v.co[face_axis] - hi_) < 1e-6:
                v.co[face_axis] -= depth * K
            elif abs(v.co[face_axis] - lo_) < 1e-6:
                v.co[face_axis] += depth * K
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


# ---------------- 茅草层 ----------------
def _rr_point(a, b, rc, t):
    """圆角矩形（半宽 a、半深 b、圆角 rc）上按周长比例 t（0–1）取点 + 外法线；起点在 +x 边中点、逆时针。"""
    rc = max(1e-6, min(rc, a * 0.999, b * 0.999))
    sx, sy = a - rc, b - rc
    segs = [('l', (a, 0), (0, 1), sy), ('c', (sx, sy), 0, rc * math.pi / 2), ('l', (sx, b), (-1, 0), 2 * sx),
            ('c', (-sx, sy), 90, rc * math.pi / 2), ('l', (-a, sy), (0, -1), 2 * sy), ('c', (-sx, -sy), 180, rc * math.pi / 2),
            ('l', (-sx, -b), (1, 0), 2 * sx), ('c', (sx, -sy), 270, rc * math.pi / 2), ('l', (a, -sy), (0, 1), sy)]
    per = sum(s[3] for s in segs)
    d = (t % 1.0) * per
    for kind, p0, dirn, ln in segs:
        if d <= ln:
            if kind == 'l':
                x, y = p0[0] + dirn[0] * d, p0[1] + dirn[1] * d
                n = (dirn[1], -dirn[0])
                return x, y, n[0], n[1]
            ang = math.radians(dirn) + d / rc
            return p0[0] + rc * math.cos(ang), p0[1] + rc * math.sin(ang), math.cos(ang), math.sin(ang)
        d -= ln
    return a, 0.0, 1.0, 0.0


def thatch_tier(name, t, m, rng=random, strand=18, vps=4, groove=3.0, tip=6.0, rows_vis=11, rows_hid=3, top=False,
                bulge=0.30, curl=0.88, dome=6.0):
    """茅草一层（同 components.tier 的剖面：底下往里卷、最鼓处在 bulge、往上收到 tE / tS，平面圆角 r），重新按"圆角矩形 × 剖面"参数化出网格：
      - 一缕一缕：沿周长每 strand 像素一缕，每缕 vps 列顶点；截面按 sin^0.5 鼓起、缕与缕之间一道 groove 深的浅槽（往上 85% 以后淡掉）；
      - 草尖：露在外面那段最下 18% 的高度往下垂，每缕一个圆头（tip 像素，每缕随机 0.6–1.2 倍）；
      - 点属性 puff_k = 缕的鼓起程度（shade 拿来压暗槽）；顶 / 底用收缩圈封口（闭合体），top = True 时顶面中间拱起 dome 像素（屋脊圆）；
      - 平滑着色。rng 用一次 uniform（相位），和原 tier(geo=True) 的 scallop 一样，后面的随机数顺序不变。"""
    u0, u1 = t['U']
    uv0, uv1 = t.get('Uvis', t['U'])
    hv = (uv1 - u0) / (u1 - u0)
    ph = rng.uniform(0, 6.28)
    loc = random.Random(int(ph * 1000) + int(u0))
    b_ = bulge

    def prof(h, tp):
        if h <= b_:
            return curl + (1 - curl) * math.sqrt(max(0.0, 1 - ((b_ - h) / b_) ** 2))
        return tp + (1 - tp) * math.sqrt(max(0.0, 1 - ((h - b_) / (1 - b_)) ** 2))
    E, S, r = t['E'], t['S'], t['r']
    per = math.pi * (3 * (E + S) - math.sqrt((3 * E + S) * (E + 3 * S)))
    ns = max(24, round(per / strand))
    N = ns * vps
    amp = [loc.uniform(0.7, 1.25) for _ in range(ns)]
    tipk = [loc.uniform(0.6, 1.2) for _ in range(ns)]
    # 竖向：露出段 rows_vis 圈（底下密），藏起来那段 rows_hid 圈
    if top:
        hs = [(k / (rows_vis + rows_hid)) ** 1.15 for k in range(rows_vis + rows_hid + 1)]
    else:
        hs = [hv * (k / rows_vis) ** 1.25 for k in range(rows_vis + 1)] + [hv + (1 - hv) * k / rows_hid for k in range(1, rows_hid + 1)]
    bm = bmesh.new()
    rings, kvals = [], []
    for h in hs:
        a = E * prof(h, t['tE'])
        bb = S * prof(h, t['tS'])
        hvz = (u0 + h * (u1 - u0) - uv0) / max(1e-6, uv1 - uv0)    # 在露出段里的相对高度
        fade = 1.0 if hvz < 0.85 else max(0.0, 1 - (hvz - 0.85) / 0.15)
        h0, h1 = max(0.0, h - 0.01), min(1.0, h + 0.01)
        dz = (h1 - h0) * (u1 - u0)
        da = E * (prof(h1, t['tE']) - prof(h0, t['tE']))
        nh = abs(dz) / max(1e-9, math.hypot(dz, da))              # 面法线的水平分量：近水平的顶 / 底面 → 0
        fade *= min(1.0, max(0.0, (nh - 0.25) / 0.35))
        ring, kr = [], []
        for j in range(N):
            si, sj = j // vps, j % vps
            bump = math.sin(math.pi * sj / vps) ** 0.5 if vps > 1 else 1.0
            x, y, nx, ny = _rr_point(a, bb, r * min(1.0, prof(h, 1.0)), j / N + ph / (2 * math.pi))
            th = math.atan2(y / S, x / E)
            lump = 1 + 0.018 * math.sin(3 * th + ph) * math.sin(7 * h + ph) + 0.010 * math.sin(11 * th + 2 * ph)
            off = -groove * amp[si] * (1 - bump) * fade
            x, y = x * lump + nx * off, y * lump + ny * off
            z = u0 + h * (u1 - u0)
            if hvz < 0.18:
                w = (1 - hvz / 0.18) ** 1.5
                z -= tip * tipk[si] * w * (0.45 + 0.55 * bump)
            ring.append(bm.verts.new(P(x, y, z)))
            kr.append(bump * fade + (1 - fade))
        rings.append(ring)
        kvals.append(kr)
    # 顶 / 底封口：收缩圈（同一高度往里缩），最后一圈成 n 边形三角化
    def cap(h, z0, ins, rise):
        a = E * prof(h, t['tE'])
        bb = S * prof(h, t['tS'])
        out = []
        for k, d in enumerate(ins):
            ring = []
            dd = d * bb
            for j in range(N):
                x, y, _, _ = _rr_point(max(a - dd, 2), max(bb - dd, 2), max(r - dd, 1), j / N + ph / (2 * math.pi))
                ring.append(bm.verts.new(P(x, y, z0 + rise[k])))
            out.append(ring)
        return out
    ins = [0.3, 0.6, 0.85] if top else [0.5]           # 藏在上一层里的顶面只要一圈
    top_r = cap(1.0, u1, ins, [dome * math.sqrt(1 - (1 - d) ** 2) if top else 0.0 for d in ins])
    bot_r = cap(0.0, u0, [0.5], [0.0])
    allr = list(reversed(bot_r)) + rings + top_r
    kall = [[1.0] * N for _ in bot_r] + kvals + [[1.0] * N for _ in top_r]
    for jr in range(len(allr) - 1):
        A, B = allr[jr], allr[jr + 1]
        for i in range(N):
            bm.faces.new((A[i], A[(i + 1) % N], B[(i + 1) % N], B[i]))
    f0 = bm.faces.new(list(reversed(allr[0])))
    f1 = bm.faces.new(allr[-1])
    bmesh.ops.triangulate(bm, faces=[f0, f1], quad_method='BEAUTY', ngon_method='BEAUTY')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    flat_k = [k for kr in kall for k in kr]
    ob = new_obj(name, bm, m)
    at = ob.data.attributes.new('puff_k', 'FLOAT', 'POINT')
    for i, kv in enumerate(flat_k):
        at.data[i].value = kv
    smooth(ob)
    ob['flat_done'] = True
    return ob


def roof(M, tiers, rng=random, name='thatch', **kw):
    """茅草屋顶（同 components.roof 的分层 + fit_tiers），每层用 thatch_tier。"""
    from bkit.components import fit_tiers
    ft = fit_tiers(tiers)
    return [thatch_tier(f'{name}{i}', t, M['thatch'], rng=rng, top=(i == len(ft) - 1), **kw) for i, t in enumerate(ft)]


# ---------------- 老虎窗茅草拱罩 ----------------
def hood_roll(name, m, ec, s, R, cu, rad=(15, 14), seg=12, n=34, ridge=0.10, a0=0.05, a1=math.pi - 0.05, sx=1.1, su=0.85):
    """老虎窗茅草拱罩：沿拱形（e = ec + R cosθ × sx、u = cu + R sinθ × su、S = s）扫一整根圆卷（截面半径 rad = (拱面内, 沿 S)），
    每隔一圈截面放大 / 缩小一点 → 一道道横向草束棱（ridge = 起伏比例），两头收圆封口。点属性 puff_k = 棱的鼓起。"""
    bm = bmesh.new()
    rings, ks = [], []
    th = [a0 + (a1 - a0) * k / (n - 1) for k in range(n)]
    endn = 3
    for k, a in enumerate(th):
        c = Vector((ec + R * math.cos(a) * sx, s, cu + R * math.sin(a) * su))
        tan = Vector((-R * math.sin(a) * sx, 0, R * math.cos(a) * su)).normalized()
        nrm = Vector((tan.z, 0, -tan.x))                       # 拱面内朝外
        bump = 0.5 + 0.5 * math.cos(math.pi * k)               # 一圈鼓一圈收
        sc = 1 - ridge * (1 - bump)
        e_ = min(k, n - 1 - k)
        if e_ < endn:                                          # 两头收圆
            sc *= math.sqrt(max(0.05, 1 - ((endn - e_) / (endn + 0.6)) ** 2))
        ring = []
        for i in range(seg):
            q = 2 * math.pi * i / seg
            off = nrm * math.cos(q) * rad[0] * sc + Vector((0, 1, 0)) * math.sin(q) * rad[1] * sc
            pe = c + off
            ring.append(bm.verts.new(P(pe.x, pe.y, pe.z)))
        rings.append(ring)
        ks.append(bump if e_ >= endn else 1.0)
    for j in range(len(rings) - 1):
        for i in range(seg):
            bm.faces.new((rings[j][i], rings[j][(i + 1) % seg], rings[j + 1][(i + 1) % seg], rings[j + 1][i]))
    f0 = bm.faces.new(list(reversed(rings[0])))
    f1 = bm.faces.new(rings[-1])
    bmesh.ops.triangulate(bm, faces=[f0, f1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = new_obj(name, bm, m)
    at = ob.data.attributes.new('puff_k', 'FLOAT', 'POINT')
    for j in range(len(rings)):
        for i in range(seg):
            at.data[j * seg + i].value = ks[j]
    smooth(ob)
    ob['flat_done'] = True
    return ob


# ---------------- 桶 ----------------
def staved_barrel(name, c, r, U, m, staves=12, seg_per=3, bulge=0.10, groove=1.2, rings=5):
    """木桶身：竖圆柱、中间鼓 bulge，桶板之间一道 groove 像素的竖槽（每块板 seg_per 列顶点），上下封口。平滑着色。"""
    bm = bmesh.new()
    N = staves * seg_per
    u0, u1 = U
    rs = []
    for k in range(rings + 1):
        z = u0 + (u1 - u0) * k / rings
        hz = (z - (u0 + u1) / 2) / ((u1 - u0) / 2)
        kk = 1 + bulge * (1 - hz * hz)
        ring = []
        for j in range(N):
            a = 2 * math.pi * j / N
            rr = r * kk - (groove if j % seg_per == 0 else 0.0)
            ring.append(bm.verts.new(P(c[0] + rr * math.cos(a), c[1] + rr * math.sin(a), z)))
        rs.append(ring)
    for j in range(rings):
        for i in range(N):
            bm.faces.new((rs[j][i], rs[j][(i + 1) % N], rs[j + 1][(i + 1) % N], rs[j + 1][i]))
    f0 = bm.faces.new(list(reversed(rs[0])))
    f1 = bm.faces.new(rs[-1])
    bmesh.ops.triangulate(bm, faces=[f0, f1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = new_obj(name, bm, m)
    smooth(ob, angle=60)
    ob['flat_done'] = True
    return ob


def blob(name, c, rx, ry, rz, m, sub=2):
    """压扁的球（同 core.blob），平滑着色。"""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1)
    o = P(*c)
    for v in bm.verts:
        v.co = Vector((v.co.x * rx * K, v.co.y * ry * K, v.co.z * rz * K)) + o
    ob = new_obj(name, bm, m)
    smooth(ob)
    ob['flat_done'] = True
    return ob


def cylinder(name, c, r, U, m, seg=24):
    """竖圆柱（铁箍这种），平滑侧面、端面硬边。"""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r * K, radius2=r * K, depth=(U[1] - U[0]) * K)
    o = P(c[0], c[1], (U[0] + U[1]) / 2)
    for v in bm.verts:
        v.co += o
    ob = new_obj(name, bm, m)
    smooth(ob, angle=50)
    ob['flat_done'] = True
    return ob


# ---------------- 已有模型整体换成纯色 × 顶点色 ----------------
def _base_tex(m):
    """材质底色接的贴图节点（直接接或经 Mix 接到 Base Color），没有 = None。"""
    if not m or not m.use_nodes:
        return None
    for nd in m.node_tree.nodes:
        if nd.type == 'TEX_IMAGE' and nd.image is not None:
            return nd
    return None


def tex_mean_srgb(img):
    """贴图平均色（sRGB 0–1）。Blender 里 sRGB 贴图的 pixels 就是 sRGB 值；非 sRGB（线性）贴图先转回 sRGB 再平均。"""
    import numpy as np
    px = np.array(img.pixels[:]).reshape(-1, 4)
    px = px[px[:, 3] > 0.5][:, :3] if (px[:, 3] > 0.5).any() else px[:, :3]
    if img.colorspace_settings.name != 'sRGB':
        px = np.where(px <= 0.0031308, px * 12.92, 1.055 * np.power(px, 1 / 2.4) - 0.055)
    return [float(x) for x in px.mean(0)]


def flatten(objs=None, colors=None, keep=(), shade_kw=None, tree=None):
    """把一组网格的材质全换成纯色 × 顶点色，并写顶点色明暗（已有模型套方向 A 的第一步，几何不动）。
      颜色来源：colors[材质名]（sRGB）> 贴图平均色 > 原底色（纯色材质按原线性值，不再转）；
      keep = 不换的材质名前缀（发光的灯罩 / 玻璃这类）；
      shade_kw = 传给 shade 的参数（不给用默认）；网格都会写顶点色（没写的物体在 Blender 里乘出来是黑的）。
    返回 {原材质名: 新材质名}。"""
    objs = [o for o in (objs or bpy.data.objects) if o.type == 'MESH']
    colors = colors or {}
    done = {}
    for o in objs:
        for slot in o.material_slots:
            m = slot.material
            if m is None or m.name.startswith(keep) or m.name.endswith('_vc'):
                continue
            if m.name not in done:
                if m.name in colors:
                    nm = color_mat(f'f_{m.name}', colors[m.name])
                else:
                    t = _base_tex(m)
                    if t is not None:
                        nm = color_mat(f'f_{m.name}', tex_mean_srgb(t.image))
                    else:
                        base = m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value if m.use_nodes else (*m.diffuse_color[:3], 1)
                        mm = bpy.data.materials.new(f'f_{m.name}')
                        mm.use_nodes = True
                        b = mm.node_tree.nodes['Principled BSDF']
                        b.inputs['Base Color'].default_value = tuple(base)
                        b.inputs['Roughness'].default_value = 0.9
                        em = m.node_tree.nodes['Principled BSDF'].inputs.get('Emission Color') if m.use_nodes else None
                        if em is not None and m.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value > 0:
                            b.inputs['Emission Color'].default_value = tuple(em.default_value)
                            b.inputs['Emission Strength'].default_value = m.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value
                        nm = veg.vcol_mat(mm)
                done[m.name] = nm
            slot.material = done[m.name]
    shade(objs, tree or bvh_all(objs), **(shade_kw or {}))
    return {k: v.name for k, v in done.items()}
