"""橡树定稿（2026-10-23 评审："先这样吧"）= 第 5 版 pads + 每层明暗 中档；环境变量默认值就是定下的参数。原第 5 版说明：
橡树重做 第 5 版 pads：叶片叠成的树冠团（评审 2026-10-23："参考图的花椰菜形状不是真的花椰菜，是叶子拼出来的"）。
从第 4 版 floret.py 复制：树干 / 橡叶放法同第 4 版；每个叶簇换成 oak_pads.pad_cluster（扇贝边厚叶片按层从顶往下叠成圆顶，瓦片式）。
---- 以下是第 4 版的注释 ----
橡树重做 第 4 版 floret：花椰菜树冠 + 有厚度的叶片（评审 2026-10-23："还是都好丑啊，参考图应该是花椰菜一样的团，加一些有厚度的叶片"）。
树干 / 根 / 主枝 / 树洞同第 3 版 trunk（下面原注释）；改的：
  - 树冠：每个叶簇换成 oak_floret.floret_puff（簇芯 → 中圆瓣 → 小花球，体素合成一体、真实法线，缝里靠遮挡变暗）；
    簇位置 / 半径同 PUFFS；小花球半径 FLORET_R（参考正视图量的 11–18 厘米）；
  - 浅色橡叶：厚度 LEAF_THICK（第 3 版 2.5 厘米）。
---- 以下是第 3 版的注释 ----
橡树重做试验 第 3 版 trunk（veg/flat/OAK_TRY.md）：树冠和 A 版（veg/flat/tree_oak.py）一样，只改树干、根和浅色橡叶。

    blender -b --factory-startup --python examples/tree_oak.py -- out/tree_oak.glb

和 A 版的区别（量的都是 cand/fourview3/veg_tree_oak_1，100.6 像素/米；正视图 E = (x − 409) / 1.006、右视图 S = (374 − x) / 1.006、
U = (478 − y) / 1.006；"半宽" = 那一行树皮色像素（r > g + 12 且 r > b + 40）左右端距离 / 2 / 1.006）：
  - 树干：A 版是线性收细的椭圆管（地面半轴 65 / 53 → 顶 42 / 36，中段 U 117 正面剪影宽 107 厘米，参考 130），
    换成 oak_trunk.flared_trunk：按高度查剪影半宽表 ENV（正视图 / 右视图逐行量，下表），中段以上同 A 版收到 42 / 36；
  - 根：A 版 = 小截面外扩 + 6 条从树干里拱出来、末端扎进地里的长弯根（打光图读成一圈尖棱锥）。参考的根是树干底部外扩出的
    一圈短圆根（根头圆、离干身 85 厘米以内），改成同一根管子截面上的 7 个圆裂片（TOE_AZ 方位），根间收进到 CORE，
    根头在 U < NOSE 处按圆弧收回；去掉 veg.roots 的长根；
  - 浅色橡叶：A 版 24 个散点、size 46（veg 'oak' 5 裂片，宽 / 长 0.7）、只有材质槽分档没有顶点色，留下 12 片；
    参考正视图看得到约 11 片、右视图约 14 片，正面主要几片长 58–75 像素（厘米），下沿几片 45–50；正中那片长 ~75、宽 ~55、每边 3 个裂片
    → oak_trunk 'oak7' 叶形（沿叶长每边 3 个圆裂片 + 叶尖，宽 / 长 0.72），size 66 ± 15%（56–76 厘米），散 64 个点、种子 18
    （puff_leaves 悬空 / 落沟自查后留 31 片）+ 簇 5 外侧按方向放 1 片侧叶（EDGE_LEAVES），朝向放宽到偏下的簇侧；
    再 clear_leaves：叶面被鼓包顶穿 / 叶叶相交的往外推（10 片推了 0.5–2.5 厘米），最后 32 片；
    叶片材质换成纯色 × 顶点色（F.shade），和树冠一样有明暗；
  - 树冠里的暗色堵缝芯（canopy_plug）也补顶点色（A 版它和橡叶没有 COLOR_0）。
主枝、树洞、叶簇（位置 / 半径 / 种子 / 细分）、颜色都和 A 版相同。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))))  # -> import bkit
import bpy  # noqa: E402
from bkit import core, materials, veg  # noqa: E402
from bkit import flat as F  # noqa: E402
from bkit import oak_trunk as OT  # noqa: E402
from bkit import oak_floret as FL  # noqa: E402
from bkit import oak_pads as PD  # noqa: E402

OUT = Path(sys.argv[sys.argv.index('--') + 1])
SEED = 3
import os  # noqa: E402
_E = lambda k, d: float(os.environ.get(k, d))   # noqa: E731  调参用环境变量（默认 = 定下的值）

# ---- 树干：剪影半宽（厘米）。正视图 / 右视图逐行量（行 y → U）：----
#   U     12   18   28   38   48   58   68   78   97  117  137  157
#   正面 148  150  145  131  117  105   86   78   71   65   65   80（157 已是分叉处、含主枝根）
#   右侧 128  127  120  109   88   79   73   67   60   54   45   50（背 / 左视图 U 140 处 51、65）
#   根头：正视图 U 4 剪影宽 218（U 12 是 297）、U 0 只剩 18 → 根头在下面 ~20 厘米内收圆
TRUNK_C = (-3, 16)          # 根部中心：正视图 U 18 剪影中线 x 402.5 → E −6、U 117 x 406.5 → E −2.5；右视图 x 357 → S +17（同 A 版）
TRUNK_H = 290               # 同 A 版（顶埋进正面大簇 3）
TRUNK_BEND = (9, -6)        # 同 A 版
ENV = [(0, 152, 128), (14, 153, 128), (20, 154, 127), (28, 149, 121), (38, 135, 110), (48, 120, 90), (58, 107, 80),
       (68, 89, 73), (78, 80, 67), (97, 72, 60), (117, 66, 54), (137, 64, 51), (157, 58, 47), (185, 50, 42), (215, 44, 38),
       (250, 40, 35), (290, 36, 32)]   # 第 5 版：U 157 以上收细（参考正视图那里分成左右两根粗枝，主干本身不粗；原 70 / 62 / 54 / 47 / 42）   # 正面 E 方向 +3%：最靠侧的根（方位 105° / 260°）不正对 ±E，剪影比根尖半径小约 3%
MID = (70, 58)              # 根以上的干身半宽（U 97 处），根间收进的基准
CORE_K = 0.3                # 根与根之间：半径 = 干身 + 0.3 × (ENV − 干身)
CORE = [(u, a if u >= 97 else MID[0] + CORE_K * (a - MID[0]), b if u >= 97 else MID[1] + CORE_K * (b - MID[1])) for u, a, b in ENV]
# 根：7 条。正视图地面一排根头（U 8 一行的树皮段 x 282–355 / 379–451 / 466–526 → E −90 / +9 / +89）+ 两侧更高处各一个侧根；
#   右视图看得到 4 条 → 方位（0 = 正面 +S，90 = +E）：
TOE_AZ = [5, 50, 105, 160, 210, 260, 310]
TOE_LEN = [1.0, 0.9, 1.0, 0.85, 0.95, 1.0, 0.9]
TOE_W = 2.0                 # 根宽：正视图正对相机那条根头宽 72 像素、离中心 ~120 厘米 → 半宽角 ~14°（cos^2 在 7 条根时半高宽 12.9°）
NOSE = 34                   # 根头圆弧半径（厘米）：22 时 U 4 剪影宽 271（参考 218）、U 12 287（参考 297），34 折中
LEVELS = [-3, 0, 1.5, 3.5, 6, 9, 13, 18, 24, 31, 39, 48, 58, 68, 79, 92, 106, 122, 140, 160, 185, 215, 250, 290]
TRUNK_SEG = 70              # 一圈 70 段：7 条根 × 10 段（根头圆）
GROOVES, GROOVE_DEPTH = 7, 0.06    # 竖槽：根与根之间各一条，U 97–260 全深、往下 50 厘米渐隐（参考正视图干身上的竖纹从根间往上走）

# ---- 以下和 A 版（veg/flat/tree_oak.py）相同 ----
PUFFS = [
    (5, -10, 372, 78), (-105, 15, 352, 70), (105, -45, 345, 70), (10, 88, 300, 100, 0.8), (-148, 35, 272, 80),
    (152, 10, 258, 78), (-165, -60, 215, 64), (-15, -105, 285, 90), (118, -110, 210, 64), (135, 85, 192, 54),
    (-140, 95, 192, 48),
]
PLUG = (0, -5, 290, 135, 105, 70)
BRANCHES = [
    ((-22, 16, 140), (-160, 25, 235), 38, 20), ((18, 16, 140), (160, 10, 228), 36, 19),   # 第 5 版：正视图左右两根粗枝（参考 y 250–300 一带露出来）加粗、起点放低 ((-3, 42, 170), (5, 92, 275), 26, 13),
    ((-3, -12, 165), (-12, -100, 265), 25, 12), ((14, 36, 150), (125, 80, 195), 20, 10), ((-18, -6, 150), (-160, -55, 212), 20, 10),
    ((5, 10, 215), (5, -10, 360), 30, 16),
]
KNOT = dict(U=122, azimuth=45, r=12, stretch=1.4)
SMALL_R = 66
SHADE = dict(dist=70, w_down=0.6, w_ao=0.9, w_crease=0.6, dark=(0.22, 0.28, 0.34), blur=1)
BARK_RGB = [0.627, 0.392, 0.184]
LEAF_RGB = [_E('LR', 0.54), _E('LG', 0.66), _E('LB', 0.14)]   # 第 5 版：叶片叠层遮挡多、打光后 p50 79/100/41（参考 95/118/39）→ 底色提亮偏黄   # 第 4 版：参考正视图树冠 p50 95/118/39、p90 148/165/58（偏黄），原 0.42/0.54/0.17 打光后 p50 88/112/48 偏蓝
SHADE_LEAF = dict(dist=_E('AO_DIST', 25), w_down=0.45, w_ao=0.8, w_crease=_E('W_CREASE', 1.0), dark=(_E('DK_R', 0.30), _E('DK_G', 0.36), _E('DK_B', 0.20)), up=0.10, blur=int(_E('SH_BLUR', 0)))   # 第 4 版：暗部改暖（参考 p10 59/77/19）；花球间缝靠 40 厘米遮挡射线
SHADE_WOOD = dict(dist=60, w_down=0.35, w_ao=0.85, w_crease=0.0, dark=(0.36, 0.28, 0.22), up=0.08, blur=1)

# ---- 浅色橡叶（这一版改）----
LEAVES, LEAF_SIZE, LEAF_SHAPE, LEAF_SEG = int(_E('LEAVES', 40)), 66, 'oak7', 21
LEAF_SEED = int(__import__('os').environ.get('OAK_LEAF_SEED', 18))   # 种子 10–21 各跑一次挑的：18 留下 31 片、没有出 A 版包围盒的（环境变量 OAK_LEAF_SEED 可换）
LEAF_UP = (-0.45, 0.95)     # A 版 (−0.2, 0.95)：参考正视图簇下沿也有叶（y 260–320 三片）
LEAF_MIN_DIST = 56          # 两片叶中心最小距离（厘米，≈ 0.93 叶长）
SHADE_LLEAF = dict(dist=60, w_down=0.45, w_ao=0.6, w_crease=0.0, dark=(0.55, 0.60, 0.62), up=0.10, blur=0)
FLORET_R, VOXEL, CANOPY_TRIS = _E('FLORET_R', 20.0), _E('VOXEL', 2.5), _E('CANOPY_TRIS', 36000)   # 小花球半径（厘米）、体素边长、树冠减面后总三角形
FL.LOBE_IN, FL.FLORET_IN = _E('LOBE_IN', 0.6), _E('FLORET_IN', 0.3)
R_SCALE = _E('R_SCALE', 1.07)   # 簇半径整体缩放
LEAF_THICK = _E('LEAF_THICK', 7.0)
EDGE_LEAVES = [((152, 10, 258), (1, 0, 0.1), 58, 80)]   # 轮廓边上的侧叶：(从哪个点, 往哪个方向打射线, 叶长, 转角)。
#   簇 5 正 +E 侧：参考正视图右沿 x 640–660、y 230–300 有侧面贴着的叶；A 版这里也有一片（A 版包围盒 +E 沿 2.598 米就是它），
#   随机散的这一侧都被悬空自查去掉 → 包围盒 +E 只到簇 5 的 2.537，差 6 厘米
BBOX_A =((-2.5978, -0.03, -2.1007), (2.4816, 4.5173, 2.2258))   # A 版 GLB 包围盒（glTF x, y, z = −E, U, −S 米）


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    core.reset_scene()
    materials.load('toy_clay', textures=False, units_per_m=100, srgb_colors=True)
    OT.install_shapes()
    V = veg.veg_materials('tree_oak')
    V['bark'] = F.color_mat('f_oak_bark', BARK_RGB)
    V['knot'] = F.color_mat('f_oak_knot', veg.veg_spec()['colors']['oak_knot']['color'])
    V['leaf'] = materials.mat('f_oak_leaf', color=LEAF_RGB)

    t = OT.flared_trunk('trunk', V['bark'], base=TRUNK_C, h=TRUNK_H, env=ENV, core_tab=CORE, bend=TRUNK_BEND,
                        toe_az=TOE_AZ, toe_len=TOE_LEN, toe_w=TOE_W, nose=NOSE, levels=LEVELS, grooves=GROOVES,
                        groove_depth=GROOVE_DEPTH, seg=TRUNK_SEG, seed=SEED)
    for k, (a, b, r0, r1) in enumerate(BRANCHES):
        veg.branch(f'branch_{k}', V['bark'], a, b, r0, r1, lift=0.12)
    veg.knothole('knot', V['bark'], V['knot'], t, **KNOT)
    wood = [o for o in bpy.data.objects if o.type == 'MESH']
    S3 = veg.shade_mats(V['leaf'])
    # 第 6 版（评审："每一团好像尺寸都差不多大"）：主团大小拉开（r × (r / 75)^SIZE_POW：100 → 119、48 → 37），再从主团朝外偏下挂子团
    mains = [(pf[0], pf[1], pf[2], pf[3] * R_SCALE * (pf[3] / 75) ** _E('SIZE_POW', 0)) + tuple(pf[4:]) for pf in PUFFS]
    # 第 7 版（评审："团太多了"，第 6 版 37 团；参考图约 8 个大团）：主团只留 MAINS 个最大的，再整体放大 GROW 补回被删掉的那部分体积
    keep = sorted(range(len(mains)), key=lambda i: -mains[i][3])[:int(_E('MAINS', len(mains)))]
    mains = [mains[i][:3] + (mains[i][3] * _E('GROW', 1.0),) + tuple(mains[i][4:]) for i in sorted(keep)]
    kids = PD.child_clumps(mains, seed=SEED + 11, n=(int(_E('KID_MIN', 2)), int(_E('KID_MAX', 4))),
                            total=int(_E('KIDS_TOTAL', 999))) if _E('KIDS', 0) else []
    ALL = mains + kids
    area = [pf[3] ** 2 for pf in ALL]
    cs, nsph, cores, frames = [], 0, [], []
    TIERS = ((0, 1, 0.50), (34, 6, 0.40), (62, 9, 0.36), (90, 11, 0.32), (118, 10, 0.30))   # 离顶角度°、片数、片半径 / 簇半径；118° = 簇底那圈（第 1 轮簇底露暗芯）
    CORE_M = veg.vcol_mat(materials.mat('f_oak_core', color=[x * 0.45 for x in LEAF_RGB]))
    for k, pf in enumerate(ALL):
        e, s_, u, r = pf[:4]
        sq = pf[4] if len(pf) > 4 else 0.85
        obs, n, fr = PD.pad_cluster(f'canopy_{k:02d}', veg.vcol_mat(V['leaf']), (e, s_, u), r, squash=sq, seed=SEED * 100 + k,
                                thick=_E('PAD_THICK', 7.0), bulge=_E('PAD_BULGE', 6.0), tilt=_E('PAD_TILT', 14.0),
                                inset=_E('PAD_INSET', 0.10), outward=(0, 0, 290), core_m=CORE_M, seg=int(_E('PAD_SEG', 24)), rows=int(_E('PAD_ROWS', 2)),
                                tiers=PD.auto_tiers(r, sq, rho=_E('PAD_RHO', 28.0)) if _E('AUTO_TIERS', 0) else TIERS,
                                others=[(q[:3], q[3], q[4] if len(q) > 4 else 0.85) for j, q in enumerate(ALL) if j != k] if _E('CULL', 0) else (),
                                pad_edge=_E('PAD_EDGE', 0.8), core_sub=int(_E('CORE_SUB', 3)))
        ob = obs[0]
        cores.extend(obs[1:])
        frames += fr
        cs.append(ob)
        nsph += n
    print(f'[oak_pads] 树冠 {len(cs)} 簇、{nsph} 片叶片')
    puffs = [o for o in cs if not o.name.endswith('_plug')]
    LL = veg.vcol_mat(V['leaf_light'])
    leaves = PD.pad_leaves('oakleaf', frames, LL, n_total=LEAVES, size=LEAF_SIZE, shape=LEAF_SHAPE, seg=LEAF_SEG,
                           thick=LEAF_THICK, seed=LEAF_SEED, max_tier=int(_E('LEAF_TIER', 2)))
    n0, cst = len(leaves), '不查'
    print(f'[oak_pads] 橡叶 放 {n0} 片 → 相交处理 {cst} → {len(leaves)} 片')
    plug = cores
    for o in plug:                                     # 堵缝芯换乘顶点色版（顶点色下面一起算）
        o.data.materials[0] = veg.vcol_mat(o.data.materials[0])

    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    tree = F.bvh_all(meshes)
    F.shade(puffs, tree, **SHADE_LEAF)
    F.shade([o for o in meshes if o.name.startswith(('trunk', 'branch', 'knot'))], tree, **SHADE_WOOD)
    F.shade(leaves, tree, **SHADE_LLEAF)
    F.shade(plug, tree, **SHADE_LEAF)
    veg.check_normals()
    tri, lo_, hi_ = veg.stats()
    print(f'[oak_pads] 三角形 {tri}  包围盒 宽 {hi_[0] - lo_[0]:.2f} × 深 {hi_[1] - lo_[1]:.2f} × 高 {hi_[2] - lo_[2]:.2f} 米  底 {lo_[2]:.3f}')
    core.export(OUT, label='oak_pads')


main()
