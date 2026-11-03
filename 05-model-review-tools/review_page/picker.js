/* 挑选器（页面模板共用）：页面上 button.like[data-k] 点一下 = 喜欢 / 取消；#pick-note 留言；
 * 自动存到页面 db 的一个文档（Artifact 发布时要带 capabilities: {db: {}}），我这边用 read_db 读回。
 *   Picker.init({ doc: 'picks/style_r2' })
 * 存的是 { liked: [key…], note, at }。没有 db（离线 / 没登录）时照常能点，只是提示存不下来。 */
(function () {
  const $ = (s) => document.querySelector(s);
  function paint(liked) {
    for (const b of document.querySelectorAll('button.like[data-k]')) {
      const on = liked.has(b.dataset.k);
      b.setAttribute('aria-pressed', String(on));
      b.textContent = on ? '已喜欢' : '喜欢';
      b.closest('section')?.classList.toggle('on', on);
    }
  }
  window.Picker = {
    async init({ doc }) {
      const liked = new Set();
      const state = $('#pick-state'), note = $('#pick-note');
      let ref = null, timer = null, chain = Promise.resolve();
      const save = () => {
        if (!ref) return;
        clearTimeout(timer);
        timer = setTimeout(() => {
          state && (state.textContent = '保存中…');
          chain = chain.then(() => ref.set({ liked: [...liked], note: note?.value ?? '', at: new Date().toISOString() }))
            .then(() => { state && (state.textContent = '已保存'); })
            .catch(() => { state && (state.textContent = '没存上；直接告诉我也行'); });
        }, 700);
      };
      for (const b of document.querySelectorAll('button.like[data-k]')) {
        b.addEventListener('click', () => { liked.has(b.dataset.k) ? liked.delete(b.dataset.k) : liked.add(b.dataset.k); paint(liked); save(); });
      }
      note?.addEventListener('input', save);
      paint(liked);
      const db = await window.claude?.use?.('db');
      if (!db) { state && (state.textContent = '这里存不了选择；直接告诉我喜欢哪个就行'); return; }
      ref = db.doc(doc);
      const snap = await ref.get().catch(() => null);
      if (snap?.exists) {
        const d = snap.data();
        for (const k of d.liked ?? []) liked.add(k);
        if (note && !note.value) note.value = d.note ?? '';
        paint(liked);
        state && (state.textContent = '已读回上次的选择');
      } else state && (state.textContent = '选择会自动保存');
    },
  };
})();
