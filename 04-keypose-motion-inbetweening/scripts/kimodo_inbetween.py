"""Kimodo + 全身关键帧约束：定格姿势（soma_poses.npz）放到指定帧，中间由 Kimodo 生成。
输入 $WORK_DIR/poses/<act>/soma_poses.npz（poses_to_soma.py 输出），关键帧号 / 提示词 / 帧数取 motions_def.MOTIONS[act]['kimodo']。
输出 $WORK_DIR/kimodo_kf/<act>/s<k>.npz（Kimodo 原始输出 + 骨架信息 + 种子 / 关键帧）和 constraints.json。
用法（环境变量见 run_kimodo.sh）：WORK_DIR=<工作目录> NS=4 python kimodo_inbetween.py [act,...]"""
import json, os, sys, time
import numpy as np, torch
from kimodo import load_model
from kimodo.tools import seed_everything
from kimodo.constraints import load_constraints_lst
from kimodo.geometry import matrix_to_axis_angle
WORK = os.environ.get('WORK_DIR', 'work')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import motions_def as MD
JOBS = {k: v['kimodo'] for k, v in MD.MOTIONS.items()}
only = sys.argv[1].split(',') if len(sys.argv) > 1 else list(JOBS)
NS = int(os.environ.get('NS', 4))
model, resolved = load_model('Kimodo-SOMA-RP-v1.2', device='cuda:0', default_family='Kimodo', return_resolved_name=True)
sk = model.skeleton; sk77 = sk.somaskel77 if hasattr(sk, 'somaskel77') else sk
names = list(sk77.bone_order_names); parents = sk77.joint_parents.cpu().numpy(); neutral = sk77.neutral_joints.cpu().numpy()
for act in only:
    J = JOBS[act]; P = np.load(f'{WORK}/poses/{act}/soma_poses.npz')
    assert [str(x) for x in P['names']] == names
    fi = [f for f, _ in J['keys']]; pi = [p for _, p in J['keys']]
    aa = matrix_to_axis_angle(torch.tensor(P['local_rot'][pi], dtype=torch.float32)).numpy()
    root = P['root'][pi].copy(); root[:, [0, 2]] -= root[0, [0, 2]]
    cons = [{'type': 'fullbody', 'frame_indices': fi, 'local_joints_rot': aa.tolist(), 'root_positions': root.tolist()}]
    os.makedirs(f'{WORK}/kimodo_kf/{act}', exist_ok=True)
    json.dump(cons, open(f'{WORK}/kimodo_kf/{act}/constraints.json', 'w'))
    for k in range(NS):
        seed_everything(2000 + k * 37); t = time.time()
        cl = load_constraints_lst(cons, sk, device='cuda:0')
        o = model(J['text'], J['nf'], num_denoising_steps=100, num_samples=1, post_processing=True, return_numpy=True,
                  cfg_type='separated', cfg_weight=[2.0, 2.0], constraint_lst=cl)
        single = {kk: np.asarray(v[0] if hasattr(v, 'shape') and len(v.shape) > 0 and v.shape[0] == 1 else v) for kk, v in o.items() if hasattr(v, 'shape')}
        # 关键帧处的关节位置误差（生成 vs 约束 FK）
        np.savez(f'{WORK}/kimodo_kf/{act}/s{k}.npz', **single, neutral_joints=neutral, parents=parents, names=np.array(names),
                 fps=float(model.fps), seed=2000 + k * 37, text=J['text'], key_frames=np.array(fi), key_poses=np.array(pi))
        print(f'GEN {act} s{k} {time.time() - t:.1f}s T={single["posed_joints"].shape[0]} peak={torch.cuda.max_memory_allocated() / 2**30:.1f}GiB', flush=True)
print('DONE')
