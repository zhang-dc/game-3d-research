"""动作定义示例（关键姿势 + Kimodo 补帧）。kimodo_inbetween.py 读 MOTIONS[act]["kimodo"]；姿势表本身给摆姿势脚本用（本仓库未收录，格式见 README）。

坐标约定（UAL 骨架角色，Blender armature 空间）：
  角度 yaw 正 = 向右转；lean 正 = 前倾；dirv(az, el)：az 0 = 正前、正 = 向右，el = 仰角。
  hand / lhand：手（socket）位置，相对肩中点、在"上身朝向"坐标里（x 正 = 左、y 正 = 前、z 正 = 上），单位 m。
  hand_w / lhand_w：同上但相对 rest 髋点在地面的投影（用于够地面），世界朝向。
  z：工具柄方向（工具框 Z，从主手指向工具头），上身坐标里的 (az, el)。
  t：工具框里 TOOL['v'] 这根轴要朝的方向（斧刃 / 竿下侧 / 壶身 / 锄刃 / 锤面），上身坐标 (az, el)，自动正交化。
  hip_shift：髋位移 (x 左, y 前, z 上)；stance：两脚位移。
工具：kind = pv_axe / pv_rod / pv_can（自建占位道具）或角色文件自带的 tool_hoe / tool_hammer；two_handed 时副手握 grip_off。
Kimodo：keys = [(30fps 帧号, 姿势序号)]，nf = 生成帧数；loop 动作重定向时按 period（秒）截循环段。
events：[(事件名, 姿势名)]，事件时刻 = 该姿势的关键帧。
"""

MOTIONS = {}

# ---------------------------------------------------------------- 横砍（用户认可：s1 / s2） ----------------------------------------------------------------
MOTIONS['chop_side'] = dict(
    tool=dict(kind='pv_axe', two_handed=True, v=(1, 0, 0)), loop=True, period=[1.25, 1.35],
    stance={'Left': (0.04, 0.10, 0), 'Right': (-0.04, -0.10, 0)},
    poses=[
        dict(name='windup', hold=0.55, hips_yaw=25, spine_yaw=40, lean=10, hip_shift=(-0.05, -0.02, -0.05), head_yaw=-45,
             hand=(-0.20, 0.10, -0.30), z=(110, 25), t='swing'),
        dict(name='hit', hold=0.40, hips_yaw=-20, spine_yaw=-15, lean=14, hip_shift=(0.05, 0.03, -0.06), head_yaw=10,
             hand=(0.02, 0.33, -0.30), z=(-15, 0), t='swing'),
    ],
    events=[('hit', 'hit')],
    kimodo=dict(nf=120, keys=[(0, 0), (15, 1), (39, 0), (54, 1), (78, 0), (93, 1), (117, 0)],
                text='A person chops a tree trunk with an axe held in both hands, using powerful horizontal swings: '
                     'twisting the torso to the right to wind up, then swinging hard from right to left at waist height, again and again.'))

# ---------------------------------------------------------------- 钓鱼（用户认可：s2 / s3） ----------------------------------------------------------------
_fish = [
    dict(name='ready', hold=0.5, hips_yaw=0, spine_yaw=0, lean=4, hip_shift=(0, 0, -0.02), head_yaw=0, hand=(-0.08, 0.28, -0.30), z=(0, 45), t='down'),
    dict(name='backcast', hold=0.4, hips_yaw=10, spine_yaw=10, lean=-6, hip_shift=(-0.03, -0.03, -0.01), head_yaw=-5, hand=(-0.16, 0.06, 0.10), z=(0, 115), t='down'),
    dict(name='cast', hold=0.3, hips_yaw=-5, spine_yaw=-5, lean=12, hip_shift=(0.02, 0.04, -0.04), head_yaw=0, hand=(-0.05, 0.33, -0.18), z=(0, 15), t='down'),
    dict(name='wait', hold=2.0, hips_yaw=0, spine_yaw=0, lean=6, hip_shift=(0, 0.02, -0.03), head_yaw=0, hand=(-0.08, 0.28, -0.28), z=(0, 30), t='down'),
    dict(name='reel_a', hold=0.25, hips_yaw=0, spine_yaw=0, lean=4, hip_shift=(0, 0.01, -0.03), head_yaw=0, hand=(-0.08, 0.27, -0.26), z=(0, 45), t='down', crank=0),
    dict(name='reel_b', hold=0.25, hips_yaw=0, spine_yaw=0, lean=4, hip_shift=(0, 0.01, -0.03), head_yaw=0, hand=(-0.08, 0.27, -0.26), z=(0, 45), t='down', crank=180),
]
MOTIONS['fish'] = dict(
    tool=dict(kind='pv_rod', two_handed=True, v=(1, 0, 0)), loop=False,
    stance={'Left': (0.03, 0.08, 0), 'Right': (-0.03, -0.06, 0)},
    poses=_fish[:4] + [_fish[4], _fish[5]] * 4,
    events=[('cast_release', 'cast'), ('line_wait', 'wait'), ('reel_start', 'reel_a')],
    kimodo=dict(nf=210, keys=[(0, 0), (24, 1), (36, 2), (54, 3), (120, 3)] + [(135 + 8 * i, 4 + (i % 2)) for i in range(8)],
                text='A person holds a fishing rod with both hands, lifts it back over the right shoulder, whips it forward to cast, '
                     'waits holding the rod in front of the chest, then turns the reel with the left hand.'))

