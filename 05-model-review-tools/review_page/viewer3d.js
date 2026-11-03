/* 像素 3D 预览器（review_page/page.py 拼页时内联）。依赖 three r128 + GLTFLoader（legacy 全局版）。
 *
 *   const v = new PixelViewer(hostEl, { glb: 'data:…' 或 URL, fitM: 9.0, rotY: 180 });
 *   v.set({ ppm: 64 | 32 | 0, light: 'step' | 'smooth', wire: true | false（三角形网格线）, spin: false（默认，面数多时转起来卡）| true });
 *
 * 机位：正交，默认俯角 36.87°（游戏机位）；拖动 = 自由视角（横向转、纵向调俯角），双击回到游戏机位。
 * 像素化：按 ppm（像素/米）定渲染分辨率，再最近邻放大；ppm = 0 不像素化。
 *
 * 部件约定（和 01-blender-procedural-buildings/bkit 导出一致）：
 *   节点名 part.<id>（three 的 GLTFLoader 会删掉名字里的点，原名在 userData.name）；节点原点 = 转轴。
 *   extras.axis = 'x' | 'y' | 'z'（Blender 轴，Z 向上）+ extras.range = [关, 开]（度）→ 点一下开 / 关；
 *   extras.axis 但没有 range → 可旋转件（风车叶片），"动起来"时一直转；
 *   extras.stage = foundation | frame | done（从哪个阶段起出现），extras.only_stage = 只在这个阶段出现（脚手架）。
 *   阶段名不是这三个时（每个模型自己的阶段，如帐篷 poles / cover），任一节点写 extras.stages = [按顺序的阶段 id]、
 *   extras.stage_names = {id: 中文名}（bkit 导出时放在 stage_order 空节点上）；默认显示最后一个阶段（建成）。
 * 有可交互部件时，构造后 v.parts 列出它们；v.stages 列出模型里出现过的施工阶段。
 */
