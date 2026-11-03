"""评审 / 对比页的拼页工具：图片、可拖动 3D 预览（像素化、部件开合、施工阶段）、挑选按钮，写成单个 HTML。

    from page import Page                             # 把 review_page/ 加进 sys.path
    p = Page('三种画法转 3D', lead='同一栋茅草住房……')
    p.finding('<b>这一版改了什么</b>', '1. ……')
    p.controls_3d()                                   # 全局：像素密度 / 光照 / 自动转
    p.section('圆胖玩具 × 黏土', p.cols([p.img('probe.png', '探针原图'), p.viewer('house.glb', fit_m=9, rot_y=180)]),
              sub='第二版', stats={'面数': 8000}, pick='toy_clay')
    p.picker('picks/style_r3')                        # 有 pick= 的卡片出现"喜欢"按钮 + 页尾留言框
    p.write('out.html')                               # 发布时 capabilities 用 p.capabilities

组件都在 kit.css / viewer3d.js / picker.js 里，写出时整份内联；图片转 WebP data URI，GLB 内嵌（PNG 贴图转 JPEG 省体积）。
3D 预览器：像素化（64 / 32 / 不像素化）、分档光照、拖拽自由视角、双击回游戏机位、点部件开关（part.* + extras.axis/range）、
施工阶段切换（extras.stage / only_stage）——约定见 viewer3d.js 顶部。
页面限 16 MB：写出时超了直接报错。
"""
from __future__ import annotations

import base64
import html
import io
import json
import struct
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
THREE = ('<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>\n'
         '<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js"></script>')
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="stylesheet" '
         'href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&family=JetBrains+Mono:wght@400;600&display=swap">')
LIMIT = 16 * 2**20
import os  # noqa: E402
REVIEW = Path(os.environ.get('REVIEW_DIR', 'review'))      # write_local 写到这个目录（用任意静态服务器托管它）
URL = os.environ.get('REVIEW_URL', 'http://127.0.0.1:8000')  # 该目录对应的地址，只用于打印链接
LOCAL_HEAD = ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
              '<meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0">\n')
esc = html.escape


def glb_jpeg(data: bytes, q: int = 88) -> bytes:
    """GLB 里的 PNG 贴图改存 JPEG（trimesh 导出是无损 PNG，几个模型就能撑破 16 MB）。"""
    jl = struct.unpack_from('<I', data, 12)[0]
    j = json.loads(data[20:20 + jl])
    bin_ = data[20 + jl + 8:]
    chunks, off = [], 0
    for i, bv in enumerate(j['bufferViews']):
        raw = bin_[bv.get('byteOffset', 0):bv.get('byteOffset', 0) + bv['byteLength']]
        im = next((x for x in j.get('images', []) if x.get('bufferView') == i), None)
        if im is not None and im.get('mimeType') == 'image/png':
            buf = io.BytesIO()
            Image.open(io.BytesIO(raw)).convert('RGB').save(buf, 'JPEG', quality=q)
            raw, im['mimeType'] = buf.getvalue(), 'image/jpeg'
        pad = (-len(raw)) % 4
        bv['byteOffset'], bv['byteLength'] = off, len(raw)
        chunks.append(raw + b'\0' * pad)
        off += len(raw) + pad
    newbin = b''.join(chunks)
    j['buffers'] = [{'byteLength': len(newbin)}]
    js = json.dumps(j, separators=(',', ':')).encode()
    js += b' ' * ((-len(js)) % 4)
    body = struct.pack('<I4s', len(js), b'JSON') + js + struct.pack('<I4s', len(newbin), b'BIN\0') + newbin
    return struct.pack('<4sII', b'glTF', 2, 12 + len(body)) + body


