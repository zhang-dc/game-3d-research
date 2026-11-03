"""Blender 程序建模：圆胖玩具 × 黏土茅草房（s5_toyclay_1）。评审 2026-10-22："能不能直接参考成品，用 blender 迭代建模"。
定的是：四视图为准、Pixal3D 成品辅助；纯色材质 + 少量程序纹理。

    GEO=1 blender -b --factory-startup --python examples/house_textured.py -- out/house.glb
（原项目定稿另用 MATS=<贴图目录> THATCH=band：贴图是从生成的参考图上裁的，本仓库不带，见 README）
尺寸全按拉齐后的四视图量（rectify.json：地面行 632.2、正视图中线 384），单位 1 像素 = 0.01 Blender 单位。
坐标约定 P(E, S, U)：E = 正视图向右、S = 朝正面相机、U = 离地高度（像素）。
Blender 里 x = −E、y = S、z = U → 导出 glTF 后 (−E, U, −S)，和 Pixal3D 的 GLB 一个朝向（预览时绕 Y 转 180° 正面朝相机）。
每改一轮：改下面的尺寸 → 重跑 → compare.py 叠图看偏差。

材质和组件在建筑套件 ../bkit/（评审 2026-10-22："最好形成可以复用的材质和组件，方便建模时复用"）：这里只剩量出来的尺寸、
按顺序搭、导出。搬过去前后 A–E 五种开关组合的组装版 + 每个部件 GLB 逐个比过（glbeq + 三角形 / 法线 / UV / 材质 / 贴图像素），没变。
开关（环境变量，build.sh 不用改）：
  MATS=<目录>   平铺贴图从这个目录读（mats/crop = 材质库 toy_clay 那批，s5 定稿用；mats/proc、mats/gen 是别的候选）；不设 = 第 1–4 轮的简单噪声
  GEO=1         几何质感：茅草下沿波浪边、石块大小 / 边角不规则、木料微弯
  THATCH=band   茅草一层一条带（材质库 thatch_band）
  NMAP=1        茅草带配法线贴图
  PROJ=1        四视图直投（已否，侧面拉丝：评审 "本来建模挺规整的，越改越烂了"）
  UNITS=m       导出前整体换成真实米数（四视图每米 70.6 像素 → ×1.4164），预览器按实际尺寸显示；
                不设 = 1 像素 = 0.01 单位（compare.py 默认 --k 0.01 对的是这个；换成米后对照用 --k 0.014164）
"""
from __future__ import annotations

import os
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))                   # 01-blender-procedural-buildings/ → import bkit
from bkit import components as C, core, materials, projection, props  # noqa: E402

random.seed(7)                                         # 石块长短 / 深浅、烟囱石块、茅草波浪边都接着这个种子走：组件调用顺序别动

# ---------------- 量出来的尺寸（像素） ----------------
BASE = dict(E=200, S=127, U=(0, 56))                  # 石基：两层石块
WALL = dict(E=190, S=120, U=(56, 200))                # 墙身，顶部藏进屋顶
# 木构架（参考图量的）：角柱往里占 31 × 29、凸出墙面 2（16 太窄，评审 2026-10-22："我们木头柱子有点窄"，先 24，再按参考图量）；
# 墙顶横梁 U 158–182（参考图里露出 162–170，上面藏在檐口下）；梁头 U 152–176；
# 斜撑 45°：下端在角柱内侧离墙角 24、离地 124，上端顶到墙顶横梁 166（背视图 e−24 → e−64，侧视图 s−24 → s−56）
FRAME = dict(plate=(158, 182), post=(31, 29), post_out=2, beam_u=(152, 176),
             brace_u=(124, 166), brace_in=24, brace_reach=(64, 56), brace_out=3, brace_w=12)
