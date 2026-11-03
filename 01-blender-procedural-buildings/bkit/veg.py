"""建筑套件 · 植被组件库（Blender 里 import）。用户 2026-10-23："植被 Blender 建 3D（同营地级）"，要"形成可以复用的材质和组件，方便建模时复用"。

约定同营地级（camp/*.py）：
  - 坐标 P(E, S, U)：E = 正视图向右、S = 朝正面相机、U = 离地；**单位厘米**，core.K = 0.01 → Blender 1 = 1 米（导出即米，不用 to_meters）。
  - 材质：M = materials.load('toy_clay', textures=True, units_per_m=100, srgb_colors=True)；植被专用贴图 / 颜色用 veg_materials(item)
    （贴图从各自四视图裁：building/veg/veg_materials.py → lib/materials/toy_clay/veg/<名>.png + veg_materials.json，不动 materials.json）。
  - 曲面一律平滑着色（叶片留硬边）；每个网格都是闭合体、法线朝外（游戏剔背面；构建完用 check_normals() 自查）。
  - 植被不分施工阶段，导出 core.export(out, label=<id>)。树叶 / 叶片都是静态的（不做会动的件）。
  - 随机数全走 seed 参数（random.Random(seed)），同参数同结果；组件调用顺序不影响别的组件。

组件（参数细节见各函数 docstring；数值都是厘米）：
  trunk(...)            树干：地面到分叉，中心线可弯、截面椭圆、往上收细、根部外扩 roots 条根、可加竖槽；树皮 UV 绕一圈 = u、沿干 = v
  branch(...)           主枝：两点间弯曲收细的圆枝（起点埋进树干、末端埋进树冠），树皮 UV 同 trunk
  roots(...)            露在地面上的粗根：从树干里往外拱、末端扎进地里的几条弯圆根
  knothole(...)         树洞：树干表面一圈凸起的圆唇 + 里面深色凹面（按方向射线贴在树干上）
  canopy_cluster(...)   阔叶树冠（旧做法，别的树还在用）：包络椭球里摆 n 个圆鼓叶团 + 一个芯（不透光），底面压平
  ---- 圆鼓叶簇树冠（2026-10-23 新做法：用户看了橡树 / 圆灌木说"改一改"——旧的"光滑芯 + 外面贴扁平叶片"像贴了贴纸的球、树干被树冠盖住）----
  shade_mats(m, tints)  一块材质 → 几档深浅（明 → 暗，贴图按 tint 乘像素 / 纯色乘颜色），给叶簇的材质槽用
  puff_cluster(...)     一个独立的圆鼓叶簇：细分球 + 十几个菜花状小鼓包（圆帽剖面取最大 → 鼓包之间是沟），多个材质槽
  puff_layout(...)      按包络（中心 + 半轴）自动排 n 个叶簇中心 [(E, S, U, 半径), …]（不照参考逐个摆时用）
  canopy_puffs(...)     按叶簇中心列表摆 5–12 个叶簇（部分重叠）+ 可选暗色堵洞芯，最后 shade_faces 按"法线朝下 + 被别的簇挡住 + 鼓包沟"分明暗
  shade_faces(...)      给一组多材质槽网格按面分明暗档（任何网格都能用：朝下程度 + 环境遮挡射线 + 鼓包沟）
  shade_at(...)         单点的暗度 0–1（同 shade_faces 的算法；给叶片 / 点缀小件选深浅档用）
  puff_leaves(...)      叶簇边缘少量点缀叶片（贴合叶簇表面，按 shade_at 选深浅）
  conifer_tiers(...)    针叶树：一层层下垂的锥形叶层，下沿是一圈圆头叶瓣（瓣尖下垂、瓣间收进），层层错开
  bush(...)             灌木：贴地的小号叶团（canopy_cluster；n=0 只要光滑圆顶芯）+ 可选一层叶片贴着表面、叶尖朝下瓦片式铺满
  lump(...)             单个圆鼓叶团（canopy_cluster / bush 内部用，也可单独摆）
  leaf(...)             单片叶（有厚度、可弯成贴合曲面）：shape = 'oak' 橡叶 / 'trefoil' 三裂叶 / 'round' 椭圆叶
  fruit / flower / mushroom   点缀小件（果子 / 花朵 / 蘑菇）
  scatter_on(...)       在一组物体的外表面上散布小件（从外往里打射线取最外层表面，避开被遮住的面）
  scatter_ground(...)   在地面圆环里散布小件（蘑菇、落果）
  bvh(objs)             一组物体的 BVHTree（给 leaf(conform=…) 复用）
  check_normals(objs)   每个网格的闭合 / 法线朝外自查（有符号体积 > 0）；导出后再用 building/veg/check_glb.py 查 GLB
  stats(objs)           三角形数 + 包围盒（米）

最小用法（建一棵树）：
    from bkit import core, materials, veg
    core.reset_scene()
    M = materials.load('toy_clay', textures=True, units_per_m=100, srgb_colors=True)
    V = veg.veg_materials('tree_oak')              # {'bark', 'leaf', 'leaf_light', 'knot'}
    t = veg.trunk('trunk', V['bark'], base=(0, 0), h=200, r=(60, 50), r_top=(45, 38), roots=6, root_len=40, root_h=45)
    veg.roots('root', V['bark'], t, n=6, reach=(130, 160), r=(40, 4))
    cs = veg.canopy_cluster('canopy', V['leaf'], c=(0, 0, 300), r=(240, 210, 200), r_bot=100, n=14, seed=3, zmin=-0.4, core_drop=0.3)
    tree = veg.bvh(cs)
    veg.scatter_on(cs, 30, lambda i, p, n, rng: veg.leaf(f'oakleaf_{i:02d}', V['leaf_light'], p, n, size=40, seg=20,
                                                         sink=0, conform=tree), seed=5, min_dist=40)
    veg.check_normals()
    core.export(out, label='tree_x')
完整例子：building/veg/tree_oak.py（阔叶树）、tree_pine.py（针叶树）、bush_round.py（灌木）；
构建 + 叠图 + 打光 + GLB 法线自查：bash building/veg/build_all.sh（单样 build.sh <id>、render.sh <id> <宽度米>）。
三角形参考（2026-10-23）：橡树 9756 → 叶簇版 14852、松树 9476、圆灌木 8216 → 叶簇版 9936；叶簇 1280 / 个（puff sub=4）、320（sub=3）；叶团 320 / 个（sub=3）、叶片 4 × seg、针叶层约 2 × 每层瓣数 × 6 × 11。
新植被：先在 building/veg/veg_materials.py 加裁图 / 取色并重跑，再在下面 ITEM_MATS 登记这样植被的材质角色。
"""
from __future__ import annotations

import json
import math
import random

import bmesh
import numpy as np
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from . import materials
from .core import K, P, new_obj
from .props import smooth

CAM = (0.0, 0.8, 0.6)        # 游戏机位方向（E, S, U）：从正面俯 36.87°（atan 0.75）
VEG_DIR = materials.LIB / 'toy_clay' / 'veg'

# 每样植被用哪几块材质：角色 → ('tile', 贴图 id) / ('color', 颜色 id) / ('rgb', [r, g, b] sRGB) / 列表（几档深浅）
ITEM_MATS = {
    'tree_oak': {'bark': ('tile', 'oak_bark'), 'leaf': ('tile', 'oak_leaf'),
                 'leaf_light': ('color', 'oak_leaf_light'), 'knot': ('color', 'oak_knot')},
    'tree_pine': {'bark': ('tile', 'pine_bark'), 'needle': ('tile', 'pine_needle')},
    # 灌木芯用纯色 bush_core：bush_foliage 贴图（11×8 texel）在芯上是一块块深色斑点（第 1 版打光图），先不用、留在库里
    'bush_round': {'foliage': ('color', 'bush_core'),
                   'leaf': [('color', 'bush_leaf_dark'), ('color', 'bush_leaf_mid'), ('color', 'bush_leaf_light')]},
    # 点缀小件的占位色（还没有对应四视图；建到那样植被时换成从它四视图取的色）
    'decor': {'fruit': ('rgb', [0.78, 0.18, 0.12]), 'stem': ('rgb', [0.40, 0.26, 0.12]),
              'petal': ('rgb', [0.95, 0.80, 0.85]), 'petal_c': ('rgb', [0.98, 0.80, 0.25]),
              'cap': ('rgb', [0.80, 0.20, 0.15]), 'cap_dot': ('rgb', [0.96, 0.93, 0.85]), 'mush_stem': ('rgb', [0.93, 0.88, 0.76])},
}


def veg_spec():
    """读 lib/materials/toy_clay/veg/veg_materials.json（veg_materials.py 写的：tiles 贴图 + colors 取色，每项带来源）。"""
    return json.loads((VEG_DIR / 'veg_materials.json').read_text(encoding='utf-8'))


def veg_materials(item):
    """一样植被的材质字典：角色 → Blender 材质（列表角色 → 材质列表）。先调过 materials.load(..., srgb_colors=True)（颜色按 sRGB 转线性）。
    贴图走 materials.ext_mat(ref_px_per_m=100)：材质上 'tile' = 一张贴图覆盖多少厘米（64 texel/米）。材质名 v_<id>。"""
    sp = veg_spec()

    def one(role, e):
        kind, val = e
        if kind == 'tile':
            t = sp['tiles'][val]
            if not (VEG_DIR / t['file']).exists():   # 开源版不带贴图 PNG：退回该贴图的平均色（纯色流程不需要贴图）
                return materials.mat(f'v_{val}', color=list(t['color']))
            return materials.ext_mat(f'v_{val}', VEG_DIR / t['file'], texel_per_m=sp['texel_per_m'], ref_px_per_m=100)
        if kind == 'color':
            return materials.mat(f'v_{val}', color=sp['colors'][val]['color'])
        return materials.mat(f'v_{role}', color=list(val))
    out = {}
    for role, e in ITEM_MATS[item].items():
        out[role] = [one(f'{role}{k}', x) for k, x in enumerate(e)] if isinstance(e, list) else one(role, e)
    return out


# ---------------- 坐标小工具 ----------------
def D(e, s, u):
    """(E, S, U) 方向 → Blender 方向（不乘 K）。"""
    return Vector((-e, s, u))


