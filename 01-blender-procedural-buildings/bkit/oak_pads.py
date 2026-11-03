"""叶片叠成的树冠团（2026-10-23 橡树第 5 版；评审："参考图的花椰菜形状不是真的花椰菜，是叶子拼出来的"）。

放大参考正视图看：一个叶簇 = 一层层有厚度的扇贝边叶片（边缘一圈圆弧瓣），像瓦片一样从顶往下叠成圆顶，
上一层的下沿盖住下一层的上沿，层与层之间是台阶；大浅色橡叶搁在最上面。
这里：簇 = 圆顶（椭球）+ 按层（从顶往下）排的叶片 pad：每片是扇贝边的厚圆片（上面微鼓、边缘圆角往下收、底面平），
贴着圆顶放、下沿往外翘一点（瓦片式）；里面一个暗色芯挡住缝。
坐标 / 单位同 bkit.core：P(E, S, U) 厘米，K = 0.01。
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from bkit.core import K, P


def _outline(phi, lobes, depth, phase):
    """扇贝边：半径系数（1 = 瓣尖），lobes 个圆瓣，瓣间凹进 depth。"""
    c = abs(math.cos((phi + phase) * lobes / 2))
    return 1 - depth + depth * c ** 0.5


def pad_mesh(bm, rho, thick, bulge, lobes=8, depth=0.14, seg=48, rows=5, phase=0.0, rim=0.25):
    """在 bm 里加一片叶片（局部坐标：z 朝外，xy 是叶面，原点 = 叶面底中心），返回新顶点。
    rho = 半径（瓣尖），thick = 边缘厚度，bulge = 中心比边缘高多少，rim = 边缘圆角占半径的比例。"""
    verts = []
    top = [bm.verts.new((0, 0, thick + bulge))]
    ring_t = [i / rows for i in range(1, rows + 1)]
    rings = []
    for t in ring_t:
        ring = []
        for j in range(seg):
            phi = 2 * math.pi * j / seg
            r = rho * _outline(phi, lobes, depth, phase)
            # 上面：中心鼓 bulge，往外按 (1 − t²) 落；最外一圈 = 圆角开始
            tt = t * (1 - rim * 0.5)
            z = thick + bulge * (1 - tt * tt)
            ring.append(bm.verts.new((math.cos(phi) * r * tt, math.sin(phi) * r * tt, z)))
        rings.append(ring)
    # 圆角：从上面边缘绕到侧边中线、再到底面（3 步）
    for a in (0.5, 1.0):
        ring = []
        for j in range(seg):
            phi = 2 * math.pi * j / seg
            r = rho * _outline(phi, lobes, depth, phase)
            rr = r * (1 - rim * 0.5 * (1 - math.sin(a * math.pi / 2)))
            z = thick * 0.5 + thick * 0.5 * math.cos(a * math.pi / 2)
            ring.append(bm.verts.new((math.cos(phi) * rr, math.sin(phi) * rr, z)))
        rings.append(ring)
    ring = []
    for j in range(seg):
        phi = 2 * math.pi * j / seg
        r = rho * _outline(phi, lobes, depth, phase) * (1 - rim * 0.5)
        ring.append(bm.verts.new((math.cos(phi) * r, math.sin(phi) * r, 0)))
    rings.append(ring)
    bot = bm.verts.new((0, 0, 0))
    for j in range(seg):
        k = (j + 1) % seg
        bm.faces.new((top[0], rings[0][j], rings[0][k]))
    for a, b in zip(rings[:-1], rings[1:]):
        for j in range(seg):
            k = (j + 1) % seg
            bm.faces.new((a[j], b[j], b[k], a[k]))
    for j in range(seg):
        k = (j + 1) % seg
        bm.faces.new((rings[-1][k], rings[-1][j], bot))
    verts = top + [v for r in rings for v in r] + [bot]
    return verts


def pad_cluster(name, m, c, R, squash=0.85, seed=0, tiers=((0, 1, 0.52), (36, 6, 0.42), (66, 9, 0.38), (96, 10, 0.34)),
                thick=7.0, bulge=6.0, lobes=(7, 10), depth=0.14, tilt=14.0, seg=48, rows=4, inset=0.10, outward=None,
                core_m=None, core_k=0.86, core_sub=2, others=(), bury=0.92, pad_edge=0.5):
    """一簇：tiers = [(离顶的角度 θ°, 片数, 片半径 / R)]，θ 从 0（顶）往下；每片放在圆顶 (R, R, R·squash) 上，
    叶面法线 = 圆顶法线、再绕水平切线把下沿往外翘 tilt°；片的底面往圆顶里埋 inset × R（上层压下层）。
    outward = 树冠中心 (E, S, U)：朝里面（被别的簇挡住）的片不放。core_m = 暗芯材质（椭球 core_k × 圆顶）。返回 [片网格, 芯]。"""
    rng = random.Random(seed)
    c = Vector(c)
    bm = bmesh.new()
    lay = bm.verts.layers.float.new('puff_k')            # 先建好（中途新建层会让已有顶点引用失效）
    npad = 0
    frames = []                                       # 每片的 (层号, 叶面上表面中心 (E, S, U), 法线 (E, S, U), 半径)：放橡叶用
    for ti, (th_deg, n, rk) in enumerate(tiers):
        th = math.radians(th_deg)
        n = max(1, n)
        off = rng.uniform(0, 2 * math.pi)
        for i in range(n):
            ph = off + 2 * math.pi * i / n + rng.uniform(-0.12, 0.12) * (n > 1)
            th_i = th + math.radians(rng.uniform(-4, 4)) * (th_deg > 0)
            d = Vector((math.sin(th_i) * math.cos(ph), math.sin(th_i) * math.sin(ph), math.cos(th_i)))
            if outward is not None and th_deg > 0:
                o = c - Vector(outward)
                if o.length > 1e-6 and d.dot(o.normalized()) < -0.3:
                    continue
            p = c + Vector((d.x * R, d.y * R, d.z * R * squash))
            # 埋在别的团里面（看不见）的片不放：others = [(中心, 半径, squash)]，片心在 bury × 那团椭球里就跳过
            if any(((p.x - oc[0]) / (orr * bury)) ** 2 + ((p.y - oc[1]) / (orr * bury)) ** 2 + ((p.z - oc[2]) / (orr * osq * bury)) ** 2 < 1
                   for oc, orr, osq in others):
                continue
            nrm = Vector((d.x / R, d.y / R, d.z / (R * squash))).normalized()
            # 叶面局部框架：z = 法线；x = 沿经线往下（下沿方向）
            down = Vector((0, 0, -1))
            xa = (down - nrm * down.dot(nrm))
            xa = xa.normalized() if xa.length > 1e-4 else Vector((1, 0, 0))
            ya = nrm.cross(xa).normalized()
            rot = Matrix((xa, ya, nrm)).transposed().to_4x4()
            rot = rot @ Matrix.Rotation(math.radians(-tilt) if th_deg > 0 else 0, 4, 'Y')   # 下沿（+x）往外翘
            rho = R * rk * rng.uniform(0.9, 1.1)
            vs = pad_mesh(bm, rho, thick, bulge, lobes=rng.randint(*lobes), depth=depth, seg=seg, rows=rows,
                          phase=rng.uniform(0, 1))
            base = p - nrm * (inset * R)
            mtx = Matrix.Translation(base) @ rot
            # 每片叶片自己的明暗（评审 2026-10-23："每一层的明暗更明显一点"）：点属性 puff_k（flat.shade 的凹沟项按 1 − puff_k 压暗）
            # = 叶面中心 1、往边缘按 (r / rho)² 落、侧边 / 底面按高度落到 0 → 一层压一层的地方下沿一道暗边
            top = thick + bulge
            for v in vs:
                rr = math.hypot(v.co.x, v.co.y) / max(rho, 1e-6)
                v[lay] = max(0.0, min(1.0, (v.co.z / top) ** 1.5 * (1 - pad_edge * min(1.0, rr) ** 2)))
            for v in vs:
                w = mtx @ v.co
                v.co = P(*w)
            npad += 1
            nz = (mtx.to_3x3() @ Vector((0, 0, 1))).normalized()
            frames.append((ti, mtx @ Vector((0, 0, thick + bulge)), nz, rho))
    me = bpy.data.meshes.new(name)
    # P() 把 E 取反（镜像），面的绕向跟着反了 → 法线朝里（2026-10-24 两个子任务查出橡树 22 个网格有符号体积为负）：按外侧重算
    bm.normal_update()                                # 先刷新面法线缓存（不刷新时 recalc 按旧法线判断，离原点远的团翻不过来）
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(m)
    for pl in ob.data.polygons:
        pl.use_smooth = True
    ob['flat_done'] = 1
    out = [ob]
    if core_m is not None:
        cb = bmesh.new()
        bmesh.ops.create_icosphere(cb, subdivisions=core_sub, radius=1)
        for v in cb.verts:
            v.co = P(c.x + v.co.x * R * core_k, c.y + v.co.y * R * core_k, c.z + v.co.z * R * squash * core_k)
        cm = bpy.data.meshes.new(name + '_core')
        cb.normal_update()
        bmesh.ops.recalc_face_normals(cb, faces=cb.faces)
        cb.to_mesh(cm)
        cb.free()
        co = bpy.data.objects.new(name + '_core', cm)
        bpy.context.collection.objects.link(co)
        co.data.materials.append(core_m)
        for pl in co.data.polygons:
            pl.use_smooth = True
        co['flat_done'] = 1
        out.append(co)
    return out, npad, frames


def pad_leaves(name, frames, m, n_total=30, size=66, shape='oak7', seg=21, thick=7.0, seed=0, max_tier=1, lift=1.5,
               min_dist=60.0):
    """浅色橡叶搁在叶片正中：从 frames（pad_cluster 返回的，各簇合起来）里挑层号 ≤ max_tier 的片，随机取 n_total 片，
    叶面 = 那片的上表面中心 + 法线方向抬 lift 厘米，按片半径的 3 倍弯（cup_r）。不查顶穿（上一层叶片压住橡叶边 = 参考图那样叶被叶片盖住一点）。"""
    from bkit import veg
    rng = random.Random(seed)
    cand = [f for f in frames if f[0] <= max_tier]
    rng.shuffle(cand)
    out, placed = [], []
    for ti, p, nz, rho in cand:
        if len(out) >= n_total:
            break
        if any((p - q).length < min_dist for q in placed):
            continue
        lf = veg.leaf(f'{name}_{len(out):02d}', m, tuple(p + nz * lift), tuple(nz), size=size * rng.uniform(0.85, 1.15), shape=shape,
                      thick=thick, spin=rng.uniform(0, 360), seg=seg, sink=0, cup_r=rho * 3)
        out.append(lf)
        placed.append(p)
    return out


def auto_tiers(R, squash=0.85, rho=28.0, overlap=1.35, th_max=120.0):
    """叶片按绝对尺寸 rho（厘米）铺：从顶往下每层间隔 ≈ rho × 1.25 / R 弧度，每层片数 = 这圈周长 / (rho × overlap)。
    大簇层数多、片数多，小簇只有一两层（评审 2026-10-23："每一团好像尺寸都差不多大"）。返回 tiers [(θ°, 片数, 片半径 / R)]。"""
    out = [(0, 1, min(0.7, rho * 1.1 / R))]
    dth = math.degrees(rho * 1.25 / R)
    th = dth
    while th <= th_max:
        circ = 2 * math.pi * R * math.sin(math.radians(th))
        n = max(3, round(circ / (rho * overlap)))
        out.append((th, n, rho / R))
        th += dth
    return out


def child_clumps(puffs, center=(0, 0, 290), n=(2, 4), k=(0.35, 0.6), seed=0, down=(-0.75, 0.15), min_r=22.0, total=None):
    """子团：每个主团 (E, S, U, R[, squash]) 朝外、偏下的表面上挂 n 个小团，半径 = k × R，中心在母团表面往里 0.35 × 子团半径。
    朝外 = 离树冠中心 center 的水平方向；竖直分量在 down 范围（下沿 / 侧边，参考图小团挂在下沿和两侧）。返回子团列表（同 puffs 格式）。"""
    rng = random.Random(seed)
    c0 = Vector(center)
    out = []
    for pf in puffs:
        e, s, u, R = pf[:4]
        sq = pf[4] if len(pf) > 4 else 0.85
        c = Vector((e, s, u))
        h = Vector((c.x - c0.x, c.y - c0.y, 0))
        h = h.normalized() if h.length > 1e-3 else Vector((1, 0, 0))
        for _ in range(rng.randint(*n)):
            a = rng.uniform(-1.1, 1.1)
            hd = Vector((h.x * math.cos(a) - h.y * math.sin(a), h.x * math.sin(a) + h.y * math.cos(a), 0))
            z = rng.uniform(*down)
            d = (hd * math.sqrt(max(0, 1 - z * z)) + Vector((0, 0, z))).normalized()
            r = max(min_r, R * rng.uniform(*k))
            p = c + Vector((d.x * R, d.y * R, d.z * R * sq)) - d * r * 0.35
            out.append((p.x, p.y, p.z, r, 0.9))
    if total is not None:                          # 只要 total 个：挑最靠下的（参考图小团挂在下沿）
        out = sorted(out, key=lambda q: q[2])[:total]
    return out
