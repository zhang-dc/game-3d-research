# 06 · ¾ 俯视像素游戏里的建筑比例

> English summary: in a ¾ top-down camera the player judges proportions on screen, with the character as the ruler.
> Real-world metres are a sanity check, not an argument. With the projection `sx = x, sy = y·F − z` (F = 0.75, i.e.
> 36.87° pitch) walls are not foreshortened but roof depth is, so deep, steep roofs swamp the walls. Targets below come from
> measuring Pokémon Emerald tiles and pixel-art tutorials; `screen_ratio.py` computes them for a design.

## 判据是屏幕比例，尺子是角色

- 角色可见身高 H = 56 px（64 px 帧）。所有目标都写成"屏幕上是 H 的几倍"。
- 教训：按真实米制建的小屋被说"比例有问题"，拿住宅层高去辩护，被批"嘴硬"。评审判的是游戏画面。
- 投影：`sx = x，sy = y·F − z`，竖直方向 1:1，只有进深 × F。墙的屏幕高度 = 建模高度；屋顶屏高里有一大块是"进深 × F"。
  - 正立面墙露出 = 层数 × 层高 − (挑檐 × F + 封檐板)
  - 屋顶屏高 = max(屋脊抬升 + (进深/2 + 挑檐)·F，(进深 + 2·挑檐)·F)（坡度小于 atan F 时后坡也露出来，取第二项）

## 目标区间（屏幕值）

| 项 | 目标 | 依据 |
|---|---|---|
| 屋顶屏高 ÷ 墙露出 | 0.9–1.3，> 1.5 就"压墙" | 宝可梦绿宝石平房实测 1.1–1.4；Medeiros 教程约 1.0 |
| 单层墙露出 ÷ H | 1.3–2.0 | 绿宝石 1.15–1.4 |
| 门高 ÷ H | 1.0–1.5 | 绿宝石 0.9；真实门 2.0–2.1 m ÷ 1.75 m ≈ 1.2 |
| 门宽 ÷ 门高 | 0.45–0.75 | DIN 18101：885 × 2010 mm ≈ 0.44 |
| 窗台离地 ÷ H | 0.45–0.55 | 真实 750–900 mm；绿宝石 0.45 |
| 窗顶 | 与门顶对齐 | 常规做法 |
| 挑檐 | 屏幕 6–17 px，不遮门窗 | 真实 300–600 mm |

区间外不是错，是要拿出理由；最终由评审看图定。

## 真实建筑约束（保证"像房子"，别反过来用它否定评审）

- 坡度按屋面材料：茅草 45–55°（最小 45°）；黏土平瓦 ≥ 35°；天然石板瓦 ≥ 20°；木瓦 ≥ 14°。英国传统民居约 50°、跨度约 5 m。
- 进深大 + 坡陡 → 屋顶过大：正解是拆成平行多跨、L / T 形，而不是压低檐口（Essex Design Guide）。
- 二层外挑约 400 mm，最多 1200 mm；靠屋脊的烟囱出口高出屋脊 ≥ 600 mm；老虎窗低于屋脊、离檐口和屋脊各约 0.5 m，窗近似正方形。
- 立面：上层窗对齐下层门窗开间；门在入口开间居中；窗不贴墙角。

## 屋顶压墙时的调整顺序

1. 减进深（或拆成多跨 / L、T 形）——"进深 × F"通常是大头
2. 降坡度，但不低于屋面材料的最小坡度
3. 加墙高
4. 缩挑檐
5. 改机位 F——影响全游戏素材和阴影，最后才动

一个实测反例：平视下屋顶还占一半高度，说明屋顶抬升本身太大，是几何问题，不是机位问题（"这就是建模的比例有问题，跟游戏感没什么关系了"）。

## 其他规矩

- 建筑 1:1 展示、不缩放：门窗和角色、道具的比例一缩就穿帮。
- 生成参考图时**不要在提示词里限定比例**（"图片模型比你懂建筑"），比例放到建模时对。也别把比例写过头（"又低又宽"会画得过扁）。
- 被说"看着窄 / 比例怪"时，先查预览器的显示设置（纵向拉伸、缩放、机位），再查模型——一次"太窄"其实是预览器开着纵向 ×1.25。

## screen_ratio.py

```bash
python screen_ratio.py --depth 6 --storeys 1 --storey 128 --pitch 30 --eave 6 [--F 0.75] [--door 84]
# 进深单位：米 = 格，1 格 = 32 px；其余 px。输出墙露出、屋顶屏高、二者之比、墙 ÷ 角色、门 ÷ 角色，按上表标注
```

## 出处（2026-10 调研）

- 宝可梦绿宝石：pret/pokeemerald 反编译仓库的图块集和地图（主角帧 16×32，可见高 21 px）。门高 ÷ h 0.86–0.95，墙 1.15–1.4，窗台 0.45，平房屋顶 ÷ 墙 1.1–1.4。
- Pedro Medeiros "Top Down Houses"：https://saint11.art/img/pixel-tutorials/Top-Down-Houses-Compressed.gif
- LPC 风格指南：https://lpc.opengameart.org/static/LPC-Style-Guide/build/styleguide.html
- 坡度：NHBC 7.2.19；Cupa（石板瓦最小坡度）；thatchinginfo.com、thatchadvicecentre.co.uk（茅草）；CSSB（木瓦）
- 体量：Essex Design Guide（building form）
- 门：DIN 18101；烟囱：Approved Document J（经 LABC 转引）；老虎窗：Camden / Oldham / Reigate & Banstead 规划指引；Jetty：designingbuildings.co.uk

没查到可靠出处、不要当规则用的：典型檐口高度、黄金比在民居中的实际用法、三段式的量化比例。
