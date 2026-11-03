# 04 · 角色动作：程序摆关键姿势 + AI 补中间帧

> English summary: for short tool-use loops (chop, fish, water, hoe, hammer, gather, steer) on a small low-poly human
> with a UAL-style skeleton, the approach that got approved was: write each motion as a short table of key poses,
> solve them with an anatomically constrained arm IK, transfer them to NVIDIA Kimodo's SOMA skeleton, and let
> Kimodo-SOMA-RP-v1.2 generate the in-betweens under full-body keyframe constraints; then retarget back, lock the tool
> rigidly to the main hand, and rank samples by joint metrics (no eyeballing). Hand keying, pure text-to-motion
> (HY-Motion 1.0) and hard pose-to-pose cuts were all rejected.

## 结论

| 路线 | 结果 |
|---|---|
| 手 K 关键帧 | "小人动作有点抽象" |
| 文字生成动作（HY-Motion 1.0，以及 Kimodo 纯文字） | 跑通了，但"挥得没力气 / 幅度太小，跟没有一样"、"胳膊关节完全不是人体的关节"；工具方向不受控 |
| 纯定格姿势（不做过渡，直接切） | 可用但太硬；保留下来当关键帧 |
| **关键姿势 + Kimodo 全身关键帧约束补帧** | **采用**："这个补帧效果还可以啊，我们后面就做关键帧让 AI 补齐吧" |

还有几条通用经验：

1. **道具刚性锁主手，副手只去够握点。** 第一版让副手 IK 反过来带动工具朝向：斧子在手里转、掌舵时手往下窜。
2. **手臂要按人体关节限制解**，不要"按工具硬定手朝向、再让前臂顺着摆"——那样肘会翻到腕上、前臂转 177°。见下面 `arm_anat.py`。
3. **循环段必须包含源动作里最快的那一下。** 按"首尾姿态最接近"挑循环段会挑到静止段，结果"跟没有一样"。
4. **事件时刻（命中、出竿）取关键姿势所在帧**，不要用减速点检测：横砍检测到收斧那段，树的方向摆反了。
5. **验收量整段轨迹**（预备最高点、扫角、峰速、腕弯折、肘进躯干），只量命中帧会被优化方钻空子（见 `docs/methodology.md`）。
6. **工具朝向在两个关键帧之间直接 slerp 会转进身体内侧** → 在插值方向附近搜索（左右 ±60°、上下 ±30°）挑代价最小的。只搜俯仰试过，腕弯更大。
7. 小角色手臂比 SOMA 短：手腕离肩超过约 0.46 m（握点 0.54 m）就够不到；摆姿势时打印每个姿势"够不到"的量，非 0 就改手位。
8. 托管图像 API 做不了逐帧姿态控制（另一个项目里用量化指标穷举证伪过：步幅相关系数 0.01–0.34，基线 0.86）；加的角色参考图越多姿态越差。
   正解是 img2img（姿态图当底图）或 ControlNet，或者干脆走骨骼动画——这也是本节路线的起点。

## 管线

```
motions_def.py  每个动作：关键姿势表、工具、站位、事件、Kimodo 帧号 / 帧数 / 提示词
  ↓  摆关键姿势（未收录，见"未收录"）：脊柱分段转体 + 前倾 + 重心；腿两骨 IK 踩固定站位；手臂 arm_anat；工具握法在 60 种里挑代价最小
poses/<act>/basis.npz          每个关键姿势的 pose bone 局部四元数 / 位移
  ↓  poses_to_soma.py（Blender）  两边 rest 都是 T 姿势：每骨"相对 rest 的世界旋转"换轴照搬；无对应关节 = 单位阵；髋高按比例缩放
poses/<act>/soma_poses.npz     SOMA77 局部旋转 + 根位置
  ↓  kimodo_inbetween.py（run_kimodo.sh）  fullbody 约束放到指定帧号，生成 NS 个样本（默认 4，100 步去噪，CFG 2.0/2.0）
kimodo_kf/<act>/s<k>.npz
  ↓  重定向回原骨架（未收录）：循环段截取、脚底锁定、工具刚性锁主手、工具朝向 = 关键帧值 + 中间搜索、主手位置关键帧校正、副手够握点
retarget/kimodo_kf/<act>/<样本>/report.json   关节指标
  ↓  rank_samples.py   分 = 两手腕弯折最大值/45 + 肘或手离脊柱线 < 0.10 m 的量 × 20 + 副手离握点 > 1 cm 罚 10 + 首尾姿态差 × 20
selection_kf.json
```

