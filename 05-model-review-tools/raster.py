"""正交视图投影 + 三角形光栅化的两个小工具（compare.py / open_check.py 用）。

模型坐标约定：glTF (x, y, z) = (−E, U, −S)；E = 正视图向右，S = 朝正面相机，U = 离地高度。yaw 0 = 正面，90 = 右侧。
"""
import numpy as np


def to_view(P: np.ndarray, yaw: float) -> np.ndarray:
    """模型坐标 → 视图坐标 (x 右, y 上, z 朝镜头)。"""
    v = P * np.array([-1, 1, -1])
    t = np.radians(yaw)
    c, s = np.cos(t), np.sin(t)
    return np.c_[v[:, 0] * c - v[:, 2] * s, v[:, 1], v[:, 0] * s + v[:, 2] * c]


def tri_raster(p2: np.ndarray, W: int, H: int):
    """一个三角形覆盖的像素中心 → (xs, ys, 重心坐标 3 列)。p2: 3×2，像素坐标。"""
    x0, y0 = np.floor(p2.min(0)).astype(int)
    x1, y1 = np.ceil(p2.max(0)).astype(int)
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W - 1), min(y1, H - 1)
    if x1 < x0 or y1 < y0:
        return None
    xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
    xs, ys = xs.ravel(), ys.ravel()
    a, b, c = p2
    den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(den) < 1e-12:
        return None
    px, py = xs + 0.5, ys + 0.5
    w0 = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / den
    w1 = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / den
    w2 = 1 - w0 - w1
    k = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
    if not k.any():
        return None
    return xs[k], ys[k], np.c_[w0[k], w1[k], w2[k]]
