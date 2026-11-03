"""贴图试验 A · 茅草房的组件（照 bkit.components 同名组件改：尺寸 / 铰链 / 部件约定不变，换成圆角木料 + 板缝 + 一整根茅草拱罩）。
随机数：base / chimney 直接用 bkit.components（石块长短 / 深浅同定稿）；这里的组件不用全局 random（纹槽用自己的 Random）。"""
from __future__ import annotations

import math
import random

import numpy as np
from mathutils import Matrix

import sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))))  # -> import bkit
from bkit.core import P, arch_panel, boolean_cut, box, created_since, make_part, reuv, snapshot  # noqa: E402
from bkit import flat as F  # noqa: E402

RNG = random.Random(23)                                 # 木料纹槽位置


def walls(M, E=190, S=120, U=(56, 200), cell=32, **frame_kw):
    """墙身（切格子，顶点色才有檐下 / 墙角渐变）+ 木构架。"""
    before = snapshot()
    F.grid_box('wall', (-E, E), (-S, S), U, M['plaster'], cell=cell)
    timber_frame(M, E, S, post_u0=U[0], **frame_kw)
    return created_since(before)


def timber_frame(M, E=190, S=120, post_u0=56, plate=(158, 182), post=(31, 29), post_out=2, beam_u=(152, 176),
                 brace_u=(124, 166), brace_in=24, brace_reach=(64, 56), brace_out=3, brace_w=12):
    """同 components.timber_frame 的件和尺寸，每根换成圆角方木 + 顺纹浅槽（F.bar / F.bar_between）。"""
    e, s = E, S
    PL = plate
    T = M['timber']
    pe, ps = post
    for ss in (-1, 1):
        F.bar(f'plateS{ss}', (-e - 4, e + 4), sorted((ss * (s - 4), ss * (s + 9))), PL, T, rng=RNG)
    for se in (-1, 1):
        F.bar(f'plateE{se}', sorted((se * (e - 4), se * (e + 9))), (-s - 4, s + 4), PL, T, rng=RNG)
    for se in (-1, 1):
        for ss in (-1, 1):
            F.bar(f'post{se}{ss}', sorted((se * (e - pe), se * (e + post_out))), sorted((ss * (s - ps), ss * (s + post_out))),
                  (post_u0, PL[1]), T, rng=RNG, axis='U')
            # 两向梁头：沿 S 那根比沿 E 那根窄 0.6（原版两根外表面共面，打光有黑点）
            F.bar(f'beamE{se}{ss}', sorted((se * (e - 30), se * (e + 14))), sorted((ss * (s - 6), ss * (s + 6))), beam_u, T, rng=RNG,
                  axis='E')
            F.bar(f'beamS{se}{ss}', sorted((se * (e - 5.4), se * (e + 5.4))), sorted((ss * (s - 30), ss * (s + 14))),
                  (beam_u[0] + 0.6, beam_u[1] - 0.6), T, rng=RNG, axis='S')
    ra, rb = brace_reach
    for ss in (-1, 1):
        for se in (-1, 1):
            F.bar_between(f'braceS{se}{ss}', (se * (e - brace_in), ss * (s + brace_out), brace_u[0]),
                          (se * (e - ra), ss * (s + brace_out), brace_u[1]), brace_w, T, rng=RNG)
            F.bar_between(f'braceE{se}{ss}', (se * (e + brace_out), ss * (s - brace_in), brace_u[0]),
                          (se * (e + brace_out), ss * (s - rb), brace_u[1]), brace_w, T, rng=RNG)


