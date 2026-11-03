"""关键帧补帧版挑样本（不看图）：分 = 两手腕弯折最大值/45 + 肘或手离脊柱线 <0.10 m 的量×20 + 副手离握点 >1 cm 罚 10 + 首尾姿态差×20。
读 $WORK_DIR/retarget/kimodo_kf/<act>/<样本>/report.json（重定向步骤写的关节指标），写 $WORK_DIR/selection_kf.json（每个动作按分排序）。
WORK_DIR=<工作目录> python rank_samples.py [act,...]"""
import json, glob, os, sys
WORK = os.environ.get('WORK_DIR', 'work')
path = f'{WORK}/selection_kf.json'
sel = json.load(open(path, encoding='utf8')) if os.path.exists(path) else {}
sel['_rule'] = __doc__.split('\n')[0]
acts = sys.argv[1].split(',') if len(sys.argv) > 1 else sorted(os.listdir(f'{WORK}/retarget/kimodo_kf'))
for a in acts:
    sc = {}
    for p in glob.glob(f'{WORK}/retarget/kimodo_kf/{a}/*/report.json'):
        k = os.path.basename(os.path.dirname(p)); r = json.load(open(p, encoding='utf8')); an = r.get('arm_anatomy', {})
        wr = max(x for x in [(r.get('right_wrist_bend_deg') or [0, 0, 0])[2], (r.get('left_wrist_bend_deg') or [0, 0, 0])[2]])
        inside = sum(max(0, 0.10 - an[s][m]) for s in ('right', 'left') if s in an for m in ('elbow_to_spine_min_m', 'wrist_to_spine_min_m'))
        pen = 10 if (r.get('offhand_to_grip_max_m') or 0) > 0.01 else 0
        sc[k] = round(wr / 45 + inside * 20 + pen + (r.get('loop_pose_err_m') or 0) * 20, 3)
    order = sorted(sc, key=sc.get); sel[a] = {'order': order, 'scores': sc}
    print(a, [(k, sc[k]) for k in order])
json.dump(sel, open(path, 'w', encoding='utf8'), indent=1, ensure_ascii=False)