# 茅草四层（从下往上）：U 范围、最鼓处半宽 E / S、顶部收进比例、圆角
TIERS = [dict(U=(171, 236), E=247, S=165, tE=0.93, tS=0.87, r=18),
         dict(U=(231, 290), E=227, S=141, tE=0.84, tS=0.76, r=18),
         dict(U=(285, 350), E=191, S=106, tE=0.84, tS=0.71, r=18),
         dict(U=(345, 392), E=155, S=72, tE=0.72, tS=0.55, r=32)]   # 屋脊圆：r 24 → 32（第 3 轮顶上是方的）
CHIM = dict(E=(-147, -79), S=(-37, 37), U=(320, 427))
DORMERS = [dict(side=1, E=5), dict(side=-1, E=-17)]   # 正面 / 背面老虎窗中心
DORMER_TILT = 22                                      # 度：窗面从 (U222, S150) 倾到 (U330, S108)，跟屋面斜度
DOOR = dict(E=(-117, 3), U=(40, 172), win=((-77, -37), (95, 139)), knob=(-89, 83))   # 门框外轮廓；门上小窗 (E, U)；把手 (E, U)
STEPS = dict(E=(-119, 3))
WIN_F = dict(E=(59, 116), U=(102, 149))               # 正面窗玻璃
WIN_SIDE = dict(S=(-24, 26), U=(92, 147))             # 两侧窗玻璃
LANTERN = dict(E=(-167, -134), U=(105, 165))
BARREL = dict(E=(-197, -134), U=(7, 92), S=161)

MATS = os.environ.get('MATS')                          # 贴图来源目录（materials.py 出的 mats/<来源>/）
GEO = os.environ.get('GEO') == '1'
THATCH_BAND = os.environ.get('THATCH') == 'band'
NMAP = os.environ.get('NMAP') == '1'
PROJ = os.environ.get('PROJ') == '1'
UNITS_M = os.environ.get('UNITS') == 'm'
PX_PER_M = 70.6                                        # 四视图每米像素（房宽 7 米 ≈ 494 像素）


def main():
    out = sys.argv[sys.argv.index('--') + 1]
    core.reset_scene()
    projection.setup(HERE / 'mats' / 'proj')           # 四视图投影图（只有 PROJ=1 用）
    M = materials.load('toy_clay', textures=bool(MATS), tex_dir=MATS)
    C.base(M, **BASE, slab=PROJ, proj=PROJ)            # PROJ 时换成一整块圆角石台，石块从四视图投
    C.walls(M, **WALL, proj=PROJ, **FRAME)
    C.roof(M, TIERS, band=materials.band('toy_clay', nmap=NMAP) if THATCH_BAND else None, geo=GEO)
    C.chimney(M, **CHIM)
    for d in DORMERS:
        C.dormer(M, **d, tilt=DORMER_TILT)
    FRONT = {'S+': 'front', 'S-': 'front', 'E+': 'front', 'E-': 'front'}
    with projection.projected(FRONT, on=PROJ):         # 门、门框、台阶、正面窗（框 / 玻璃 / 百叶 / 花箱）← 正视图
        C.door(M, **DOOR, S0=WALL['S'], proj=PROJ)
        C.steps(M, **STEPS, S0=BASE['S'])
        C.window('winF', WIN_F['E'], WIN_F['U'], WALL['S'], M, flowerbox=True)
    for sd, x, v in (('E', WALL['E'], 'left'), ('-E', -WALL['E'], 'left')):   # 两侧都用左视图（右视图那扇窗是贴过去的，贴块灰泥深浅不同）
        with projection.projected({k: v for k in ('S+', 'S-', 'E+', 'E-')}, on=PROJ):   # 两侧窗 ← 侧视图
            C.window(f'win{sd}', WIN_SIDE['S'], WIN_SIDE['U'], x, M, side=sd)
    C.lantern(M, **LANTERN, S0=WALL['S'])
    C.barrel(M, **BARREL)
    if GEO:
        C.roughen()
    if UNITS_M:
        props.to_meters(PX_PER_M)
    core.export(out, label='house')


main()
