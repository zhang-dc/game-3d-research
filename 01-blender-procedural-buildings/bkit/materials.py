"""建筑套件 · 材质库（Blender 里 import）。评审 2026-10-22："最好形成可以复用的材质和组件，方便建模时复用"。

一种风格一个目录：lib/materials/<风格>/materials.json + 贴图。现在有 toy_clay（圆胖玩具 × 黏土，茅草房 s5 定稿那套）。
materials.json 里每个材质写着 kind（tile 平铺贴图 / band 茅草带 / color 纯色 / procedural 程序纹理）、贴图文件、颜色、
一张贴图覆盖多少四视图像素、来源（blender_house/materials.py 哪个子命令、从哪张视图哪块裁）、用在哪、评审怎么说的。

    M = materials.load('toy_clay')                    # 定稿那套：平铺贴图 + 纯色
    M = materials.load('toy_clay', textures=False)    # 第 1–4 轮的"纯色 + 少量程序纹理"
    band = materials.band('toy_clay')                 # 茅草一层一条带（给 components.roof）
M 的键和材质名同茅草房原来的 materials()：M['thatch']、M['plaster']……；M['stone'] / M['chimney'] 是三个深浅的列表。
材质按名字缓存（同名只建一次）；换场景（core.reset_scene）时一起清掉。
"""
from __future__ import annotations

import json
from pathlib import Path

import bpy
import numpy as np

LIB = Path(__file__).resolve().parent / 'lib' / 'materials'
_MATS: dict[str, bpy.types.Material] = {}


def reset_cache():
    """清掉材质缓存（场景清空后旧材质已经不在了）。"""
    _MATS.clear()


def cached(name):
    """缓存里的同名材质，没有返回 None。"""
    return _MATS.get(name)


def spec(style='toy_clay'):
    """读 lib/materials/<style>/materials.json。"""
    return json.loads((LIB / style / 'materials.json').read_text(encoding='utf-8'))


def palette(style='toy_clay'):
    """这套风格从四视图取的颜色表（名字 → [r, g, b]，0–1）。"""
    return spec(style)['palette']


# ---------------- 底层：建材质 / 程序纹理 ----------------
def tex_image(name, size, fn):
    """程序纹理：size × size 的图，fn(size) 给 RGB（0–1），打包进 .blend（导出 glTF 时嵌进去）。"""
    img = bpy.data.images.new(name, size, size, alpha=False)
    a = np.ones((size, size, 4), np.float32)
    a[..., :3] = fn(size)
    img.pixels.foreach_set(a.ravel())
    img.pack()
    return img


def streaks(base, amp, axis, size=64, seed=0):
    """竖条（茅草）/ 横条（木纹）：每列（行）亮度随机起伏 ±amp，再加 0.3 × amp 的细噪声。返回给 tex_image 的 fn。"""
    rng = np.random.default_rng(seed)

    def fn(n):
        line = 1 + amp * (rng.random(n) * 2 - 1)
        line = np.convolve(line, [0.25, 0.5, 0.25], 'same')
        g = np.tile(line, (n, 1)) if axis == 'v' else np.tile(line[:, None], (1, n))
        g = g * (1 + amp * 0.3 * (rng.random((n, n)) * 2 - 1))
        return np.clip(np.array(base)[None, None] * g[..., None], 0, 1)
    return fn


def speckle(base, amp, size=64, seed=0):
    """斑点（灰泥）：每个像素亮度随机 ±amp。返回给 tex_image 的 fn。"""
    rng = np.random.default_rng(seed)

    def fn(n):
        g = 1 + amp * (rng.random((n, n)) * 2 - 1)
        return np.clip(np.array(base)[None, None] * g[..., None], 0, 1)
    return fn


SRGB_COLORS = False   # True：纯色 color 当 sRGB（四视图取的色都是 sRGB）先转线性再填 Base Color；load(srgb_colors=True) 打开


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def mat(name, color=None, tex=None):
    """Principled BSDF，粗糙度 0.9；有 tex 用贴图（最近邻）当底色，没有用纯色 color（[r, g, b]）。同名只建一次。
    颜色：SRGB_COLORS 打开时按 sRGB 转线性（2026-10-22 营地级核查：直接把 sRGB 取色填进线性槽，打光后偏浅发灰，螺栓成了白点）；
    茅草房定稿没开（颜色按原样，改要评审定）。"""
    if name in _MATS:
        return _MATS[name]
    if color is not None and SRGB_COLORS:
        color = [srgb_to_linear(c) for c in color[:3]]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = 0.9
    if tex is not None:
        t = m.node_tree.nodes.new('ShaderNodeTexImage')
        t.image = tex
        t.interpolation = 'Closest'
        m.node_tree.links.new(t.outputs['Color'], bsdf.inputs['Base Color'])
    else:
        bsdf.inputs['Base Color'].default_value = (*color, 1)
    _MATS[name] = m
    return m