(function () {
  const GAME_PITCH = Math.atan(0.75);
  // Blender 轴 → three 轴（glTF 导出时 Z 上 → Y 上，Y → -Z）
  const AXIS = { x: new THREE.Vector3(1, 0, 0), y: new THREE.Vector3(0, 0, -1), z: new THREE.Vector3(0, 1, 0) };
  const STAGE_ORDER = ['foundation', 'frame', 'done'];
  let steps = null;
  function stepTex() {
    if (steps) return steps;
    steps = new THREE.DataTexture(new Uint8Array([90, 170, 255]), 3, 1, THREE.LuminanceFormat);
    steps.minFilter = steps.magFilter = THREE.NearestFilter; steps.needsUpdate = true;
    return steps;
  }
  function toBuf(uri) {
    const s = atob(uri.split(',')[1]);
    const b = new Uint8Array(s.length);
    for (let i = 0; i < s.length; i++) b[i] = s.charCodeAt(i);
    return b.buffer;
  }
  // 所有预览器共用一个 WebGL 渲染器，各自只有一张 2D 画布（渲染完 drawImage 拷过去）：
  // 浏览器同时只留 ~16 个 WebGL 上下文，一页几十个模型时多出来的会被丢掉变黑
  let shared = null;
  function gl() {
    if (shared) return shared;
    shared = new THREE.WebGLRenderer({ antialias: false, alpha: true });
    shared.outputEncoding = THREE.sRGBEncoding;
    shared.setPixelRatio(1);
    return shared;
  }
  // 滚出屏幕的预览器不画（几十个百万面模型一起转太重），滚回来再补画
  const io = 'IntersectionObserver' in window ? new IntersectionObserver((es) => {
    for (const e of es) { const v = e.target.__pv; v.visible = e.isIntersecting; if (v.visible && v.stale) v._draw(); }
  }, { rootMargin: '200px' }) : null;
  const all = [];
  let last = performance.now();
  function tick(t) {
    const dt = Math.min(0.1, (t - last) / 1000); last = t;
    for (const v of all) v._tick(dt);
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);

  class PixelViewer {
    constructor(host, opts) {
      this.o = Object.assign({ ppm: 64, light: 'step', spin: false, rotY: 0, fitM: 0, onReady: null }, opts);
      this.canvas = document.createElement('canvas');
      this.canvas.style.cssText = 'width:100%;height:100%;display:block;image-rendering:pixelated;touch-action:none;cursor:grab';
      host.append(this.canvas);
      this.ctx = this.canvas.getContext('2d');
      this.visible = true; this.stale = false;
      this.canvas.__pv = this; io?.observe(this.canvas);
      this.scene = new THREE.Scene();
      this.scene.add(new THREE.HemisphereLight(0xdfe8ff, 0x55673f, 0.55));
      const sun = new THREE.DirectionalLight(0xfff1d8, 1.0);
      sun.position.set(-0.6, 1, 0.8);
      this.scene.add(sun);
      this.cam = new THREE.OrthographicCamera(-1, 1, 1, -1, -1e4, 1e4);
      this.yaw = 0; this.pitch = GAME_PITCH; this.model = null;
      this.parts = []; this.spinners = []; this.stages = []; this.stage = 'done'; this.animOn = true;
      this._bindDrag();
      const onload = (g) => this._setup(g);
      const onerr = (e) => host.insertAdjacentHTML('beforeend', `<p style="color:#b03a2e;font-size:13px">3D 载入失败：${e?.message ?? e}</p>`);
      const L = new THREE.GLTFLoader();
      if (this.o.glb.startsWith('data:')) L.parse(toBuf(this.o.glb), '', onload, onerr); else L.load(this.o.glb, onload, undefined, onerr);
      all.push(this);
    }

    set(p) { Object.assign(this.o, p); if ('light' in p && this.model) this._materials(); if ('wire' in p && this.model) this._wire(); this._draw(); }

    /** 三角形网格线（2026-10-24 用户："我能不能看到三角形网格"）：每个网格叠一层 WireframeGeometry 线框，随部件 / 施工阶段一起显隐 */
    _wire() {
      this.model.traverse((n) => {
        if (!n.isMesh) return;
        if (this.o.wire && !n.userData.wire) {
          const w = new THREE.LineSegments(new THREE.WireframeGeometry(n.geometry),
            new THREE.LineBasicMaterial({ color: 0x1b1f24, transparent: true, opacity: 0.55, depthTest: true }));
          w.renderOrder = 1;
          n.add(w);
          n.userData.wire = w;
        }
        if (n.userData.wire) n.userData.wire.visible = !!this.o.wire;
      });
    }

    _setup(g) {
      const holder = new THREE.Group(), flip = new THREE.Group();
      flip.add(g.scene);
      flip.rotation.y = (this.o.rotY || 0) * Math.PI / 180;
      holder.add(flip);
      let b = new THREE.Box3().setFromObject(holder);
      if (this.o.fitM) holder.scale.setScalar(this.o.fitM / Math.max(b.max.x - b.min.x, 1e-6));
      b = new THREE.Box3().setFromObject(holder);
      holder.position.set(-(b.min.x + b.max.x) / 2, -b.min.y, -(b.min.z + b.max.z) / 2);
      this.model = new THREE.Group(); this.model.add(holder); this.scene.add(this.model);
      this.size = new THREE.Box3().setFromObject(this.model).getSize(new THREE.Vector3());
      const seen = new Set();
      this.stageOrder = STAGE_ORDER; this.stageNames = {};
      g.scene.traverse((n) => {
        const ud = n.userData || {};
        const name = ud.name || n.name || '';
        if (Array.isArray(ud.stages)) { this.stageOrder = ud.stages; this.stageNames = ud.stage_names || {}; }
        if (ud.stage) seen.add(ud.stage);
        if (ud.only_stage) seen.add(ud.only_stage);
        if (!name.startsWith('part.') || !ud.axis) return;
        const rec = { node: n, name, axis: AXIS[ud.axis] || AXIS.z, base: n.quaternion.clone() };
        if (Array.isArray(ud.range)) Object.assign(rec, { range: ud.range, t: 0, target: 0 }), this.parts.push(rec);
        else this.spinners.push(Object.assign(rec, { angle: 0 }));
      });
      this.stages = this.stageOrder.filter((s) => seen.has(s));
      this.stage = this.stages.length ? this.stages[this.stages.length - 1] : 'done';
      if (this.stages.length) this.setStage(this.stage);   // 只在某阶段出现的件（脚手架）在建成状态下先藏起来
      this._materials();
      if (this.o.wire) this._wire();
      this._draw();
      this.o.onReady?.(this);
    }

    _materials() {
      this.model.traverse((n) => {
        if (!n.isMesh) return;
        if (!n.geometry.getAttribute('normal')) n.geometry.computeVertexNormals();   // 生成器输出常不带法线，不补就是全黑剪影
        const src = n.userData.src ?? (n.userData.src = n.material);
        const map = src.map ?? null;
        const normalMap = src.normalMap ?? null;     // GLB 带法线贴图就带上（茅草带等）
        if (map) { map.encoding = THREE.sRGBEncoding; map.magFilter = this.o.smooth ? THREE.LinearFilter : THREE.NearestFilter; }
        const color = map ? 0xffffff : (this.o.color ?? src.color);   // o.color：无贴图模型的统一底色（纯白素模会过曝）
        const emissive = src.emissive && src.emissive.getHex() ? src.emissive : undefined;
        n.material = this.o.light === 'step'
          ? new THREE.MeshToonMaterial({ map, color, gradientMap: stepTex(), emissive, normalMap, vertexColors: !!n.geometry.getAttribute('color') })
          : normalMap   // r128 的 Lambert 不吃法线贴图，有法线贴图时换不反光的 Phong
            ? new THREE.MeshPhongMaterial({ map, color, emissive, normalMap, shininess: 0, specular: 0x000000, vertexColors: !!n.geometry.getAttribute('color') })
            : new THREE.MeshLambertMaterial({ map, color, emissive, vertexColors: !!n.geometry.getAttribute('color') });   // 顶点色明暗（植被叶簇 shade_verts）要带上
      });
    }

    /** 施工阶段：只显示 stage ≤ 当前阶段、only_stage = 当前阶段的部件 */
    setStage(s) {
      this.stage = s;
      const order = this.stageOrder || STAGE_ORDER, k = order.indexOf(s);
      this.model?.traverse((n) => {
        const ud = n.userData || {};
        if (ud.only_stage) n.visible = ud.only_stage === s;
        else if (ud.stage) n.visible = order.indexOf(ud.stage) <= k;
      });
      this._draw();
    }

    /** 开 / 关某个（或全部）可开合部件 */
    toggle(rec) { for (const p of rec ? [rec] : this.parts) p.target = p.target ? 0 : 1; }

    _bindDrag() {
      const c = this.canvas;
      let d = null;
      c.addEventListener('pointerdown', (e) => {
        d = { x: e.clientX, y: e.clientY, yaw: this.yaw, pitch: this.pitch, moved: false };
        c.setPointerCapture(e.pointerId); c.style.cursor = 'grabbing';
      });
      c.addEventListener('pointermove', (e) => {
        if (!d) return;
        const dx = e.clientX - d.x, dy = e.clientY - d.y;
        if (Math.abs(dx) + Math.abs(dy) > 4) { d.moved = true; this.o.spin = false; this.onSpinChange?.(false); }
        if (!d.moved) return;
        this.yaw = d.yaw + dx * 0.012;
        this.pitch = Math.min(1.553, Math.max(0.087, d.pitch + dy * 0.008));
        this._draw();
      });
      const up = (e) => {
        if (d && !d.moved) this._click(e);
        d = null; c.style.cursor = 'grab';
      };
      c.addEventListener('pointerup', up);
      c.addEventListener('pointercancel', () => { d = null; c.style.cursor = 'grab'; });
      c.addEventListener('dblclick', () => { this.yaw = 0; this.pitch = GAME_PITCH; this._draw(); });
    }

    /** 点到哪个可开合部件（或它的子节点）就开 / 关它 */
    _click(e) {
      if (!this.parts.length) return;
      const r = this.canvas.getBoundingClientRect();
      const p = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      const ray = new THREE.Raycaster();
      ray.setFromCamera(p, this.cam);
      const hit = ray.intersectObject(this.model, true)[0];
      if (!hit) return;
      for (let n = hit.object; n; n = n.parent) {
        const rec = this.parts.find((q) => q.node === n);
        if (rec) { this.toggle(rec); return; }
      }
    }

    _tick(dt) {
      if (!this.model) return;
      let dirty = false;
      if (this.o.spin) { this.yaw += dt * 0.5; dirty = true; }
      for (const p of this.parts) {
        if (p.t === p.target) continue;
        p.t = p.target > p.t ? Math.min(p.target, p.t + dt / 0.6) : Math.max(p.target, p.t - dt / 0.6);
        const ease = p.t * p.t * (3 - 2 * p.t);
        const deg = p.range[0] + (p.range[1] - p.range[0]) * ease;
        p.node.quaternion.copy(p.base).multiply(new THREE.Quaternion().setFromAxisAngle(p.axis, deg * Math.PI / 180));
        dirty = true;
      }
      if (this.animOn) for (const s of this.spinners) {
        s.angle += dt * 2.0;
        s.node.quaternion.copy(s.base).multiply(new THREE.Quaternion().setFromAxisAngle(s.axis, s.angle));
        dirty = true;
      }
      if (dirty) this._draw();
    }

    _draw() {
      if (!this.model) return;
      if (!this.visible) { this.stale = true; return; }
      this.stale = false;
      this.model.rotation.y = this.yaw;
      const r = (Math.max(this.size.x, this.size.z) * 0.8 + this.size.y * 0.5) / (this.o.zoom || 1);
      // 不像素化时按画布显示宽度 × 屏幕像素比渲染（看百万面细节，固定 512 会糊）
      const px = this.o.ppm ? Math.max(16, Math.round(r * 2 * this.o.ppm))
        : Math.min(2048, Math.round((this.canvas.clientWidth || 512) * (window.devicePixelRatio || 1)));
      this.canvas.style.imageRendering = this.o.ppm ? 'pixelated' : 'auto';
      const R = gl();
      R.setSize(px, px, false);
      Object.assign(this.cam, { left: -r, right: r, top: r, bottom: -r });
      this.cam.position.set(0, Math.sin(this.pitch) * 50, Math.cos(this.pitch) * 50);
      this.cam.lookAt(0, this.size.y * 0.4, 0);
      this.cam.updateProjectionMatrix();
      R.render(this.scene, this.cam);
      if (this.canvas.width !== px) this.canvas.width = this.canvas.height = px;
      this.ctx.clearRect(0, 0, px, px);
      this.ctx.drawImage(R.domElement, 0, 0);   // 同一任务里紧跟 render 拷，不需要 preserveDrawingBuffer
    }
  }
  window.PixelViewer = PixelViewer;
})();
