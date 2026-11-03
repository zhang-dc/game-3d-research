"""可动件开合方向的数值检查（只报数，不下结论）：组装版 GLB 里每个 part.* 按 extras.range 从 range[0] 转到 range[1]，
看它是往屋外转还是往屋里（墙里）转。open_check.py 出的是图，这个出数，两个一起看。

    python part_dir.py <组装版.glb> [--k 0.014164] [--out S+|S-|E+|E-]

每个部件一行：
  墙       铰链挨着哪面墙：按铰链相对"本体"（所有非 part.* 网格）包围盒中心的位置，按半宽归一后取大的那个轴
           （E+ / E− = 正视图右 / 左侧墙，S+ = 正面墙，S− = 背面墙；glTF 里 x = −E、z = −S）。括号里是归一后的偏离（1 = 贴着包围盒边）
  起转     刚开始转的那一下，部件质心的移动方向和"屋外"方向的夹角余弦：+1 = 正往外，−1 = 正往屋里
  多进屋   转动全程（range[0] → range[1] 取 --steps 个角度）部件上最靠屋里的点，比起始角度时又往屋里多走了多少；0 = 没有更往里
  末端     转到 range[1] 时质心在铰链平面外多远（正 = 屋外）
距离是模型单位（UNITS=m 导出 = 米）；给 --k（模型单位 / 四视图像素，同 compare.py）再换成四视图像素。
--out 指定屋外方向（单独一个组件、本体不是整栋房子时，按位置判墙会判错）。
只算 extras.axis = 'z'（Blender 竖直轴 = glTF +Y，同 open_check.py）；别的轴打印"没算"。
转法同预览器 viewer3d.js：绕部件自己的原点（= 铰链）转 range 里的角度，正角 = 右手绕竖直轴。
"""
from __future__ import annotations

import argparse
import json
import re
import struct

import numpy as np
import trimesh

WALL_N = {'E+': (-1.0, 0.0), 'E-': (1.0, 0.0), 'S+': (0.0, -1.0), 'S-': (0.0, 1.0)}   # (glTF x, glTF z)


def gltf_json(path: str) -> dict:
    d = open(path, 'rb').read()
    jl = struct.unpack_from('<I', d, 12)[0]
    return json.loads(d[20:20 + jl])


def rot_y(deg: float) -> np.ndarray:
    t = np.radians(deg)
    c, s = np.cos(t), np.sin(t)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('glb')
    ap.add_argument('--k', type=float, default=0.0, help='模型单位 / 四视图像素（UNITS=m 的茅草房 = 0.014164，像素单位导出 = 0.01）')
    ap.add_argument('--out', choices=sorted(WALL_N), help='屋外方向（不给 = 按铰链位置判）')
    ap.add_argument('--steps', type=int, default=19)
    a = ap.parse_args()

    ext = {n.get('name'): n.get('extras') or {} for n in gltf_json(a.glb)['nodes']}
    sc = trimesh.load(a.glb, force='scene', process=False)
    parts, body = {}, []
    for node in sc.graph.nodes_geometry:
        T, g = sc.graph[node]
        v = trimesh.transform_points(np.asarray(sc.geometry[g].vertices, float), T)
        base = node if node in ext else re.sub(r'_[0-9a-f]{6}$', '', node)   # 多材质部件 trimesh 拆成 part.door_xxxxxx
        if base.startswith('part.'):
            parts.setdefault(base, {'T': T, 'v': []})['v'].append(v)
        else:
            body.append(v)
    if not parts:
        print('没有 part.* 节点')
        return
    B = np.concatenate(body) if body else np.concatenate([np.concatenate(p['v']) for p in parts.values()])
    lo, hi = B.min(0), B.max(0)
    c, half = (lo + hi) / 2, np.maximum((hi - lo) / 2, 1e-9)
    unit = (lambda x: f'{x:+.3f}（{x / a.k:+.1f} px）') if a.k else (lambda x: f'{x:+.3f}')
    print(f'本体包围盒中心 glTF {np.round(c, 3).tolist()}，半宽 {np.round(half, 3).tolist()}；距离单位 = 模型单位' + (f'，--k {a.k}' if a.k else ''))
    print('部件 | range | 墙 | 起转（cos，+ = 往外） | 多进屋 | 末端')
    for name in sorted(parts):
        e = ext.get(name, {})
        rng = e.get('range')
        if e.get('axis') != 'z' or not (isinstance(rng, list) and len(rng) == 2):
            print(f'{name} | {rng} | 没算（axis = {e.get("axis")!r}，只算竖直轴 z 且带 range 的）')
            continue
        T = parts[name]['T']
        h = T[:3, 3]
        V = np.concatenate(parts[name]['v']) - h
        d = h - c
        r = np.abs(d[[0, 2]]) / half[[0, 2]]
        if a.out:
            wall = a.out
        elif r[0] >= r[1]:
            wall = 'E-' if d[0] > 0 else 'E+'
        else:
            wall = 'S+' if d[2] < 0 else 'S-'
        nx, nz = WALL_N[wall]
        n = np.array([nx, 0.0, nz])
        r0, r1 = float(rng[0]), float(rng[1])
        cen = V.mean(0)
        R0 = rot_y(r0)
        c0 = R0 @ cen
        tan = np.array([c0[2], 0.0, -c0[0]]) * np.sign(r1 - r0)          # d(R(θ)c)/dθ 的方向，θ 往 r1 走
        start = float(tan @ n / max(np.linalg.norm(tan), 1e-12))
        deep0 = float((V @ R0.T @ n).min())
        deep = min(float((V @ rot_y(t).T @ n).min()) for t in np.linspace(r0, r1, a.steps))
        end = float(rot_y(r1) @ cen @ n)
        where = '' if a.out else f'（{max(r):.2f}）'
        print(f'{name} | {rng} | {wall}{where} | {start:+.2f} | {unit(deep - deep0)} | {unit(end)}')


if __name__ == '__main__':
    main()
