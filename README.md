# game-3d-research

Research notes and small tools from building **stylized 3D assets for a 3D-rendered, pixel-art, ¾ top-down 2D game**:
procedural buildings and vegetation in Blender, AI multi-view image-to-3D, keypose + AI in-betweening for character motion,
and the review/QA tooling used to judge all of it.

The most useful part is not the code but the **negative results**: every section lists what was tried, how it was measured,
and why it was rejected. The work was done Sep–Nov 2026 on one workstation (RTX 5090 D 32 GB, WSL2 Ubuntu 24.04, Blender 5.2.2).

> 中文：这是一个"3D 渲染成像素风的 ¾ 俯视 2D 游戏"在做 3D 素材时的研究整理——Blender 程序建模建筑 / 植被、
> AI 多视图图生 3D、角色动作"关键姿势 + AI 补帧"、以及评审工具。最有价值的是每一节的"试过、为什么失败"。
> 各子目录的 README 用中文写，本页英文为主。

## Contents

| Dir | Topic | Main conclusion | Code |
|---|---|---|---|
| [`docs/methodology.md`](docs/methodology.md) | How to evaluate generated / procedural 3D | Report numbers, not impressions; judge in the target renderer; ablate every conditioning input; change one thing per round | — |
| [`01-blender-procedural-buildings`](01-blender-procedural-buildings/) | Blender scripts that model buildings from a 4-view reference sheet | Hand-scripted parts (thatch tiers, timber frame, door/window as separate movable parts) beat both AI meshes and "box + projected texture". Flat colour × vertex-colour shading beat tiled textures | `bkit` kit + 3 runnable examples |
| [`02-multiview-image-to-3d`](02-multiview-image-to-3d/) | GPT Image 4-view sheet → Pixal3D multi-view reconstruction → decimation | Pixal3D's own export is the baseline; whole-model "fix-up" chains (voxel remesh, wall flattening, projection texturing) made things worse; 33 catalogued failure modes | `roof_check.py` gate |
| [`03-stylized-vegetation`](03-stylized-vegetation/) | Trees / bushes for pixel rendering | Canopies = overlapping leaf "pads" placed by measuring the reference; AI high-poly + decimation, element assembly, and surface-fitting were all rejected | uses `01` kit (`examples/tree_oak.py`) |
| [`04-keypose-motion-inbetweening`](04-keypose-motion-inbetweening/) | Tool-use character animation (chop, fish, water, hoe…) | Program the key poses, let NVIDIA Kimodo in-between them under full-body keyframe constraints; text-to-motion alone and hand keying were rejected | anatomical arm IK + Viterbi, SOMA transfer, Kimodo driver, sample ranking |
| [`05-model-review-tools`](05-model-review-tools/) | QA tools | Silhouette IoU against the reference views, lit renders for seams, mesh-equality regression, movable-part direction checks, single-file review pages with a pixelated 3D viewer | 6 scripts + page kit |
| [`06-building-screen-proportions`](06-building-screen-proportions/) | Building proportions in a ¾ top-down camera | Judge on-screen ratios with the character as the ruler, not real-world metres | `screen_ratio.py` |

## Quick start

```bash
# Blender 5.2.x on PATH (tested 5.2.2, Linux). Examples write GLB + per-part GLBs.
cd 01-blender-procedural-buildings
blender -b --factory-startup --python examples/house_flat.py -- out/house_flat.glb
blender -b --factory-startup --python examples/tree_oak.py   -- out/tree_oak.glb
GEO=1 blender -b --factory-startup --python examples/house_textured.py -- out/house_textured.glb

# Review tools (plain Python ≥ 3.10)
pip install -r requirements.txt
python 05-model-review-tools/glbeq.py a.glb b.glb
python 05-model-review-tools/compare.py model.glb sheet.png --views <dir with front/right/back/left.png> --k 0.01
```

The keypose/Kimodo scripts need a Kimodo install and your own UAL-compatible rig; see that folder's README.

## Dependencies

| Part | Needs |
|---|---|
| `01`, `03`, `render_lit.py`, `poses_to_soma.py` | Blender 5.2.x (bundled Python; uses `bpy`, `bmesh`, `mathutils`, `numpy`) |
| `05`, `06`, `roof_check.py`, `rank_samples.py`, `arm_anat.py` | Python ≥ 3.10, `numpy`, `scipy`, `pillow`, `trimesh` (`requirements.txt`) |
| `kimodo_inbetween.py` | NVIDIA Kimodo (code Apache-2.0) + `Kimodo-SOMA-RP-v1.2` weights (NVIDIA Open Model License), CUDA GPU (~15 GiB peak) |
| Review pages | Browser; three.js r128 from cdnjs/jsdelivr |

Not included: model weights, generated images/meshes, the character model, texture crops of generated images. See [THIRD_PARTY.md](THIRD_PARTY.md).

## Status and caveats

- This is a research dump, not a library. APIs are whatever the experiments needed. Code comments are in Chinese and keep
  the original dev history (version numbers, reviewer quotes, names of files that are not published) as provenance.
- Measurements and verdicts come from one project's art direction ("chunky toy × clay" style, 64 texels/m, pixelated
  orthographic camera at 36.87° pitch). Transfer the method, re-check the thresholds.
- Licence terms of third-party models were read from their LICENSE files at the time; this is not legal advice.

## License

- Code: [MIT](LICENSE).
- Documentation (`*.md`, the JSON data tables): [CC BY 4.0](LICENSE-docs.md).
- Third-party components are under their own terms: [THIRD_PARTY.md](THIRD_PARTY.md).

Contributions: see [CONTRIBUTING.md](CONTRIBUTING.md).