def to_esu(v):
    """Blender 坐标点 → (E, S, U) 厘米。"""
    return (-v.x / K, v.y / K, v.z / K)


def dir_esu(v):
    """Blender 方向 → (E, S, U) 方向。"""
    return (-v.x, v.y, v.z)


def _frame(d):
    d = d.normalized()
    up = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    u = d.cross(up).normalized()
    return u, d.cross(u).normalized(), d


def _bezier(p0, p1, p2, t):
    return p0 * (1 - t) ** 2 + p1 * 2 * t * (1 - t) + p2 * t * t


def _tube_uv(ob, uvw, tile):
    """管子（树干 / 枝）的 UV：uvw[顶点] = (绕一圈的比例 0–1, 沿管长厘米)；u 一圈铺 round(周长 / 贴图宽) 张，跨 0/1 的那圈面补 1。
    端盖（uvw 是 None 的顶点所在面）按平面投。"""
    me = ob.data
    uvl = me.uv_layers['UV']
    tu, tv = tile
    for poly in me.polygons:
        vs = [me.loops[li].vertex_index for li in poly.loop_indices]
        if poly.loop_total > 4:                        # 端盖
            for li, i in zip(poly.loop_indices, vs):
                co = me.vertices[i].co / K
                uvl.data[li].uv = (co.x / tu, co.y / tv)
            continue
        ts = [uvw[i][0] for i in vs]
        if max(ts) - min(ts) > 0.5:
            ts = [t + 1 if t < 0.5 else t for t in ts]
        for li, i, t in zip(poly.loop_indices, vs, ts):
            uvl.data[li].uv = (t * uvw[i][2], uvw[i][1] / tv)


