# 01 · Blender 程序建模建筑（照四视图迭代）

> English summary: model buildings with Blender Python scripts, measuring every part in pixels on a 4-view reference
> sheet (front/right/back/left). Small hand-scripted parts (stone base, timber frame, curved thatch tiers, doors and
> shutters as separate movable parts) clearly beat both AI-generated meshes and "simple massing + projected texture".
> The reusable kit is `bkit/`; three examples rebuild the final house and oak tree.

## 结论

1. **形体细节要做成几何，贴图只补颜色。** "规整盒子 + 四视图投影贴图"被评审否掉（"整个模型的细节都没了，直接一个平面，更丑了"）。
   被认可的版本：每个部件单独成件（石基、墙、角柱、斜撑、梁头、分层茅草、烟囱、老虎窗、门、窗、百叶、花箱、壁灯、木桶），约 200 个网格、1.6–2 万三角形。
2. **以参考四视图为准、按像素量尺寸**，AI 重建的网格只作参考（看屋顶上表面、转角、背面这些四视图看不到的地方）。
   每轮按四视图像素坐标叠图，报剪影 IoU 和平均色差，再改常量重跑（`05-model-review-tools/compare.py`）。
3. **表面方向：纯色 × 顶点色明暗 + 浅几何（"方向 A"）胜过平铺贴图（"方向 B"）。**
   每种材质一个从参考图取的中位色；明暗写进顶点色（朝下、半球射线遮挡、凹沟变暗，朝上稍亮）；质感靠浅几何（草缕槽、木纹槽、板缝、石缝）。
   平铺贴图版被评"贴图很难看，没对齐的感觉"。
4. **会动的件单独建模、单独出 GLB**：原点在转轴上，开合角写在 glTF extras；本体只留 `mount.<id>` 挂点。另出一个组装版给预览器用。
5. **重复元素不能太规整。** 石墙像砌砖、圆木 / 板 / 瓦同尺寸成排会被说"太规整"。做法：在参考图上量每类重复元素的尺寸变异系数、倾角、行规整度，
   模型的统计量往参考靠；评审在 0.5× / 1× / 1.5× 参考变异度三档里选了 1.5×。生成参考图时提示词里 "nothing crooked" 这类句子要删。
6. **比例看着不对就是几何错了**，直接改墙高 / 屋顶抬升 / 檐口；不要拿真实建筑规范辩护（见 `06-building-screen-proportions`）。

### 试过、被否掉的

| 做法 | 结果 / 原因 |
|---|---|
| 参数化白模（几十个面的平墙平顶）+ 生成材质按部位贴 | "参数化建模建的方方正正的"；怎么贴都丑 |
| 按尺寸量出石基 / 墙 / 人字顶，再四视图投影贴图 | "细节都没了，直接一个平面"；比 AI 网格修补版还差 |
| 四视图整张直投到各部件面上（`PROJ=1`） | 只在正对视图的面上成立，侧面拉丝；"越改越烂了" |
| 生图模型画材质表 | 接缝比超线（木 1.98、石 1.39，阈值 1.3） |
| 从 AI 重建网格烘贴图 | 带明暗、射线打空出黑块 |
| 纯色 + 少量程序纹理 | 形对了以后被嫌"太规整" |
| 茅草裁小块平铺；茅草带多段拼 | 看不出是稻草；接缝"怪怪的" |
| 体素闭合 + marching cubes "量化"成像素风 | "一坨意义不明的东西"：树干、门洞全被抹平 |
| 用 Blender 整体重烘 / 重修 AI 网格 | 误差比原流程大（MAE 7.3–9.0 vs 6.8），见 `02` |

### 评审反馈里沉淀下来的建模规矩

- 木构件结构上连起来：墙顶一圈横梁压在檐口下，角柱伸到横梁顶，斜撑两头插进柱和梁；任何木件不悬空贴墙。粗细照参考图量。
- 茅草每层剖面是圆弧（底边内卷、中下部最鼓、顺椭圆弧收进上一层），不是"圆角盒子往上收"；层间朝下的面用深阴影色。
- 板状件挤出时保留原面（封闭实体）；门、老虎窗都从背面看一遍。门 / 百叶有真实厚度；门上窗要布尔挖穿、框里外两面都做；门洞接近纯黑并比门扇四边各宽 2 px。
- 倒角 / 变形只动该动的地方（只倒竖边四角；波浪边只推最下 15% 高度）。
- 曲面平滑着色、硬折角留硬边（`props.smooth(ob, angle=…)`）；低面数件 > 35° 的折角别顶点平均（会整条发黑）。
- 实心几何，材质不开透明 / alphaTest。
- 会动的东西分类：刚体部件（门、风车叶、车轮）拆件绕支点转；整体随风（树、草、旗）交给顶点着色器按高度摆（默认幅度 0.04 m 级）；
  状态变化（施工、生长、季节）换模型；烟、火、水花不建模，交给粒子 / 精灵。参考图里不画会动的件和烟火。
- 建筑 1:1 展示，不缩放（门窗和角色的比例一缩就穿帮）；纯装饰物可以按格子比例。

## 目录