# ---------------------------------------------------------------- 浇水：右手提壶，前倾倒水，左手自然垂 ----------------------------------------------------------------
# 壶：握后把手，把手 = 工具 Z，壶身在手指前方（TOOL v = 'can_fwd'）。倒水 = 整壶绕横轴前倾。
MOTIONS['water'] = dict(
    tool=dict(kind='pv_can', two_handed=False, v='can_fwd'), loop=True, period=[1.9, 2.1],
    stance={'Left': (0.03, 0.06, 0), 'Right': (-0.03, -0.04, 0)},
    poses=[
        dict(name='hold', hold=0.6, hips_yaw=-5, spine_yaw=-5, lean=8, hip_shift=(0, 0.01, -0.02), head_yaw=0, head_pitch=15,
             hand=(-0.16, 0.24, -0.40), z=(0, 90), t=(0, 0), lhand=(0.22, 0.04, -0.42)),
        dict(name='pour', hold=1.2, hips_yaw=-5, spine_yaw=-5, lean=16, hip_shift=(0, 0.03, -0.04), head_yaw=0, head_pitch=25,
             hand=(-0.14, 0.30, -0.36), z=(0, 50), t=(0, -40), lhand=(0.22, 0.06, -0.41)),
    ],
    events=[('pour_start', 'pour')],
    kimodo=dict(nf=150, keys=[(0, 0), (18, 1), (48, 1), (63, 0), (78, 1), (108, 1), (123, 0), (138, 1)],
                text='A person holds a watering can in the right hand, tilts it forward to pour water onto plants in front, '
                     'then levels it again, repeating slowly.'))

# ---------------------------------------------------------------- 锄地：双手举锄 → 锄头落地 ----------------------------------------------------------------
# 锄（tool_hoe）：柄 = 工具 Z，主手握点 = socket 原点，副手握点在柄尾 0.12 m；锄刃朝工具 −Y（v）。
MOTIONS['hoe'] = dict(
    tool=dict(kind='tool_hoe', two_handed=True, v=(0, -1, 0)), loop=True, period=[1.25, 1.35],
    stance={'Left': (0.05, 0.12, 0), 'Right': (-0.05, -0.10, 0)},
    poses=[
        dict(name='raise', hold=0.55, hips_yaw=0, spine_yaw=0, lean=-4, hip_shift=(0, -0.03, -0.02), head_yaw=0, head_pitch=5,
             hand=(-0.04, 0.22, -0.08), z=(0, 70), t=(180, 20)),
        dict(name='strike', hold=0.40, hips_yaw=0, spine_yaw=0, lean=24, hip_shift=(0, 0.04, -0.08), head_yaw=0, head_pitch=20,
             hand=(-0.06, 0.24, -0.34), z=(0, -60), t=(180, -30)),
    ],
    events=[('hit', 'strike')],
    kimodo=dict(nf=120, keys=[(0, 0), (15, 1), (39, 0), (54, 1), (78, 0), (93, 1), (117, 0)],
                text='A person hoes the soil with a long hoe held in both hands: raising it up in front, then chopping it down hard '
                     'into the ground in front of the feet, again and again.'))

