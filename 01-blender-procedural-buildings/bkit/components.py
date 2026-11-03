"""建筑套件 · 组件库（Blender 里 import）：石基、墙 + 木构架、茅草屋顶、烟囱、窗、门、台阶、老虎窗、壁灯、木桶、几何质感。

约定（同 core）：
  - 尺寸全是四视图像素，坐标 (E, S, U)：E = 正视图向右、S = 朝正面、U = 离地；范围写 (min, max)。房子中心在 E = S = 0。
  - 每个组件第一个参数是材质字典 M（materials.load() 出的），用到的键写在各自 docstring 里。
  - 默认值 = 茅草房 s5_toyclay_1 量出来的数（blender_house/house_s5.py 也显式传了一遍）；
    组件不读任何全局开关：贴图 / 几何质感 / 投影都走参数（geo=、band=、proj=），随机数走 rng=（默认 random 模块本身，
    调用方先 random.seed()；同一个种子、同样的调用顺序 → 石块 / 波浪边一样）。
  - 返回建出来的物体列表（可动部件返回 part.* 物体本身，见 core.make_part）。
  - 正面（+S）以外的墙：window 用 side= 挂到侧墙；dormer 用 side=±1 分前后；door / lantern / steps 只做正面（+S）。
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

from .core import K, P, arch_panel, blob, boolean_cut, box, brace, created_since, cylinder, make_part, new_obj, reuv, snapshot
from .projection import projected

FOUR = ('S+', 'S-', 'E+', 'E-')


# ---------------- 石基 ----------------
def base(M, E=200, S=127, U=(0, 56), slab=False, proj=False, rng=random):
    """石基：半宽 E × 半深 S，高 U。两层石块沿四边排（块长 44–70 随机、错缝），里面一块芯，四角各一块大石。
    slab=True 换成一整块圆角石台（茅草房 PROJ=1 那版用：石块花纹从四视图投）；proj=True 时石台按 正背 ← 背视图、两侧 ← 左视图 投。
    用 M['stone']（三个深浅的列表，每块随机取一个；芯 / 石台用中间那个）。rng 用到：uniform（块长）、choice（深浅）。"""
    e, s = E, S
    u0, u1 = U
    before = snapshot()
    if slab:
        with projected({'S+': 'back', 'S-': 'back', 'E+': 'left', 'E-': 'left'}, on=proj):
            box('base_slab', (-e, e), (-s, s), (u0, u1), M['stone'][1], bevel=5, seg=3)
        return created_since(before)
    mid = (u0 + u1) / 2
    n = 0
    for (ua, ub), off in (((u0, mid - 1), 0), ((mid + 1, u1), 25)):   # 上层错开 25 % 18 = 7 像素
        for side in FOUR:
            L = 2 * (e if side[0] == 'S' else s)
            x = -L / 2 - off % 18
            while x < L / 2:
                ln = rng.uniform(44, 70)
                a, b = max(x, -L / 2), min(x + ln, L / 2)
                if b - a > 8:
                    d = 14                                     # 石块进深
                    if side == 'S+':
                        box(f'stone{n}', (a, b), (s - d, s), (ua, ub), rng.choice(M['stone']), bevel=5)
                    elif side == 'S-':
                        box(f'stone{n}', (a, b), (-s, -s + d), (ua, ub), rng.choice(M['stone']), bevel=5)
                    elif side == 'E+':
                        box(f'stone{n}', (e - d, e), (a, b), (ua, ub), rng.choice(M['stone']), bevel=5)
                    else:
                        box(f'stone{n}', (-e, -e + d), (a, b), (ua, ub), rng.choice(M['stone']), bevel=5)
                    n += 1
                x += ln + 2
    box('base_core', (-e + 4, e - 4), (-s + 4, s - 4), (u0, u1 - 1), M['stone'][1])
    for se in (-1, 1):                                 # 四角大石块
        for ss in (-1, 1):
            box(f'corner{se}{ss}', sorted((se * (e - 30), se * (e + 2))), sorted((ss * (s - 30), ss * (s + 2))), (u0, u1 + 2),
                rng.choice(M['stone']), bevel=6)
    return created_since(before)


# ---------------- 墙 + 木构架 ----------------
def walls(M, E=190, S=120, U=(56, 200), frame=True, proj=False, **frame_kw):
    """墙身：半宽 E × 半深 S、高 U（顶部藏进屋顶）的一整块，用 M['plaster']；frame=True 再搭木构架（timber_frame，参数照传）。
    proj=True（不推荐）：墙面按 正背 ← 背视图、两侧 ← 左视图 投。"""
    before = snapshot()
    with projected({'S+': 'back', 'S-': 'back', 'E+': 'left', 'E-': 'left'}, on=proj):
        box('wall', (-E, E), (-S, S), U, M['plaster'])   # 墙面也投：和投上去的窗框 / 百叶同一个灰泥色
    if frame:
        timber_frame(M, E, S, post_u0=U[0], proj=proj, **frame_kw)
    return created_since(before)


def timber_frame(M, E=190, S=120, post_u0=56, plate=(158, 182), post=(31, 29), post_out=2, beam_u=(152, 176),
                 brace_u=(124, 166), brace_in=24, brace_reach=(64, 56), brace_out=3, brace_w=12, proj=False):
    """墙外的木构架（M['timber']）：墙顶一圈横梁 + 四根角柱 + 柱头两向梁头 + 每面墙两根斜撑。E / S = 墙面半宽 / 半深。
      plate      墙顶横梁 U 范围（压在檐口下面；参考图里露出 U 162–170，上面藏在檐口下）
      post       角柱从墙角往里占多少（沿 E, 沿 S），post_out = 凸出墙面多少；柱子从 post_u0 伸到横梁顶
      beam_u     梁头 U 范围（沿 E 那根从墙角往里 30、往外伸 14；沿 S 那根同理）
      brace_*    斜撑：下端离墙角 brace_in、高 brace_u[0]，上端离墙角 brace_reach（前后墙, 两侧墙）、高 brace_u[1]，
                 离墙面 brace_out，截面 brace_w；两头各多伸 6 插进柱子和梁里
    用户 2026-10-22 定下来的：
      "墙角的木头支撑没建模出来，看起来跟支撑柱子和房子顶部没有连接着"——加墙顶横梁，角柱伸到横梁顶，斜撑下端插进角柱、上端插进横梁；
      "我们木头柱子有点窄"——角柱 16 → 24，后来按参考图量（背视图柱宽 31、侧视图 28）改成往里占 31 × 29、只凸出墙面 2。
    proj=True（不推荐）：贴在某面墙上的细长构件（横梁、梁头、斜撑）所有面都取那面墙的视图（按面朝向取的话，侧面在另一张视图里只是一条边，
    取到旁边的高光 / 背景，用户 2026-10-22："侧着看，还是有缝啊"）。"""
    e, s = E, S
    PL = plate
    before = snapshot()
    wood_cfg = {'S+': 'back', 'S-': 'back', 'E+': 'left', 'E-': 'left'}
    FB, SIDE = {'all': 'back'}, {'all': 'left'}
    pe, ps = post
    with projected(FB, on=proj):
        for ss in (-1, 1):
            box(f'plateS{ss}', (-e - 4, e + 4), sorted((ss * (s - 4), ss * (s + 9))), PL, M['timber'], bevel=2)
    with projected(SIDE, on=proj):
        for se in (-1, 1):
            box(f'plateE{se}', sorted((se * (e - 4), se * (e + 9))), (-s - 4, s + 4), PL, M['timber'], bevel=2)
    for se in (-1, 1):                                 # 角柱（伸到横梁顶）+ 柱头梁端
        for ss in (-1, 1):
            with projected(wood_cfg, on=proj):
                box(f'post{se}{ss}', sorted((se * (e - pe), se * (e + post_out))), sorted((ss * (s - ps), ss * (s + post_out))),
                    (post_u0, PL[1]), M['timber'], bevel=3)
            with projected(FB, on=proj):
                box(f'beamE{se}{ss}', sorted((se * (e - 30), se * (e + 14))), sorted((ss * (s - 6), ss * (s + 6))), beam_u, M['timber'],
                    bevel=2)
            with projected(SIDE, on=proj):
                box(f'beamS{se}{ss}', sorted((se * (e - 6), se * (e + 6))), sorted((ss * (s - 30), ss * (s + 14))), beam_u, M['timber'],
                    bevel=2)
    ra, rb = brace_reach
    for ss in (-1, 1):                                 # 斜撑：每面墙两个角，下端插进角柱、上端插进横梁（45°）
        for se in (-1, 1):
            with projected(FB, on=proj):
                brace(f'braceS{se}{ss}', (se * (e - brace_in), ss * (s + brace_out), brace_u[0]),
                      (se * (e - ra), ss * (s + brace_out), brace_u[1]), brace_w, M['timber'])
            with projected(SIDE, on=proj):
                brace(f'braceE{se}{ss}', (se * (e + brace_out), ss * (s - brace_in), brace_u[0]),
                      (se * (e + brace_out), ss * (s - rb), brace_u[1]), brace_w, M['timber'])
    return created_since(before)


# ---------------- 茅草屋顶 ----------------
BULGE, CURL = 0.30, 0.88                              # 茅草层最鼓处高度（层高比例）、底边往里卷到多少


def fit_tiers(tiers, bulge=BULGE):
    """每层往上伸进上一层里（伸到上一层高度的一半），收进量按"到上一层下沿那个高度，正好收到上一层最鼓处的宽度"来解
    （椭圆弧 f(h) = top + (1−top)·√(1−x²)）：外轮廓是一条连续的弧，只在上一层下沿往里卷的地方留一道窄凹缝。
    （第 6 轮各层顶面露出一圈平台，看着像一级级台阶。）返回新列表，每层多一个 Uvis = 露在外面的那段 U。"""
    out = [dict(t) for t in tiers]
    for i in range(len(out) - 1):
        lo, up = out[i], out[i + 1]
        u0, ub = lo['U'][0], up['U'][0]
        u1 = ub + 0.5 * (up['U'][1] - up['U'][0])
        lo['Uvis'] = (u0, ub)                          # 露在外面的那段（贴图竖向、波浪边都按这段算）
        lo['U'] = (u0, u1)
        hb = (ub - u0) / (u1 - u0)
        x = (hb - bulge) / (1 - bulge)
        sq = math.sqrt(max(0.0, 1 - x * x))
        for ax, tk in (('E', 'tE'), ('S', 'tS')):
            f = min(1.0, up[ax] / lo[ax])
            lo[tk] = min(0.98, max(0.3, (f - sq) / (1 - sq) if sq < 0.999 else f))
    return out


def tier(name, t, m, geo=False, bulge=BULGE, curl=CURL, rng=random):
    """茅草一层：t = dict(U=(底, 顶), E=最鼓处半宽, S=最鼓处半深, tE / tS = 顶部收进比例, r = 平面四角圆角[, Uvis])。
    竖向剖面是圆滑的弧——用户 2026-10-22："从侧面看，这个每层茅草是圆滑弧形的，我们建模的有点呆"：
    底下往里卷（椭圆弧，底面处水平，卷到 curl），最鼓处在 bulge 高度，往上按椭圆弧收到 tE / tS（顶面处水平）；平面四角按 r 倒圆。
    geo=True：水平方向也细分 + 下沿波浪边（scallop，用 rng.uniform 一次）。m = 材质列表（同 new_obj）。"""
    u0, u1 = t['U']
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if abs((e.verts[0].co - e.verts[1].co).z) > 0.5], cuts=10)
    if geo:                                            # 水平方向也细分，波浪边才有顶点可推
        bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if abs((e.verts[0].co - e.verts[1].co).z) < 1e-6], cuts=10)
    b = bulge

    def prof(h, top):
        if h <= b:
            return curl + (1 - curl) * math.sqrt(max(0.0, 1 - ((b - h) / b) ** 2))
        return top + (1 - top) * math.sqrt(max(0.0, 1 - ((h - b) / (1 - b)) ** 2))
    # 只倒平面四个角的竖边（单位立方体里 |x| = |y| = 0.5 的竖边）；第 7 轮把侧面所有竖网格线都倒了角，俯视轮廓成了锯齿
    vert_edges = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 1e-6
                  and all(abs(abs(v.co.x) - 0.5) < 1e-6 and abs(abs(v.co.y) - 0.5) < 1e-6 for v in e.verts)]
    for v in bm.verts:
        h = v.co.z + 0.5                                   # 0 底 → 1 顶
        v.co = Vector((v.co.x * 2 * t['E'] * K * prof(h, t['tE']), v.co.y * 2 * t['S'] * K * prof(h, t['tS']),
                       (u0 + h * (u1 - u0)) * K))
    bmesh.ops.bevel(bm, geom=vert_edges, offset=t['r'] * K, segments=4, affect='EDGES', profile=0.5, clamp_overlap=True)
    if geo:
        scallop(bm, t, rng=rng)
    return new_obj(name, bm, m)


def scallop(bm, t, rng=random):
    """茅草一层的下沿：一缕一缕往下垂的波浪边（只推最下 15% 高度，越靠底推得越多；第 6 轮推到 25%，下沿成了锯齿），整层再加一点低频鼓包。"""
    u0, u1 = t.get('Uvis', t['U'])
    n = max(12, int(2 * math.pi * math.sqrt(t['E'] * t['S']) / 26))
    ph = rng.uniform(0, 6.28)
    for v in bm.verts:
        h = (v.co.z / K - u0) / (u1 - u0)
        th = math.atan2(v.co.y / t['S'], v.co.x / t['E'])
        lump = 1 + 0.018 * math.sin(3 * th + ph) * math.sin(7 * h + ph) + 0.010 * math.sin(11 * th + 2 * ph)
        v.co.x *= lump
        v.co.y *= lump
        if h < 0.15:
            w = (1 - h / 0.15) ** 1.5
            v.co.z -= 5 * K * w * (0.5 + 0.5 * math.cos(n * th + ph)) * (0.7 + 0.3 * math.sin(5 * th))


def tier_uv(ob, t, band_w):
    """茅草层贴"一层一条带"：u 绕着这一层转一圈（整数条带，首尾接上），v = 这一层露在外面那段从底到顶（贴图上沿 = 层顶、下沿草尖 = 层底）。
    每层起点按高度错开（用户 2026-10-22："稻草的接缝看着怪怪的"——首尾接缝不在同一列上下对齐），起点放在背面左角。
    朝上的面（屋脊顶）改用材质槽 2、普通平铺：绕圈贴法在顶面会扭成人字纹。"""
    a, b = t['E'], t['S']
    per = math.pi * (3 * (a + b) - math.sqrt((3 * a + b) * (a + 3 * b)))
    reps = max(1, round(per / band_w))
    u0, u1 = t.get('Uvis', t['U'])
    phase = (u0 * 0.618) % 1.0
    me = ob.data
    uvl = me.uv_layers['UV']
    for poly in me.polygons:
        if poly.normal.z > 0.6:
            poly.material_index = 2
            for li in poly.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co / K
                uvl.data[li].uv = (co.x / 64, co.y / 64)
            continue
        us = []
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            th = math.atan2(-co.y / (b * K), -co.x / (a * K))
            us.append((li, (th / (2 * math.pi) + 0.5) * reps + phase, min(max((co.z / K - u0) / (u1 - u0), 0.0), 1.0)))
        lo, hi = min(x[1] for x in us), max(x[1] for x in us)
        for li, u, v in us:
            if hi - lo > reps / 2 and u < reps / 2 + phase:
                u += reps
            uvl.data[li].uv = (u, v)


def roof(M, tiers, band=None, geo=False, rng=random, name='thatch'):
    """茅草屋顶：tiers = 从下往上每层的 dict(U, E, S, tE, tS, r)（见 tier），先 fit_tiers 让每层伸进上一层、外轮廓连成一条弧。
    每层三个材质槽：0 = 侧面（band 不为空用茅草带 + tier_uv，否则 M['thatch'] 平铺）、1 = 朝下的面 M['thatch_under']
    （层间阴影线；用户 2026-10-22："接缝黄黄的，看着不好看"——原来用深茅草色，像一道黄缝）、2 = 朝上的面 M['thatch']。
    band = materials.band() 出的茅草带材质（用户 2026-10-22 认可的定稿用它）；geo=True 下沿波浪边（每层 rng.uniform 一次）。
    物体名 <name>0、<name>1……（从下往上）。"""
    out = []
    for i, t in enumerate(fit_tiers(tiers)):
        ob = tier(f'{name}{i}', t, [band if band is not None else M['thatch'], M['thatch_under'], M['thatch']], geo=geo, rng=rng)
        if band is not None:
            tier_uv(ob, t, band['band_w'])
        for poly in ob.data.polygons:                  # 朝下的面用深色：层与层之间的阴影线
            poly.material_index = 1 if poly.normal.z < -0.75 else (2 if band is not None and poly.normal.z > 0.6 else 0)
        out.append(ob)
    return out


# ---------------- 烟囱 ----------------
def chimney(M, E=(-147, -79), S=(-37, 37), U=(320, 427), rows=4, cap=14, rng=random):
    """石砌烟囱：E / S / U 范围；rows 层石块、一层两块错缝（每块随机取一个深浅 M['chimney']），顶上 cap 高的帽（最亮那个）+ 深色烟囱口 M['dark']。"""
    before = snapshot()
    h = (U[1] - cap - U[0]) / rows
    for r in range(rows):                              # 一层两块石头，错缝
        ua, ub = U[0] + r * h, U[0] + (r + 1) * h - 1.5
        cut = (E[0] + E[1]) / 2 + (8 if r % 2 else -8)
        box(f'chimA{r}', (E[0], cut - 1), S, (ua, ub), rng.choice(M['chimney']), bevel=3)
        box(f'chimB{r}', (cut + 1, E[1]), S, (ua, ub), rng.choice(M['chimney']), bevel=3)
    box('chim_cap', (E[0] - 4, E[1] + 4), (S[0] - 4, S[1] + 4), (U[1] - cap, U[1]), M['chimney'][2], bevel=3)
    box('chim_hole', (E[0] + 12, E[1] - 12), (S[0] + 12, S[1] - 12), (U[1] - 4, U[1] + 0.5), M['dark'])
    return created_since(before)


# ---------------- 窗 ----------------
def window(name, E, U, S0, M, out=1, shutters=True, side=None, flowerbox=False, frame_w=7, shutter_angle=178):
    """窗：玻璃 + 十字窗棂 + 框（M['glass'] / M['frame']）(+ 两扇百叶 M['shutter'] + 花箱 M['flowerbox'] / M['leaf'] / M['petal'] / M['petal_c'])。
      E / U      玻璃范围（像素）；S0 = 墙面所在的 S；out = 朝外方向（+1 = +S，正面墙）
      side       None = 窗在前后墙；'E' / '-E' = 窗在侧墙（这时 E 当 S 用、S0 = 侧墙的 E）
      frame_w    窗框宽（框凸出墙 6，下框宽一点、凸出 8）
      flowerbox  窗下花箱（叶丛和花只在前后墙的窗上有）
    百叶：每扇是一个可动部件 part.shutter_<name>_<0|1>（用户 2026-10-22："可活动的部件都应该单独建模"），8 像素厚 + 两根横档
    （"门和百叶窗应该有厚度"），铰链 = 靠窗那条边、离墙 9（合上转 shutter_angle 度正好压在凸出 8 的窗框前面不穿模）。
    返回 [玻璃 / 框 / 窗棂 / 花箱…] + 百叶部件。"""
    def b(nm, e, u, d0, d1, m, bev=0.0):
        if side is None:
            return box(nm, e, sorted((S0 + out * d0, S0 + out * d1)), u, m, bevel=bev)
        sg = 1 if side == 'E' else -1
        return box(nm, sorted((S0 + sg * d0, S0 + sg * d1)), e, u, m, bevel=bev)
    before = snapshot()
    parts = []
    e0, e1 = E
    u0, u1 = U
    f = frame_w
    b(f'{name}_glass', E, U, 0, 2, M['glass'])
    b(f'{name}_frT', (e0 - f, e1 + f), (u1, u1 + f), 0, 6, M['frame'], 1.5)
    b(f'{name}_frB', (e0 - f - 3, e1 + f + 3), (u0 - f, u0), 0, 8, M['frame'], 1.5)
    b(f'{name}_frL', (e0 - f, e0), U, 0, 6, M['frame'])
    b(f'{name}_frR', (e1, e1 + f), U, 0, 6, M['frame'])
    em, um = (e0 + e1) / 2, (u0 + u1) / 2
    b(f'{name}_mV', (em - 2, em + 2), U, 0, 4, M['frame'])
    b(f'{name}_mH', E, (um - 2, um + 2), 0, 4, M['frame'])
    if shutters:
        w = (e1 - e0) * 0.42
        for k, (a, c) in enumerate(((e0 - f - w - 2, e0 - f - 2), (e1 + f + 2, e1 + f + w + 2))):
            before_k = snapshot()
            b(f'{name}_sh{k}', (a, c), (u0 - 4, u1 + 6), 0.5, 8.5, M['shutter'], 2)        # 百叶 8 像素厚（约 11 厘米）
            for j in (0.3, 0.7):                       # 横档只在一面（打开贴墙时朝外）
                uu = u0 - 4 + j * (u1 + 10 - u0)
                b(f'{name}_shb{k}{j}', (a + 2, c - 2), (uu - 2, uu + 2), 8.5, 10.5, M['shutter'])
            inner = c if k == 0 else a                 # 铰链 = 靠窗的那条边
            sgn = -1 if k == 0 else 1                  # 百叶从铰链往远离窗的方向伸（沿墙面坐标）
            if side is None:
                hinge, d, n = P(inner, S0 + out * 9, u0 - 4), (-sgn, 0), (0, out)        # x = −E
            else:
                sg = 1 if side == 'E' else -1
                hinge, d, n = P(S0 + sg * 9, inner, u0 - 4), (0, sgn), (-sg, 0)
            parts.append(make_part(f'shutter_{name}_{k}', created_since(before_k), hinge, d, n, shutter_angle))
    if flowerbox:
        b(f'{name}_box', (e0 - 33, e1 + 23), (u0 - 50, u0 - 10), 0, 22, M['flowerbox'], 2)
        for i in range(7):
            x = e0 - 28 + i * ((e1 - e0 + 46) / 6)
            if side is None:
                blob(f'{name}_leaf{i}', (x, S0 + out * 12, u0 - 6), 11, 9, 8, M['leaf'], 1)
            if i % 2 == 0 and side is None:
                blob(f'{name}_fl{i}', (x + 4, S0 + out * 18, u0 + 2), 6, 3, 5, M['petal'], 1)
                blob(f'{name}_flc{i}', (x + 4, S0 + out * 21, u0 + 2), 2.5, 1.5, 2.5, M['petal_c'], 1)
    return [o for o in created_since(before) if o not in parts] + parts


# ---------------- 门 / 台阶 ----------------
def door(M, E=(-117, 3), U=(40, 172), S0=120, inset=16, win=((-77, -37), (95, 139)), knob=(-89, 83), angle=100, proj=False):
    """正面墙上的拱门：门框 + 门洞 + 门扇部件 part.door。
      E / U   门框外轮廓（矩形 + 上面半圆）；S0 = 墙面 S；inset = 门扇比门框每边窄多少
      win     门上小窗 (E 范围, U 范围)，None = 没有；knob = 把手 (E, U)；angle = 向外开多少度
    门框 7 厚（M['frame']）；门洞 = 门框里贴一块接近纯黑的板 M['void']，比门扇四边各宽 2（开门时边上不露木头）；
    门扇 8 厚（M['door']），铰链在右（+E）边、门扇往 −E 伸，绕竖直轴向外（+S）开 0 → angle。
    用户 2026-10-22 定下来的：
      "门应该单独建模""可活动的部件都应该单独建模"——门扇（门板 + 小窗 + 窗棂 + 压条 + 里外把手）合成一个部件，原点 = 铰链；
      "理论上，我们自己建模应该更好做可交互模型吧，把开关门做一下"——部件 extras 写转轴和开合角，预览页点一下开 / 关；
      "门没有建模背面"——拱形板挤出保留原面（core.arch_panel）；
      "门的内部应该是黑色阴影"、"门打开房子内部看起来还是不够黑啊"——门洞用接近纯黑的 void；
      "门和百叶窗应该有厚度"——门扇 8 像素（约 11 厘米）；
      "门的正面有窗户，背面没有，这不是很奇怪吗"——小窗是真窗洞：布尔挖穿门板，玻璃在厚度中间，窗棂贯穿整个厚度；
      "门上窗户的四条边在外面有，在里面没有，很奇怪"——窗框压条（宽 5、厚 2）里外两面都有。
    proj=True（不推荐）：门洞和窗洞切刀不投（其余跟着外面的 projected）。返回 [门框, 门洞, part.door]。"""
    before = snapshot()
    arch_panel('door_frame', E, U, (S0, S0 + 7), M['frame'])
    inner = (E[0] + inset, E[1] - inset)
    with projected(None, on=proj):
        arch_panel('door_hole', (inner[0] - 2, inner[1] + 2), (U[0], U[1] - 10), (S0 + 7, S0 + 7.5), M['void'])
    before_leaf = snapshot()
    s0, s1 = S0 + 7.6, S0 + 15.6                        # 门扇 8 像素厚
    leaf_ob = arch_panel('door', inner, (U[0], U[1] - 12), (s0, s1), M['door'])
    if win is not None:
        WE, WU = win
        with projected(None, on=proj):
            cut = box('door_cut', WE, (s0 - 2, s1 + 2), WU, M['dark'])
        boolean_cut(leaf_ob, cut)
        reuv(leaf_ob, M['door'])                        # 挖洞后重新投（布尔会把切刀的材质带进来）
        sm = (s0 + s1) / 2
        box('door_glass', WE, (sm - 0.5, sm + 0.5), WU, M['glass'])
        wm, hm = (WE[0] + WE[1]) / 2, (WU[0] + WU[1]) / 2
        box('door_mV', (wm - 2, wm + 2), (s0 + 1, s1 - 1), WU, M['frame'])
        box('door_mH', WE, (s0 + 1, s1 - 1), (hm - 2, hm + 2), M['frame'])
        tw = 5                                          # 窗框压条宽 5、厚 2，里外两面都有
        for k, (a_, b_) in enumerate((((WE[0] - tw, WE[1] + tw), (WU[1], WU[1] + tw)), ((WE[0] - tw, WE[1] + tw), (WU[0] - tw, WU[0])),
                                      ((WE[0] - tw, WE[0]), WU), ((WE[1], WE[1] + tw), WU))):
            box(f'door_trimO{k}', a_, (s1, s1 + 2), b_, M['frame'])
            box(f'door_trimI{k}', a_, (s0 - 2, s0), b_, M['frame'])
    blob('door_knob', (knob[0], s1 + 4, knob[1]), 4, 4, 4, M['metal'], 1)
    blob('door_knob_in', (knob[0], s0 - 3, knob[1]), 3.5, 3.5, 3.5, M['metal'], 1)   # 门里面的把手
    part = make_part('door', created_since(before_leaf), P(inner[1], S0 + 11.6, U[0]), (1, 0), (0, 1), angle)
    return [o for o in created_since(before) if o is not part] + [part]


def steps(M, E=(-119, 3), S0=127, treads=(32, 14), rise=20, inset=6, tuck=6):
    """门前台阶（M['step']）：E = 最下一级的宽；S0 = 石基正面；treads = 每一级伸出石基多少（从下往上）；
    rise = 每级高；上一级每边比下一级窄 inset；每级往石基里藏 tuck。物体名 step1、step2……（从下往上）。"""
    e0, e1 = E
    s = S0
    out = []
    for i, dep in enumerate(treads):
        out.append(box(f'step{i + 1}', (e0 + i * inset, e1 - i * inset), (s - tuck, s + dep), (i * rise, (i + 1) * rise), M['step'], bevel=3))
    return out


# ---------------- 老虎窗 ----------------
def dormer(M, side=1, E=5, tilt=22, s_face=160, s_back=95, U=(222, 322), half=52, glass=((-30, 30), (240, 300)), hood=(62, 282)):
    """老虎窗：小屋身（M['plaster']）+ 拱形窗框（M['frame']）+ 拱形玻璃 + 十字窗棂 + 茅草拱罩（一串 M['thatch'] 圆鼓块沿拱形排开）。
      side   +1 = 正面（+S）、−1 = 背面；E = 窗中心
      s_face 窗面底边所在的 S（第 8 轮茅草层改成圆鼓剖面后 150 被第 3 层挡住下半截，挪到 160）；s_back = 屋身往屋里伸到哪
      U      屋身高度（窗框比屋身高 4）；half = 屋身半宽（窗框半宽 half − 2）
      glass  玻璃相对窗中心的 E 范围 + U 范围；hood = 拱罩 (半径, 圆心 U)，只盖在窗上方（第 3 轮两头的块从侧面看凸出屋顶）
      tilt   整个老虎窗以窗面底边为轴顺屋面往后倾的角度（第 1 轮竖直，侧视图凸出屋顶；第 2 轮往里收又被茅草挡住）
    返回建出的物体（已经倾斜好）。"""
    sg, ec = side, E
    before = snapshot()
    u0, u1 = U
    S = sorted((sg * s_back, sg * s_face))
    ge, gu = (ec + glass[0][0], ec + glass[0][1]), glass[1]
    box(f'dorm_body{sg}', (ec - half, ec + half), S, (u0, u1), M['plaster'])
    arch_panel(f'dorm_frame{sg}', (ec - (half - 2), ec + (half - 2)), (u0, u1 + 4), sorted((sg * s_face, sg * (s_face + 6))), M['frame'])
    arch_panel(f'dorm_glass{sg}', ge, gu, sorted((sg * (s_face + 6), sg * (s_face + 7))), M['glass'])
    box(f'dorm_mV{sg}', (ec - 2, ec + 2), sorted((sg * (s_face + 6), sg * (s_face + 9))), gu, M['frame'])
    gm = (gu[0] + gu[1]) / 2
    box(f'dorm_mH{sg}', ge, sorted((sg * (s_face + 6), sg * (s_face + 9))), (gm - 2, gm + 2), M['frame'])
    R, cu = hood                                        # 茅草拱罩：一串圆鼓块沿拱形排开（半径 ~ 拱宽一半）
    for i, a in enumerate(np.linspace(0.05, math.pi - 0.05, 11)):
        e = ec + R * math.cos(a) * 1.1
        u = cu + R * math.sin(a) * 0.85
        blob(f'dorm_hood{sg}_{i}', (e, sg * (s_face + 4), u), 16, 14, 15, M['thatch'], 2)
    piv = P(ec, sg * s_face, u0)
    T = Matrix.Translation(piv) @ Matrix.Rotation(sg * math.radians(tilt), 4, 'X') @ Matrix.Translation(-piv)
    objs = created_since(before)
    for ob in objs:
        ob.data.transform(T)
    return objs


# ---------------- 壁灯 / 木桶 ----------------
def lantern(M, E=(-167, -134), U=(105, 165), S0=120):
    """正面墙上的壁灯：灯架（伸出墙 24）+ 灯顶 + 灯罩（M['lamp']）+ 两根竖条 + 灯座（M['metal']）。E / U = 整个灯的范围，S0 = 墙面。"""
    before = snapshot()
    ec = (E[0] + E[1]) / 2
    box('lan_arm', (ec - 3, ec + 3), (S0, S0 + 24), (U[1] - 8, U[1] - 2), M['metal'])
    box('lan_top', (E[0] + 2, E[1] - 2), (S0 + 8, S0 + 32), (U[1] - 26, U[1] - 12), M['metal'], bevel=3)
    box('lan_glass', (E[0] + 5, E[1] - 5), (S0 + 11, S0 + 29), (U[0] + 12, U[1] - 26), M['lamp'])
    for k, (a, c) in enumerate(((E[0] + 4, E[0] + 8), (E[1] - 8, E[1] - 4))):
        box(f'lan_bar{k}', (a, c), (S0 + 9, S0 + 31), (U[0] + 10, U[1] - 26), M['metal'])
    box('lan_bot', (E[0] + 4, E[1] - 4), (S0 + 9, S0 + 31), (U[0] + 4, U[0] + 12), M['metal'], bevel=2)
    return created_since(before)


def barrel(M, E=(-197, -134), U=(7, 92), S=161, plants=True):
    """木桶花盆：E / U = 整体范围（桶身顶 = U[1] − 22，上面是叶丛和花），S = 桶中心。
    桶身中间鼓 10%（M['barrel']）、两道铁箍（M['hoop']）；plants=True 桶口六团叶（M['leaf']）+ 四朵花（M['petal'] / M['petal_c']）。"""
    before = snapshot()
    Sc = S
    ec = (E[0] + E[1]) / 2
    r = (E[1] - E[0]) / 2 - 4
    top = U[1] - 22
    cylinder('barrel', (ec, Sc), r, (U[0], top), M['barrel'], seg=20, bulge=0.10)
    for k, u in enumerate((U[0] + 14, top - 14)):
        cylinder(f'hoop{k}', (ec, Sc), r * 1.06 + 1.5, (u - 3, u + 3), M['hoop'], seg=20)
    if plants:
        for i in range(6):
            a = i / 6 * 2 * math.pi
            blob(f'bleaf{i}', (ec + r * 0.55 * math.cos(a), Sc + r * 0.55 * math.sin(a), top + 8), 15, 15, 11, M['leaf'], 1)
        for i, (dx, ds) in enumerate(((-10, 6), (8, 10), (0, -6), (14, -2))):
            blob(f'bfl{i}', (ec + dx, Sc + ds, top + 20), 7, 7, 3, M['petal'], 1)
            blob(f'bflc{i}', (ec + dx, Sc + ds, top + 23), 2.5, 2.5, 1.5, M['petal_c'], 1)
    return created_since(before)


# ---------------- 几何质感 ----------------
def roughen(stone=('stone', 'corner', 'chimA', 'chimB', 'step'), wood=('post', 'beam', 'brace'), lean=('post',), seed=11, objs=None):
    """几何质感（用户 2026-10-22 定材质来源时，"几何上的质感要不要一起做"答"一起做"；茅草房 GEO=1）：按物体名前缀挑——
    石块：每块随机缩一点 + 顶点抖 1.2 像素（边角不齐）；木料：顶点抖 0.7 像素，lean 前缀的（角柱）整根微微歪。
    茅草层的波浪边不在这里，在 roof(geo=True)。用自己的 random.Random(seed)，按物体名顺序走（objs 不给 = 场景里所有物体），
    和别处的随机数互不影响。最后调（所有组件都搭完之后）。"""
    rng = random.Random(seed)
    for ob in (bpy.data.objects if objs is None else sorted(objs, key=lambda o: o.name)):
        if ob.type != 'MESH':
            continue
        nm = ob.name
        if nm.startswith(stone):
            amp, sc = 1.2, (rng.uniform(0.93, 1.0), rng.uniform(0.93, 1.0), rng.uniform(0.9, 1.0))
        elif nm.startswith(wood):
            amp, sc = 0.7, (1, 1, 1)
        else:
            continue
        vs = ob.data.vertices
        c = sum((v.co for v in vs), Vector()) / len(vs)
        tilt = Vector((rng.uniform(-0.01, 0.01), rng.uniform(-0.01, 0.01), 0)) if nm.startswith(lean) else Vector()
        for v in vs:
            d = v.co - c
            d = Vector((d.x * sc[0], d.y * sc[1], d.z * sc[2]))
            v.co = c + d + tilt * (d.z / K) * K + Vector([rng.uniform(-amp, amp) * K for _ in range(3)])
