"""建筑套件 · 四视图直投（不推荐，只为复现茅草房 PROJ=1 那一版）。

不推荐：四视图直投只在正对视图的面上成立，侧面 / 底面 / 斜面会拉丝（用户 2026-10-22："本来建模挺规整的，越改越烂了"）。
来历：用户 2026-10-22 "木头柱子，石头底座，门，窗，看着太规整了， 也按一样的逻辑修一下"——和茅草带一样，样子直接取四视图上它自己那块：
模型按四视图像素尺寸搭，几何和四视图对齐，按像素坐标把四视图投到对应面上（blender_house/mats/proj/，大块明暗压一半）。
之后又修过"木头柱子怎么有接缝"（投影图透明处按最近不透明像素外延）、"侧着看，还是有缝啊"（细长构件所有面取所在墙的视图，cfg 'all'），
最后用户认可的是不投的那版（"上一版：茅草带 + 几何质感，其余是生成的贴图 这个还可以"）。

    projection.setup(img_dir)                         # 投影图目录（<视图>.png），四视图像素几何默认 = 茅草房
    with projection.projected({'S+': 'front', 'E+': 'left', ...}, on=True):
        ...                                           # 里面新建的物体按面朝向取对应视图投 UV、换成 proj_<视图> 材质
cfg 的键：面朝向 'S+' / 'S-' / 'E+' / 'E-'（朝上的面 'U'，没写就用 'S+'），或 'all'（所有面都取这一张）；值 = 视图名。
"""
from __future__ import annotations

from pathlib import Path

import bpy

from . import core
from .core import K
from .materials import cached, mat

# 茅草房四视图（拉齐后，rectify.json）：正视图中线 CX、地面行 GROUND、整张宽高
CX, GROUND, VIEW_W, VIEW_H = 384.0, 632.2, 768, 672
VIEW_X = {'front': lambda E, S: CX + E, 'back': lambda E, S: CX - E, 'right': lambda E, S: CX - S,
          'left': lambda E, S: CX + S, 'right_nowin': lambda E, S: CX - S}
IMG_DIR: Path | None = None


def setup(img_dir, cx=384.0, ground=632.2, view_w=768, view_h=672):
    """投影图目录（blender_house/mats/proj/ 这种，<视图>.png）+ 四视图像素几何（默认 = 茅草房 s5_toyclay_1）。"""
    global IMG_DIR, CX, GROUND, VIEW_W, VIEW_H
    IMG_DIR, CX, GROUND, VIEW_W, VIEW_H = Path(img_dir), cx, ground, view_w, view_h


class projected:
    """with projected(cfg, on=…)：里面新建的物体按面朝向取对应视图投 UV。on=False 时什么都不做（茅草房不开 PROJ）。
    可嵌套：projected(None, on=True) 临时关掉（门洞那块黑板、门上窗洞的切刀不投）。"""
    def __init__(self, cfg, on=True):
        self.cfg, self.on, self.prev = cfg, on, None

    def __enter__(self):
        self.prev = core.uv_override
        if self.on:
            cfg = self.cfg
            core.uv_override = (lambda ob: apply_proj(ob, cfg)) if cfg else None
        return self

    def __exit__(self, *a):
        core.uv_override = self.prev


def proj_mat(view):
    """视图 view 的投影材质 proj_<view>（<IMG_DIR>/<view>.png，最近邻）。"""
    m = cached(f'proj_{view}')
    if m is None:
        if IMG_DIR is None:
            raise RuntimeError('先 projection.setup(投影图目录)')
        img = bpy.data.images.load(str(IMG_DIR / f'{view}.png'))
        img.pack()
        m = mat(f'proj_{view}', tex=img)
    return m


def apply_proj(ob, cfg):
    """把 ob 的材质换成用到的视图的投影材质，每个面按朝向选视图、按像素坐标投 UV。"""
    me = ob.data
    views = sorted(set(cfg.values()))
    me.materials.clear()
    for v in views:
        me.materials.append(proj_mat(v))
    uvl = me.uv_layers.get('UV') or me.uv_layers.new(name='UV')
    for poly in me.polygons:
        nE, nS, nU = -poly.normal.x, poly.normal.y, poly.normal.z
        if abs(nU) > max(abs(nE), abs(nS)):
            d = 'U'
        elif abs(nS) >= abs(nE):
            d = 'S+' if nS > 0 else 'S-'
        else:
            d = 'E+' if nE > 0 else 'E-'
        v = cfg.get('all') or cfg.get(d) or cfg.get('S+') or views[0]   # 'all'：细长构件所有面都取它所在那面墙的视图
        poly.material_index = views.index(v)
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            E, S, U = -co.x / K, co.y / K, co.z / K
            uvl.data[li].uv = (VIEW_X[v](E, S) / VIEW_W, 1 - (GROUND - U) / VIEW_H)