class Page:
    def __init__(self, title: str, lead: str = ''):
        self.title, self.lead = title, lead
        self.head: list[str] = []
        self.body: list[str] = []
        self.viewers: list[dict] = []
        self.pick_doc: str | None = None
        self.has_ctl = False

    # ---- 小件（返回 HTML 片段） ----
    def img(self, src, caption: str = '', w: int = 640, cls: str = '', quality: int = 88, lossless: bool = False) -> str:
        """lossless = 无损 WebP 且不缩小（像素图：有损压缩会把像素边糊掉）；配 cls='px' 放大时最近邻。"""
        im = src if isinstance(src, Image.Image) else Image.open(src)
        im = im.convert('RGBA') if im.mode in ('RGBA', 'LA', 'P') else im.convert('RGB')
        if not lossless:
            im.thumbnail((w, w))
        buf = io.BytesIO()
        if lossless:
            im.save(buf, 'WEBP', lossless=True, quality=100, method=6)
        else:
            im.save(buf, 'WEBP', quality=quality, method=6)
        uri = 'data:image/webp;base64,' + base64.b64encode(buf.getvalue()).decode()
        cap = f'<figcaption>{caption}</figcaption>' if caption else ''
        return f'<figure><img class="{cls}" alt="{esc(caption) or "图"}" src="{uri}" loading="lazy">{cap}</figure>'

    def wide(self, src, heads: list[str] | None = None, w: int = 1100, alt: str = '') -> str:
        """一张宽图（逐面对照这类），可带列标题。"""
        h = f'<div class="heads">{"".join(f"<span>{esc(x)}</span>" for x in heads)}</div>' if heads else ''
        return f'<div class="wide">{h}{self.img(src, "", w).replace("<figure>", "").replace("</figure>", "")}</div>'

    def viewer(self, glb, fit_m: float = 0, rot_y: float = 0, caption: str = '', smooth: bool = False, zoom: float = 1,
               color: int | None = None, keep_png: bool = False) -> str:
        """smooth = 贴图放大用线性采样（默认最近邻，同游戏）；zoom = 取景放大（默认取景按房子留了余量，单体雕塑类可给 1.5 左右）；
        color = 无贴图模型的统一底色（如 0x9a9a9a；生成器的纯几何输出默认白色，打光会过曝）；
        keep_png = 贴图保持 PNG（像素贴图转 JPEG 会糊、串色）。"""
        data = glb if isinstance(glb, bytes) else Path(glb).read_bytes()
        v = {'glb': 'data:model/gltf-binary;base64,' + base64.b64encode(data if keep_png else glb_jpeg(data)).decode(),
             'fitM': fit_m, 'rotY': rot_y, 'smooth': smooth, 'zoom': zoom}
        if color is not None:
            v['color'] = color
        self.viewers.append(v)
        i = len(self.viewers) - 1
        cap = f'<figcaption>{caption}</figcaption>' if caption else ''
        return f'<figure><div class="view" data-v="{i}"></div><div class="viewbar" data-vbar="{i}"></div>{cap}</figure>'

    def cols(self, items: list[str], min_px: int = 280) -> str:
        return f'<div class="cols" style="--col:{min_px}px">{"".join(items)}</div>'

    def stats(self, d: dict) -> str:
        return '<div class="stats">' + ''.join(
            f'<span>{esc(str(k))} <b class="{"bad" if isinstance(v, tuple) and v[1] else ""}">'
            f'{esc(str(v[0] if isinstance(v, tuple) else v))}</b></span>' for k, v in d.items()) + '</div>'

    def details(self, summary: str, inner: str) -> str:
        return f'<details><summary>{summary}</summary><div style="margin-top:10px">{inner}</div></details>'

    # ---- 块（直接加进页面） ----
    def finding(self, *paras: str):
        self.head.append('<div class="finding">' + ''.join(f'<p>{p}</p>' for p in paras) + '</div>')

    def note(self, text: str):
        self.head.append(f'<p class="note">{text}</p>')

    def controls_3d(self, ppm: int = 64, light: str = 'step'):
        """ppm / light = 页面打开时的默认值（看几何细节的页面用 ppm=0、light='smooth'）。"""
        self.has_ctl = True
        sel = lambda v, cur: ' selected' if v == cur else ''  # noqa: E731
        self.head.append(
            f'<div class="ctl"><label>像素密度 <select id="v-ppm"><option value="64"{sel(64, ppm)}>64 像素/米（游戏）</option>'
            f'<option value="32"{sel(32, ppm)}>32 像素/米</option><option value="0"{sel(0, ppm)}>不像素化</option></select></label>'
            f'<label>光照 <select id="v-light"><option value="step"{sel("step", light)}>分档（近似引擎）</option>'
            f'<option value="smooth"{sel("smooth", light)}>平滑</option></select></label>'
            '<button type="button" id="v-spin">自动转：关</button>'
            '<button type="button" id="v-wire">网格线：关</button>'
            '<span>3D 上拖动 = 自由视角，双击回游戏机位，点门这类部件 = 开 / 关</span></div>')

    def section(self, title: str, inner: str, sub: str = '', stats: dict | None = None, pick: str | None = None):
        btn = f'<button class="like" type="button" data-k="{esc(pick)}">喜欢</button>' if pick else ''
        head = f'<div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:center"><h2>{title}</h2>{btn}</div>'
        self.body.append(f'<section>{head}' + (f'<p class="sub">{sub}</p>' if sub else '') + inner
                         + (self.stats(stats) if stats else '') + '</section>')

    def raw(self, html_: str):
        self.body.append(html_)

    def picker(self, doc: str):
        self.pick_doc = doc
        self.body.append('<label style="display:grid;gap:6px"><b>想要的感觉 / 哪个最接近、差在哪</b>'
                         '<textarea id="pick-note"></textarea></label><span class="state" id="pick-state">正在连接存储…</span>')

    @property
    def capabilities(self) -> dict:
        return {'db': {}} if self.pick_doc else {}

    # ---- 写出 ----
    def write_local(self, name: str) -> str:
        """写到 $REVIEW_DIR 下，没有 16 MB 限制；顺手重写 $REVIEW_DIR/index.html 目录。
        返回本机地址（REVIEW_URL + 文件名；静态服务器自己开，如 python -m http.server -d $REVIEW_DIR）。"""
        out = self.write(REVIEW / f'{name}.html', limit=False)
        # 内嵌的 GLB / 图片拆成 <名>_files/ 下的文件，页面里只留相对路径：开发服务器（如 vite）启动时会扫根目录下所有 .html 找依赖，
        # 内嵌 100 万面 GLB 的 120 MB 页面把它扫到堆内存爆掉（2026-10-22）
        import hashlib
        import re
        fdir = REVIEW / f'{name}_files'
        if fdir.exists():
            for f in fdir.iterdir():
                f.unlink()
        fdir.mkdir(exist_ok=True)
        ext = {'model/gltf-binary': 'glb', 'image/webp': 'webp', 'image/png': 'png', 'image/jpeg': 'jpg'}

        def spill(m):
            data = base64.b64decode(m.group(2))
            fn = f'{hashlib.sha1(data).hexdigest()[:12]}.{ext[m.group(1)]}'
            (fdir / fn).write_bytes(data)
            return f'{fdir.name}/{fn}'
        text = re.sub(r'data:(model/gltf-binary|image/webp|image/png|image/jpeg);base64,([A-Za-z0-9+/=]+)', spill,
                      out.read_text(encoding='utf-8'))
        out.write_text(LOCAL_HEAD + text, encoding='utf-8')   # Claude 页面会自己套骨架，本地要自己写
        write_index()
        return f'{URL}/{out.name}'

    def write(self, path, limit: bool = True) -> Path:
        css = (HERE / 'kit.css').read_text(encoding='utf-8')
        parts = [f'<title>{esc(self.title)}</title>', '<meta name="claude:viewport-fit-sides" content="cover">', FONTS,
                 f'<style>{css}</style>', '<div class="wrap"><header>', f'<h1>{esc(self.title)}</h1>',
                 f'<p class="lead">{self.lead}</p>' if self.lead else '', *self.head, '</header>',
                 '<div style="display:grid;gap:20px">', *self.body, '</div></div>']
        if self.viewers:
            parts += [THREE, f'<script>{(HERE / "viewer3d.js").read_text(encoding="utf-8")}</script>',
                      f'<script>window.__V = {json.dumps(self.viewers, separators=(",", ":"))};</script>', INIT_VIEWERS]
        if self.pick_doc:
            parts += [f'<script>{(HERE / "picker.js").read_text(encoding="utf-8")}</script>',
                      f'<script>Picker.init({{ doc: {json.dumps(self.pick_doc)} }});</script>']
        out = Path(path)
        out.write_text('\n'.join(parts), encoding='utf-8')
        n = out.stat().st_size
        if limit and n > LIMIT:
            raise SystemExit(f'页面 {n / 2**20:.1f} MB，超过 16 MB 上限：少放几个模型或把图缩小')
        return out