def ext_mat(name, path, tint=1.0, texel_per_m=64, ref_px_per_m=70.6):
    """贴图文件 → 平铺材质 name；tint 乘到像素上（同一张石头贴图出几个深浅，新图名 <文件名>_<tint>）。
    材质上记 'tile' = 一张贴图覆盖多少四视图像素（贴图尺寸 / texel_per_m × ref_px_per_m），core.box_uv 按它铺。"""
    if name in _MATS:
        return _MATS[name]
    path = Path(path)
    img = bpy.data.images.load(str(path))
    if tint != 1.0:
        w, h = img.size
        a = np.empty(w * h * 4, np.float32)
        img.pixels.foreach_get(a)
        a = a.reshape(-1, 4)
        a[:, :3] = np.clip(a[:, :3] * tint, 0, 1)
        img2 = bpy.data.images.new(f'{path.stem}_{tint}', w, h, alpha=False)
        img2.pixels.foreach_set(a.ravel())
        img = img2
    img.pack()
    m = mat(name, tex=img)
    m['tile'] = (img.size[0] / texel_per_m * ref_px_per_m, img.size[1] / texel_per_m * ref_px_per_m)
    return m


# ---------------- 按风格加载 ----------------
def _simple(e):
    """materials.json 一项的"简单版"（textures=False 时的样子）：纯色 / 程序纹理；stone、chimney 这种出深浅列表。"""
    s = e.get('simple', e)
    color = e['color']
    if s['kind'] == 'color':
        if 'variants' in s:
            return [mat(v['blender'], color=[min(1, x * v['factor']) for x in color]) for v in s['variants']]
        return mat(s['blender'], color=color)
    if s['kind'] == 'procedural':
        if s['fn'] == 'streaks':
            fn = streaks(color, s['amp'], s['axis'], seed=s['seed'])
        elif s['fn'] == 'speckle':
            fn = speckle(color, s['amp'], seed=s['seed'])
        else:
            raise ValueError(f'未知程序纹理 {s["fn"]}')
        return mat(s['blender'], tex=tex_image(s['image'], s['size'], fn))
    raise ValueError(f'simple 只认 color / procedural，收到 {s["kind"]}')


def load(style='toy_clay', textures=True, tex_dir=None, units_per_m=None, srgb_colors=False):
    """一套材质 → 字典 M（键 = materials.json 的 id）。
    textures=True：kind = tile 的材质用平铺贴图（茅草房 MATS=mats/crop 那套，s5 定稿）；
                   tex_dir 换贴图目录（blender_house/mats/proc、mats/gen 这些候选，文件名同 thatch.png / plaster.png / timber.png / stone.png），
                   不给 = 材质库自己的 lib/materials/<style>/。
    textures=False：全换成 simple（纯色 + 64×64 程序纹理，茅草房不设 MATS 那套）。
    茅草带不在 M 里，另用 band()。
    units_per_m：模型 1 米 = 多少建模单位（贴图按 64 texel/米铺时换算用）。不给 = materials.json 的 ref_px_per_m
                 （茅草房按四视图像素建，70.6）；营地级这类按厘米建的给 100（2026-10-22）。"""
    global SRGB_COLORS
    SRGB_COLORS = srgb_colors                          # 之后脚本里自己 mat(color=…) 的也按这个走
    sp = spec(style)
    M = {}
    for mid, e in sp['materials'].items():             # 先把简单版都建出来（贴图版再覆盖；和原来 materials_base() + update 一样）
        if e['kind'] != 'band':
            M[mid] = _simple(e)
    if textures:
        d = Path(tex_dir) if tex_dir else LIB / style
        for mid, e in sp['materials'].items():
            if e['kind'] != 'tile':
                continue
            kw = dict(texel_per_m=e.get('texel_per_m', sp['texel_per_m']), ref_px_per_m=units_per_m or sp['ref_px_per_m'])
            src = d / e['file']
            if not src.exists():                       # tex_dir 里没有的（营地级这些后加的）回退到材质库自己的目录
                src = LIB / style / e['file']
            if 'variants' in e:
                M[mid] = [ext_mat(v['blender'], src, v.get('tint', 1.0), **kw) for v in e['variants']]
            else:
                M[mid] = ext_mat(e['blender'], src, e.get('tint', 1.0), **kw)
    return M


def band(style='toy_clay', mid='thatch_band', nmap=False, tex_dir=None, units_per_m=None):
    """茅草"一层一条带"材质（kind = band）：给 components.roof(band=…)。nmap=True 配法线贴图（同名材质只建一次，第一次调用定）。
    材质上记 'band_w' = 一条带横向覆盖多少四视图像素，tier_uv 按它算每层绕几条。"""
    sp = spec(style)
    e = sp['materials'][mid]
    if e['blender'] in _MATS:
        return _MATS[e['blender']]
    d = Path(tex_dir) if tex_dir else LIB / style
    img = bpy.data.images.load(str(d / e['file']))
    img.pack()
    m = mat(e['blender'], tex=img)
    if nmap:
        nimg = bpy.data.images.load(str(d / e['normal']))
        nimg.colorspace_settings.name = 'Non-Color'
        nimg.pack()
        nt = m.node_tree
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = nimg
        t.interpolation = 'Closest'
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nt.links.new(t.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], nt.nodes['Principled BSDF'].inputs['Normal'])
    m['band_w'] = img.size[0] / e.get('texel_per_m', sp['texel_per_m']) * (units_per_m or sp['ref_px_per_m'])
    return m
