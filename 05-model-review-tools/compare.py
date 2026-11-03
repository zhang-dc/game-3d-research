"""Blender 建模 vs 四视图：按四视图的像素坐标直接渲染（不做框对齐，偏一个像素就是偏一个像素），叠图 + 剪影 IoU。

    python compare.py <模型.glb> <out.png> --views <四视图目录> [--k 0.01] [--cx 384 --ground 632.2]
四视图目录里放 front.png / right.png / back.png / left.png（RGBA，背景透明，同一像素尺度、地面在同一行）。
--cx = 正视图里模型中线的 x 像素，--ground = 地面所在行；不给就读目录里的 rectify.json（拉齐四视图时写的）。
--k = 1 像素对应多少模型单位（按像素建模、未换算成米时 0.01；换成米后 = 1 / 每米像素数）。
输出一张图：每行一个视图 = 参考 | 模型 | 叠图（参考半透明 + 模型剪影红边）；外加俯视、斜 45°、斜 225°。
同时打印每个视图的剪影 IoU、颜色平均差（两边都有像素的地方，0–255），写到 <out>.json。
模型坐标约定同 house_s5.py：glTF (−E, U, −S) × k。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from raster import to_view, tri_raster  # noqa: E402

VIEWS = [('front', 0), ('right', 90), ('back', 180), ('left', 270)]


def meshes(glb: Path):
    sc = trimesh.load(glb, force='scene', process=False)
    return sc.dump() if len(sc.geometry) > 1 else list(sc.geometry.values())


def color_fn(m):
    """返回 f(face 下标, 重心坐标) → RGB；有贴图按 UV 取，没有就用材质底色。"""
    mat = getattr(m.visual, 'material', None)
    tex = getattr(mat, 'baseColorTexture', None) if mat is not None else None
    uv = getattr(m.visual, 'uv', None)
    if tex is not None and uv is not None:
        t = np.asarray(tex.convert('RGB'))
        uv = np.asarray(uv, float)
        fac = np.asarray(getattr(mat, 'baseColorFactor', None) if getattr(mat, 'baseColorFactor', None) is not None else [255] * 4,
                         float)[:3] / 255

        def f(face, w):
            q = w @ uv[face]
            tx = (np.mod(q[:, 0], 1) * (t.shape[1] - 1)).astype(int)
            ty = ((1 - np.mod(q[:, 1], 1)) * (t.shape[0] - 1)).astype(int)
            return (t[ty, tx] * fac).astype(np.uint8)
        return f
    c = None
    if mat is not None:
        c = getattr(mat, 'baseColorFactor', None)
        if c is None and hasattr(mat, 'main_color'):
            c = mat.main_color
    if c is None and hasattr(m.visual, 'face_colors'):
        c = m.visual.face_colors[0]
    c = np.asarray(c if c is not None else [200, 200, 200, 255], float)[:3]
    c = c * 255 if c.max() <= 1.0 else c
    return lambda face, w: np.tile(c.astype(np.uint8), (len(w), 1))


def raster(ms, proj, W, H):
    """proj(顶点) → (像素 x, 像素 y, 深度[越大越近])。"""
    depth = np.full((H, W), -np.inf)
    out = np.zeros((H, W, 4), np.uint8)
    for m in ms:
        px, py, z = proj(np.asarray(m.vertices, float))
        p2 = np.c_[px, py]
        col = color_fn(m)
        for f in np.asarray(m.faces):
            r = tri_raster(p2[f], W, H)
            if r is None:
                continue
            xs, ys, w = r
            zz = w @ z[f]
            near = zz > depth[ys, xs]
            if not near.any():
                continue
            xs, ys, w, zz = xs[near], ys[near], w[near], zz[near]
            depth[ys, xs] = zz
            out[ys, xs, :3] = col(f, w)
            out[ys, xs, 3] = 255
    return Image.fromarray(out, 'RGBA')


def aligned(ms, yaw, k, cx, ground, W, H):
    def proj(v):
        q = to_view(v, yaw)
        return cx + q[:, 0] / k, ground - q[:, 1] / k, q[:, 2]
    return raster(ms, proj, W, H)


def oblique(ms, yaw, pitch, S=360):
    vs = []
    for m in ms:
        q = to_view(np.asarray(m.vertices, float), yaw)
        p = np.radians(pitch)
        y, z = q[:, 1].copy(), q[:, 2].copy()
        q[:, 1], q[:, 2] = y * np.cos(p) - z * np.sin(p), y * np.sin(p) + z * np.cos(p)
        vs.append(q)
    a = np.concatenate(vs)
    x0, x1, y0, y1 = a[:, 0].min(), a[:, 0].max(), a[:, 1].min(), a[:, 1].max()
    s = (S - 1) / max(x1 - x0, y1 - y0)
    it = iter(vs)

    def proj(v):
        q = next(it)
        return (q[:, 0] - x0) * s, (y1 - q[:, 1]) * s, q[:, 2]
    return raster(ms, proj, int((x1 - x0) * s) + 1, int((y1 - y0) * s) + 1)


def on_white(im):
    bg = Image.new('RGB', im.size, (255, 255, 255))
    bg.paste(im, (0, 0), im)
    return bg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('glb')
    ap.add_argument('out')
    ap.add_argument('--views', required=True, help='四视图目录（front/right/back/left.png）')
    ap.add_argument('--k', type=float, default=0.01)
    ap.add_argument('--cx', type=float, help='正视图模型中线 x 像素')
    ap.add_argument('--ground', type=float, help='地面行 y 像素')
    a = ap.parse_args()
    d = Path(a.views)
    if a.cx is None or a.ground is None:
        rc = json.loads((d / 'rectify.json').read_text())
        fx = rc['moves']['front']['x_tgt']
        cx = a.cx if a.cx is not None else (fx[0] + fx[3]) / 2
        ground = a.ground if a.ground is not None else rc['moves']['front']['y_tgt'][3]
    else:
        cx, ground = a.cx, a.ground
    ms = meshes(Path(a.glb))
    rows, stats = [], {}
    for v, yaw in VIEWS:
        ref = Image.open(d / (f'{v}.png' if v != 'right' or not (d / 'right.png').exists() else 'right.png')).convert('RGBA')
        W, H = ref.size
        mod = aligned(ms, yaw, a.k, cx, ground, W, H)
        ra, ma = np.asarray(ref)[..., 3] > 128, np.asarray(mod)[..., 3] > 0
        inter = ra & ma
        iou = inter.sum() / max((ra | ma).sum(), 1)
        cd = np.abs(np.asarray(ref)[..., :3].astype(int) - np.asarray(mod)[..., :3].astype(int)).mean(-1)[inter].mean()
        stats[v] = dict(iou=round(float(iou), 3), color_diff=round(float(cd), 1),
                        ref_only=int((ra & ~ma).sum()), model_only=int((ma & ~ra).sum()))
        edge = Image.fromarray((ma * 255).astype(np.uint8)).filter(ImageFilter.FIND_EDGES)
        ov = Image.blend(on_white(ref), on_white(mod), 0.5)
        red = Image.new('RGB', ov.size, (230, 30, 30))
        ov.paste(red, (0, 0), edge)
        bb = (ref.getbbox(), mod.getbbox())
        box = (min(b[0] for b in bb if b) - 10, min(b[1] for b in bb if b) - 10,
               max(b[2] for b in bb if b) + 10, max(b[3] for b in bb if b) + 10)
        rows.append([on_white(ref).crop(box), on_white(mod).crop(box), ov.crop(box)])
    extra = [on_white(oblique(ms, y, p)) for y, p in ((0, 90), (45, 35), (225, 35))]
    cw = max(im.width for r in rows for im in r)
    ch = max(im.height for r in rows for im in r)
    sheet = Image.new('RGB', (3 * (cw + 8), len(rows) * (ch + 8) + 368), (255, 255, 255))
    dr = ImageDraw.Draw(sheet)
    for r, row in enumerate(rows):
        for c, im in enumerate(row):
            sheet.paste(im, (c * (cw + 8), r * (ch + 8)))
        v = VIEWS[r][0]
        dr.text((4, r * (ch + 8) + 4), f'{v}  IoU {stats[v]["iou"]}  色差 {stats[v]["color_diff"]}', fill=(200, 0, 0))
    y = len(rows) * (ch + 8)
    for c, im in enumerate(extra):
        im.thumbnail((cw, 360))
        sheet.paste(im, (c * (cw + 8), y))
    sheet.save(a.out)
    Path(a.out).with_suffix('.json').write_text(json.dumps(stats, ensure_ascii=False, indent=1))
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == '__main__':
    main()
