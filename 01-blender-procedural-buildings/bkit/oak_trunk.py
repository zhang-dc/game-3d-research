"""橡树重做试验第 3 版（trunk）组件：粗树干 + 底部外扩成一圈短圆根（根和干是同一根管子），宽裂片橡叶轮廓。
（veg/flat/OAK_TRY.md 第 3 版；2026-10-23。不改 bkit/veg.py：叶形用 install_shapes() 往 veg._outline 里挂一个新形状。）

  flared_trunk(...)   树干：按高度给"轮廓半宽"表（正视图 E / 右视图 S 量的剪影半宽，含根），底部 toes 条短圆根是截面上的圆裂片
                      （根间收进到 core 比例），根头在地面附近按半径 nose 的圆弧收回（圆头根、不是尖锥）；中段竖槽在根与根之间。
  outline_oak7(...)   7 裂片橡叶轮廓（叶尖 1 个 + 每边 3 个圆裂片，宽 / 长 ≈ 0.8；veg 'oak' 是 5 裂片、宽 / 长 ≈ 0.7）
  install_shapes()    把 'oak7' 挂进 veg._outline（veg.leaf / veg.puff_leaves 的 shape='oak7' 就能用）
  placed_leaf(...)    按方向放一片叶（轮廓边上的侧叶；随机散布时这种常被悬空自查去掉）
  clear_leaves(...)   叶面和叶簇三角形还相交的往外推（puff_leaves 只查顶点）、推不开 / 叶叶相交的删
坐标 / 单位同 bkit.veg：P(E, S, U)，厘米。
"""
from __future__ import annotations

import math
import random

from mathutils import Vector

from bkit import veg
from bkit.core import K, P


def _interp(tab, u):
    """tab = [(U, a, b), …]（U 升序）→ 在 u 处线性插值 (a, b)。"""
    if u <= tab[0][0]:
        return tab[0][1], tab[0][2]
    for (u0, a0, b0), (u1, a1, b1) in zip(tab, tab[1:]):
        if u <= u1:
            f = (u - u0) / (u1 - u0)
            return a0 + (a1 - a0) * f, b0 + (b1 - b0) * f
    return tab[-1][1], tab[-1][2]


def _ell(a, b, th):
    """半轴 (a, b) 椭圆在极角 th 方向的半径（th 从 +E 起、往 +S 转）。"""
    return 1.0 / math.sqrt((math.cos(th) / a) ** 2 + (math.sin(th) / b) ** 2)