```
bkit/                 Blender 里 import 的建模套件
  core.py             单位与坐标 P(E,S,U)、box / cylinder / blob / arch_panel / brace、make_part（可动部件）、tag（施工阶段）、export
  components.py       石基、墙 + 木构架、分层茅草屋顶、烟囱、窗 + 百叶 + 花箱、门、台阶、老虎窗、壁灯、木桶、roughen（几何质感）
  materials.py        材质库：load(style) → 材质字典；band()（茅草带）；程序纹理
  props.py            圆木、绳圈、石块、有厚度的布 / 板、smooth、to_meters、按施工阶段导出
  flat.py, flat_parts.py   方向 A：纯色 × 顶点色材质、shade()（顶点色明暗）、圆角木料 + 纹槽、茅草缕、桶板
  veg.py              植被组件（树干、枝、叶簇、叶形、法线自查）
  oak_pads.py, oak_trunk.py, oak_floret.py   橡树：叶片叠团树冠、按剪影表外扩的树干和根
  organic.py          带种子的顶点扰动（共享边界一致、锚点固定；不依赖 bpy），给重复元素做参差
  projection.py       四视图直投（已否，只为复现对照）
  lib/materials/toy_clay/materials.json         材质表（颜色、来源、用途；贴图 PNG 未收录）
  lib/materials/toy_clay/veg/veg_materials.json 植被颜色表
examples/
  house_flat.py       茅草房 · 方向 A（纯色 × 顶点色），约 2.9 万三角形
  house_textured.py   茅草房 · 原定稿那条（无贴图时退回"纯色 + 程序纹理"）
  tree_oak.py         橡树（详见 03），约 7.6 万三角形
tools/scan_view.py    按行 / 列扫四视图剪影和颜色区块，直接换算成建模坐标——量尺寸用
```

## 坐标与单位

| 项 | 约定 |
|---|---|
| 建模坐标 | `P(E, S, U)`：E = 正视图向右、S = 朝正面相机、U = 离地；Blender `(x, y, z) = (−E, S, U) × K`；范围参数一律 `(min, max)` |
| K | 0.01：房子按四视图像素建（1 px = 0.01 单位）；树按厘米建（1 cm = 0.01 → 1 单位 = 1 m） |
| 四视图尺度 | 示例房子拉齐后约 70.6 px/m，`props.to_meters(70.6)` 导出前换成米 |
| glTF 朝向 | 导出后 `(−E, U, −S)`：正面朝 glTF −Z，预览时绕 Y 转 180° |
| 贴图密度 | 64 texel/m、最近邻（游戏渲染规格） |
| 可动部件 | 节点 `part.<id>`，原点 = 转轴，extras `axis`（Blender 轴）+ `range = [关, 开]`（度）+ `stage`；部件 id 只用 `[a-z0-9_]` |
| 施工阶段 | `core.tag(objs, stage=…, only_stage=…)`；默认 foundation / frame / done，可自定义 `export(out, stages=[…], stage_names={…})` |

## 怎么跑

需要 Blender 5.2.x（测试过 5.2.2 Linux），只用 Blender 自带的 Python。

```bash
cd 01-blender-procedural-buildings
blender -b --factory-startup --python examples/house_flat.py -- out/house_flat.glb
blender -b --factory-startup --python examples/tree_oak.py   -- out/tree_oak.glb
GEO=1 blender -b --factory-startup --python examples/house_textured.py -- out/house_textured.glb
```

每个都会写 `out/<名>.glb`（组装版）和 `out/<名>_parts/`（`body.glb` + 每个可动部件一个 GLB）。
2026-11-03 在发布前用这三个命令重建过，`house_flat` 和 `tree_oak` 与原项目产物逐网格一致（`05-model-review-tools/glbeq.py`）。

`house_textured.py` 的环境变量：`GEO=1` 几何质感；`MATS=<目录>` + `THATCH=band` 用平铺贴图 / 茅草带（需要你自己的贴图，文件名见 materials.json）；
`UNITS=m` 导出前换成米；`PROJ=1` 四视图直投（已否，需要投影图目录）。

新建筑：复制一个 example，改顶部尺寸常量（像素或厘米），按顺序调组件 → `C.roughen()` → `props.to_meters(...)` → `core.export(out)`。
组件调用顺序决定随机数（石块、波浪边），定了别动。

## 已知问题

- `components.py` 的茅草房组件是平直着色导出（`flat.py` 版已平滑）。
- `materials.json` 的 `color` 是 sRGB 取色；旧组件直接当线性值用，不打光时比取色亮。`flat.py` 会先转线性。
- 十字窗棂、两向梁头交叉处共面重叠，Cycles 下有黑点。
- `door` / `lantern` / `steps` 只能挂正面墙。
- Blender 5.2 提示 `Material.use_nodes` 会在 6.0 去掉。
- 代码注释保留了原项目的研发记录（版本号、评审原话、未收录的文件名），作为出处说明；那些文件不在本仓库。

## 未收录

- 贴图 PNG（`lib/materials/**/*.png`）：是从生成的参考图上裁的，来源图的再分发条款未核实。
- 参考四视图、生成的 GLB、组件目录预览图。
- 材质裁图 / 取色 / 拉齐四视图的脚本（依赖内部生图服务）。
