"""第 3 轮：按人体关节限制解手臂（numpy 向量化，在 Blender 里 import）。

farmer 骨架（UAL）rest = T 姿势、手掌朝前；Shoulder→Arm→ForeArm→Hand 的 rest 相对旋转都是单位阵，骨 Y 沿骨。
走 / 跑样本实测：肘只绕本地 Z 轴弯（右 −Z、左 +Z，前臂往前收），手腕相对前臂 ≤30°。

给定手骨朝向 H 和 socket 目标（→ 腕位置 w），肩点 s 固定，肘在以 s–w 为轴的圆上（swivel φ）。对每个 φ：
  上臂 Y 指向肘，上臂 X 取在臂平面内 → 肘是纯铰链（前臂局部旋转 = Rz(α)·Ry(τ)，α 由弯角定，τ = 前臂旋前 / 旋后）
  手局部旋转 = (上臂 · Rz(α))ᵀ · H 拆成 swing（腕弯折）+ twist（绕前臂轴）；twist 交给前臂 τ（±85°），剩下的留在手上。
代价（度为单位）：腕弯折 + 3×超 45° 部分 + 4×前臂旋转超 85° + 2×上臂旋转超 85° + 肘高于肩–腕连线 + 肘插进躯干 + 够不到。
逐帧状态 = (手绕握柄的滚转档, φ 档)，Viterbi 求整段代价最小（相邻帧 φ / 滚转变化也计代价）。
"""
import math
import numpy as np

LIM = {'wrist_soft': 45.0, 'twist': 85.0, 'upper_twist': 85.0, 'elbow_up_m': 0.03, 'torso_r': 0.16}


def _norm(v, eps=1e-9):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, eps)


def rot_axis(axis, ang):  # (3,), 标量或 (...) → (...,3,3)
    axis = np.asarray(axis, float); axis = axis / np.linalg.norm(axis)
    ang = np.asarray(ang, float); c, s = np.cos(ang), np.sin(ang); C = 1 - c
    x, y, z = axis
    R = np.empty(ang.shape + (3, 3))
    R[..., 0, 0] = c + x * x * C; R[..., 0, 1] = x * y * C - z * s; R[..., 0, 2] = x * z * C + y * s
    R[..., 1, 0] = y * x * C + z * s; R[..., 1, 1] = c + y * y * C; R[..., 1, 2] = y * z * C - x * s
    R[..., 2, 0] = z * x * C - y * s; R[..., 2, 1] = z * y * C + x * s; R[..., 2, 2] = c + z * z * C
    return R


def swing_twist_y(R):
    """R (...,3,3) → (swing 度 = Y 轴偏离, twist 度 = 绕 Y 的转角, 范围 ±180)。"""
    swing = np.degrees(np.arccos(np.clip(R[..., 1, 1], -1, 1)))
    # 去掉 swing：S = 把 Y 转到 R·Y 的最小旋转；T = Sᵀ R 是绕 Y 的旋转
    y2 = R[..., :, 1]
    k = np.cross(np.broadcast_to([0., 1., 0.], y2.shape), y2)
    kn = np.linalg.norm(k, axis=-1)
    ang = np.radians(swing)
    kk = k / np.maximum(kn, 1e-9)[..., None]
    c, s = np.cos(ang), np.sin(ang); C = 1 - c
    x, y, z = kk[..., 0], kk[..., 1], kk[..., 2]
    S = np.empty(R.shape)
    S[..., 0, 0] = c + x * x * C; S[..., 0, 1] = x * y * C - z * s; S[..., 0, 2] = x * z * C + y * s
    S[..., 1, 0] = y * x * C + z * s; S[..., 1, 1] = c + y * y * C; S[..., 1, 2] = y * z * C - x * s
    S[..., 2, 0] = z * x * C - y * s; S[..., 2, 1] = z * y * C + x * s; S[..., 2, 2] = c + z * z * C
    small = kn < 1e-6
    S[small] = np.eye(3)
    T = np.einsum('...ji,...jk->...ik', S, R)
    tw = np.degrees(np.arctan2(T[..., 0, 2], T[..., 0, 0]))
    return swing, tw