def _tube(name, m, rings, ring_v, circ, cap0=True, cap1=True):
    """rings：每圈一组 Blender 点（同样个数）；ring_v：每圈沿管长的厘米数；circ：每圈周长（厘米，算 u 铺几张）。两头封盖，闭合体。"""
    bm = bmesh.new()
    seg = len(rings[0])
    vv = [[bm.verts.new(p) for p in r] for r in rings]
    for j in range(len(vv) - 1):
        for i in range(seg):
            bm.faces.new((vv[j][i], vv[j][(i + 1) % seg], vv[j + 1][(i + 1) % seg], vv[j + 1][i]))
    caps = []
    if cap0:
        caps.append(bm.faces.new(list(reversed(vv[0]))))
    if cap1:
        caps.append(bm.faces.new(vv[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    tw = (m.get('tile') or (32, 32))[0]
    uvw = []
    reps = max(1, round(sorted(circ)[len(circ) // 2] / tw))    # 整根用同一个圈数（每圈不同会把竖纹扭成人字）：取周长中位数那圈
    for j, r in enumerate(rings):
        for i in range(seg):
            uvw.append((i / seg, ring_v[j], reps))
    ob = new_obj(name, bm, m)
    # bmesh.to_mesh 保持顶点顺序：顶点 j*seg+i
    _tube_uv(ob, uvw, m.get('tile') or (32, 32))
    smooth(ob)
    for poly in ob.data.polygons:                      # 端盖保持平
        if poly.loop_total > 4:
            poly.use_smooth = False
    return ob


# ---------------- 树干 / 主枝 / 树洞 ----------------
def trunk(name, m, base=(0, 0), h=200, r=(50, 50), r_top=None, bend=(0, 0), roots=5, root_len=40, root_h=30, root_w=2.5,
          grooves=0, groove_depth=0.05, seg=28, rings=12, sink=5, seed=0):
    """树干：从地面（U = −sink，埋进地里一点不露缝）到分叉高度 h。
    base = (E, S) 根部中心；r = (rE, rS) 地面以上（根以外）的截面半轴；r_top = 顶部半轴（默认 r × 0.75，= 收细）；
    bend = (dE, dS) 顶部相对根部的偏移（中心线是二次贝塞尔，弯在上半段）；
    roots = 根数（均匀分布 + 随机抖动 ±0.25 个间隔、每条长短 0.7–1.1 随机），root_len = 地面处根往外多伸的厘米数，
    root_h = 根的外扩往上衰减的高度（高斯 exp(−(U / root_h)²)：根肩是圆的），root_w = 根的尖锐度（越大根越窄、根间凹得越深）；
    根间也外扩 0.2 × root_len（根之间不是直筒）；
    grooves = 竖槽条数（松树那种），groove_depth = 槽深占半径比例；seg = 一圈多少段、rings = 沿干多少圈（下密上疏）。
    返回物体；物体上记 'axis'（中心线 5 个点的 (E, S, U)），branch / knothole 用。"""
    rng = random.Random(seed)
    rE, rS = r
    tE, tS = r_top or (rE * 0.75, rS * 0.75)
    p0 = Vector((base[0], base[1], -sink))
    p2 = Vector((base[0] + bend[0], base[1] + bend[1], h))
    p1 = Vector((base[0], base[1], h * 0.5))
    ang = [2 * math.pi * (k + rng.uniform(-0.25, 0.25)) / max(roots, 1) for k in range(roots)]
    rot0 = rng.uniform(0, 2 * math.pi)
    ang = [a + rot0 for a in ang]
    rlen = [rng.uniform(0.7, 1.1) for _ in range(roots)]
    gph = rng.uniform(0, 6.28)
    rs, vs, circ = [], [], []
    L = 0.0
    prev = None
    for j in range(rings + 1):
        t = (j / rings) ** 1.6
        c = _bezier(p0, p1, p2, t)
        u = max(c.z, 0.0)
        if prev is not None:
            L += (c - prev).length
        prev = c
        a_ = rE + (tE - rE) * t
        b_ = rS + (tS - rS) * t
        ring = []
        per = 0.0
        for i in range(seg):
            th = 2 * math.pi * i / seg
            rr = 1.0
            if grooves:
                rr -= groove_depth * (0.5 + 0.5 * math.cos(grooves * th + gph)) ** 3
            x, y = a_ * math.cos(th) * rr, b_ * math.sin(th) * rr
            if roots:
                lob = 0.0
                for a, rl in zip(ang, rlen):           # 每条根：角距 dθ 在 ±(π / roots) 里是 cos 包，root_w 次方让根变窄
                    dth = abs(((th - a + math.pi) % (2 * math.pi)) - math.pi)
                    lob = max(lob, rl * max(0.0, math.cos(min(dth * roots / 2, math.pi / 2))) ** root_w)
                ext = root_len * math.exp(-(u / root_h) ** 2) * (0.2 + 0.8 * lob)
                x += ext * math.cos(th)
                y += ext * math.sin(th)
            ring.append(P(c.x + x, c.y + y, c.z))
        for i in range(seg):
            per += (ring[i] - ring[(i + 1) % seg]).length / K
        rs.append(ring)
        vs.append(L)
        circ.append(per)
    ob = _tube(name, m, rs, vs, circ)
    ob['axis'] = [tuple(_bezier(p0, p1, p2, k / 4)) for k in range(5)]
    return ob


def roots(name, m, trunk_ob, n=6, reach=(120, 160), r=(28, 9), U0=70, sink=12, seed=0, seg=8, rings=7, ecc=(1.0, 1.0), floor=-2,
          arch=0.75):
    """露在地面上的粗根：n 条弯圆根，从树干里 U0 高处（中心线上，起点埋在树干里）往外拱、末端扎进地下 sink 厘米。
    reach = 末端离树干中心的水平距离范围（厘米，每条随机），r = (起点半径, 末端半径)；ecc = (E, S) 方向距离缩放（树干是椭圆时用）。
    arch = 控制点高度占 U0 的比例（越大根越拱）；floor = 低于这个高度（厘米）的顶点压平（地下部分）。
    方向：均匀分布 + 抖动 ±0.3 个间隔。比 trunk(roots=…) 的截面外扩更像一条条根（trunk 那种在地面附近会鼓成一层台阶，第 1 轮俯视看得到）；
    两个可以一起用：trunk 的小外扩把根和树干接上。返回物体列表。"""
    rng = random.Random(seed)
    ax = [Vector(a) for a in trunk_ob['axis']]
    c0 = _poly(ax, 0.0)
    rot = rng.uniform(0, 2 * math.pi)
    out = []
    for k in range(n):
        a = rot + 2 * math.pi * (k + rng.uniform(-0.3, 0.3)) / n
        dx, dy = math.sin(a) * ecc[0], math.cos(a) * ecc[1]
        L = rng.uniform(*reach)
        st = (c0.x + dx * L * 0.15, c0.y + dy * L * 0.15, U0)
        md = (c0.x + dx * L * 0.45, c0.y + dy * L * 0.45, U0 * arch)
        en = (c0.x + dx * L, c0.y + dy * L, -sink)
        ob = branch(f'{name}_{k}', m, st, en, r[0] * rng.uniform(0.85, 1.1), r[1], mid=md, seg=seg, rings=rings)
        for v in ob.data.vertices:                      # 地下部分压平在 floor（末端截面不露出地面、包围盒不往下拖）
            if v.co.z < floor * K:
                v.co.z = floor * K
        out.append(ob)
    return out


def trunk_point(ob, t):
    """trunk 中心线上 t（0 = 根、1 = 顶）处的 (E, S, U)。"""
    return tuple(_poly([Vector(a) for a in ob['axis']], t))


def _poly(ax, t):
    x = t * (len(ax) - 1)
    k = min(int(x), len(ax) - 2)
    return ax[k].lerp(ax[k + 1], x - k)


def branch(name, m, a, b, r, r_end=None, lift=0.2, seg=10, rings=6, mid=None):
    """主枝：a → b（(E, S, U)），起点半径 r、末端 r_end（默认 r × 0.55）；中段往上拱 lift × 长度（枝往上弯）；
    mid = 贝塞尔控制点 (E, S, U)，给了就不用 lift（根：从树干里往外拱再扎进地里）。
    起点要埋进树干、末端埋进树冠（两头都封盖，不露缝；第 1 轮橡树一根主枝末端露在树冠底下，看得到截面）。树皮 UV 同 trunk。"""
    pa, pb = Vector(a), Vector(b)
    L0 = (pb - pa).length
    pm = Vector(mid) if mid is not None else (pa + pb) / 2 + Vector((0, 0, lift * L0))
    r_end = r * 0.55 if r_end is None else r_end
    rs, vs, circ = [], [], []
    L = 0.0
    prev = None
    for j in range(rings + 1):
        t = j / rings
        c = _bezier(pa, pm, pb, t)
        tan = (_bezier(pa, pm, pb, min(1, t + 0.01)) - _bezier(pa, pm, pb, max(0, t - 0.01)))
        u, v, _ = _frame(D(*tan))
        if prev is not None:
            L += (c - prev).length
        prev = c
        rr = r + (r_end - r) * t
        pc = P(*c)
        rs.append([pc + (u * math.cos(2 * math.pi * i / seg) + v * math.sin(2 * math.pi * i / seg)) * rr * K for i in range(seg)])
        vs.append(L)
        circ.append(2 * math.pi * rr)
    return _tube(name, m, rs, vs, circ)


def _torus(name, m, c, n, R, rt, seg=16, tube=6, stretch=1.0):
    """圆环：中心 c、法线 n（Blender），大半径 R、管半径 rt（Blender 单位）；stretch = 沿竖直方向拉长（椭圆唇）。"""
    u, v, d = _frame(n)
    if abs(d.z) < 0.9:                                # 让 v 尽量竖直
        v = (Vector((0, 0, 1)) - d * d.z).normalized()
        u = v.cross(d).normalized()
    bm = bmesh.new()
    rings = []
    for i in range(seg):
        t = 2 * math.pi * i / seg
        rad = u * math.cos(t) + v * math.sin(t) * stretch
        cen = c + rad * R
        radn = (u * math.cos(t) + v * math.sin(t)).normalized()
        rings.append([bm.verts.new(cen + (radn * math.cos(2 * math.pi * j / tube) + d * math.sin(2 * math.pi * j / tube)) * rt)
                      for j in range(tube)])
    for i in range(seg):
        for j in range(tube):
            bm.faces.new((rings[i][j], rings[(i + 1) % seg][j], rings[(i + 1) % seg][(j + 1) % tube], rings[i][(j + 1) % tube]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return smooth(new_obj(name, bm, m))


def _ellipsoid(name, m, c, axes, sub=3):
    """沿正交轴 axes = [(方向 Blender, 半径 Blender), ×3] 的椭球，中心 c（Blender）。"""
    axes = list(axes)
    if axes[0][0].cross(axes[1][0]).dot(axes[2][0]) < 0:   # 左手系会把球翻成里朝外：第三轴反向（椭球对称，形状不变）
        axes[2] = (-axes[2][0], axes[2][1])
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1)
    for vt in bm.verts:
        x, y, z = vt.co
        vt.co = c + axes[0][0] * x * axes[0][1] + axes[1][0] * y * axes[1][1] + axes[2][0] * z * axes[2][1]
    # 不调 recalc_face_normals：很薄的椭球（蘑菇白点厚 0.05 r）它会判反；icosphere 原本朝外、右手系线性变换后仍朝外
    bm.normal_update()
    return smooth(new_obj(name, bm, m))


def knothole(name, m_rim, m_in, target, U, azimuth, r=12, stretch=1.35, rim=0.32):
    """树洞：在 target（树干物体）上、高度 U（厘米）、方位 azimuth（度，0 = 正面 +S、90 = +E）处，从外往里打射线取表面点，
    贴一圈凸起的圆唇（_torus，竖向拉长 stretch 倍）+ 里面一块深色凹面（压扁椭球，半埋在树干里）。r = 洞口半径，rim = 唇粗占 r 比例。
    返回 [唇, 里面]；射线没打中返回 []。"""
    a = math.radians(azimuth)
    d = D(math.sin(a), math.cos(a), 0)
    ax = [Vector(x) for x in target['axis']]
    c = _poly(ax, max(0.0, min(1.0, U / max(ax[-1].z, 1))))
    org = P(c.x, c.y, U) + d * 10.0
    hit = _raycast([target], org, -d)
    if hit is None:
        return []
    p, n = hit
    rim_ob = _torus(f'{name}_rim', m_rim, p + n * r * rim * 0.2 * K, n, r * K, r * rim * K, stretch=stretch)
    u, v, dd = _frame(n)
    if abs(dd.z) < 0.9:
        v = (Vector((0, 0, 1)) - dd * dd.z).normalized()
        u = v.cross(dd).normalized()
    inner = _ellipsoid(f'{name}_in', m_in, p - n * r * 0.25 * K, [(u, r * 0.95 * K), (v, r * 0.95 * stretch * K), (dd, r * 0.45 * K)], sub=2)
    return [rim_ob, inner]


# ---------------- 射线 / 散布 ----------------
def _bvh(objs):
    verts, polys = [], []
    for o in objs:
        mw = o.matrix_world
        base = len(verts)
        verts += [mw @ v.co for v in o.data.vertices]
        polys += [[base + i for i in p.vertices] for p in o.data.polygons]
    return BVHTree.FromPolygons(verts, polys)


def _raycast(objs, org, d, tree=None):
    tree = tree or _bvh(objs)
    loc, nrm, _, _ = tree.ray_cast(org, d)
    if loc is None:
        return None
    if nrm.dot(d) > 0:
        nrm = -nrm
    return loc, nrm.normalized()


def scatter_on(targets, n, make, seed=0, center=None, up=(-0.3, 1.0), min_dist=0.0, tries=20, even=False):
    """在 targets（物体列表）的外表面散布 n 个小件：随机方向 d（d 的竖直分量在 up 范围内）从包围球外朝 center（默认包围盒中心）打射线，
    取第一个打中的点 = 最外层表面（被别的叶团挡住的面不会选到，不会埋在里面）；min_dist（厘米）= 两件之间最小距离（每件最多重试 tries 次）。
    make(i, p, n, rng) 建一件：p = 表面点 (E, S, U)，n = 外法线 (E, S, U)，rng = random.Random；返回物体或物体列表。返回所有建出的物体。
    even = True：方向按斐波那契球面均匀铺（竖直分量在 up 范围里均匀、方位角按黄金角转 + 小抖动），不随机——要铺满一层（灌木叶）时用；
    第 1 版灌木随机方向，叶子一带一带、中间露出大块芯。"""
    rng = random.Random(seed)
    tree = _bvh(targets)
    pts = [o.matrix_world @ Vector(c) for o in targets for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    cen = P(*center) if center is not None else (lo + hi) / 2
    R = (hi - lo).length
    out, hits = [], []
    ga = math.pi * (3 - math.sqrt(5))
    rot = rng.uniform(0, 2 * math.pi)
    for i in range(n):
        for t_ in range(tries):
            if even and t_ == 0:
                z = up[1] - (i + 0.5) / n * (up[1] - up[0]) + rng.uniform(-0.02, 0.02)
                a = rot + i * ga + rng.uniform(-0.1, 0.1)
            else:
                z = rng.uniform(*up)
                a = rng.uniform(0, 2 * math.pi)
            q = math.sqrt(max(0.0, 1 - z * z))
            d = Vector((q * math.cos(a), q * math.sin(a), z))
            hit = _raycast(None, cen + d * R, -d, tree)
            if hit is None:
                continue
            p, nrm = hit
            if min_dist and any((p - h).length / K < min_dist for h in hits):
                continue
            hits.append(p)
            r = make(i, to_esu(p), dir_esu(nrm), rng)
            out += r if isinstance(r, list) else [r]
            break
    return out


def scatter_ground(n, make, seed=0, c=(0, 0), r=(50, 150), U=0.0, min_dist=0.0, tries=20):
    """在地面圆环（中心 c = (E, S)、半径 r = (内, 外) 厘米）里散布 n 件：make(i, p, n, rng)，p = (E, S, U)、n = (0, 0, 1)。"""
    rng = random.Random(seed)
    out, hits = [], []
    for i in range(n):
        for _ in range(tries):
            a = rng.uniform(0, 2 * math.pi)
            rr = math.sqrt(rng.uniform(r[0] ** 2, r[1] ** 2))
            p = (c[0] + rr * math.sin(a), c[1] + rr * math.cos(a), U)
            if min_dist and any(math.hypot(p[0] - h[0], p[1] - h[1]) < min_dist for h in hits):
                continue
            hits.append(p)
            o = make(i, p, (0, 0, 1), rng)
            out += o if isinstance(o, list) else [o]
            break
    return out


# ---------------- 叶团 / 树冠 ----------------
def _env_r(d, r, r_bot, top_p=2.0):
    """包络沿单位方向 d（E, S, U 分量）的半径：下半 = 椭球（竖直半轴 r_bot），上半 = 超椭球（竖直方向指数 top_p，< 2 顶更尖、> 2 更平）。"""
    if d[2] >= 0:
        h = math.hypot(d[0] / r[0], d[1] / r[1])
        # 沿射线二分 t：(水平分量 / 半轴)² + (竖直 / rU)^p = 1
        lo, hi = 0.0, 4 * max(r)
        for _ in range(40):
            t = (lo + hi) / 2
            if (h * t) ** 2 + (abs(d[2]) * t / r[2]) ** top_p > 1:
                hi = t
            else:
                lo = t
        return lo
    return 1.0 / math.sqrt((d[0] / r[0]) ** 2 + (d[1] / r[1]) ** 2 + (d[2] / r_bot) ** 2)


def lump(name, m, c, r, bumps=5, bump_amp=0.12, bump_w=0.55, seed=0, sub=3, flat_u=None, flat_k=0.3, uv_out=None, r_down=None):
    """一个圆鼓叶团：c = (E, S, U) 中心，r = 半径（数 = 圆，或 (rE, rS, rU)），表面 bumps 个小鼓包（菜花状，每个鼓包占的角度 ~ bump_w 弧度），
    bump_amp = 鼓包高占半径比例；flat_u = 给了就把低于这个高度的部分往上压（压成 flat_k 倍，底面略平）。sub = 细分级（Blender 的 icosphere：2 → 80、3 → 320 三角形）。
    uv_out = 这团朝外的方向 (E, S, U)：给了就用经纬度 UV（_sphere_uv，接缝藏在朝里那面），不给 = core.box_uv。
    r_down = 下半球的竖直半径（不给 = 同 rU；树冠芯 / 灌木圆顶上下不对称时用）。"""
    rng = random.Random(seed)
    rr = (r, r, r) if isinstance(r, (int, float)) else r
    bd = []
    for _ in range(bumps):
        z = rng.uniform(-0.6, 1.0)
        a = rng.uniform(0, 2 * math.pi)
        q = math.sqrt(1 - z * z)
        bd.append(Vector((q * math.cos(a), q * math.sin(a), z)))
    cw = math.cos(bump_w)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1)
    o = P(*c)
    unit = []
    for vt in bm.verts:
        nn = vt.co.normalized()
        unit.append(nn.copy())
        k = 1.0
        if bd:
            s = max(max(0.0, (nn.dot(b) - cw) / (1 - cw)) for b in bd)
            k += bump_amp * math.sqrt(s)
        x, y, z = nn * k
        rz = rr[2] if (z >= 0 or r_down is None) else r_down
        p = o + Vector((x * rr[0] * K, y * rr[1] * K, z * rz * K))
        if flat_u is not None and p.z < flat_u * K:
            p.z = flat_u * K - (flat_u * K - p.z) * flat_k
        vt.co = p
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = new_obj(name, bm, m)
    if uv_out is not None:
        _sphere_uv(ob, unit, D(*uv_out), sum(rr) / 3, m)
    return smooth(ob)


def _sphere_uv(ob, unit, out, R, m):
    """叶团的经纬度 UV（代替 box_uv：box_uv 在法线换投影方向处有一道道接缝，第 1 轮打光图里叶团正中看得到竖线）。
    极轴 = out × 游戏机位方向（CAM，正面俯 36.87°）→ 两个极点（贴图收成一点）落在游戏机位看过去的轮廓边上；经线接缝在 −out（朝树冠里面）。
    第 2 轮用的是 out × 竖直：两侧叶团的极点正对正面，仰看 / 平视看得到一个放射状的收点。
    unit[顶点] = 变形前单位球上的方向；R = 平均半径（厘米），贴图按 m['tile'] 厘米一张。"""
    out = out.normalized()
    pa = out.cross(D(*CAM).normalized())
    if pa.length < 0.2:
        pa = out.cross(Vector((0, 0, 1)))
    if pa.length < 0.2:
        pa = Vector((1, 0, 0))
    pa.normalize()
    e2 = (out - pa * out.dot(pa)).normalized()
    e3 = pa.cross(e2)
    tw, th = m.get('tile') or (32, 32)
    me = ob.data
    uvl = me.uv_layers['UV']
    for poly in me.polygons:
        vs = [me.loops[li].vertex_index for li in poly.loop_indices]
        lat = [math.asin(max(-1.0, min(1.0, unit[i].dot(pa)))) for i in vs]
        lon = [math.atan2(unit[i].dot(e3), unit[i].dot(e2)) for i in vs]
        if max(lon) - min(lon) > math.pi:
            lon = [x + 2 * math.pi if x < 0 else x for x in lon]
        for li, la, lo in zip(poly.loop_indices, lat, lon):
            uvl.data[li].uv = (lo * R / tw, la * R / th)


def canopy_cluster(name, m, c, r, r_bot=None, n=12, seed=0, lump_r=(0.40, 0.55), squash=0.85, bumps=5, bump_amp=0.12,
                   core=0.8, flat=0.3, zmin=-0.45, sub=3, lumps=None, top_p=2.0, core_drop=None, bump_w=0.55):
    """阔叶树冠：包络椭球（中心 c = (E, S, U)、半轴 r = (rE, rS, rU 上半)、r_bot = 下半竖直半轴，默认 rU × 0.5 = 底面扁）里摆 n 个叶团。
    top_p = 上半竖直方向的超椭球指数（2 = 椭球；1.6–1.8 顶更收、像圆顶；见 _env_r）。
    摆法：n 个方向按斐波那契球面均匀铺在竖直分量 ≥ zmin 的那部分（整体随机转一个角、每个方向抖一点），每个叶团半径 =
    平均半轴 × uniform(lump_r)，球心从包络面沿方向往里收 0.85 个叶团半径（叶团外沿略鼓出包络）；竖直方向压成 squash 倍。
    zmin 取 −0.3 ~ −0.5：朝下的叶团都在外圈（水平分量 ≥ 0.87），正下方不放叶团，树干 / 主枝从叶团圈中间露出来。
    芯 = 包络 × core 的椭球（叶团之间就算有缝也透不了光）；core_drop 给了，芯的底压平在 c.U − r_bot × core_drop（比外圈叶团高 = 底面中间凹进去）。
    底面：叶团低于 c.U − r_bot × (1 − flat) 的顶点往上压成 0.3 倍（底面略平）。
    lumps = [(E, S, U, 半径), …] 给了就不随机、按给的摆（照参考图逐团摆时用）。
    每个叶团 bumps 个小鼓包（lump()）。返回 [芯, 叶团 …]（名字 <name>_core、<name>_00 …）。三角形：(n + 1) × 320（sub = 3）。"""
    rng = random.Random(seed)
    r_bot = r[2] * 0.5 if r_bot is None else r_bot
    flat_u = c[2] - r_bot * (1 - flat)
    mean = (r[0] + r[1] + r[2]) / 3
    core_u = flat_u if core_drop is None else c[2] - r_bot * core_drop
    out = [lump(f"{name}_core", m, c, (r[0] * core, r[1] * core, r[2] * core), bumps=0, sub=sub, flat_u=core_u, r_down=r_bot * core,
                uv_out=(0, 1, 0))]
    if lumps is None:
        lumps = []
        rot = rng.uniform(0, 2 * math.pi)
        ga = math.pi * (3 - math.sqrt(5))
        for i in range(n):
            z = 1 - (i + 0.5) / n * (1 - zmin)
            z = max(-1.0, min(1.0, z + rng.uniform(-0.06, 0.06)))
            a = rot + i * ga + rng.uniform(-0.25, 0.25)
            q = math.sqrt(max(0.0, 1 - z * z))
            d = (q * math.sin(a), q * math.cos(a), z)
            R = _env_r(d, r, r_bot, top_p)
            rl = mean * rng.uniform(*lump_r)
            k = R - rl * 0.85
            lumps.append((c[0] + d[0] * k, c[1] + d[1] * k, c[2] + d[2] * k, rl))
    for i, (e, s, u, rl) in enumerate(lumps):
        out.append(lump(f'{name}_{i:02d}', m, (e, s, u), (rl, rl, rl * squash), bumps=bumps, bump_amp=bump_amp, bump_w=bump_w,
                        seed=rng.randrange(1 << 30), sub=sub, flat_u=flat_u,
                        uv_out=(e - c[0], s - c[1], u - c[2] + 1e-3)))
    return out


# ---------------- 圆鼓叶簇树冠（2026-10-23 新做法）----------------
#   用户看了橡树 / 圆灌木的自评后说"改一改"：参考四视图（橡树 / 苹果 / 秋枫 / 柳树 / 灌木）的树冠是一团团圆鼓鼓的叶簇叠起来，
#   簇和簇之间有明暗、轮廓凹凸；旧做法（canopy_cluster：光滑芯 + 外面贴扁平叶片）像贴了贴纸的球，树冠底面压太低盖住树干。
#   新做法：5–12 个独立叶簇（puff_cluster），部分重叠，不要大芯；每簇几档深浅材质槽，按面分明暗（shade_faces）。
#   用法（照参考逐簇摆）：
#       S3 = veg.shade_mats(V['leaf'])                                  # [明, 中, 暗] 三个材质
#       puffs = [(E, S, U, r), …] 或 (E, S, U, r, squash)               # 簇中心 + 半径（厘米），从四视图量；或 veg.puff_layout(...)
#       cs = veg.canopy_puffs('canopy', S3, puffs, seed=3, occluders=[树干, 主枝…])
#       veg.puff_leaves('leaf', cs, [浅叶材质…], 14, size=46, shape='oak', seed=5)     # 可选
#   主枝末端要伸进某个簇的中心（branch(a, (簇 E, S, U), …)），树冠底面（最低簇的底）抬到参考里分叉以上。
def _lin2srgb(c):
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def shade_mats(m, tints=(1.0, 0.74, 0.52), hue=(0.96, 1.0, 1.08)):
    """一块材质 → len(tints) 档深浅的材质列表（第 0 档 = 原材质，往后越来越暗）。
    贴图材质（ext_mat 建的）：按 tint 乘像素出新贴图（材质名 <原名>_s<k>，'tile' 同原材质）；纯色材质：线性底色乘 tint。
    hue = 暗档额外乘的 (R, G, B)（按暗的程度插值：暗面略偏冷，参考图簇底是偏蓝的深绿）。"""
    out = [m]
    img = None
    if m.node_tree:
        for nd in m.node_tree.nodes:
            if nd.type == 'TEX_IMAGE' and nd.image is not None:
                img = nd.image
    for k, t in enumerate(tints[1:], 1):
        f = (1 - t) / max(1e-6, 1 - min(tints))           # 0 = 最亮、1 = 最暗档
        mul = [t * (1 + (h - 1) * f) for h in hue]
        name = f'{m.name}_s{k}'
        if name in bpy.data.materials:
            out.append(bpy.data.materials[name])
            continue
        if img is not None:
            w, h_ = img.size
            a = np.empty(w * h_ * 4, np.float32)
            img.pixels.foreach_get(a)
            a = a.reshape(-1, 4)
            a[:, :3] = np.clip(a[:, :3] * np.array(mul, np.float32), 0, 1)
            im2 = bpy.data.images.new(f'{img.name}_s{k}', w, h_, alpha=False)
            im2.pixels.foreach_set(a.ravel())
            im2.pack()
            mm = materials.mat(name, tex=im2)
        else:
            bc = m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value
            lin = [bc[i] * mul[i] for i in range(3)]
            srgb_on = getattr(materials, 'SRGB_COLORS', False)
            mm = materials.mat(name, color=[_lin2srgb(x) for x in lin] if srgb_on else lin)
        if m.get('tile'):
            mm['tile'] = tuple(m['tile'])
        out.append(mm)
    return out


# 半球方向（局部 z = 法线），余弦分布，固定 16 条：环境遮挡用
_HEMI = []
for _i in range(16):
    _z = math.sqrt(1 - (_i + 0.5) / 16)
    _a = _i * math.pi * (3 - math.sqrt(5))
    _q = math.sqrt(max(0.0, 1 - _z * _z))
    _HEMI.append(Vector((_q * math.cos(_a), _q * math.sin(_a), _z)))


def _occl(tree, p, n, dist):
    """p（Blender）沿外法线 n 的半球里 16 条射线，dist（Blender 单位）内打中的比例 0–1。"""
    u, v, d = _frame(n)
    o = p + n * 0.004
    hit = 0
    for h in _HEMI:
        dd = u * h.x + v * h.y + d * h.z
        if tree.ray_cast(o, dd, dist)[0] is not None:
            hit += 1
    return hit / len(_HEMI)


def shade_at(tree, p, n, dist=60.0, w_down=0.55, w_ao=0.75, crease=0.0, w_crease=0.0):
    """单点暗度 0（亮）– 1（暗）：p / n = (E, S, U) 厘米 / 外法线；tree = 遮挡物的 BVHTree；dist = 遮挡射线长（厘米）。
    = w_down × 法线朝下程度（max(0, −nU)）+ w_ao × 半球被挡的比例 + w_crease × crease（鼓包沟 0–1），截到 0–1。"""
    nb = D(*n).normalized()
    v = w_down * max(0.0, -nb.z) + w_ao * _occl(tree, P(*p), nb, dist * K) + w_crease * crease
    return max(0.0, min(1.0, v))


def shade_faces(objs, tree=None, dist=60.0, w_down=0.55, w_ao=0.75, w_crease=0.45, cuts=(0.30, 0.55), bias=None):
    """给一组网格按面分明暗档：每个网格的材质槽 = [明, 中, 暗 …]（shade_mats 出的），面的暗度 = shade_at（面中心、面法线）
    + 鼓包沟（网格上有 'puff_k' 点属性时：面三个顶点的鼓包高度 0–1，沟 = 1 − 高度），按 cuts 分档（暗度 < cuts[0] → 槽 0 …）。
    tree = 遮挡物 BVHTree（不给 = objs 自己；簇和簇互相挡出簇间的暗）；bias = {物体名: 加到暗度上的数}（个别簇整体压暗 / 提亮）。
    返回每档面数。"""
    tree = tree or _bvh(objs)
    cnt = [0] * (len(cuts) + 1)
    for o in objs:
        me = o.data
        mw = o.matrix_world
        nm = mw.to_3x3().inverted().transposed()
        kat = me.attributes.get('puff_k')
        b = (bias or {}).get(o.name, 0.0)
        nslot = len(me.materials)
        for poly in me.polygons:
            p = mw @ poly.center
            n = (nm @ poly.normal).normalized()
            cr = 0.0
            if kat is not None:
                cr = 1.0 - sum(kat.data[i].value for i in poly.vertices) / len(poly.vertices)
            v = w_down * max(0.0, -n.z) + w_ao * _occl(tree, p, n, dist * K) + w_crease * cr + b
            k = sum(1 for c in cuts if v >= c)
            k = min(k, nslot - 1)
            poly.material_index = k
            cnt[k] += 1
    return cnt


def vcol_mat(m, attr='Col'):
    """材质 m 的"乘顶点色"版（名字 <原名>_vc，同名只建一次）：底色（贴图或纯色）× 点属性 attr（Color Attribute 节点 + Mix 乘）。
    glTF 导出成 COLOR_0（规范里 COLOR_0 乘 baseColor；three.js GLTFLoader 自动开 vertexColors），Blender 导回来也接上。
    叶簇明暗默认走这个（shade_verts）：材质槽分档（shade_faces）在面边界上是一块块三角形锯齿（2026-10-23 第 1 版打光图）。"""
    name = f'{m.name}_vc'
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mm = m.copy()
    mm.name = name
    nt = mm.node_tree
    bsdf = nt.nodes['Principled BSDF']
    vc = nt.nodes.new('ShaderNodeVertexColor')
    vc.layer_name = attr
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1.0
    src = bsdf.inputs['Base Color'].links[0].from_socket if bsdf.inputs['Base Color'].is_linked else None
    if src is not None:
        nt.links.new(src, mix.inputs['A'])
    else:
        mix.inputs['A'].default_value = tuple(bsdf.inputs['Base Color'].default_value)
    nt.links.new(vc.outputs['Color'], mix.inputs['B'])
    nt.links.new(mix.outputs['Result'], bsdf.inputs['Base Color'])
    if m.get('tile'):
        mm['tile'] = tuple(m['tile'])
    return mm


def shade_verts(objs, tree=None, dist=60.0, w_down=0.55, w_ao=0.75, w_crease=0.45, dark=(0.30, 0.36, 0.40), gamma=1.0,
                blur=2, attr='Col', bias=None):
    """给一组网格写顶点色明暗（点属性 attr，FLOAT_COLOR，线性值）：每个顶点暗度 v = w_down × 法线朝下程度 + w_ao × 半球被挡比例
    （射线长 dist 厘米，打 tree：不给 = objs 自己）+ w_crease × 鼓包沟（有 'puff_k' 属性时 1 − 鼓包高度），截到 0–1，
    再和相邻顶点平均 blur 次（边界不出锯齿）；颜色 = 1 − v^gamma × (1 − dark)（dark = 最暗处乘的 (R, G, B)，偏冷）。
    材质要用 vcol_mat(…) 版才看得到。bias = {物体名: 加到暗度上的数}。返回每个网格的平均暗度。"""
    tree = tree or _bvh(objs)
    res = {}
    for o in objs:
        me = o.data
        mw = o.matrix_world
        nm = mw.to_3x3().inverted().transposed()
        kat = me.attributes.get('puff_k')
        b = (bias or {}).get(o.name, 0.0)
        vals = []
        for vt in me.vertices:
            p = mw @ vt.co
            n = (nm @ vt.normal).normalized()
            cr = (1.0 - kat.data[vt.index].value) if kat is not None else 0.0
            v = w_down * max(0.0, -n.z) + w_ao * _occl(tree, p, n, dist * K) + w_crease * cr + b
            vals.append(max(0.0, min(1.0, v)))
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
            ca.data[i].color = (1 - f * (1 - dark[0]), 1 - f * (1 - dark[1]), 1 - f * (1 - dark[2]), 1.0)
        me.color_attributes.active_color = ca
        res[o.name] = sum(vals) / max(1, len(vals))
    return res


def puff_cluster(name, mats, c, r, squash=0.85, bumps=16, bump_amp=0.16, bump_w=0.42, bump_zmin=-0.45, sub=4, seed=0,
                 flat_u=None, flat_k=0.35, uv_out=None, wobble=0.04):
    """一个独立的圆鼓叶簇（闭合、法线朝外、平滑着色）：c = (E, S, U) 簇中心，r = 半径（厘米），竖直方向压成 squash 倍。
    表面 bumps 个菜花状小鼓包：方向按斐波那契球面铺在竖直分量 ≥ bump_zmin 的那部分（簇底少鼓包、圆滑），每个鼓包是角半径
    bump_w × uniform(0.8, 1.2) 弧度的圆帽，高 bump_amp × 半径；多个鼓包取最大 → 鼓包之间是一道道沟（轮廓凹凸起伏）。
    wobble = 整簇低频起伏（簇不是正球）。flat_u = 低于这个高度（厘米）的顶点往上压成 flat_k 倍（簇底略平）。
    mats = 一个材质或 [明, 中, 暗 …] 列表（shade_mats）；面先全用第 0 档，canopy_puffs / shade_faces 再分档。
    uv_out = 这簇朝外的方向 (E, S, U)（经纬度 UV、接缝藏在朝里那面，同 lump）；不给 = 竖直。
    网格上写点属性 'puff_k'（鼓包高度 0–1，shade_faces 拿来压暗沟）。三角形 = 20 × 4^(sub − 1)：sub 4 → 1280、3 → 320。"""
    rng = random.Random(seed)
    bd = []
    ga = math.pi * (3 - math.sqrt(5))
    rot = rng.uniform(0, 2 * math.pi)
    for i in range(bumps):
        z = 1 - (i + 0.5) / bumps * (1 - bump_zmin) + rng.uniform(-0.05, 0.05)
        z = max(-1.0, min(1.0, z))
        a = rot + i * ga + rng.uniform(-0.3, 0.3)
        q = math.sqrt(max(0.0, 1 - z * z))
        w = bump_w * rng.uniform(0.8, 1.2)
        bd.append((Vector((q * math.cos(a), q * math.sin(a), z)), w, rng.uniform(0.75, 1.15)))
    wv = [(Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))).normalized(), rng.uniform(0, 6.28)) for _ in range(3)]
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1)
    o = P(*c)
    unit, ks = [], []
    for vt in bm.verts:
        nn = vt.co.normalized()
        unit.append(nn.copy())
        s = 0.0
        for b, w, amp in bd:
            ang = math.acos(max(-1.0, min(1.0, nn.dot(b))))
            if ang < w:
                s = max(s, amp * math.sqrt(1 - (ang / w) ** 2))      # 圆帽剖面：鼓包顶圆、边上陡（沟清楚）
        ks.append(min(1.0, s))
        k = 1.0 + bump_amp * s + wobble * sum(math.sin(3 * nn.dot(d) + ph) for d, ph in wv) / 3
        x, y, z = nn * k
        p = o + Vector((x * r * K, y * r * K, z * r * squash * K))
        if flat_u is not None and p.z < flat_u * K:
            p.z = flat_u * K - (flat_u * K - p.z) * flat_k
        vt.co = p
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = new_obj(name, bm, mats)
    m0 = mats[0] if isinstance(mats, list) else mats
    _sphere_uv(ob, unit, D(*(uv_out or (0, 0, 1))), r, m0)
    at = ob.data.attributes.new('puff_k', 'FLOAT', 'POINT')
    for i, kv in enumerate(ks):
        at.data[i].value = kv
    return smooth(ob)


def puff_layout(c, r, r_bot=None, n=8, seed=0, lump_r=(0.42, 0.58), zmin=-0.35, top_p=1.8, inset=0.9):
    """按包络自动排 n 个叶簇：返回 [(E, S, U, 半径), …]。包络 / 斐波那契铺法同 canopy_cluster（c = 中心，r = (rE, rS, rU 上半)，
    r_bot = 下半竖直半轴，默认 rU × 0.5），每簇半径 = 平均半轴 × uniform(lump_r)，簇心从包络面往里收 inset 个簇半径。
    n 少（5–12）时簇大、互相重叠多；zmin 越大簇越集中在上半（树冠底面越高、露出越多树干）。"""
    rng = random.Random(seed)
    r_bot = r[2] * 0.5 if r_bot is None else r_bot
    mean = (r[0] + r[1] + r[2]) / 3
    rot = rng.uniform(0, 2 * math.pi)
    ga = math.pi * (3 - math.sqrt(5))
    out = []
    for i in range(n):
        z = 1 - (i + 0.5) / n * (1 - zmin)
        z = max(-1.0, min(1.0, z + rng.uniform(-0.06, 0.06)))
        a = rot + i * ga + rng.uniform(-0.25, 0.25)
        q = math.sqrt(max(0.0, 1 - z * z))
        d = (q * math.sin(a), q * math.cos(a), z)
        R = _env_r(d, r, r_bot, top_p)
        rl = mean * rng.uniform(*lump_r)
        k = max(0.0, R - rl * inset)
        out.append((c[0] + d[0] * k, c[1] + d[1] * k, c[2] + d[2] * k, rl))
    return out


def canopy_puffs(name, mats, puffs, seed=0, squash=0.85, bumps=None, bump_amp=0.16, bump_w=None, sub=4, small_r=0, small_sub=3,
                 plug=None, plug_m=None, occluders=(), shade=None, flat=None, mode='vcol'):
    """阔叶树冠 = 按 puffs 摆的独立叶簇（puff_cluster），最后按面分明暗。
    puffs = [(E, S, U, 半径) 或 (E, S, U, 半径, squash), …]（厘米；照四视图逐簇量，或 puff_layout 自动排）；簇要和邻簇部分重叠
    （中心距 < 两半径和 × 0.8，否则簇间透光）。mats = [明, 中, 暗 …]（shade_mats）。
    bumps = 每簇鼓包数（不给 = 半径 / 3.5，截到 12–26 个）；bump_w = 鼓包角半径（不给 = 按鼓包数算，铺满上半）。
    sub = 细分级；半径 < small_r 的簇用 small_sub（省面）。flat = 簇底压平的比例（给了：每簇低于 中心 − 半径 × squash × flat 的部分压扁）。
    plug = (E, S, U, rE, rS, rU) 给了就在里面加一个暗色椭球（plug_m，默认最暗档）堵住簇间缝、看不到穿过树冠的背景；不当表面用。
    occluders = 别的挡光物（树干、主枝）参与明暗射线。
    mode = 'vcol'（默认）：mats 取第一个材质，换成 vcol_mat 版，shade_verts 写顶点色（平滑过渡）；shade = shade_verts 的参数
    （dist / w_down / w_ao / w_crease / dark / gamma / blur）；plug 默认 = 叶材质 × 0.3 的纯暗档。
    mode = 'slots'：mats = [明, 中, 暗 …]（shade_mats），shade_faces 按面分档（shade = dist / w_down / w_ao / w_crease / cuts）；
    面边界是三角形锯齿，只在看不到顶点色的地方用。
    返回叶簇物体列表（名字 <name>_00 …；plug 在最后，名字 <name>_plug）。"""
    rng = random.Random(seed)
    mats = mats if isinstance(mats, list) else [mats]
    if mode == 'vcol':
        if plug is not None and plug_m is None:
            plug_m = shade_mats(mats[0], tints=(1.0, 0.3))[1]
        mats = [vcol_mat(mats[0])]
    cx = sum(p[0] for p in puffs) / len(puffs)
    cy = sum(p[1] for p in puffs) / len(puffs)
    cz = sum(p[2] for p in puffs) / len(puffs)
    out = []
    for i, pf in enumerate(puffs):
        e, s, u, rr = pf[:4]
        sq = pf[4] if len(pf) > 4 else squash
        nb = bumps or int(max(12, min(26, rr / 3.5)))
        bw = bump_w or math.sqrt(2 * math.pi * 1.45 / nb) * 0.62     # 鼓包占上 1.45 球面度 / 个数 → 角半径（略有重叠）
        sb = small_sub if rr < small_r else sub
        fu = (u - rr * sq * flat) if flat is not None else None
        out.append(puff_cluster(f'{name}_{i:02d}', mats, (e, s, u), rr, squash=sq, bumps=nb, bump_amp=bump_amp, bump_w=bw,
                                sub=sb, seed=rng.randrange(1 << 30), flat_u=fu,
                                uv_out=(e - cx, s - cy, u - cz + 1e-3)))
    pl = None
    if plug is not None:
        e, s, u, a, b, c_ = plug
        pl = lump(f'{name}_plug', plug_m or mats[-1], (e, s, u), (a, b, c_), bumps=0, sub=3)
    sh = dict(shade or {})
    tree = _bvh(out + ([pl] if pl else []) + list(occluders))
    if mode == 'vcol':
        shade_verts(out, tree=tree, **sh)
    else:
        shade_faces(out, tree=tree, **sh)
    if pl is not None:
        out.append(pl)
    return out


def puff_leaves(name, puffs, mats, n, size=40, shape='oak', seed=0, up=(-0.3, 0.9), min_dist=None, thick=2.5, seg=20, lift=0.5,
                center=None, rim=0.35, tree=None, dist=60.0, conform=True, cup_r=80.0, sink=1.5, max_push=0.3):
    """叶簇边缘少量点缀叶片：在 puffs（叶簇物体）最外层表面散 n 片叶（scatter_on），rim = 法线竖直分量上限
    （|nU| ≤ 1 − rim 的点才放 = 只放簇侧边，0 = 不挑）。
    conform = True：叶面每点落到簇表面上方 lift（贴合）；鼓包大（bump_amp ≥ 0.2）时叶子顺着鼓包和沟折成皱巴巴的一团
    （2026-10-23 橡树第 2 版），这时给 False：叶片按半径 cup_r 的球面弯，再整片沿法线推到不被鼓包顶穿（搁在鼓包顶上；第 3 版往里埋 sink 时鼓包把叶顶穿成碎片），叶边下面跨沟处有几厘米空隙；要推出去超过 max_push × 叶长的叶（落在簇间沟里）不放。
    mats = 一个材质或几档（明 → 暗）：按 shade_at 的暗度选档（暗处的叶也暗）。返回叶片列表。"""
    mats = mats if isinstance(mats, list) else [mats]
    tree = tree or _bvh(puffs)

    def mk(i, p, nn, rng):
        if rim and abs(nn[2]) > 1 - rim:
            return []
        v = shade_at(tree, p, nn, dist=dist, w_ao=0.6)
        mm = mats[min(len(mats) - 1, int(v * len(mats) * 1.2))]
        ob = leaf(f'{name}_{i:02d}', mm, p, nn, size=size * rng.uniform(0.85, 1.15), shape=shape, thick=thick,
                  spin=rng.uniform(0, 360), seg=seg, sink=0 if conform else sink, conform=tree if conform else None,
                  lift=lift, cup_r=None if conform else cup_r)
        if not conform:                                 # 搁在鼓包顶上：沿法线找叶片各点被簇表面顶穿的最深处，整片往外推出来
            nb = D(*nn).normalized()
            deep = 0.0
            for v in ob.data.vertices:
                w = ob.matrix_world @ v.co
                loc = tree.ray_cast(w + nb * 60 * K, -nb, 60 * K)[0]
                if loc is not None:
                    deep = max(deep, (loc - w).dot(nb))
            if deep > max_push * size:            # 推得太远 = 叶落在两簇之间的沟里、推出来会悬空：不要这片
                bpy.data.objects.remove(ob)
                return []
            if deep > 0:
                for v in ob.data.vertices:
                    v.co += ob.matrix_world.inverted().to_3x3() @ (nb * (deep + 0.3 * K))
            # 悬空检查：叶片各点沿 −法线 max_push × 叶长内找不到簇表面的超过 30% → 叶伸出簇外（2026-10-23 第 3 版正面一片探出 22 厘米）
            far = 0
            for v in ob.data.vertices:
                w = ob.matrix_world @ v.co
                if tree.ray_cast(w, -nb, max_push * size * K)[0] is None:
                    far += 1
            if far > 0.3 * len(ob.data.vertices):
                bpy.data.objects.remove(ob)
                return []
        return ob
    return scatter_on(puffs, n, mk, seed=seed, center=center, up=up, min_dist=min_dist or size * 0.9)


# ---------------- 针叶层 ----------------
def conifer_tiers(name, m, c=(0, 0), tiers=(), squash_S=1.0, spl=6, rings=7, seed=0, droop=0.35, notch=0.18, lobe_out=0.12,
                  thick=0.22, stagger=True):
    """针叶树：从上往下一层层锥形叶层。tiers = [dict(U=(顶, 下沿), r=(顶半径, 下沿半径), lobes=叶瓣数), …]，第一层顶半径给 0 = 尖顶。
    每层：外表面从顶往下外鼓（凸剖面）到下沿；下沿一圈 lobes 个圆头叶瓣：瓣中心往下垂 droop × 层高 × 0.3、瓣中心往外鼓、瓣间往里收 ±lobe_out/2 × 半径（从层中段往下越来越明显，瓣间成竖槽）；瓣的下沿轮廓是半圆，
    瓣之间往上收 notch × 层高 × 0.3；下沿往里卷一圈再用下表面收回树干（层厚 thick × 层高），顶上封盖——每层是闭合体。
    顶要埋进上一层里（U 顶比上一层下沿高）才不露缝；stagger = 每层叶瓣转半个瓣错开。squash_S = S 方向压扁（侧面比正面窄）。
    spl = 每个叶瓣横向段数，rings = 外表面竖向圈数。返回每层一个物体（<name>_0 … 从上往下）。"""
    rng = random.Random(seed)
    out = []
    for k, t in enumerate(tiers):
        u0, u1 = t['U']
        r0, r1 = t['r']
        r0 = max(r0, 1.0)                               # 尖顶：顶圈收成 1 厘米（不收成一点，免得退化面）
        nl = t.get('lobes', 12)
        H = u0 - u1
        N = nl * spl
        ph = (math.pi / nl if (stagger and k % 2) else 0.0) + rng.uniform(-0.1, 0.1)
        jit = [rng.uniform(0.75, 1.15) for _ in range(nl)]
        bm = bmesh.new()
        rows = []
        prof = []                                       # (t, 半径系数, 高度)
        for j in range(rings + 1):
            s = j / rings
            prof.append(s)

        def lobe(th):
            x = (th - ph) * nl / (2 * math.pi)
            i = int(math.floor(x + 0.5)) % nl
            f = x - math.floor(x + 0.5)                 # −0.5 … 0.5，0 = 瓣中心
            return math.sqrt(max(0.0, 1 - (2 * f) ** 2)), jit[i]     # 半圆：瓣尖圆、瓣间是尖凹口（第 1 轮 cos^0.7 + 每瓣 4 段，瓣尖是尖的）
        # 外表面
        for s in prof:
            row = []
            for i in range(N):
                th = 2 * math.pi * i / N
                lv, jj = lobe(th)
                rad = r0 + (r1 - r0) * (1 - (1 - s) ** 1.5)
                rad *= 1 + lobe_out * (lv - 0.5) * s ** 1.5     # 下半段就分成一瓣瓣（瓣间有竖向凹槽），不只是下沿一圈
                uu = u0 - H * s - (droop * jj * lv - notch * (1 - lv)) * H * 0.3 * s ** 3
                row.append(P(c[0] + rad * math.sin(th), c[1] + rad * math.cos(th) * squash_S, uu))
            rows.append(row)
        # 下沿往里卷 + 下表面
        last = rows[-1]
        under = [(0.93, 0.35), (0.75, 1.0), (0.45, 1.8)]
        for fr, du in under:
            row = []
            for i in range(N):
                th = 2 * math.pi * i / N
                q = last[i]
                ce = P(c[0], c[1], 0)
                hv = Vector((q.x - ce.x, q.y - ce.y, 0)) * fr
                row.append(Vector((ce.x + hv.x, ce.y + hv.y, q.z + du * thick * H * K)))
            rows.append(row)
        vv = [[bm.verts.new(p) for p in row] for row in rows]
        for j in range(len(vv) - 1):
            for i in range(N):
                bm.faces.new((vv[j][i], vv[j][(i + 1) % N], vv[j + 1][(i + 1) % N], vv[j + 1][i]))
        top = bm.verts.new(P(c[0], c[1], u0 + (0 if r0 <= 0 else 1)))
        for i in range(N):
            bm.faces.new((top, vv[0][(i + 1) % N], vv[0][i]))
        bot = bm.verts.new(P(c[0], c[1], rows[-1][0].z / K + thick * H))
        for i in range(N):
            bm.faces.new((bot, vv[-1][i], vv[-1][(i + 1) % N]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        ob = new_obj(f'{name}_{k}', bm, m)
        # 柱面 UV（绕一圈 = u、高度 = v），同 trunk：顶点顺序 = 各圈依次 + 顶心 + 底心
        tw = (m.get('tile') or (32, 32))[0]
        reps = max(1, round(2 * math.pi * r1 / tw))
        uvw = [(i / N, rows[j][i].z / K, reps) for j in range(len(rows)) for i in range(N)]
        uvw += [(0.0, u0, reps), (0.0, rows[-1][0].z / K, reps)]
        _tube_uv(ob, uvw, m.get('tile') or (32, 32))
        out.append(smooth(ob))
    return out


# ---------------- 叶片 ----------------
def _outline(shape, size, seg):
    """叶片轮廓（局部 2D：x = 叶尖方向，y = 横向），返回 (点列表, 中心点)。'trefoil' / 'round' 的原点 = 叶柄处，'oak' 原点 = 叶中心。"""
    pts = []
    if shape == 'oak':
        # 长椭圆 + 5 个圆裂片（|cos(2.5φ)|：叶尖一个、两边各 2 个，叶柄处凹进）；seg 取 20（每裂片 4 点：峰、两腰、谷）。
        # 第 2 轮 7 裂片 seg 21 每裂片只有 3 点、采不到谷，出来是圆片
        a, b = size / 2, size * 0.34
        for i in range(seg):
            ph = 2 * math.pi * i / seg
            base = 1 / math.sqrt((math.cos(ph) / a) ** 2 + (math.sin(ph) / b) ** 2)
            rr = base * (0.62 + 0.42 * abs(math.cos(2.5 * ph)) ** 0.7)
            pts.append((rr * math.cos(ph), rr * math.sin(ph)))
        return pts, (0.0, 0.0)
    if shape == 'round':
        a, b = size / 2, size * 0.3
        for i in range(seg):
            ph = 2 * math.pi * i / seg
            pts.append((a + a * math.cos(ph), b * math.sin(ph)))
        return pts, (a, 0.0)
    # trefoil：三个椭圆裂片的并集（裂片中心在叶柄前 0.36 size、±52°，沿径向半轴 0.30、横向 0.19 size → 叶宽 ≈ size、叶长 ≈ 0.66 size）。
    # 按极角分段取点：每个裂片从凹口到凹口（外侧到切线方向）均匀取 seg // 3 个点，叶柄处 2 个点。
    # 第 1 版圆裂片 + 极角均匀取 14 点：采不到凹口（锯齿多边形），叶长只有 0.59 size（比四视图的叶短胖）。
    d0, ra, rb, g = size * 0.36, size * 0.30, size * 0.19, 52.0
    m = max(3, seg // 3)

    def far(ph):
        best = -1.0
        for gk in (-g, 0.0, g):
            q = ph - math.radians(gk)
            ux, uy = math.cos(q), math.sin(q)
            A = (ux / ra) ** 2 + (uy / rb) ** 2
            B = -2 * d0 * ux / ra ** 2
            C = (d0 / ra) ** 2 - 1
            disc = B * B - 4 * A * C
            if disc >= 0:
                best = max(best, (-B + math.sqrt(disc)) / (2 * A))
        return best
    tang = g
    while far(math.radians(tang + 0.5)) > 0:
        tang += 0.5
    for lo_, hi_ in ((-tang, -g / 2), (-g / 2, g / 2), (g / 2, tang)):
        for k in range(m):
            ph = math.radians(lo_ + (hi_ - lo_) * k / m)
            rr = far(ph)
            pts.append((rr * math.cos(ph), rr * math.sin(ph)))
    ph = math.radians(tang)
    rr = far(ph)
    pts.append((rr * math.cos(ph), rr * math.sin(ph)))
    pts += [(-size * 0.03, size * 0.04), (-size * 0.03, -size * 0.04)]
    return pts, (d0, 0.0)


def leaf(name, m, p, n, axis=None, size=30, shape='oak', thick=2.0, cup_r=None, tilt=0.0, sink=0.5, seg=16, spin=0.0,
         conform=None, lift=0.4, lift_tip=0.0):
    """单片叶（闭合薄片：上下两面 + 一圈侧边，中间厚 thick、边上一半厚）。
    p = 附着点 (E, S, U)（'oak' 是叶中心，'trefoil' / 'round' 是叶柄处），n = 表面外法线 (E, S, U)，axis = 叶尖朝向（会投到切平面；
    不给 = 随机 / 按 spin 度转）；size = 叶长（厘米）；cup_r = 按半径 cup_r 的球面弯下去贴合曲面（不给 = 平）；
    tilt = 叶尖往外翘的角度（度，灌木瓦片式铺叶用）；sink = 整片沿法线往里埋的厘米数（贴紧不悬空）。
    conform = 物体列表或 BVHTree：给了就让叶面每个点沿法线落到这个表面上方 lift 厘米（贴在叶团表面的贴片叶用——
    第 1 轮橡叶平放 + cup_r，叶团鼓包把叶子顶穿、只露碎片；conform 后不埋不悬空）；落不到表面的点退回 cup_r 弯法。
    lift_tip = conform 时叶尖比叶柄多抬的厘米数（按沿叶长的距离线性加）：灌木叶一片压一片的瓦片感，又不翘成一层层平台。
    材质 UV 按叶面局部平面投（贴图 tile 厘米一张）。三角形 = 4 × seg。"""
    nb = D(*n).normalized()
    if axis is None:
        a = Vector((math.cos(math.radians(spin)), math.sin(math.radians(spin)), 0))
    else:
        a = D(*axis)
    a = (a - nb * a.dot(nb))
    if a.length < 1e-6:
        a = _frame(nb)[0]
    a.normalize()
    if tilt:
        t = math.radians(tilt)
        a, nb = (a * math.cos(t) + nb * math.sin(t)).normalized(), (nb * math.cos(t) - a * math.sin(t)).normalized()
    y = nb.cross(a).normalized()
    pts, ctr = _outline(shape, size, seg)
    o = P(*p) - nb * sink * K
    bm = bmesh.new()
    tree = None
    if conform is not None:
        tree = conform if isinstance(conform, BVHTree) else _bvh(conform)

    def at(x, yy, dz):
        b = o + (a * x + y * yy) * K
        if tree is not None:                            # 贴合：每个点沿法线往下找表面，放在表面上方 lift（叶团鼓包不会把叶子顶穿）
            loc, _, _, _ = tree.ray_cast(b + nb * 40 * K, -nb, 60 * K)
            if loc is None:                             # 沿法线打不到（贴地那圈、表面边上）：取最近的表面点，不退回平面（第 3 版灌木底下一圈尖刺）
                loc = tree.find_nearest(b)[0]
            if loc is not None:
                return loc + nb * (lift + lift_tip * max(0.0, x) / size + thick / 2 + dz) * K
        dd = math.hypot(x - ctr[0], yy - ctr[1])
        bend = (dd * dd / (2 * cup_r)) if cup_r else 0.0
        return b + nb * (dz - bend) * K
    cx = sum(q[0] for q in pts) / len(pts)
    cy = sum(q[1] for q in pts) / len(pts)
    t_top = bm.verts.new(at(cx, cy, thick / 2))
    t_bot = bm.verts.new(at(cx, cy, -thick / 2))
    top = [bm.verts.new(at(x, yy, thick / 4)) for x, yy in pts]
    bot = [bm.verts.new(at(x, yy, -thick / 4)) for x, yy in pts]
    N = len(pts)
    for i in range(N):
        j = (i + 1) % N
        bm.faces.new((t_top, top[i], top[j]))
        bm.faces.new((t_bot, bot[j], bot[i]))
        bm.faces.new((top[i], bot[i], bot[j], top[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = new_obj(name, bm, m)
    tw, th = m.get('tile') or (32, 32)
    me = ob.data
    uvl = me.uv_layers['UV']
    for poly in me.polygons:
        for li in poly.loop_indices:
            q = (me.vertices[me.loops[li].vertex_index].co - o) / K
            uvl.data[li].uv = (q.dot(a) / tw, q.dot(y) / th)
    return smooth(ob, angle=50)


# ---------------- 灌木 ----------------
def bush(name, m, c=(0, 0), r=(60, 55, 60), h=None, n=7, seed=0, leaves=0, leaf_m=None, leaf_size=30, leaf_shape='trefoil',
         leaf_tilt=0, leaf_up=(-0.35, 1.0), lump_r=(0.45, 0.6), core=0.85, flat=0.15, sub=3, leaf_lift=(0.3, 2.5), leaf_lift_tip=6.0,
         leaf_seg=18):
    """灌木 = 贴地的小号叶团组合。c = (E, S) 地面中心，r = (rE, rS, rU) 包络半轴，h = 总高（默认 rU × 1.6）；
    包络中心在 U = h − rU、下半竖直半轴 = h − rU（底面压平贴地，最低点 ≈ 0）。n 个叶团、core 芯、seed 同 canopy_cluster。
    leaves > 0 时再在外表面铺 leaves 片叶（scatter_on）：每片叶柄在表面点、叶尖顺坡朝下（瓦片式），叶面贴着叶团（conform），
    离表面 uniform(leaf_lift) 厘米（每片不同，叠在一起不共面闪烁）、叶尖再抬 leaf_lift_tip；leaf_tilt = 额外往外翘的角度（默认 0：
    第 1 版翘 18° 不贴合，叶片在上半圈伸成一层层平台）；
    leaf_m = 一个材质或几档深浅的列表（按高度从下往上选：下深上浅）；leaf_up = 射线方向竖直分量范围（不往贴地的底面铺）。
    返回 (叶团列表, 叶片列表)。"""
    h = r[2] * 1.6 if h is None else h
    cu = h - r[2]
    lumps = canopy_cluster(name, m, (c[0], c[1], cu), r, r_bot=cu, n=n, seed=seed, lump_r=lump_r, core=core, flat=flat,
                           zmin=-0.5, sub=sub, bumps=3, bump_amp=0.08)
    for o in lumps:                                     # 低于地面的顶点抬到地面（贴地、不穿地）
        for v in o.data.vertices:
            if v.co.z < 0:
                v.co.z = 0.0
    lv = []
    if leaves:
        mats = leaf_m if isinstance(leaf_m, list) else [leaf_m]

        def mk(i, p, nn, rng):
            nb = D(*nn)
            down = Vector((0, 0, -1)) - nb * (-nb.z)
            if down.length < 0.3:                       # 顶上：叶尖朝外（水平径向）
                down = Vector((-(p[0] - c[0]), p[1] - c[1], 0)) + Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), 0)) * 5
            sz = leaf_size * rng.uniform(0.85, 1.15)
            # 叶柄往坡上挪 0.26 size（≈ 叶长的 40%）：叶子盖在打中的点上而不是全在它下面（第 3 版顶上一圈露芯）
            pb = P(*p) - down.normalized() * sz * 0.26 * K
            p = to_esu(pb)
            fr = max(0.0, min(0.999, p[2] / h))       # 深浅：按高度分档再随机 ±0.6 档（第 1 版只按高度，一圈一圈颜色分带）
            mm = mats[max(0, min(len(mats) - 1, int(fr * len(mats) * 1.1 + rng.uniform(-0.6, 0.6))))]
            return leaf(f'{name}_leaf_{i:02d}', mm, p, nn, axis=dir_esu(down), size=sz,
                        shape=leaf_shape, thick=2.0, tilt=leaf_tilt * rng.uniform(0.7, 1.2), sink=0.0, seg=leaf_seg,
                        cup_r=max(r) * 0.8, conform=tree, lift=rng.uniform(*leaf_lift), lift_tip=leaf_lift_tip)
        tree = _bvh(lumps)
        lv = scatter_on(lumps, leaves, mk, seed=seed + 101, center=(c[0], c[1], cu * 0.8), up=leaf_up,
                        min_dist=leaf_size * 0.3, even=True)
        for o in lv:                                    # 贴地那圈叶子不穿到地下
            for v in o.data.vertices:
                if v.co.z < 0:
                    v.co.z = 0.0
    return lumps, lv


# ---------------- 点缀小件 ----------------
def fruit(name, m, p, r=6, stem_m=None, n=(0, 0, 1)):
    """果子：p = 挂点 (E, S, U)（果子顶），半径 r；略扁的球 + 一截果柄（stem_m 给了才有）。返回物体列表。"""
    c = (p[0], p[1], p[2] - r * 0.9)
    out = [_ellipsoid(name, m, P(*c), [(Vector((1, 0, 0)), r * K), (Vector((0, 1, 0)), r * K), (Vector((0, 0, 1)), r * 0.9 * K)], sub=2)]
    if stem_m is not None:
        out.append(branch(f'{name}_stem', stem_m, (c[0], c[1], c[2] + r * 0.7), (c[0], c[1] + r * 0.2, c[2] + r * 1.4), r * 0.15,
                          r * 0.12, lift=0.0, seg=6, rings=1))
    return out


def flower(name, petal_m, center_m, p, n=(0, 0, 1), r=6, petals=5, spin=0.0):
    """花朵：p = 花心 (E, S, U)、n = 朝向（花面法线），r = 花半径；petals 片椭圆花瓣（压扁椭球）围一圈 + 圆鼓花心。返回物体列表。"""
    nb = D(*n).normalized()
    u, v, d = _frame(nb)
    o = P(*p)
    out = []
    for k in range(petals):
        a = math.radians(spin) + 2 * math.pi * k / petals
        dirp = u * math.cos(a) + v * math.sin(a)
        side = d.cross(dirp).normalized()
        out.append(_ellipsoid(f'{name}_p{k}', petal_m, o + dirp * r * 0.55 * K,
                              [(dirp, r * 0.5 * K), (side, r * 0.3 * K), (d, r * 0.12 * K)], sub=2))
    out.append(_ellipsoid(f'{name}_c', center_m, o + d * r * 0.1 * K, [(u, r * 0.3 * K), (v, r * 0.3 * K), (d, r * 0.2 * K)], sub=2))
    return out


def mushroom(name, cap_m, stem_m, p, h=10, r=6, dot_m=None, dots=0, seed=0, lean=0.0):
    """蘑菇：p = 根部 (E, S, U)，h = 高（到伞顶），r = 伞半径；伞柄 = 收细圆柱（埋进地 1 厘米），伞 = 上鼓下平的半椭球；
    dots > 0 且给 dot_m 时伞面加几粒白点（小压扁球，半埋）。lean = 往 +E 歪的角度（度）。返回物体列表。"""
    rng = random.Random(seed)
    tl = math.radians(lean)
    top = (p[0] + math.sin(tl) * h * 0.7, p[1], p[2] + math.cos(tl) * h * 0.7)
    out = [branch(f'{name}_stem', stem_m, (p[0], p[1], p[2] - 1), top, r * 0.32, r * 0.26, lift=0.0, seg=8, rings=2)]
    cap_c = P(top[0], top[1], top[2] - h * 0.05)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1)
    for vt in bm.verts:
        x, y, z = vt.co
        z = z if z > 0 else z * 0.25
        vt.co = cap_c + Vector((x * r * K, y * r * K, z * h * 0.38 * K))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    cap = smooth(new_obj(f'{name}_cap', bm, cap_m))
    out.append(cap)
    if dot_m is not None and dots:
        for k in range(dots):
            a = rng.uniform(0, 2 * math.pi)
            q = rng.uniform(0.25, 0.75)
            dn = Vector((q * math.cos(a), q * math.sin(a), math.sqrt(1 - q * q))).normalized()
            hit = _raycast([cap], cap_c + dn * h * 2 * K, -dn)
            if hit is None:
                continue
            pp, nn = hit
            u, v, d = _frame(nn)
            out.append(_ellipsoid(f'{name}_dot{k}', dot_m, pp, [(u, r * 0.16 * K), (v, r * 0.16 * K), (d, r * 0.05 * K)], sub=1))
    return out


# ---------------- 自查 ----------------
def check_normals(objs=None):
    """每个网格：是否闭合（每条边正好两个面）、有符号体积（> 0 = 法线朝外）。返回 [(名字, 闭合, 体积 m³)]，并打印有问题的。"""
    res = []
    for o in objs or [x for x in bpy.data.objects if x.type == 'MESH']:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.transform(o.matrix_world)
        closed = all(len(e.link_faces) == 2 for e in bm.edges)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        vol = sum(f.verts[0].co.dot(f.verts[1].co.cross(f.verts[2].co)) for f in bm.faces) / 6
        bm.free()
        res.append((o.name, closed, vol))
        if not closed or vol <= 0:
            print(f'[veg] 法线 / 闭合问题：{o.name} 闭合={closed} 体积={vol:.5f}')
    return res


def stats(objs=None):
    """三角形数 + 包围盒（米，Blender 坐标 x / y / z = −E / S / U）。"""
    objs = objs or [x for x in bpy.data.objects if x.type == 'MESH']
    tri = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs)
    pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return tri, lo, hi


def bvh(objs):
    """一组物体（世界坐标）的 BVHTree：给 leaf(conform=…) 复用，免得每片叶子重建一次。"""
    return _bvh(objs)
