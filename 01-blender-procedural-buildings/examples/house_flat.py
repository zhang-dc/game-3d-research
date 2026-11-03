"""贴图试验 A · 茅草房（只用颜色 + 明暗）。从 blender_house/house_s5.py 复制改的：尺寸常量原样，组件换成 flatkit / flatparts。

    blender -b --factory-startup --python examples/house_flat.py -- out/house_flat.glb
和定稿（build.sh s5 = MATS=mats/crop THATCH=band GEO=1 UNITS=m）的区别：
  - 没有平铺贴图 / 茅草带：每个材质 = materials.json 的四视图取色（sRGB → 线性）× 顶点色；
  - 顶点色明暗（flatkit.shade）：朝下、被遮挡（24 条半球射线，射线长 SHADE_DIST 像素）、茅草缕间的槽变暗，朝上稍亮；
  - 茅草层重新出网格（flatkit.thatch_tier）：剖面同定稿，加一缕一缕的竖向浅槽 + 下沿每缕一个草尖，平滑着色；
  - 木构架圆角方木 + 顺纹浅槽，百叶 / 门板 / 花箱板缝，桶板竖槽，老虎窗拱罩一整根圆卷；石基芯换深色砂浆色（石块缝）；
  - 其余（石块排布、烟囱、台阶、壁灯）同定稿组件，最后统一平滑着色（硬折角 > 48° 留硬边）；
  - 导出前 props.to_meters(70.6)（= 定稿 UNITS=m）。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))))  # -> import bkit
import bpy  # noqa: E402
from bkit import components as C, core, props, veg  # noqa: E402
from bkit import flat as F  # noqa: E402
from bkit import flat_parts as FP  # noqa: E402

random.seed(7)

# ---------------- 尺寸（同 house_s5.py） ----------------
BASE = dict(E=200, S=127, U=(0, 56))
WALL = dict(E=190, S=120, U=(56, 200))
FRAME = dict(plate=(158, 182), post=(31, 29), post_out=2, beam_u=(152, 176),
             brace_u=(124, 166), brace_in=24, brace_reach=(64, 56), brace_out=3, brace_w=12)
TIERS = [dict(U=(171, 236), E=247, S=165, tE=0.93, tS=0.87, r=18),
         dict(U=(231, 290), E=227, S=141, tE=0.84, tS=0.76, r=18),
         dict(U=(285, 350), E=191, S=106, tE=0.84, tS=0.71, r=18),
         dict(U=(345, 392), E=155, S=72, tE=0.72, tS=0.55, r=32)]
CHIM = dict(E=(-147, -79), S=(-37, 37), U=(320, 427))
DORMERS = [dict(side=1, E=5), dict(side=-1, E=-17)]
DORMER_TILT = 22
DOOR = dict(E=(-117, 3), U=(40, 172), win=((-77, -37), (95, 139)), knob=(-89, 83))
STEPS = dict(E=(-119, 3))
WIN_F = dict(E=(59, 116), U=(102, 149))
WIN_SIDE = dict(S=(-24, 26), U=(92, 147))
LANTERN = dict(E=(-167, -134), U=(105, 165))
BARREL = dict(E=(-197, -134), U=(7, 92), S=161)
PX_PER_M = 70.6

# ---------------- 这一版自己的参数 ----------------
THATCH = dict(strand=19, vps=2, groove=3.0, tip=5.0, rows_vis=6, rows_hid=1)   # 一缕 19 像素（27 厘米，2 列顶点：槽 + 脊）、槽深 3、草尖 5
MORTAR = [0.36, 0.32, 0.29]                            # 石块缝砂浆（四视图石基缝 p10 约 70/60/49 → 稍亮一点）
SHADE_DIST = 70                                        # 遮挡射线长（像素，约 1 米）
DARK = {                                               # 最暗处乘的颜色（线性），按材质族
    'thatch': (0.40, 0.27, 0.15), 'wood': (0.38, 0.30, 0.25), 'plaster': (0.50, 0.44, 0.40),
    'stone': (0.42, 0.42, 0.46), 'other': (0.42, 0.42, 0.45)}
FAMILY = {'f_thatch': 'thatch', 'f_timber': 'wood', 'f_door': 'wood', 'f_frame': 'wood', 'f_shutter': 'wood', 'f_barrel': 'wood',
          'f_flowerbox': 'wood', 'f_plaster': 'plaster', 'f_step': 'stone', 'f_mortar': 'stone'}


def family(ob):
    m = ob.data.materials[0].name.replace('_vc', '') if ob.data.materials else ''
    if m.startswith(('f_stone', 'f_chim')):
        return 'stone'
    return FAMILY.get(m, 'other')


def main():
    out = sys.argv[sys.argv.index('--') + 1]
    core.reset_scene()
    M = F.house_mats(override={'mortar': MORTAR})
    C.base(M, **BASE)                                  # 石块排布同定稿（random 顺序）
    bpy.data.objects['base_core'].data.materials[0] = M['mortar']
    FP.walls(M, **WALL, **FRAME)
    F.roof(M, TIERS, rng=random, **THATCH)
    C.chimney(M, **CHIM)
    for d in DORMERS:
        FP.dormer(M, **d, tilt=DORMER_TILT)
    FP.door(M, **DOOR, S0=WALL['S'])
    C.steps(M, **STEPS, S0=BASE['S'])
    FP.window('winF', WIN_F['E'], WIN_F['U'], WALL['S'], M, flowerbox=True)
    for sd, x in (('E', WALL['E']), ('-E', -WALL['E'])):
        FP.window(f'win{sd}', WIN_SIDE['S'], WIN_SIDE['U'], x, M, side=sd)
    C.lantern(M, **LANTERN, S0=WALL['S'])
    FP.barrel(M, **BARREL)
    C.roughen(wood=('post',), lean=('post',))           # 石块抖动 / 角柱微歪同定稿；其余木料不抖（纹槽是几何做的）
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    F.finish(meshes)
    tree = F.bvh_all(meshes)
    fam = {}
    for o in meshes:
        fam.setdefault(family(o), []).append(o)
    for k, objs in fam.items():
        F.shade(objs, tree, dist=SHADE_DIST, w_down=0.45, w_ao=0.85, w_crease=0.55, dark=DARK[k], up=0.10)
    veg.check_normals(meshes)
    tri, lo, hi = veg.stats(meshes)
    props.to_meters(PX_PER_M)
    print(f'[flat_house] 三角形 {tri}（{len(meshes)} 个网格）  宽 {(hi[0] - lo[0]) / 0.706:.2f} × 深 {(hi[1] - lo[1]) / 0.706:.2f} × 高 '
          f'{(hi[2] - lo[2]) / 0.706:.2f} 米')
    for k, objs in sorted(fam.items()):
        print(f'[flat_house]   {k}: {sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs)} 三角形')
    core.export(out, label='flat_house')


main()