def write_index():
    """review/ 下所有页面按修改时间倒序列成目录页（归档用）。"""
    import re
    import time
    rows = []
    for f in sorted(REVIEW.glob('*.html'), key=lambda f: -f.stat().st_mtime):
        if f.name == 'index.html':
            continue
        head = f.read_text(encoding='utf-8', errors='ignore')[:4000]
        t = re.search(r'<title>(.*?)</title>', head)
        rows.append(f'<tr><td><a href="{f.name}">{t.group(1) if t else f.stem}</a></td><td>{f.stem}</td>'
                    f'<td>{time.strftime("%Y-%m-%d %H:%M", time.localtime(f.stat().st_mtime))}</td>'
                    f'<td>{f.stat().st_size / 2**20:.1f} MB</td></tr>')
    css = (HERE / 'kit.css').read_text(encoding='utf-8')
    (REVIEW / 'index.html').write_text(
        f'<!doctype html><meta charset="utf-8"><title>素材预览页</title>{FONTS}<style>{css}</style><div class="wrap"><header><h1>素材预览页</h1>'
        '<p class="lead">对比页 / 挑选页，新的在上面。</p></header><section><div class="wide"><table>'
        '<tr><th>页面</th><th>文件</th><th>更新</th><th>大小</th></tr>' + ''.join(rows) + '</table></div></section></div>', encoding='utf-8')


