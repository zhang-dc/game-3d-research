# Third-party components and licenses

**This repository redistributes no third-party code, model weights, datasets or assets.** It contains scripts that
*call* some of the tools below (you install them yourself) and documentation that *discusses* others.

"Verified" means the licence text was read from the official repository's LICENSE file or model card at the date shown.
"Not verified" means we did not read the primary text; check it yourself before use. None of this is legal advice.

## Used by scripts in this repository

| Component | Used by | License | Verified | Notes |
|---|---|---|---|---|
| Blender 5.2.x | `01`, `03`, `render_lit.py`, `poses_to_soma.py` | GPL-2.0-or-later | General knowledge, not re-checked | Our bpy scripts are MIT (GPL-compatible). Blender itself is not distributed |
| NVIDIA Kimodo (code) | `kimodo_inbetween.py` imports `kimodo` | Apache-2.0 | Verified 2026-11-02 (LICENSE in official repo clone) | Not vendored |
| Kimodo-SOMA-RP-v1.2 (weights) | `kimodo_inbetween.py` loads it | NVIDIA Open Model License | Verified 2026-11-02 (repo README model table + HF model card) | "Models are commercially usable"; §2.4 "NVIDIA claims no ownership rights in outputs". Redistributing the *model* requires the licence and notice "Licensed by NVIDIA Corporation under the NVIDIA Open Model License". Model card: ready for commercial use, incl. game and media animation; 30 fps, ≤ 10 s per clip. Trained on Bones Rigplay 1 |
| Kimodo-SMPLX-RP-v1 (weights) | not used | NVIDIA Internal Scientific Research and Development Model License (non-commercial) + SMPL-X (MPI, non-commercial) | Verified 2026-11-02 (repo README) | Listed only to warn: do not swap it in for commercial work |
| SOMA skeleton (NVlabs SOMA-X) | Kimodo output skeleton (`somaskel77`) | Apache-2.0 | Verified 2026-11-02 (HF metadata) | |
| LLM2Vec-Meta-Llama-3-8B-Instruct | Kimodo's text encoder (runtime) | Adapter MIT; base Meta Llama 3 Community License | Verified 2026-11-02 | MAU > 700M needs a licence from Meta; "Built with Meta Llama 3" when distributing Llama itself |
| Quaternius Universal Animation Library (UAL) | Skeleton naming / rest-pose convention assumed by `04` | CC0 1.0 | Verified 2026-10-30 / 10-31 (official itch.io page + `License.txt` inside the package) | Source: https://quaternius.itch.io/universal-animation-library . The character model built on it is **not** included |
| three.js r128 + GLTFLoader | `review_page` loads from cdnjs / jsdelivr at view time | MIT | Not re-checked for this release | Not vendored |
| numpy, scipy, Pillow, trimesh, opencv-python | plain-Python tools | BSD-3 / BSD-3 / MIT-CMU (HPND) / MIT / Apache-2.0 | Not re-checked | Installed via `requirements.txt` |

## Discussed in the documentation only

| Component | Where | License | Verified | Notes |
|---|---|---|---|---|
| Pixal3D (TencentARC) – code | `02` | MIT, © 2026 Tencent | Verified 2026-10 (LICENSE + NOTICE in repo clone) | |
| Pixal3D – weights (HF `TencentARC/Pixal3D`) | `02` | **Not verified** | — | Check the model card before commercial use |
| TRELLIS.2 (Microsoft), Pixal3D backbone | `02` | MIT | Verified (LICENSE in clone) | |
| Hunyuan3D-2.1 incl. Paint (Tencent) | `02`, `03` | Tencent Hunyuan 3D 2.1 Community License | Verified (LICENSE in clone) | **Does not apply in the EU, UK and South Korea** (territory clause); outputs are not "Model Derivatives" |
| Hunyuan3D-2mv / 2.0 / Omni | `02` | **Not verified** | — | |
| Hunyuan3D-Part (P3-SAM, X-Part) | `03` | Tencent Hunyuan 3D-Part Community License | Verified 2026-10-24 (LICENSE in clone) | EU / UK / South Korea excluded; MAU > 1M needs a licence; outputs may not be used to improve other AI models |
| HY-Motion 1.0 (Tencent) | `04` | Tencent HY-MOTION 1.0 Community License | Verified 2026-11-02 (`License.txt` in official repo clone) | §1(l)/§5(c): **may not use, reproduce, distribute or display the works *or their Output* outside the Territory = worldwide excluding EU, UK, South Korea**. MAU > 1M on release month needs a licence. §5(b): Output may not be used to improve other AI models. §6(d): Tencent claims no rights in Outputs. Its text encoders: Qwen3-8B (Apache-2.0), CLIP ViT-L/14 (MIT) |
| Hi3D v1.0 (geometry refiner) | `03` | Hi3D Open License 1.0 | **Partly**: summarised in our 2026-10-23 research notes; licence text not re-read for this release | Notes say: commercial use allowed; MAU > 200k or monthly revenue > US$1M needs a separate licence; commercial use must show "Powered by Hi3D 1.0" |
| GPT Image 2.5 (OpenAI), used to draw reference sheets | `01`, `02`, `03` | Service terms **not verified** | — | No generated images are included in this repository |
| ComfyUI-UV-Decimate, meshoptimizer, PaMO, QuadriFlow, Instant Meshes, QuadWild | `02` (decimation survey) | Not verified | — | Mentioned only; none was run in the reported experiments except as noted |
| Pokémon Emerald (pret/pokeemerald decomp) | `06` | Not applicable | — | Only pixel measurements of tiles are quoted; no assets included |

## Not included on purpose

- Model weights of any kind.
- Generated reference images, texture crops taken from them, and generated meshes / animations.
- The project's character model (geometry made in-house on a UAL skeleton, built against reference images whose
  redistribution rights were not obtained), props, and any game-engine code.