### 姿势表约定（`scripts/motions_def.py` 顶部有完整说明）

- 角度：`yaw` 正 = 向右转；`lean` 正 = 前倾；方向 `(az, el)`：az 0 = 正前、正 = 向右，el = 仰角。
- `hand` / `lhand`：手（挂点）相对肩中点、在上身朝向坐标里（x 左、y 前、z 上，米）；够地面用 `hand_w` / `lhand_w`（相对髋在地面的投影）。
- 工具：`z` = 柄方向（主手 → 工具头），`t` = 刃 / 面 / 壶身朝向（`'swing'`、`'down'` 或方向）。
- `events`：`(事件名, 姿势名)`，事件时刻 = 该姿势的关键帧。
- `kimodo`：`keys = [(30fps 帧号, 姿势序号)]`、`nf` 生成帧数、`text` 提示词（按官方示例写成较长的分段描述）。

### `arm_anat.py`：人体关节限制 IK + Viterbi（纯 numpy，可单独用）

给定手骨朝向 H 和腕目标，肩点固定，肘在以"肩–腕"为轴的圆上（swivel φ，36 档）。对每个 φ：

- 上臂 Y 指向肘、X 取在臂平面内 → 肘是纯铰链（前臂局部 = Rz(α)·Ry(τ)，α 由弯角定，τ = 前臂旋前 / 旋后）；
- 手局部旋转拆成 swing（腕弯折）+ twist（绕前臂轴）；twist 交给前臂（±85°），剩下的留在手上；
- 代价（度）：腕弯折 + 3 × 超 45° 部分 + 4 × 前臂旋转超 85° + 2 × 上臂旋转超 85° + 肘高于"肩–腕连线"（×400/m）+ 肘进躯干（×800/m）+ 够不到（×2000/m）。

逐帧状态 = (手绕握柄的滚转档, φ 档)，Viterbi 求整段代价最小（相邻帧 φ / 滚转的变化也计代价），得到连续、不翻肘的手臂。
前提：UAL 风格骨架，rest = T 姿势、手掌朝前，Shoulder→Arm→ForeArm→Hand 的 rest 相对旋转是单位阵，骨 Y 沿骨；肘只绕本地 Z 弯（右 −Z、左 +Z）。

## 怎么跑

```bash
# 1) 关键姿势 → SOMA（需要你自己的 UAL 骨架 .blend；SOMA_REF = 任意一个 Kimodo SOMA 输出 npz，只取关节名 / 父子 / 中性姿势）
RIG_BLEND=my_rig.blend RIG_OBJECT=Armature SOMA_REF=some_kimodo_output.npz WORK_DIR=work \
  blender -b --factory-startup --python scripts/poses_to_soma.py -- chop_side

# 2) Kimodo 补帧（按 Kimodo 官方说明装环境、下权重；峰值显存约 15 GiB）
KIMODO_HOME=/path/to/kimodo_assets WORK_DIR=$PWD/work PYTHON=/path/to/kimodo-venv/bin/python \
  bash scripts/run_kimodo.sh chop_side,fish

# 3) 重定向后按关节指标排序
WORK_DIR=work python scripts/rank_samples.py chop_side,fish
```

## 已知问题

- 小角色手臂比 SOMA 短：挥到最远时主手被限制在够得着的范围（横砍约挪了 0.35 m）。
- 采集：弯腰时手停在约膝盖高度（Kimodo 输出的手臂比例 → 短臂角色），无工具动作没做手位校正。
- Kimodo 单段最长 10 s、30 fps。

## 未收录

- 摆关键姿势和重定向的两个 Blender 脚本（约 1500 行）：和一个未公开的角色文件、道具挂法强耦合；算法见上面的管线说明。
- 角色模型（骨架来自 Quaternius Universal Animation Library，CC0；几何是项目自建的，未收录）、道具、生成的动作和 GLB。
- HY-Motion 那一轮的脚本（路线已否）。

许可证注意：Kimodo-SOMA 权重是 NVIDIA Open Model License（可商用、输出归使用者）；HY-Motion 1.0 的社区许可证**排除欧盟 / 英国 / 韩国**（含其输出的使用和展示），
月活 > 100 万须另行申请。见 [THIRD_PARTY.md](../THIRD_PARTY.md)。
