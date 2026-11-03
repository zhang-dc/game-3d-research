"""定格姿势（$WORK_DIR/poses/<act>/basis.npz）→ SOMA77 全身约束（Kimodo constraints JSON 的 fullbody 项所需数据）。
迁移法：两边 rest 都是 T 姿势，每根骨"相对 rest 的世界旋转" D = G·Restᵀ 换轴后照搬（Blender 骨架 (x,y前,z上) → SOMA (x,y上,z前)）。
没对应的 SOMA 关节（Neck2、手指、眼睛、脚尖末端…）局部旋转 = 单位阵。髋位置按两边髋高比例缩放。
用法：
  RIG_BLEND=<装了 UAL 骨架的 .blend> SOMA_REF=<任一 Kimodo SOMA 输出 .npz> WORK_DIR=<工作目录>   blender -b --factory-startup --python poses_to_soma.py -- <act>
输入 $WORK_DIR/poses/<act>/basis.npz：names (J,)、quat (P,J,4)、loc (P,J,3) = 每个关键姿势的 pose bone 局部四元数 / 位移
（rotation_mode = QUATERNION）。输出 $WORK_DIR/poses/<act>/soma_poses.npz（local_rot (P,77,3,3)、root (P,3)）。
环境变量：RIG_OBJECT = 骨架物体名（默认 Armature）。SOMA_REF 只用来取 SOMA77 的关节名 / 父子 / 中性姿势关节位置。
"""
import bpy, sys, json, math, os
import numpy as np
from mathutils import Matrix, Quaternion

act = sys.argv[sys.argv.index('--') + 1]
WORK = os.environ.get('WORK_DIR', 'work')
pd = f'{WORK}/poses/{act}'
bpy.ops.wm.open_mainfile(filepath=os.environ['RIG_BLEND'])
rig = bpy.data.objects[os.environ.get('RIG_OBJECT', 'Armature')]; PB = rig.pose.bones
if rig.animation_data is None: rig.animation_data_create()
for tr in rig.animation_data.nla_tracks: tr.mute = True
rig.animation_data.action = None
for b in PB: b.rotation_mode = 'QUATERNION'
B = np.load(f'{pd}/basis.npz'); names = [str(x) for x in B['names']]
K = np.load(os.environ['SOMA_REF'], allow_pickle=True)
sn = [str(x) for x in K['names']]; spar = K['parents'].astype(int); sJ = K['neutral_joints']
MAP = {'Hips': 'Hips', 'Spine1': 'Spine', 'Spine2': 'Spine1', 'Chest': 'Spine2', 'Neck1': 'Neck', 'Head': 'Head'}
for s in ('Left', 'Right'):
    MAP.update({s + 'Shoulder': s + 'Shoulder', s + 'Arm': s + 'Arm', s + 'ForeArm': s + 'ForeArm', s + 'Hand': s + 'Hand',
                s + 'Leg': s + 'UpLeg', s + 'Shin': s + 'Leg', s + 'Foot': s + 'Foot', s + 'ToeBase': s + 'ToeBase'})
C = np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]], float)
REST = {b.name: np.array([list(r) for r in b.matrix_local.to_3x3()]) for b in rig.data.bones}
hip_ual = rig.data.bones['Hips'].head_local.z
soma_ground = min(sJ[sn.index(n)][1] for n in ('LeftFoot', 'LeftToeBase', 'LeftToeEnd')) - 0.03
hip_soma = -soma_ground
k = hip_soma / hip_ual
H0 = np.array(rig.data.bones['Hips'].head_local)
LR, ROOT = [], []
for i in range(B['quat'].shape[0]):
    for j, n in enumerate(names):
        PB[n].rotation_quaternion = Quaternion(B['quat'][i, j]); PB[n].location = B['loc'][i, j]
    bpy.context.view_layer.update()
    G = {}
    for jj, n in enumerate(sn):
        if n in MAP:
            u = MAP[n]; Gu = np.array([list(r) for r in PB[u].matrix.to_3x3()])
            G[jj] = C @ (Gu @ REST[u].T) @ C.T
        else:
            G[jj] = G[spar[jj]] if spar[jj] >= 0 else np.eye(3)
    L = np.stack([G[jj] if spar[jj] < 0 else G[spar[jj]].T @ G[jj] for jj in range(len(sn))])
    LR.append(L)
    hp = np.array(PB['Hips'].head); d = hp - H0
    ROOT.append([d[0] * k, (hp[2]) * k, d[1] * k])
np.savez(f'{pd}/soma_poses.npz', local_rot=np.array(LR), root=np.array(ROOT), names=np.array(sn), k=k)
print('SOMA_OK', len(LR), 'k', round(k, 3), 'hip_soma', round(hip_soma, 3), np.round(ROOT, 3).tolist())