def window(name, E, U, S0, M, out=1, shutters=True, side=None, flowerbox=False, frame_w=7, shutter_angle=178):
    """同 components.window（尺寸、铰链、部件 id 不变）：百叶换成三块竖板（板缝）+ 圆角横档，花箱圆角木板、叶丛 / 花细分高一级。
    十字窗棂横的那根比竖的薄 0.5（原版共面，打光有黑点）。"""
    def b(nm, e, u, d0, d1, m, bev=0.0):
        if side is None:
            return box(nm, e, sorted((S0 + out * d0, S0 + out * d1)), u, m, bevel=bev)
        sg = 1 if side == 'E' else -1
        return box(nm, sorted((S0 + sg * d0, S0 + sg * d1)), e, u, m, bevel=bev)

    def bb(nm, e, u, d0, d1, m, **kw):
        if side is None:
            return F.bar(nm, e, sorted((S0 + out * d0, S0 + out * d1)), u, m, **kw)
        sg = 1 if side == 'E' else -1
        return F.bar(nm, sorted((S0 + sg * d0, S0 + sg * d1)), e, u, m, **kw)

    def blob_at(nm, x, d, u, rx, ry, rz, m, sub=2):
        if side is None:
            return F.blob(nm, (x, S0 + out * d, u), rx, ry, rz, m, sub=sub)
        sg = 1 if side == 'E' else -1
        return F.blob(nm, (S0 + sg * d, x, u), ry, rx, rz, m, sub=sub)
    before = snapshot()
    parts = []
    e0, e1 = E
    u0, u1 = U
    f = frame_w
    b(f'{name}_glass', E, U, 0, 2, M['glass'])
    b(f'{name}_frT', (e0 - f, e1 + f), (u1, u1 + f), 0, 6, M['frame'], 2.0)
    b(f'{name}_frB', (e0 - f - 3, e1 + f + 3), (u0 - f, u0), 0, 8, M['frame'], 2.0)
    b(f'{name}_frL', (e0 - f, e0), U, 0, 6, M['frame'], 1.5)
    b(f'{name}_frR', (e1, e1 + f), U, 0, 6, M['frame'], 1.5)
    em, um = (e0 + e1) / 2, (u0 + u1) / 2
    b(f'{name}_mV', (em - 2, em + 2), U, 0, 4, M['frame'], 0.8)
    b(f'{name}_mH', E, (um - 2, um + 2), 0, 3.5, M['frame'], 0.8)
    if shutters:
        w = (e1 - e0) * 0.42
        for k, (a, c) in enumerate(((e0 - f - w - 2, e0 - f - 2), (e1 + f + 2, e1 + f + w + 2))):
            before_k = snapshot()
            bb(f'{name}_sh{k}', (a, c), (u0 - 4, u1 + 6), 0.5, 8.5, M['shutter'], plank=w / 3, axis='U', rc=2.0)
            for j in (0.3, 0.7):
                uu = u0 - 4 + j * (u1 + 10 - u0)
                bb(f'{name}_shb{k}{j}', (a + 2, c - 2), (uu - 2.5, uu + 2.5), 8.0, 10.8, M['shutter'], grooves=False, rc=1.2)
            inner = c if k == 0 else a
            sgn = -1 if k == 0 else 1
            if side is None:
                hinge, d, n = P(inner, S0 + out * 9, u0 - 4), (-sgn, 0), (0, out)
            else:
                sg = 1 if side == 'E' else -1
                hinge, d, n = P(S0 + sg * 9, inner, u0 - 4), (0, sgn), (-sg, 0)
            parts.append(make_part(f'shutter_{name}_{k}', created_since(before_k), hinge, d, n, shutter_angle))
    if flowerbox:
        bb(f'{name}_box', (e0 - 33, e1 + 23), (u0 - 50, u0 - 10), 0, 22, M['flowerbox'], plank=10, axis='E', rc=3.0)
        for i in range(7):
            x = e0 - 28 + i * ((e1 - e0 + 46) / 6)
            if side is None:
                blob_at(f'{name}_leaf{i}', x, 12, u0 - 6, 11, 9, 8, M['leaf'])
            if i % 2 == 0 and side is None:
                blob_at(f'{name}_fl{i}', x + 4, 18, u0 + 2, 6, 3, 5, M['petal'])
                blob_at(f'{name}_flc{i}', x + 4, 21, u0 + 2, 2.5, 1.5, 2.5, M['petal_c'], sub=1)
    return [o for o in created_since(before) if o not in parts] + parts


def door(M, E=(-117, 3), U=(40, 172), S0=120, inset=16, win=((-77, -37), (95, 139)), knob=(-89, 83), angle=100, planks=4):
    """同 components.door（门框 / 门洞 / 门扇部件 / 小窗挖穿 / 里外压条 / 里外把手都在），门扇两面按 planks 块竖板开板缝。"""
    before = snapshot()
    arch_panel('door_frame', E, U, (S0, S0 + 7), M['frame'])
    inner = (E[0] + inset, E[1] - inset)
    arch_panel('door_hole', (inner[0] - 2, inner[1] + 2), (U[0], U[1] - 10), (S0 + 7, S0 + 7.5), M['void'])
    before_leaf = snapshot()
    s0, s1 = S0 + 7.6, S0 + 15.6
    leaf_ob = arch_panel('door', inner, (U[0], U[1] - 12), (s0, s1), M['door'], seg=12)
    xs = [-(inner[0] + (inner[1] - inner[0]) * k / planks) for k in range(1, planks)]   # Blender x = −E
    F.plank_grooves(leaf_ob, xs, axis=0, width=1.3, depth=1.4, face_axis=1)
    if win is not None:
        WE, WU = win
        cut = box('door_cut', WE, (s0 - 2, s1 + 2), WU, M['dark'])
        boolean_cut(leaf_ob, cut)
        reuv(leaf_ob, M['door'])
        sm = (s0 + s1) / 2
        box('door_glass', WE, (sm - 0.5, sm + 0.5), WU, M['glass'])
        wm, hm = (WE[0] + WE[1]) / 2, (WU[0] + WU[1]) / 2
        box('door_mV', (wm - 2, wm + 2), (s0 + 1, s1 - 1), WU, M['frame'])
        box('door_mH', WE, (s0 + 1.3, s1 - 1.3), (hm - 2, hm + 2), M['frame'])
        tw = 5
        for k, (a_, b_) in enumerate((((WE[0] - tw, WE[1] + tw), (WU[1], WU[1] + tw)), ((WE[0] - tw, WE[1] + tw), (WU[0] - tw, WU[0])),
                                      ((WE[0] - tw, WE[0]), WU), ((WE[1], WE[1] + tw), WU))):
            box(f'door_trimO{k}', a_, (s1, s1 + 2), b_, M['frame'])
            box(f'door_trimI{k}', a_, (s0 - 2, s0), b_, M['frame'])
    F.blob('door_knob', (knob[0], s1 + 4, knob[1]), 4, 4, 4, M['metal'])
    F.blob('door_knob_in', (knob[0], s0 - 3, knob[1]), 3.5, 3.5, 3.5, M['metal'])
    leaf_ob.data.polygons.foreach_set('use_smooth', [False] * len(leaf_ob.data.polygons))
    part = make_part('door', created_since(before_leaf), P(inner[1], S0 + 11.6, U[0]), (1, 0), (0, 1), angle)
    return [o for o in created_since(before) if o is not part] + [part]


