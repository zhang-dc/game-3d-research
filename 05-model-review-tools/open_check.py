"""把组装版里的可动部件（part.*）按 extras 转到"开"的位置再渲染：检查门背面、门洞、厚度、开合方向。

    python open_check.py <组装版.glb> <out.png> [开的比例 0–1]
"""
import json
import struct
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare import oblique, on_white  # noqa: E402

glb, out = sys.argv[1], sys.argv[2]
frac = float(sys.argv[3]) if len(sys.argv) > 3 else 0.6
d = Path(glb).read_bytes()
jl = struct.unpack_from('<I', d, 12)[0]
nodes = json.loads(d[20:20 + jl])['nodes']
ext = {n['name']: n.get('extras', {}) for n in nodes}
sc = trimesh.load(glb, force='scene', process=False)
for node in list(sc.graph.nodes_geometry):
    if not node.startswith('part'):
        continue
    e = ext.get(node) or ext.get(node.rsplit('_', 1)[0], {})   # 多材质的部件，trimesh 会拆成 part.door_xxxxxx 几个子网格
    ang = np.radians(e.get('range', [0, 0])[1] * frac)
    T, _ = sc.graph[node]
    R = trimesh.transformations.rotation_matrix(ang, [0, 1, 0])     # Blender z（竖直）= glTF +Y
    sc.graph.update(node, matrix=T @ R)
    print(node, e.get('range'), f'转 {np.degrees(ang):.0f}°')
ms = sc.dump()
views = [(0, 0), (20, 30), (-20, 30), (160, 25), (90, 0), (270, 0)]
ims = [on_white(oblique(ms, y, p, S=420)) for y, p in views]
W = sum(im.width for im in ims[:3]) + 20
H = max(im.height for im in ims[:3]) + max(im.height for im in ims[3:]) + 10
sheet = Image.new('RGB', (max(W, sum(im.width for im in ims[3:]) + 20), H), (255, 255, 255))
x = 0
for im in ims[:3]:
    sheet.paste(im, (x, 0)); x += im.width + 10
x, y = 0, max(im.height for im in ims[:3]) + 10
for im in ims[3:]:
    sheet.paste(im, (x, y)); x += im.width + 10
sheet.save(out)