def solve_frame(side, s, Msh, wrist, H, l1, l2, spine, nphi=36):
    """一帧的全部候选。wrist (R,3)、H (R,3,3)：每个滚转档的腕目标和手骨朝向。
    返回 dict（形状 (R,P,...)）：cost, e, Mu, Mf, wq, 各项指标。"""
    R = wrist.shape[0]
    a = wrist - s; dist_raw = np.linalg.norm(a, axis=-1)
    dist = np.clip(dist_raw, abs(l1 - l2) + 1e-3, l1 + l2 - 1e-3)
    ad = _norm(a); wq = s + ad * dist[:, None]
    resid = np.linalg.norm(wrist - wq, axis=-1)                     # 够不到的量
    cosA = np.clip((l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist), -1, 1)
    c = s + ad * (l1 * cosA)[:, None]; r = l1 * np.sqrt(1 - cosA * cosA)
    down = np.array([0, 0, -1.])
    u0 = down - ad * (ad @ down)[:, None]
    bad = np.linalg.norm(u0, axis=-1) < 1e-3
    u0[bad] = np.array([0, 1., 0]) - ad[bad] * (ad[bad] @ np.array([0, 1., 0]))[:, None]
    u0 = _norm(u0); v0 = np.cross(ad, u0)
    phi = np.arange(nphi) * (2 * math.pi / nphi)
    radial = np.cos(phi)[None, :, None] * u0[:, None] + np.sin(phi)[None, :, None] * v0[:, None]   # (R,P,3)
    e = c[:, None] + r[:, None, None] * radial
    Yu = _norm(e - s); df = _norm(wq[:, None] - e)
    th = np.arccos(np.clip(np.einsum('rpi,rpi->rp', Yu, df), -1, 1))
    perp = df - Yu * np.einsum('rpi,rpi->rp', Yu, df)[..., None]
    pn = np.linalg.norm(perp, axis=-1)
    perp = np.where((pn > 1e-5)[..., None], perp / np.maximum(pn, 1e-9)[..., None], -radial)
    sg = 1.0 if side == 'Right' else -1.0
    Xu = sg * perp; Zu = np.cross(Xu, Yu)
    Mu = np.stack([Xu, Yu, Zu], -1)                                   # 列 = 轴
    alpha = -th if side == 'Right' else th
    Rz = np.zeros(alpha.shape + (3, 3)); ca, sa = np.cos(alpha), np.sin(alpha)
    Rz[..., 0, 0] = ca; Rz[..., 0, 1] = -sa; Rz[..., 1, 0] = sa; Rz[..., 1, 1] = ca; Rz[..., 2, 2] = 1
    Mf0 = Mu @ Rz
    Q0 = np.einsum('rpji,rjk->rpik', Mf0, H)                          # 手局部（τ = 0）
    swing, tw = swing_twist_y(Q0)
    tau = np.clip(tw, -LIM['twist'], LIM['twist'])
    Ry = rot_axis([0, 1, 0], np.radians(tau))
    Mf = Mf0 @ Ry
    qu = np.einsum('ji,rpjk->rpik', Msh, Mu)
    _, tw_u = swing_twist_y(qu)
    elev = (e - c[:, None])[..., 2]                                   # 肘高出肩–腕连线（米）
    h0, h1 = spine; sd = h1 - h0; t = np.clip(np.einsum('rpi,i->rp', e - h0, sd) / (sd @ sd), 0, 1)
    dt = np.linalg.norm(e - (h0 + t[..., None] * sd), axis=-1)
    cost = (swing + 3 * np.maximum(0, swing - LIM['wrist_soft']) + 4 * np.maximum(0, np.abs(tw) - LIM['twist'])
            + 2 * np.maximum(0, np.abs(tw_u) - LIM['upper_twist']) + 400 * np.maximum(0, elev - LIM['elbow_up_m'])
            + 800 * np.maximum(0, LIM['torso_r'] - dt) + 2000 * resid[:, None])
    return {'cost': cost, 'e': e, 'Mu': Mu, 'Mf': Mf, 'wq': np.broadcast_to(wq[:, None], e.shape), 'H': np.broadcast_to(H[:, None], Mu.shape),
            'swing': swing, 'twist': tw, 'tau': tau, 'twist_u': tw_u, 'flex': np.degrees(th), 'elev': elev, 'torso_d': dt,
            'resid': np.broadcast_to(resid[:, None], swing.shape)}


def viterbi(costs, roll_step_deg, nphi, w_phi=0.3, w_roll=0.2, circ_roll=True):
    """costs: list of (R,P)；返回每帧 (r, p) 和总代价。"""
    R, P = costs[0].shape
    rr, pp = np.meshgrid(np.arange(R), np.arange(P), indexing='ij'); rr = rr.ravel(); pp = pp.ravel()
    dp_ = np.abs(pp[:, None] - pp[None, :]); dp_ = np.minimum(dp_, P - dp_) * (360.0 / P)
    dr = np.abs(rr[:, None] - rr[None, :])
    if circ_roll: dr = np.minimum(dr, R - dr)
    Tm = w_phi * dp_ + w_roll * dr * roll_step_deg
    acc = costs[0].ravel().copy(); back = []
    for c in costs[1:]:
        tot = acc[:, None] + Tm
        b = np.argmin(tot, axis=0); back.append(b)
        acc = tot[b, np.arange(len(b))] + c.ravel()
    k = int(np.argmin(acc)); total = float(acc[k]); path = [k]
    for b in reversed(back):
        k = int(b[k]); path.append(k)
    path.reverse()
    return [(int(rr[k]), int(pp[k])) for k in path], total


def pick(sol, r, p):
    return {k: (v[r, p] if hasattr(v, 'ndim') and v.ndim >= 2 else v) for k, v in sol.items()}


def viterbi_T(costs, TR, nphi, w_phi=0.3):
    """同 viterbi，但第一维（R 档）之间的转移代价直接给矩阵 TR (R,R)。"""
    R, P = costs[0].shape
    rr, pp = np.meshgrid(np.arange(R), np.arange(P), indexing='ij'); rr = rr.ravel(); pp = pp.ravel()
    dp_ = np.abs(pp[:, None] - pp[None, :]); dp_ = np.minimum(dp_, P - dp_) * (360.0 / P)
    Tm = w_phi * dp_ + TR[rr][:, rr]
    acc = costs[0].ravel().copy(); back = []
    for c in costs[1:]:
        tot = acc[:, None] + Tm
        b = np.argmin(tot, axis=0); back.append(b)
        acc = tot[b, np.arange(len(b))] + c.ravel()
    k = int(np.argmin(acc)); total = float(acc[k]); path = [k]
    for b in reversed(back):
        k = int(b[k]); path.append(k)
    path.reverse()
    return [(int(rr[k]), int(pp[k])) for k in path], total