def dormer(M, side=1, E=5, tilt=22, s_face=160, s_back=95, U=(222, 322), half=52, glass=((-30, 30), (240, 300)), hood=(62, 282)):
    """同 components.dormer，茅草拱罩从 11 个圆鼓块换成一整根带横棱的圆卷（F.hood_roll）。"""
    sg, ec = side, E
    before = snapshot()
    u0, u1 = U
    S = sorted((sg * s_back, sg * s_face))
    ge, gu = (ec + glass[0][0], ec + glass[0][1]), glass[1]
    box(f'dorm_body{sg}', (ec - half, ec + half), S, (u0, u1), M['plaster'])
    arch_panel(f'dorm_frame{sg}', (ec - (half - 2), ec + (half - 2)), (u0, u1 + 4), sorted((sg * s_face, sg * (s_face + 6))), M['frame'],
               seg=16)
    arch_panel(f'dorm_glass{sg}', ge, gu, sorted((sg * (s_face + 6), sg * (s_face + 7))), M['glass'], seg=16)
    box(f'dorm_mV{sg}', (ec - 2, ec + 2), sorted((sg * (s_face + 6), sg * (s_face + 9))), gu, M['frame'])
    gm = (gu[0] + gu[1]) / 2
    box(f'dorm_mH{sg}', ge, sorted((sg * (s_face + 6), sg * (s_face + 8.5))), (gm - 2, gm + 2), M['frame'])
    R, cu = hood
    F.hood_roll(f'dorm_hood{sg}', M['thatch'], ec, sg * (s_face + 4), R, cu, rad=(15.5, 14), seg=10, n=28)
    piv = P(ec, sg * s_face, u0)
    T = Matrix.Translation(piv) @ Matrix.Rotation(sg * math.radians(tilt), 4, 'X') @ Matrix.Translation(-piv)
    objs = created_since(before)
    for ob in objs:
        ob.data.transform(T)
    return objs


def barrel(M, E=(-197, -134), U=(7, 92), S=161):
    """同 components.barrel：桶身换成 12 块桶板（板间竖槽），铁箍平滑，叶丛 / 花细分高一级。"""
    before = snapshot()
    Sc = S
    ec = (E[0] + E[1]) / 2
    r = (E[1] - E[0]) / 2 - 4
    top = U[1] - 22
    F.staved_barrel('barrel', (ec, Sc), r, (U[0], top), M['barrel'])
    for k, u in enumerate((U[0] + 14, top - 14)):
        F.cylinder(f'hoop{k}', (ec, Sc), r * 1.06 + 1.5, (u - 3, u + 3), M['hoop'])
    for i in range(6):
        a = i / 6 * 2 * math.pi
        F.blob(f'bleaf{i}', (ec + r * 0.55 * math.cos(a), Sc + r * 0.55 * math.sin(a), top + 8), 15, 15, 11, M['leaf'])
    for i, (dx, ds) in enumerate(((-10, 6), (8, 10), (0, -6), (14, -2))):
        F.blob(f'bfl{i}', (ec + dx, Sc + ds, top + 20), 7, 7, 3, M['petal'])
        F.blob(f'bflc{i}', (ec + dx, Sc + ds, top + 23), 2.5, 2.5, 1.5, M['petal_c'], sub=1)
    return created_since(before)
