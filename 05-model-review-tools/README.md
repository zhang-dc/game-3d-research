# 05 · 模型评审工具

> English summary: small, dependency-light QA tools used every iteration — silhouette IoU / colour difference against
> the reference views in reference pixel coordinates, lit Cycles renders for seams and faceting, order-independent GLB
> equality for refactor regressions, open-state renders and numeric open-direction checks for movable parts, and a page
> kit that writes self-contained review pages with a pixelated, draggable 3D viewer.

| 文件 | 做什么 | 依赖 |
|---|---|---|
| `compare.py` | 按四视图的**像素坐标**直接渲染模型（不做框对齐，偏一个像素就是偏一个像素），出"参考 / 模型 / 叠图"表 + 俯视、斜 45°、斜 225°；打印并写出每个视图的剪影 IoU、平均色差、只在参考 / 只在模型里的像素数 | numpy, pillow, trimesh |
| `raster.py` | `to_view`（模型 → 视图坐标）、`tri_raster`（三角形覆盖的像素 + 重心坐标） | numpy |
| `render_lit.py` | Blender Cycles 正交 + 太阳光：查接缝、漏光、两面重叠闪烁、棱面（不打光的叠图里看不出来） | Blender |
| `glbeq.py` | 两个 GLB 是否同一个模型（与顶点顺序无关）：按网格名分组，比面数、材质名、排序后的世界坐标顶点、节点 extras。重构 / 抽库后回归用 | numpy, trimesh |
| `open_check.py` | 把组装版里的 `part.*` 按 extras 转到"开"的位置再渲染：看门背面、门洞、厚度、开合方向 | numpy, pillow, trimesh |
| `part_dir.py` | 开合方向的数值检查：每个部件铰链挨着哪面墙、起转时往屋外还是屋里、全程最多进屋多少、末端在铰链平面外多远 | numpy, trimesh |
| `review_page/` | `Page` 拼页：图片、可拖 3D 预览器（像素化 64 / 32 px/m、两档光、网格线、双击回游戏机位、点部件开合、施工阶段切换）、挑选按钮；写成单个 HTML 或拆资源的本地页 | pillow；页面里 three.js r128（CDN） |

## 用法

```bash
python compare.py model.glb sheet.png --views refs/house --k 0.01            # refs/house/{front,right,back,left}.png
python compare.py model.glb sheet.png --views refs/house --k 0.014164 --cx 384 --ground 632.2
blender -b --factory-startup --python render_lit.py -- model.glb lit.png 30 20 9      # yaw pitch [正交宽度米]
python glbeq.py old.glb new.glb                                               # 打印"一致"或差异
python open_check.py assembled.glb open.png 0.6
python part_dir.py assembled.glb --k 0.014164
```

```python
import sys; sys.path.insert(0, '05-model-review-tools/review_page')
from page import Page
p = Page('茅草房 两版', lead='只改了木构架粗细')
p.controls_3d()
p.section('新旧并排', p.cols([p.viewer('old.glb', fit_m=0, rot_y=180), p.viewer('new.glb', fit_m=0, rot_y=180)]),
          stats={'三角形': 19704})
p.write('review.html')                    # 单文件（内嵌资源，限 16 MB）
# 或 REVIEW_DIR=review REVIEW_URL=http://127.0.0.1:8000 → p.write_local('house')，再 python -m http.server -d review 8000
```

## 约定

- 模型坐标：glTF `(x, y, z) = (−E, U, −S)`（E = 正视图向右、S = 朝正面相机、U = 离地），和 `01` 的 bkit 导出一致；yaw 0 = 正面、90 = 右侧。
- `--k` = 1 个四视图像素对应的模型单位：按像素建模、没换成米时 0.01；换成米后 = 1 / 每米像素数。
- 部件：节点名 `part.<id>`，原点 = 转轴，`extras.axis`（Blender 轴，z 竖直）+ `extras.range = [关, 开]`（度）；`extras.stage` / `only_stage` / `stages` 见 `viewer3d.js` 顶部。

## 用这些工具时的经验

- IoU / 色差只报，不当"好坏"结论；判据是和挑中的参考图像不像。
- 7 个角度都要看（正 / 右 / 背 / 左 + 俯视 + 斜 45° + 斜 225°），并且一定打光看一遍。
- 改导出 / 构建脚本后立刻 `glbeq`；被说"刚才还是好的"时，先回看自己上一步改了什么。
- 自己的预览渲染也会骗人：曾经每个三角形只取一个颜色，木框线被画碎，误报"墙上多了交叉木框"→ 现在逐像素按 UV 取色 + 深度测试。
- 页面里百万面的模型别默认自动旋转；内嵌 100 万面 GLB 的 120 MB 页面会把开发服务器的依赖扫描撑爆，所以 `write_local` 把资源拆成文件。
- 评估游戏画面要用游戏自己的渲染器；这里的预览器和 Cycles 只用来查几何问题。