INIT_VIEWERS = r"""<script>
(() => {
  const vs = [];
  const $ = (id) => document.getElementById(id);
  const ZH = { foundation: '地基', frame: '框架', done: '建成' };
  for (const el of document.querySelectorAll('.view[data-v]')) {
    const i = +el.dataset.v, bar = document.querySelector(`[data-vbar="${i}"]`);
    const init = {};   // 初始像素密度 / 光照跟 controls_3d 的默认选项走
    if ($('v-ppm')) init.ppm = +$('v-ppm').value;
    if ($('v-light')) init.light = $('v-light').value;
    const v = new PixelViewer(el, Object.assign(init, window.__V[i], {
      onReady(v) {
        if (v.parts.length) {
          const b = document.createElement('button'); b.type = 'button';
          b.textContent = `开 / 关（${v.parts.map((p) => p.name.replace('part.', '')).join('、')}）`;
          b.addEventListener('click', () => v.toggle()); bar.append(b);
        }
        if (v.stages.length > 1) for (const s of v.stages) {
          const b = document.createElement('button'); b.type = 'button'; b.textContent = v.stageNames?.[s] ?? ZH[s] ?? s;
          b.setAttribute('aria-pressed', String(s === v.stage));
          b.addEventListener('click', () => { v.setStage(s); for (const x of bar.querySelectorAll('[aria-pressed]')) x.setAttribute('aria-pressed', String(x === b)); });
          bar.append(b);
        }
      },
    }));
    v.onSpinChange = (on) => setSpin(on);
    vs.push(v);
  }
  function setSpin(on) { for (const v of vs) v.o.spin = on; if ($('v-spin')) $('v-spin').textContent = `自动转：${on ? '开' : '关'}`; }
  $('v-ppm')?.addEventListener('change', (e) => vs.forEach((v) => v.set({ ppm: +e.target.value })));
  $('v-light')?.addEventListener('change', (e) => vs.forEach((v) => v.set({ light: e.target.value })));
  $('v-spin')?.addEventListener('click', () => setSpin(!vs[0]?.o.spin));
  $('v-wire')?.addEventListener('click', (e) => { const on = !vs[0]?.o.wire; vs.forEach((v) => v.set({ wire: on })); e.target.textContent = `网格线：${on ? '开' : '关'}`; });
})();
</script>"""
