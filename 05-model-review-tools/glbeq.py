"""两个 GLB 是否同一个模型（和顶点顺序无关）：按网格名（去掉 trimesh 加的 _xxxxxx 后缀）分组，
比面数、材质名、排序后的世界坐标顶点；再比节点 extras。
    python glbeq.py a.glb b.glb
（Blender 合并物体时顶点顺序跟"哪个是活动物体"有关，set 遍历顺序每次不同，所以要排序后比）"""
import json, re, struct, sys
from collections import defaultdict
import numpy as np, trimesh
def info(p):
    d=open(p,'rb').read(); jl=struct.unpack_from('<I',d,12)[0]; j=json.loads(d[20:20+jl])
    ex={n.get('name'):n.get('extras') for n in j['nodes'] if n.get('extras')}
    sc=trimesh.load(p,force='scene',process=False)
    g=defaultdict(list)
    for node in sc.graph.nodes_geometry:
        T,gn=sc.graph[node]; m=sc.geometry[gn]
        base=re.sub(r'_[0-9a-f]{6}$','',node)
        v=np.round(trimesh.transform_points(m.vertices,T),5)
        v=v[np.lexsort(v.T[::-1])]
        g[base].append((len(m.faces), getattr(getattr(m.visual,'material',None),'name',None), v))
    for k in g: g[k].sort(key=lambda t:(t[0], str(t[1]), t[2].shape[0]))
    return g,ex
a,ea=info(sys.argv[1]); b,eb=info(sys.argv[2])
bad=[]
if set(a)!=set(b): bad.append(f'网格名不同：只在前 {sorted(set(a)-set(b))[:5]} 只在后 {sorted(set(b)-set(a))[:5]}')
for k in sorted(set(a)&set(b)):
    if len(a[k])!=len(b[k]): bad.append(f'{k}: 子网格数 {len(a[k])}/{len(b[k])}'); continue
    for (fa,ma,va),(fb,mb,vb) in zip(a[k],b[k]):
        if fa!=fb or ma!=mb or va.shape!=vb.shape or np.abs(va-vb).max()>1e-4:
            bad.append(f'{k}: 面 {fa}/{fb} 材质 {ma}/{mb} 顶点差 {np.abs(va-vb).max() if va.shape==vb.shape else "形状不同"}')
if ea!=eb: bad.append(f'extras 不同：{[k for k in set(ea)|set(eb) if ea.get(k)!=eb.get(k)][:5]}')
print('一致' if not bad else f'不一致 {len(bad)} 处：'+'；'.join(bad[:8]), f'（网格 {sum(len(x) for x in a.values())} 个）')
