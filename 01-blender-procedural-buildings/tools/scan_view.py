"""四视图按行 / 按列扫剪影和颜色区块，直接换成建模坐标（E / S / U）——量尺寸用。

    python scan_view.py <四视图目录> <front|right|back|left> [--rows 起:止:步] [--cols 起:止:步]
        [--cls wood|stone|cloth|straw|rope|metal | --hsv h0,h1,s0,s1,v0,v1] [--image 别的图] [--cx 中线] [--ground 地面行]
        [--min 3] [--per-m 像素/米]
<四视图目录> 给完整路径，或给目录名（在环境变量 FOURVIEW_ROOT 下找）。

坐标（同 bkit.core.P 和 bkit/projection.py 的 VIEW_X）：U = 地面行 − y；横向 front：E = x − 中线，back：E = 中线 − x，
right：S = 中线 − x，left：S = x − 中线。输出的数是像素边界（区段 x0…x1 → 左边界 x0、右边界 x1 + 1）。
中线 / 地面行：目录里有 rectify.json（rectify_views.py 拉齐过）就用它（moves[视图].x_tgt 首尾的中点、y_tgt[3]）；
没有就用这张图剪影包围盒的水平中点和最下一行的下沿；--cx / --ground 可覆盖。
--per-m：给了就同时打印米数；不给且目录里有 measure.json（camp_measure.py 出的）时，正 / 背视图用 px_per_m_front、
两侧用 px_per_m_side（这两个数是按建筑表尺寸换算的，四视图画的比例和建筑表不一定一样）。
给了 --image 时 rectify.json 和 measure.json 都不用（measure.json 按切格后的图算：camp_fence_2 切掉右端后是 163.75，
sheet.png 原图 786 像素才是 4 米）；要米数就自己给 --per-m。sheet.png 没有透明通道，只能配 --cls / --hsv 扫颜色档。
颜色档 --cls 抄自 building/camp_measure.py 的 CLASSES（OpenCV HSV：H 0–180、S / V 0–255，按圆胖玩具 × 黏土那套颜色写的），
别的配色用 --hsv 自己给范围。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

FOURVIEW = Path(__import__('os').environ.get('FOURVIEW_ROOT', '.'))   # 只给目录名时在这个根目录下找
CLASSES = {   # 同 camp_measure.py
    'wood': lambda h, s, v: (h >= 5) & (h <= 20) & (s > 110) & (v > 60),
    'stone': lambda h, s, v: (s < 45) & (v > 70) & (v < 215),
    'cloth': lambda h, s, v: (h >= 12) & (h <= 30) & (s >= 25) & (s < 90) & (v > 175),
    'straw': lambda h, s, v: (h >= 15) & (h <= 28) & (s >= 110) & (v > 170),
    'rope': lambda h, s, v: (h >= 12) & (h <= 26) & (s >= 60) & (s < 140) & (v > 140) & (v <= 235),
    'metal': lambda h, s, v: (s < 40) & (v <= 70),
}
SIGN = {'front': ('E', 1), 'back': ('E', -1), 'right': ('S', -1), 'left': ('S', 1)}


def runs(m1d, min_len):
    """布尔数组里连续 True 的区段 [(起, 止)]（止含），短于 min_len 的不要。"""
    out, start = [], None
    for i, x in enumerate(list(m1d) + [False]):
        if x and start is None:
            start = i
        elif not x and start is not None:
            if i - start >= min_len:
                out.append((start, i - 1))
            start = None
    return out


def span(arg, n):
    a, b, s = (arg.split(':') + ['', '', ''])[:3]
    return range(int(a) if a else 0, int(b) if b else n, int(s) if s else 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir')
    ap.add_argument('view', choices=list(SIGN))
    ap.add_argument('--rows', default='')
    ap.add_argument('--cols', default='')
    ap.add_argument('--cls', choices=list(CLASSES))
    ap.add_argument('--hsv', default='')
    ap.add_argument('--image', default='')
    ap.add_argument('--cx', type=float)
    ap.add_argument('--ground', type=float)
    ap.add_argument('--min', type=int, default=3, help='区段最短几个像素')
    ap.add_argument('--per-m', type=float, default=0.0)
    a = ap.parse_args()
    d = Path(a.dir) if Path(a.dir).is_absolute() else FOURVIEW / a.dir
    img = Path(a.image) if a.image else d / f'{a.view}.png'
    rgba = np.asarray(Image.open(img).convert('RGBA'))
    alpha = rgba[..., 3] > 128
    H, W = alpha.shape
    ys, xs = np.nonzero(alpha)
    if not len(xs):
        sys.exit(f'{img} 没有不透明像素')
    src = '剪影包围盒'
    cx, ground = (xs.min() + xs.max() + 1) / 2, float(ys.max() + 1)
    rc = d / 'rectify.json'
    if rc.exists() and not a.image:
        mv = json.loads(rc.read_text())['moves'][a.view]
        cx, ground, src = (mv['x_tgt'][0] + mv['x_tgt'][-1]) / 2, mv['y_tgt'][3], 'rectify.json'
    if a.cx is not None:
        cx, src = a.cx, src + '（中线手给）'
    if a.ground is not None:
        ground, src = a.ground, src + '（地面行手给）'
    ppm = a.per_m
    meas = d / 'measure.json'
    if not ppm and meas.exists() and not a.image:      # --image（如 sheet.png）时不套 measure.json：它按切格后的图算，宽的东西会被切短
        mj = json.loads(meas.read_text())
        ppm = mj['px_per_m_front'] if a.view in ('front', 'back') else mj['px_per_m_side']
    mask, what = alpha, '剪影'
    if a.cls or a.hsv:
        import cv2
        hsv = cv2.cvtColor(np.ascontiguousarray(rgba[..., :3]), cv2.COLOR_RGB2HSV).astype(int)
        h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
        if a.cls:
            mask, what = CLASSES[a.cls](h, s, v) & alpha, a.cls
        else:
            h0, h1, s0, s1, v0, v1 = (int(x) for x in a.hsv.split(','))
            mask, what = (h >= h0) & (h <= h1) & (s >= s0) & (s <= s1) & (v >= v0) & (v <= v1) & alpha, f'HSV {a.hsv}'
    ax, sg = SIGN[a.view]

    def hz(x):
        return round(sg * (x - cx), 1)

    def m(x):
        return f' = {x / ppm:.3f} 米' if ppm else ''
    print(f'{img.name} {W}×{H}：中线 x {cx:g}、地面行 y {ground:g}（{src}）；横向 {ax}，竖向 U = 地面行 − y；'
          + (f'{ppm:g} 像素/米' if ppm else '不换米'))
    bb = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
    e0, e1 = sorted((hz(bb[0]), hz(bb[2])))
    print(f'剪影包围盒：{ax} {e0:g}…{e1:g}（宽 {bb[2] - bb[0]}{m(bb[2] - bb[0])}），U {ground - bb[3]:g}…{ground - bb[1]:g}'
          f'（高 {bb[3] - bb[1]}{m(bb[3] - bb[1])}）')
    if not a.rows and not a.cols:
        a.rows = f'{bb[1]}:{bb[3]}:{max(1, (bb[3] - bb[1]) // 24)}'
    if a.rows:
        print(f'— 按行（{what}，{ax} 区段）—')
        for y in span(a.rows, H):
            segs = [tuple(sorted((hz(x0), hz(x1 + 1)))) for x0, x1 in runs(mask[y], a.min)]
            if segs:
                print(f'y {y:4d}  U {ground - y:7.1f}  ' + '  '.join(f'{p:g}…{q:g}' for p, q in sorted(segs)))
    if a.cols:
        print(f'— 按列（{what}，U 区段）—')
        for x in span(a.cols, W):
            segs = [(round(ground - (y1 + 1), 1), round(ground - y0, 1)) for y0, y1 in runs(mask[:, x], a.min)]
            if segs:
                print(f'x {x:4d}  {ax} {hz(x):7.1f}  ' + '  '.join(f'U {p:g}…{q:g}' for p, q in sorted(segs)))


if __name__ == '__main__':
    main()