def flared_trunk(name, m, base=(0, 0), h=290, env=(), core_tab=(), bend=(0, 0), toes=7, toe_az=None, toe_len=None, toe_w=2.0,
                 nose=22.0, levels=(), grooves=7, groove_depth=0.06, groove_top=(97, 260), seg=70, sink=3, seed=0):
    """粗树干 + 一圈短圆根（同一根闭合管子）。
    env = [(U, 半宽E, 半宽S), …]：根的方向上截面能伸到的半径（按正 / 右视图剪影半宽量），core_tab 同格式：根与根之间收进到的半径；
    两者在没有根的高度（中段以上）取一样。截面极角 th 处半径 = core + (env − core) × lob(th) × nose(U)：
      lob = max_k 根长系数_k × cos(min(dθ × toes / 2, π/2)) ^ toe_w（dθ = 到第 k 条根方向的角距）；
      nose：U < nose 时根头按半径 nose 的圆弧收回（根伸出量减 nose − √(nose² − (nose − U)²)：地面处根头圆、根底不是平台）。
    toe_az = 每条根的方位角（度，0 = 正面 +S、90 = +E；不给 = 均匀 + 抖动），toe_len = 每条根的长度系数（0–1，乘伸出量）。
    levels = 圈的高度列表（厘米，从 −sink 到 h；底部要密：根头圆弧）。bend = 顶部中心偏移 (dE, dS)，按 (U / h)² 加。
    grooves = 竖槽条数（放在根与根之间），groove_top = (起, 止) 高度：槽深在这段里是 groove_depth，往下 / 往上渐隐。
    返回物体；物体上记 'axis'（中心线 5 个点的 (E, S, U)，veg.knothole 用）。"""
    rng = random.Random(seed)
    if toe_az is None:
        rot = rng.uniform(0, 360)
        toe_az = [rot + 360 * (k + rng.uniform(-0.2, 0.2)) / toes for k in range(toes)]
    toe_len = toe_len or [1.0] * len(toe_az)
    n = len(toe_az)
    # 方位角（0 = +S、90 = +E）→ 截面极角 th（从 +E 往 +S）：th = 90° − az
    toe_th = [math.radians(90 - a) for a in toe_az]
    groove_th = []
    srt = sorted(t % (2 * math.pi) for t in toe_th)
    for i in range(n):                                  # 槽在相邻两条根的正中间
        a, b = srt[i], srt[(i + 1) % n] + (2 * math.pi if i == n - 1 else 0)
        groove_th.append((a + b) / 2)
    groove_th = groove_th[:grooves] if grooves else []

    def centre(u):
        f = max(0.0, u / h) ** 2
        return base[0] + bend[0] * f, base[1] + bend[1] * f

    def lob(th):
        best = 0.0
        for t, ln in zip(toe_th, toe_len):
            d = abs(((th - t + math.pi) % (2 * math.pi)) - math.pi)
            best = max(best, ln * max(0.0, math.cos(min(d * n / 2, math.pi / 2))) ** toe_w)
        return best

    def gdepth(u):
        g0, g1 = groove_top
        if u < g0:
            return groove_depth * max(0.0, 1 - (g0 - u) / 50)
        if u > g1:
            return groove_depth * max(0.0, 1 - (u - g1) / 40)
        return groove_depth

    rings, vs, circ = [], [], []
    L, prev = 0.0, None
    for u in levels:
        uu = max(0.0, u)
        eE, eS = _interp(env, uu)
        cE, cS = _interp(core_tab, uu)
        cx, cy = centre(uu)
        nz = 1.0
        if uu < nose:
            cut = nose - math.sqrt(max(0.0, nose * nose - (nose - uu) ** 2))
        else:
            cut = 0.0
        if u < 0:                                       # 地下那圈：同 U = 0 再收一点（埋进地里，包围盒不往下拖）
            nz = 0.97
        gd = gdepth(uu)
        ring, per = [], 0.0
        for i in range(seg):
            th = 2 * math.pi * i / seg
            rc = _ell(cE, cS, th)
            re = _ell(eE, eS, th)
            ext = max(0.0, (re - rc) * lob(th) - cut)
            r = (rc + ext) * nz
            if gd:
                g = 0.0
                for gt in groove_th:
                    d = abs(((th - gt + math.pi) % (2 * math.pi)) - math.pi)
                    g = max(g, max(0.0, math.cos(min(d * 5.0, math.pi / 2))) ** 3)
                r *= 1 - gd * g
            ring.append(P(cx + r * math.cos(th), cy + r * math.sin(th), u))
        for i in range(seg):
            per += (ring[i] - ring[(i + 1) % seg]).length / K
        c = Vector((cx, cy, u))
        if prev is not None:
            L += (c - prev).length
        prev = c
        rings.append(ring)
        vs.append(L)
        circ.append(per)
    ob = veg._tube(name, m, rings, vs, circ)
    ob['axis'] = [(*centre(h * k / 4), h * k / 4) for k in range(5)]
    return ob


# ---------------- 叶形 ----------------
def outline_oak7(size, seg, width=0.36, depth=0.35, widest=0.85):
    """橡叶：沿叶长（x，叶柄 −size/2 → 叶尖 +size/2）两边各 3 个圆裂片 + 叶尖 1 个，裂片间凹进（不是绕中心一圈均匀分布的花瓣）。
    半宽 = width × size × 包络(t) × (1 − depth + depth × |sin(3.5πt)|)，t = 沿叶长 0–1；包络 = sin(πt^widest)^0.6（两头圆、偏叶尖处最宽）；
    |sin(3.5πt)| 的峰在 t = 1/7、3/7、5/7（每边 3 个裂片）和 1（叶尖），谷在 0、2/7、4/7、6/7。
    seg = 每边点数（取 3 的倍数 + 0：每半个裂片周期 3 点，采得到峰和谷；21 → 一圈 42 点、叶片 168 三角形）。原点 = 叶中心。
    参考四视图 veg_tree_oak_1 正视图正中那片浅色橡叶：长 ~75 像素、宽 ~55（宽 / 长 ~0.7）、每边 3 个裂片。
    depth ≤ 0.35：从叶中心扇形三角化（veg.leaf）时三角形不翻（0.42 有 2 个翻面，导出的叶片有一片有符号体积为负）。"""
    n = max(6, seg)
    side = []
    for k in range(n + 1):
        t = k / n
        env = math.sin(math.pi * t ** widest) ** 0.6 if 0 < t < 1 else 0.0
        hw = width * size * env * (1 - depth + depth * abs(math.sin(3.5 * math.pi * t)))
        side.append(((t - 0.5) * size, hw))
    pts = [(x, y) for x, y in side[1:-1]]                     # 一边：叶柄 → 叶尖（两个端点单独放一次）
    pts = [side[0]] + pts + [side[-1]] + [(x, -y) for x, y in reversed(side[1:-1])]
    return pts, (0.0, 0.0)