# ---------------------------------------------------------------- 锤：右手举锤 → 砸到身前的钉子，左手扶着木板 ----------------------------------------------------------------
# 锤（tool_hammer）：柄 = 工具 Z，锤面朝工具 +X（v）。
MOTIONS['hammer'] = dict(
    tool=dict(kind='tool_hammer', two_handed=False, v=(1, 0, 0)), loop=True, period=[0.75, 0.85],
    stance={'Left': (0.03, 0.06, 0), 'Right': (-0.03, -0.04, 0)},
    poses=[
        dict(name='raise', hold=0.45, hips_yaw=5, spine_yaw=5, lean=6, hip_shift=(0, 0, -0.02), head_yaw=-5, head_pitch=15,
             hand=(-0.20, 0.10, 0.02), z=(-10, 95), t=(0, 10), lhand=(0.04, 0.30, -0.32)),
        dict(name='strike', hold=0.30, hips_yaw=-5, spine_yaw=-5, lean=14, hip_shift=(0, 0.02, -0.03), head_yaw=0, head_pitch=25,
             hand=(-0.10, 0.22, -0.30), z=(-10, 5), t=(0, -90), lhand=(0.04, 0.30, -0.34)),
    ],
    events=[('hit', 'strike')],
    kimodo=dict(nf=100, keys=[(0, 0), (10, 1), (24, 0), (34, 1), (48, 0), (58, 1), (72, 0), (82, 1), (96, 0)],
                text='A person hammers a nail into a wooden board in front of the chest: raising a hammer in the right hand '
                     'and striking down, while the left hand holds the board, again and again.'))

# ---------------------------------------------------------------- 采集：弯腰双手从地上捡起 → 站起抱在胸前 ----------------------------------------------------------------
MOTIONS['gather'] = dict(
    tool=None, loop=False,
    stance={'Left': (0.06, 0.04, 0), 'Right': (-0.06, -0.02, 0)},
    poses=[
        dict(name='stand', hold=0.4, hips_yaw=0, spine_yaw=0, lean=2, hip_shift=(0, 0, 0), head_yaw=0, head_pitch=10,
             hand=(-0.22, 0.04, -0.42), lhand=(0.22, 0.04, -0.42)),
        dict(name='reach', hold=0.7, hips_yaw=0, spine_yaw=0, lean=70, hip_shift=(0, -0.14, -0.45), head_yaw=0, head_pitch=20,
             hand_w=(-0.08, 0.30, 0.26), lhand_w=(0.08, 0.30, 0.26)),
        dict(name='lift', hold=1.0, hips_yaw=0, spine_yaw=0, lean=4, hip_shift=(0, 0, -0.02), head_yaw=0, head_pitch=15,
             hand=(-0.07, 0.24, -0.28), lhand=(0.07, 0.24, -0.28)),
    ],
    events=[('gather', 'reach')],
    kimodo=dict(nf=75, keys=[(0, 0), (24, 1), (36, 1), (60, 2), (74, 2)],
                text='A person squats and bends down to pick something up from the ground with both hands, then stands up holding it in front of the chest.'))

# ---------------------------------------------------------------- 掌舵：双手握舵轮 10 / 2 点，左打 → 回正 → 右打 → 回正 ----------------------------------------------------------------
MOTIONS['steer'] = dict(
    tool=dict(kind='wheel', center=(0.0, 0.40, -0.18), tilt=20), loop=True, period=[2.3, 2.5],   # center：相对肩中点（上身坐标），tilt：轮面后仰
    stance={'Left': (0.05, 0.04, 0), 'Right': (-0.05, -0.02, 0)},
    poses=[
        dict(name='center', hold=0.6, hips_yaw=0, spine_yaw=0, lean=6, hip_shift=(0, 0.01, -0.02), head_yaw=0, head_pitch=5, wheel=0),
        dict(name='left', hold=0.6, hips_yaw=0, spine_yaw=8, lean=6, hip_shift=(0.02, 0.01, -0.02), head_yaw=5, head_pitch=5, wheel=35),
        dict(name='right', hold=0.6, hips_yaw=0, spine_yaw=-8, lean=6, hip_shift=(-0.02, 0.01, -0.02), head_yaw=-5, head_pitch=5, wheel=-35),
    ],
    events=[],
    kimodo=dict(nf=150, keys=[(0, 0), (18, 1), (36, 0), (54, 2), (72, 0), (90, 1), (108, 0), (126, 2), (144, 0)],
                text='A person stands at a ship wheel holding it with both hands and steers, turning the wheel to the left, back to center, '
                     'to the right, and back to center.'))
