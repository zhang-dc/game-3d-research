"""花椰菜树冠（2026-10-23 橡树第 4 版；用户："参考图应该是花椰菜一样的团，加一些有厚度的叶片"）。

一个叶簇 = 三层球：簇芯（压扁大球）→ 中圆瓣（簇表面朝外的一圈，簇外沿读成一圈波浪）→ 小花球（铺在每个中瓣朝外那面）。
所有球合成一个体（体素重构 = 布尔并，球与球之间留下真的凹缝），再减面、平滑着色。法线就是网格自己的（第 1 版 cauli 用代理法线把小包压平了）；
缝里的暗靠 flat.shade 的遮挡射线自己出来。
坐标 / 单位同 bkit.core：P(E, S, U) 厘米，K = 0.01。
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from mathutils import Vector

from bkit.core import K, P

LOBE_IN = 0.85     # 中瓣中心在簇表面往里 LOBE_IN × 瓣半径（小 = 瓣鼓出来多）
FLORET_IN = 0.55   # 小花球中心在瓣表面往里 FLORET_IN × 花球半径（小 = 花球鼓出来多、球间缝深）


def _fib(n):
    """单位球面上 n 个均匀方向（E, S, U）。"""
    out = []
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n
        a = i * math.pi * (3 - math.sqrt(5))
        q = math.sqrt(max(0.0, 1 - z * z))
        out.append(Vector((q * math.cos(a), q * math.sin(a), z)))
    return out


def floret_spheres(c, r, squash=0.85, rng=random, lobe_k=0.55, lobe_n=None, floret_r=16.0, down=-0.35, outward=None):
    """一簇的球列表 [(中心 Vector (E, S, U), 半径)]（厘米）。
    c, r = 簇中心 / 半径；squash = 竖向压扁；lobe_k = 中瓣半径 / 簇半径；lobe_n = 中瓣数（不给按面积）；
    floret_r = 小花球半径（参考正视图量的 11–18 厘米）；down = 朝下多少以下的方向不放瓣 / 花球（簇底看不见，省面）；
    outward = 树冠中心（给了：朝树冠里面的瓣也不放）。"""
    c = Vector(c)
    sph = [(c.copy(), r * 0.78)]                                  # 簇芯（体素前按 squash 压，见下）
    lr = r * lobe_k
    n = lobe_n or max(5, round(4 * math.pi * r * r / (math.pi * lr * lr) * 0.55))
    lobes = []
    for d in _fib(n * 2):
        if d.z < down:
            continue
        if outward is not None:
            o = (c - Vector(outward))
            if o.length > 1e-6 and d.dot(o.normalized()) < -0.35:
                continue
        d = (d + Vector((rng.uniform(-.15, .15), rng.uniform(-.15, .15), rng.uniform(-.1, .1)))).normalized()
        lc = c + d * (r - lr * LOBE_IN)
        lrr = lr * rng.uniform(0.85, 1.12)
        lobes.append((lc, lrr, d))
        sph.append((lc, lrr))
    for lc, lrr, d in lobes:
        m = max(6, round(2 * math.pi * lrr * lrr / (math.pi * floret_r * floret_r) * 0.9))
        for fd in _fib(m * 2):
            if fd.dot(d) < 0.05 or fd.z < down:
                continue
            fr = floret_r * rng.uniform(0.8, 1.2)
            sph.append((lc + fd * (lrr - fr * FLORET_IN), fr))
    return sph, squash


def floret_puff(name, m, c, r, squash=0.85, seed=0, floret_r=16.0, voxel=3.0, ratio=None, target=None, outward=None,
                lobe_k=0.55, down=-0.35):
    """一簇花椰菜：球 → 一个网格（UV 球拼起来）→ 体素重构合成一体 → 减面到 target 个三角形 → 平滑着色。返回物体。
    voxel = 体素边长（厘米）；ratio / target = 减面比例 / 目标三角形数（都不给不减）。"""
    rng = random.Random(seed)
    sph, sq = floret_spheres(c, r, squash, rng, lobe_k=lobe_k, floret_r=floret_r, outward=outward, down=down)
    bm = bmesh.new()
    cv = Vector(c)
    for p, s in sph:
        seg = 16 if s > 30 else 10
        res = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=max(6, seg // 2 + 1), radius=s * K)
        q = p - cv
        q.z *= sq
        off = P(*(cv + q))
        bmesh.ops.scale(bm, vec=(1, 1, sq if s > 30 else 1.0), verts=res['verts'])
        bmesh.ops.translate(bm, vec=off, verts=res['verts'])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(m)
    rm = ob.modifiers.new('rm', 'REMESH')
    rm.mode = 'VOXEL'
    rm.voxel_size = voxel * K
    rm.adaptivity = 0.0
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier='rm')
    if target or ratio:
        n = len(ob.data.polygons) * 2
        dm = ob.modifiers.new('dec', 'DECIMATE')
        dm.ratio = ratio if ratio else min(1.0, target / max(1, n))
        bpy.ops.object.modifier_apply(modifier='dec')
    for pl in ob.data.polygons:
        pl.use_smooth = True
    ob['flat_done'] = 1
    return ob, len(sph)


def cluster_leaves(name, puffs, centers, m, n_total=36, size=66, shape='oak7', seg=21, thick=7.0, seed=0, up=-0.25,
                   blend=0.6, sink=2.0, min_dist=60.0):
    """厚橡叶搁在花椰菜簇的花球顶上：每簇按 半径² 分 n_total 片；方向 d 在簇的朝外半球（d.z ≥ up）均匀取，
    从 c + d × 2r 朝簇心打射线打到本簇表面，叶心放在打到的点上，叶面法线 = blend × d + (1 − blend) × 打到的面法线
    （读成贴着团的弧面、不顺小花球乱翻），叶按簇半径弯（cup_r）、往里埋 sink 厘米。
    叶心离已有叶 < min_dist 的跳过。centers = [(E, S, U, r)]（厘米）。返回叶片列表。"""
    from mathutils.bvhtree import BVHTree
    from bkit import veg
    rng = random.Random(seed)
    tot = sum(r * r for *_, r in centers)
    out, placed = [], []
    for k, (ob, (e, s, u, r)) in enumerate(zip(puffs, centers)):
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bm.transform(ob.matrix_world)
        tree = BVHTree.FromBMesh(bm)
        bm.free()
        c = Vector((e, s, u))
        want = max(1, round(n_total * r * r / tot))
        dirs = [d for d in _fib(want * 6) if d.z >= up]
        rng.shuffle(dirs)
        got = 0
        for d in dirs:
            if got >= want:
                break
            o = P(*(c + d * 2 * r))
            hit = tree.ray_cast(o, (P(*c) - o).normalized(), 3 * r * K)
            if hit[0] is None:
                continue
            p = Vector((-hit[0].x / K, hit[0].y / K, hit[0].z / K))     # Blender → (E, S, U) 厘米
            if any((p - q).length < min_dist for q in placed):
                continue
            hn = Vector((-hit[1].x, hit[1].y, hit[1].z))
            nn = (d * blend + hn * (1 - blend)).normalized()
            lf = veg.leaf(f'{name}_{k:02d}_{got}', m, tuple(p), tuple(nn), size=size * rng.uniform(0.85, 1.15), shape=shape,
                          thick=thick, spin=rng.uniform(0, 360), seg=seg, sink=sink, cup_r=r)
            out.append(lf)
            placed.append(p)
            got += 1
    return out