def install_shapes():
    """veg._outline 认 'oak7'（包一层，别的形状照旧）。重复调用不重复包。"""
    if getattr(veg._outline, '_oak7', False):
        return
    orig = veg._outline

    def outline(shape, size, seg):
        if shape == 'oak7':
            return outline_oak7(size, seg)
        return orig(shape, size, seg)
    outline._oak7 = True
    veg._outline = outline


def placed_leaf(name, puffs, m, c, d, size=50, shape='oak7', seg=21, spin=0.0, thick=2.5, cup_r=80.0, sink=1.5, tree=None):
    """按方向放一片叶（不随机散）：从 c + d × 600 往 c（(E, S, U) 厘米）打射线，打到 puffs 最外层表面的点放叶，
    再沿法线整片推出到不被鼓包顶穿（同 veg.puff_leaves(conform=False) 的做法）。返回叶片物体；没打中返回 None。
    用途：参考图轮廓边上那种侧面贴着的叶（随机散布时轮廓最外沿的叶常被"悬空"自查去掉）。"""
    tree = tree or veg._bvh(puffs)
    dd = veg.D(*d).normalized()
    hit = veg._raycast(None, P(*c) + dd * 600 * K, -dd, tree)
    if hit is None:
        return None
    p, nrm = hit
    nn = veg.dir_esu(nrm)
    ob = veg.leaf(name, m, veg.to_esu(p), nn, size=size, shape=shape, thick=thick, spin=spin, seg=seg, sink=sink, cup_r=cup_r)
    nb = nrm.normalized()
    deep = 0.0
    for v in ob.data.vertices:
        w = ob.matrix_world @ v.co
        loc = tree.ray_cast(w + nb * 60 * K, -nb, 60 * K)[0]
        if loc is not None:
            deep = max(deep, (loc - w).dot(nb))
    if deep > 0:
        for v in ob.data.vertices:
            v.co += ob.matrix_world.inverted().to_3x3() @ (nb * (deep + 0.3 * K))
    return ob


def _obj_bvh(o):
    from mathutils.bvhtree import BVHTree
    mw = o.matrix_world
    return BVHTree.FromPolygons([mw @ v.co for v in o.data.vertices], [list(p.vertices) for p in o.data.polygons])


def clear_leaves(leaves, puffs, step=0.5, max_push=12.0):
    """叶片和叶簇三角形还相交的（puff_leaves 只按叶片顶点沿法线查顶穿，顶点之间的面还会被鼓包顶穿）：
    整片沿叶片平均法线每次推 step 厘米、最多 max_push，推不开就删；叶与叶相交的删后一片。
    返回 (留下的叶, {'pushed': 推过的片数, 'dropped_puff': 推不开删掉的, 'dropped_leaf': 叶叶相交删掉的})。"""
    import bpy
    from mathutils import Vector as V3
    ptree = veg._bvh(puffs)
    st = {'pushed': 0, 'push_cm': [], 'dropped_puff': 0, 'dropped_leaf': 0}
    keep = []
    for o in leaves:
        me = o.data
        # 推的方向：叶心（veg.leaf 的第 0 个顶点 = 上面中心）离最近簇表面点的方向
        c = o.matrix_world @ me.vertices[0].co
        loc, nrm, _, _ = ptree.find_nearest(c)
        nw = V3((0, 0, 1)) if loc is None else ((c - loc).normalized() if (c - loc).length > 1e-6 else nrm)
        moved = 0.0
        while _obj_bvh(o).overlap(ptree) and moved < max_push:
            for v in me.vertices:
                v.co += o.matrix_world.inverted().to_3x3() @ (nw * step * K)
            moved += step
        if _obj_bvh(o).overlap(ptree):
            bpy.data.objects.remove(o)
            st['dropped_puff'] += 1
            continue
        if moved:
            st['pushed'] += 1
            st['push_cm'].append(moved)
        keep.append(o)
    out = []
    for o in keep:
        b = _obj_bvh(o)
        if any(b.overlap(_obj_bvh(q)) for q in out):
            bpy.data.objects.remove(o)
            st['dropped_leaf'] += 1
            continue
        out.append(o)
    return out, st
