/* NTM 個案資料庫 — 前端。純 vanilla JS，無任何外部連線。 */
'use strict';

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const state = {
  user: null,
  schema: null,
  fieldMap: {},
  cases: [],
  editingId: null,
};

/* ------------------------------------------------------------------ */
/* API                                                                 */
/* ------------------------------------------------------------------ */
async function api(path, options = {}) {
  const opts = Object.assign({ credentials: 'same-origin' }, options);
  opts.headers = Object.assign({ 'X-NTM-Client': '1' }, options.headers || {});
  if (opts.body && typeof opts.body !== 'string') {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(opts.body);
  }
  const res = await fetch(path, opts);
  const text = await res.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch (_) { data = { error: text }; }
  if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
  return data;
}

function toast(msg) {
  const el = $('#toast');
  el.textContent = msg;
  el.classList.remove('hidden');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add('hidden'), 2600);
}

function esc(v) {
  return String(v == null ? '' : v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ------------------------------------------------------------------ */
/* 登入                                                                */
/* ------------------------------------------------------------------ */
$('#login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('#login-error').textContent = '';
  try {
    const data = await api('/api/login', {
      method: 'POST',
      body: { username: $('#login-user').value, password: $('#login-pass').value },
    });
    state.user = data.user;
    $('#login-pass').value = '';
    await startApp();
  } catch (err) {
    $('#login-error').textContent = err.message;
  }
});

$('#logout').addEventListener('click', async (e) => {
  e.preventDefault();
  await api('/api/logout', { method: 'POST' });
  location.reload();
});

/* ------------------------------------------------------------------ */
/* 啟動                                                                */
/* ------------------------------------------------------------------ */
async function boot() {
  try {
    const me = await api('/api/me');
    if (me.user) { state.user = me.user; return startApp(); }
  } catch (_) { /* 未登入 */ }
  $('#login-view').classList.remove('hidden');
}

async function startApp() {
  $('#login-view').classList.add('hidden');
  $('#app-view').classList.remove('hidden');
  $('#who').textContent = `${state.user.full_name || state.user.username}\n${roleLabel(state.user.role)}`;
  if (state.user.role !== 'admin') $$('.admin-only').forEach((el) => el.classList.add('hidden'));
  if (state.user.role === 'viewer') {
    // 唯讀帳號：不能新增個案，也不能把整份資料匯出去
    $('#btn-new').classList.add('hidden');
    $('#btn-export').classList.add('hidden');
  }

  state.schema = await api('/api/schema');
  state.schema.fields.forEach((f) => { state.fieldMap[f.name] = f; });

  // 覆蓋檔案後沒重開伺服器的話，後端還是舊程式，schema 會少東西。
  // 與其讓畫面莫名空白，不如直接說清楚。
  if (!state.schema.key || !state.schema.visit_fields) {
    showStaleServerWarning();
    return;
  }

  // 各區塊獨立建置：其中一塊出問題不該讓整個畫面空白
  const steps = [
    ['篩選條件', buildFilters],
    ['個案表單', buildForm],
    ['衛教專區', buildEducation],
    ['連結', applyPortalLinks],
  ];
  for (const [name, fn] of steps) {
    try {
      fn();
    } catch (err) {
      console.error('[' + name + '] 建置失敗', err);
      toast(name + '載入失敗，其餘功能仍可使用');
    }
  }

  try {
    await loadCases();
  } catch (err) {
    console.error('個案清單載入失敗', err);
  }
  try {
    await renderDashboard();          // 開啟就是圖表，不必再點一次
  } catch (err) {
    console.error('儀表板載入失敗', err);
  }
}

/** 前後端版本不一致時，給一個看得懂的指示，而不是一片空白。 */
function showStaleServerWarning() {
  const host = $('#dash-kpi');
  if (!host) return;
  host.textContent = '';
  const box = document.createElement('div');
  box.className = 'alert alert-red stale-warning';
  const strong = document.createElement('strong');
  strong.textContent = '伺服器還在執行舊版程式。';
  const text = document.createTextNode(
    '你剛才覆蓋了檔案，但伺服器沒有重新啟動 —— Python 是啟動時把程式讀進記憶體的。'
    + '請到啟動系統的黑色視窗按 Ctrl + C 結束，再雙擊 start.bat 重新啟動，'
    + '然後回到這裡按 Ctrl + F5 重新整理。');
  box.append(strong, document.createElement('br'), text);
  host.appendChild(box);
}

/** 入口頁與 TB 系統的位址由 config.json 設定，改位址不必動程式。 */
function applyPortalLinks() {
  const portal = state.schema.portal_url;
  const tb = state.schema.tb_url;
  if (portal) {
    $('#portal-link').href = portal;
    $('#intro-portal').href = portal;
  }
  if (tb) $('#intro-tb').href = tb;
}

/** 衛教專區：卡片式主題牆，點卡片開全文。內容來自 static/education.js。 */
function buildEducation() {
  const host = $('#edu-grid');
  host.textContent = '';
  if (typeof EDU_ARTICLES === 'undefined' || !EDU_ARTICLES.length) {
    const p = document.createElement('p');
    p.className = 'muted';
    p.textContent = '尚未載入衛教內容。';
    host.appendChild(p);
    return;
  }

  EDU_ARTICLES.forEach((article, idx) => {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = 'edu-card accent-' + (idx % 3);

    const icon = document.createElement('div');
    icon.className = 'edu-icon';
    icon.textContent = article.icon || '\u{1F4D8}';

    const title = document.createElement('div');
    title.className = 'edu-title';
    title.textContent = article.title;

    const desc = document.createElement('div');
    desc.className = 'edu-desc';
    desc.textContent = article.summary || '';

    const go = document.createElement('span');
    go.className = 'edu-go';
    go.textContent = '\u2192';

    card.append(icon, title, desc, go);
    card.addEventListener('click', () => openArticle(article));
    host.appendChild(card);
  });
}

/** 開啟一篇衛教全文。 */
function openArticle(article) {
  const reader = $('#edu-reader');
  const body = $('#edu-reader-body');
  body.textContent = '';

  const head = document.createElement('div');
  head.className = 'article-head';
  const icon = document.createElement('div');
  icon.className = 'article-icon';
  icon.textContent = article.icon || '\u{1F4D8}';
  const h = document.createElement('h2');
  h.textContent = article.title;
  head.append(icon, h);
  body.appendChild(head);

  if (article.authors && article.authors.length) {
    const by = document.createElement('p');
    by.className = 'article-authors';
    by.textContent = '撰文／' + article.authors.join('　');
    body.appendChild(by);
  }

  article.blocks.forEach((block) => {
    if (block.h) {
      const el = document.createElement('h3');
      el.textContent = block.h;
      body.appendChild(el);
    } else {
      const el = document.createElement('p');
      el.textContent = block.p;
      body.appendChild(el);
    }
  });

  reader.classList.remove('hidden');
  document.body.classList.add('print-overlay');
  document.body.style.overflow = 'hidden';
  body.scrollTop = 0;
  $('#edu-reader-close').focus();
}

function closeArticle() {
  $('#edu-reader').classList.add('hidden');
  document.body.classList.remove('print-overlay');
  document.body.style.overflow = '';
}

$('#edu-reader-close').addEventListener('click', closeArticle);
$('#edu-reader-print').addEventListener('click', () => window.print());
$('#edu-reader').addEventListener('click', (e) => {
  if (e.target.id === 'edu-reader') closeArticle();   // 點卡片外面關閉
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !$('#edu-reader').classList.contains('hidden')) {
    closeArticle();
  }
});

function roleLabel(role) {
  return { admin: '管理員', editor: '編輯', viewer: '唯讀' }[role] || role;
}

/* ------------------------------------------------------------------ */
/* 導覽                                                                */
/* ------------------------------------------------------------------ */
const VIEW_TITLES = {
  stats: '統計儀表板', list: '個案追蹤', education: '衛教專區', audit: '稽核紀錄',
};

$$('.nav-item').forEach((btn) => btn.addEventListener('click', async (e) => {
  e.preventDefault();
  const view = btn.dataset.view;
  $$('.nav-item').forEach((b) => b.classList.remove('active'));
  btn.classList.add('active');
  Object.keys(VIEW_TITLES).forEach((v) => {
    $('#view-' + v).classList.toggle('active', v === view);
  });
  $('#topbar-title').textContent = VIEW_TITLES[view];
  if (window.innerWidth <= 900) $('#sidebar').classList.remove('open');
  if (view === 'stats') await renderDashboard();
  if (view === 'audit') await renderAudit();
}));

$('#hamburger').addEventListener('click', () => $('#sidebar').classList.toggle('open'));

function tickDate() {
  const d = new Date();
  const w = ['日', '一', '二', '三', '四', '五', '六'][d.getDay()];
  const pad = (n) => String(n).padStart(2, '0');
  $('#topbar-date').textContent =
    `${d.getFullYear()}/${pad(d.getMonth() + 1)}/${pad(d.getDate())}（週${w}） `
    + `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
tickDate();
setInterval(tickDate, 30000);

/* ------------------------------------------------------------------ */
/* 清單                                                                */
/* ------------------------------------------------------------------ */
function buildFilters() {
  // 欄位名由後端 schema 決定，欄位不存在就靜靜略過，不要讓整個畫面掛掉
  const fill = (sel, field) => {
    const def = state.fieldMap[field];
    if (!def || !Array.isArray(def.options)) return;
    def.options.filter(Boolean).forEach((o) => {
      const opt = document.createElement('option');
      opt.textContent = o;
      $(sel).appendChild(opt);
    });
  };
  fill('#filter-species', state.schema.key.species);
  fill('#filter-group', state.schema.key.group);
}

const TODAY = new Date().toISOString().slice(0, 10);

let searchTimer;
$('#search').addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadCases, 250);
});
['#filter-species', '#filter-group']
  .forEach((sel) => $(sel).addEventListener('change', loadCases));
$('#btn-export').addEventListener('click', () => { window.location = '/api/export.csv'; });
$('#btn-new').addEventListener('click', () => openEditor(null));

async function loadCases() {
  const params = new URLSearchParams();
  if ($('#search').value.trim()) params.set('q', $('#search').value.trim());
  if ($('#filter-species').value) {
    params.set(state.schema.key.species, $('#filter-species').value);
  }
  if ($('#filter-group').value) {
    params.set(state.schema.key.group, $('#filter-group').value);
  }
  const data = await api('/api/cases?' + params.toString());
  state.cases = data.cases;
  renderTable(data.cases, data.total);
}

function renderTable(cases, total) {
  const cols = state.schema.list_columns;
  const head = $('#case-table').querySelector('thead tr');
  head.textContent = '';
  cols.concat(['__visits']).forEach((c) => {
    const th = document.createElement('th');
    th.textContent = c === '__visits' ? '追蹤次數'
      : (state.fieldMap[c] || {}).label || c;
    head.appendChild(th);
  });

  const body = $('#case-table').querySelector('tbody');
  body.textContent = '';
  if (!cases.length) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = cols.length + 1;
    td.className = 'muted';
    td.textContent = '目前沒有符合的個案';
    tr.appendChild(td);
    body.appendChild(tr);
  } else {
    cases.forEach((c) => {
      const tr = document.createElement('tr');
      cols.forEach((col) => {
        const td = document.createElement('td');
        let v = c[col];
        if (Array.isArray(v)) v = v.join('、');
        if (typeof v === 'boolean') v = v ? '是' : '否';
        td.textContent = v == null ? '' : v;
        tr.appendChild(td);
      });
      const td = document.createElement('td');
      td.textContent = c.visit_count ? `${c.visit_count} 次` : '—';
      tr.appendChild(td);
      tr.addEventListener('click', () => openEditor(c.id));
      body.appendChild(tr);
    });
  }
  $('#list-count').textContent = `共 ${total} 筆個案`;
  $('#topbar-badge').textContent = `個案 ${total}`;
}

function daysBetween(a, b) {
  return Math.round((new Date(b) - new Date(a)) / 86400000);
}

/* ------------------------------------------------------------------ */
/* 表單                                                                */
/* ------------------------------------------------------------------ */
function buildForm() {
  const form = $('#case-form');
  form.innerHTML = state.schema.groups.map((g) => {
    const fs = state.schema.fields.filter((f) => f.group === g.key);
    if (!fs.length) return '';
    return `<fieldset><legend>${esc(g.label)}</legend>
      <div class="field-grid">${fs.map(fieldHtml).join('')}</div></fieldset>`;
  }).join('');

  form.addEventListener('change', (e) => {
    if (['ats_clinical', 'ats_radiographic', 'ats_micro'].includes(e.target.name)) {
    }
  });
}

function fieldHtml(f, prefix) {
  const id = (prefix || 'f_') + f.name;
  const hint = f.hint
    ? `<span class="hint${f.warn ? ' warn' : ''}">${esc(f.hint)}</span>` : '';
  const wide = ['textarea', 'multi'].includes(f.type) ? ' wide' : '';
  let input;
  switch (f.type) {
    case 'bool':
      return `<div class="field${wide}"><div class="checkline">
        <input type="checkbox" id="${id}" name="${f.name}">
        <span>${esc(f.label)}</span></div>${hint}</div>`;
    case 'textarea':
      input = `<textarea id="${id}" name="${f.name}"></textarea>`;
      break;
    case 'select':
      input = `<select id="${id}" name="${f.name}">`
        + f.options.map((o) => `<option value="${esc(o)}">${esc(o || '— 未填 —')}</option>`).join('')
        + '</select>';
      break;
    case 'multi':
      input = `<div class="multi-box" id="${id}">` + f.options.map((o, i) =>
        `<label><input type="checkbox" name="${f.name}" value="${esc(o)}"
          id="${id}_${i}">${esc(o)}</label>`).join('') + '</div>';
      break;
    case 'date':
      input = `<input type="date" id="${id}" name="${f.name}">`;
      break;
    case 'int':
      input = `<input type="number" step="1" id="${id}" name="${f.name}">`;
      break;
    case 'real':
      input = `<input type="number" step="0.1" id="${id}" name="${f.name}">`;
      break;
    default:
      input = `<input type="text" id="${id}" name="${f.name}"${f.required ? ' required' : ''}>`;
  }
  return `<div class="field${wide}"><label for="${id}">${esc(f.label)}${f.required ? ' *' : ''}</label>
    ${input}${hint}</div>`;
}

function fillForm(caseData) {
  const form = $('#case-form');
  state.schema.fields.forEach((f) => {
    const val = caseData ? caseData[f.name] : null;
    if (f.type === 'multi') {
      const chosen = new Set(Array.isArray(val) ? val : []);
      form.querySelectorAll(`input[name="${f.name}"]`).forEach((cb) => {
        cb.checked = chosen.has(cb.value);
      });
    } else if (f.type === 'bool') {
      form.querySelector(`[name="${f.name}"]`).checked = !!val;
    } else {
      form.querySelector(`[name="${f.name}"]`).value = val == null ? '' : val;
    }
  });
}

function collectForm() {
  const form = $('#case-form');
  const payload = {};
  state.schema.fields.forEach((f) => {
    if (f.type === 'multi') {
      payload[f.name] = Array.from(
        form.querySelectorAll(`input[name="${f.name}"]:checked`)
      ).map((cb) => cb.value);
    } else if (f.type === 'bool') {
      payload[f.name] = form.querySelector(`[name="${f.name}"]`).checked;
    } else {
      payload[f.name] = form.querySelector(`[name="${f.name}"]`).value;
    }
  });
  return payload;
}

/* ------------------------------------------------------------------ */
/* 編輯抽屜                                                            */
/* ------------------------------------------------------------------ */
async function openEditor(id) {
  state.editingId = id;
  $('#editor-error').textContent = '';
  $('#editor-title').textContent = id ? '編輯個案' : '新增個案';
  $('#editor-delete').classList.toggle('hidden', !id || state.user.role !== 'admin');
  const readonly = state.user.role === 'viewer';
  $('#editor-save').classList.toggle('hidden', readonly);

  let data = null;
  if (id) data = (await api('/api/cases/' + id)).case;
  fillForm(data);
  $('#case-form').querySelectorAll('input, select, textarea')
    .forEach((el) => { el.disabled = readonly; });
  await loadVisits(id);
  $('#editor').classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  if (!id) $('#f_case_no').focus();
}

function closeEditor() {
  $('#editor').classList.add('hidden');
  document.body.style.overflow = '';
  state.editingId = null;
}

/* ------------------------------------------------------------------ */
/* 追蹤紀錄                                                            */
/* ------------------------------------------------------------------ */
async function loadVisits(caseId) {
  const block = $('#visit-block');
  const list = $('#visit-list');
  block.classList.remove('hidden');
  if (!caseId) {
    $('#visit-hint').classList.remove('hidden');
    $('#btn-add-visit').classList.add('hidden');
    list.textContent = '';
    return;
  }
  $('#visit-hint').classList.add('hidden');
  $('#btn-add-visit').classList.toggle('hidden', state.user.role === 'viewer');

  const data = await api('/api/cases/' + caseId + '/visits');
  list.textContent = '';
  if (!data.visits.length) {
    const p = document.createElement('p');
    p.className = 'muted';
    p.textContent = '尚無追蹤紀錄。';
    list.appendChild(p);
  }
  data.visits.forEach((v) => list.appendChild(visitRow(v)));
}

function visitRow(visit) {
  const row = document.createElement('div');
  row.className = 'visit-row';

  const head = document.createElement('div');
  head.className = 'visit-head';
  const ev = document.createElement('span');
  ev.className = 'visit-event';
  ev.textContent = visit.event || '（未指定時間點）';
  const dt = document.createElement('span');
  dt.className = 'visit-date';
  dt.textContent = visit.visit_date || '未填日期';
  const spacer = document.createElement('span');
  spacer.className = 'spacer';
  head.append(ev, dt, spacer);

  if (state.user.role !== 'viewer') {
    const edit = document.createElement('button');
    edit.type = 'button';
    edit.className = 'btn btn-outline btn-sm';
    edit.textContent = '編輯';
    edit.addEventListener('click', () => openVisitForm(row, visit));
    const del = document.createElement('button');
    del.type = 'button';
    del.className = 'btn btn-danger btn-sm';
    del.textContent = '刪除';
    del.addEventListener('click', async () => {
      if (!confirm('確定要刪除這一次追蹤紀錄嗎？')) return;
      await api(`/api/cases/${state.editingId}/visits/${visit.id}`, { method: 'DELETE' });
      await loadVisits(state.editingId);
      toast('已刪除追蹤紀錄');
    });
    head.append(edit, del);
  }

  row.appendChild(head);
  row.appendChild(visitSummary(visit));
  return row;
}

/** 摘要只放最關鍵的幾項，細節點「編輯」才展開。 */
function visitSummary(visit) {
  const box = document.createElement('div');
  box.className = 'visit-summary';
  const bits = [];
  const culture = visit.culture_result || visit.ntm_sputumculture_initial;
  if (culture) bits.push(['痰培養', culture]);
  if (visit.imaging_change || visit.cxr) bits.push(['影像', visit.imaging_change || visit.cxr]);
  if (visit.visit_status) bits.push(['狀態', visit.visit_status]);
  const ae = visit.adverse_events || visit.adverse_effect;
  if (Array.isArray(ae) && ae.length) bits.push(['不良反應', ae.join('、')]);

  if (!bits.length) {
    box.className = 'visit-summary muted';
    box.textContent = '（尚未填寫內容）';
    return box;
  }
  bits.forEach(([label, value]) => {
    const span = document.createElement('span');
    const b = document.createElement('b');
    b.textContent = label + '：';
    span.appendChild(b);
    const val = document.createElement('span');
    val.textContent = value;
    if (label === '痰培養') {
      val.className = String(value).includes('陰') ? 'cul-neg'
        : String(value).includes('陽') ? 'cul-pos' : '';
    }
    span.appendChild(val);
    box.appendChild(span);
  });
  return box;
}

/** 展開一列的編輯表單；visit 為 null 代表新增。 */
function openVisitForm(anchor, visit) {
  const existing = anchor.querySelector('.visit-form');
  if (existing) { existing.remove(); return; }

  const form = document.createElement('div');
  form.className = 'visit-form';
  state.schema.visit_fields.forEach((f) => {
    form.insertAdjacentHTML('beforeend', fieldHtml(f, 'vf_'));
  });

  const actions = document.createElement('div');
  actions.className = 'visit-actions';
  const save = document.createElement('button');
  save.type = 'button';
  save.className = 'btn btn-orange btn-sm';
  save.textContent = '儲存這次追蹤';
  const cancel = document.createElement('button');
  cancel.type = 'button';
  cancel.className = 'btn btn-outline btn-sm';
  cancel.textContent = '取消';
  cancel.addEventListener('click', () => form.remove());
  const err = document.createElement('span');
  err.className = 'error';
  actions.append(save, cancel, err);
  form.appendChild(actions);
  anchor.appendChild(form);

  // 帶入現有值
  state.schema.visit_fields.forEach((f) => {
    const el = form.querySelector(`[name="${f.name}"]`);
    const val = visit ? visit[f.name] : null;
    if (f.type === 'multi') {
      const chosen = new Set(Array.isArray(val) ? val : []);
      form.querySelectorAll(`input[name="${f.name}"]`)
        .forEach((cb) => { cb.checked = chosen.has(cb.value); });
    } else if (f.type === 'bool') {
      el.checked = !!val;
    } else if (el) {
      el.value = val == null ? '' : val;
    }
  });

  save.addEventListener('click', async () => {
    err.textContent = '';
    const payload = {};
    state.schema.visit_fields.forEach((f) => {
      if (f.type === 'multi') {
        payload[f.name] = Array.from(
          form.querySelectorAll(`input[name="${f.name}"]:checked`)).map((cb) => cb.value);
      } else if (f.type === 'bool') {
        payload[f.name] = form.querySelector(`[name="${f.name}"]`).checked;
      } else {
        const el = form.querySelector(`[name="${f.name}"]`);
        payload[f.name] = el ? el.value : '';
      }
    });
    try {
      if (visit) {
        await api(`/api/cases/${state.editingId}/visits/${visit.id}`,
                  { method: 'PUT', body: payload });
      } else {
        await api(`/api/cases/${state.editingId}/visits`, { method: 'POST', body: payload });
      }
      await loadVisits(state.editingId);
      toast('已儲存追蹤紀錄');
    } catch (e) {
      err.textContent = e.message;
    }
  });
}

$('#btn-add-visit').addEventListener('click', () => {
  const holder = document.createElement('div');
  holder.className = 'visit-row';
  const head = document.createElement('div');
  head.className = 'visit-head';
  const ev = document.createElement('span');
  ev.className = 'visit-event';
  ev.textContent = '新增一次追蹤';
  head.appendChild(ev);
  holder.appendChild(head);
  $('#visit-list').appendChild(holder);
  openVisitForm(holder, null);
  holder.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
});

$('#editor-cancel').addEventListener('click', closeEditor);
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !$('#editor').classList.contains('hidden')) closeEditor();
});

$('#editor-save').addEventListener('click', async () => {
  $('#editor-error').textContent = '';
  const payload = collectForm();
  if (!payload.case_no || !payload.case_no.trim()) {
    $('#editor-error').textContent = '研究編號為必填';
    return;
  }
  try {
    if (state.editingId) {
      await api('/api/cases/' + state.editingId, { method: 'PUT', body: payload });
    } else {
      await api('/api/cases', { method: 'POST', body: payload });
    }
    closeEditor();
    await loadCases();
    toast('已儲存');
  } catch (err) {
    $('#editor-error').textContent = err.message;
  }
});

$('#editor-delete').addEventListener('click', async () => {
  if (!state.editingId) return;
  if (!confirm('確定要刪除這筆個案嗎？（軟刪除，仍可由資料庫還原）')) return;
  await api('/api/cases/' + state.editingId, { method: 'DELETE' });
  closeEditor();
  await loadCases();
  toast('已刪除');
});

/* ------------------------------------------------------------------ */
/* 統計儀表板                                                          */
/* ------------------------------------------------------------------ */
const dash = { unit: 'year', group: '', mode: 'n', built: false, data: null,
  trendCard: null };

function buildDashControls() {
  if (dash.built) return;
  dash.built = true;

  const sp = $('#f-dash-species');
  sp.insertAdjacentHTML('beforeend', '<option value="">全部菌種</option>');
  const speciesDef = state.fieldMap[state.schema.key.species] || {};
  (speciesDef.options || []).filter(Boolean).forEach((o) => {
    const opt = document.createElement('option');
    opt.textContent = o;            // 選項文字是資料，用 textContent
    sp.appendChild(opt);
  });

  ['#f-year-from', '#f-year-to', '#f-dash-species'].forEach((sel) => {
    $(sel).addEventListener('change', renderDashboard);
  });
  $$('#f-group button').forEach((b) => b.addEventListener('click', () => {
    $$('#f-group button').forEach((x) => x.classList.remove('on'));
    b.classList.add('on');
    dash.group = b.dataset.g;        // '' = 兩組並排對照
    renderDashboard();
  }));
  $$('#f-mode button').forEach((b) => b.addEventListener('click', () => {
    $$('#f-mode button').forEach((x) => x.classList.remove('on'));
    b.classList.add('on');
    dash.mode = b.dataset.m;
    if (dash.data) paintDashboard(dash.data);   // 換算而已，不必重新取資料
  }));
  $$('#f-unit button').forEach((b) => b.addEventListener('click', () => {
    $$('#f-unit button').forEach((x) => x.classList.remove('on'));
    b.classList.add('on');
    dash.unit = b.dataset.unit;
    if (dash.data) drawTrend(dash.data);
  }));
  $('#f-reset').addEventListener('click', () => {
    $('#f-year-from').value = '';
    $('#f-year-to').value = '';
    $('#f-dash-species').value = '';
    dash.group = '';
    dash.mode = 'n';
    $$('#f-group button').forEach((x) => x.classList.toggle('on', x.dataset.g === ''));
    $$('#f-mode button').forEach((x) => x.classList.toggle('on', x.dataset.m === 'n'));
    renderDashboard();
  });
}

function fillYearOptions(years) {
  ['#f-year-from', '#f-year-to'].forEach((sel) => {
    const node = $(sel);
    const keep = node.value;
    node.textContent = '';
    const any = document.createElement('option');
    any.value = '';
    any.textContent = '不限';
    node.appendChild(any);
    years.forEach((y) => {
      const o = document.createElement('option');
      o.value = y;
      o.textContent = y;
      node.appendChild(o);
    });
    node.value = keep;
  });
}

async function renderDashboard() {
  buildDashControls();
  const wrap = $('#dash-charts');
  wrap.style.opacity = '.5';            // 重新載入時維持畫面，不閃骨架

  const params = new URLSearchParams();
  if ($('#f-year-from').value) params.set('year_from', $('#f-year-from').value);
  if ($('#f-year-to').value) params.set('year_to', $('#f-year-to').value);
  if ($('#f-dash-species').value) params.set('species', $('#f-dash-species').value);
  if (dash.group) params.set('group', dash.group);

  const d = await api('/api/dashboard?' + params.toString());
  dash.data = d;
  fillYearOptions(d.years_available);
  paintDashboard(d);
}

/** 只負責畫，不重新取資料 —— 視窗寬度改變時直接重畫即可。 */
function paintDashboard(d) {
  const wrap = $('#dash-charts');
  renderKpi(d.kpi, d);

  wrap.textContent = '';
  dash.trendCard = null;   // 上面已清空容器，卡片要重建
  drawTrend(d);

  const groups = d.groups || ['治療組', '觀察組'];
  const compare = !dash.group && d.by_group;   // 沒挑族群時，兩組並排比較
  const asPct = compare && dash.mode === 'pct';
  $('#fb-mode').classList.toggle('hidden', !compare);   // 只有對照模式用得到

  /** 兩組人數不一樣（例如 28 vs 12），直接比長度會看錯，
   *  所以提供「組內占比」：每組各自除以自己的分母。 */
  const toRows = (rows) => {
    if (!asPct) return rows;
    const t = d.group_totals || {};
    return rows.map((r) => {
      const out = { key: r.key, raw: {} };
      groups.forEach((g) => {
        out.raw[g] = r[g] || 0;
        out[g] = t[g] ? Math.round((r[g] || 0) / t[g] * 1000) / 10 : 0;
      });
      return out;
    });
  };
  const cols = (labelName) => [{ key: 'key', label: labelName }].concat(
    groups.map((g) => ({ key: g, label: g + (asPct ? ' %' : ''), numeric: true })));

  // 統計欄位由後端的 STAT_FIELDS 決定，前端不寫死欄位名
  Object.keys(d.by || {}).forEach((name) => {
    const rows = d.by[name];
    const label = (state.fieldMap[name] || {}).label || name;
    // 組別欄位本身在對照模式下沒有資訊量（每組只會對到自己），KPI 已經有人數
    if (compare && name === state.schema.key.group) return;
    const grows = toRows((d.by_group || {})[name] || []);
    if (compare) {
      drawCard(label, groupNote(d, grows.length),
        (host) => hbarGrouped(host, grows,
          { title: label, labelWidth: 230, groups, unit: asPct ? 'pct' : 'n' }),
        (host) => table(host, cols(label), grows),
        grows.length > 5);
    } else {
      drawCard(label, rows.length + ' 類',
        (host) => hbar(host, rows, { title: label, labelWidth: 230 }),
        (host) => table(host, [{ key: 'key', label: label },
                               { key: 'count', label: '個案數', numeric: true }], rows),
        rows.length > 6);
    }
  });

  const bothNote = compare ? '兩組合計，要看單一族群請切換上方「族群」' : '';
  drawCard('年齡與性別分布', bothNote || '依收案年齡', (host) => pyramid(host, d.pyramid),
    (host) => table(host, [
      { key: 'band', label: '年齡層' }, { key: 'male', label: '男', numeric: true },
      { key: 'female', label: '女', numeric: true },
      { key: 'other', label: '其他/未填', numeric: true },
    ], d.pyramid), true);

  drawCard('各追蹤時間點的紀錄數', bothNote || '看每個時間點收到多少筆',
    (host) => hbar(host, d.visit_timeline, { labelWidth: 190 }),
    (host) => table(host, [{ key: 'key', label: '時間點' },
                           { key: 'count', label: '紀錄數', numeric: true }],
                    d.visit_timeline), true);

  if (compare) {
    const cg = toRows(d.comorbid_group || []);
    drawCard('共病（' + groups.join(' vs ') + '）', groupNote(d, cg.length),
      (host) => hbarGrouped(host, cg,
        { labelWidth: 220, groups, unit: asPct ? 'pct' : 'n' }),
      (host) => table(host, cols('共病'), cg),
      true);
  } else {
    drawCard('共病盛行率', d.kpi.total ? '分母 ' + d.kpi.total + ' 例' : '',
      (host) => hbar(host, d.comorbid, { labelWidth: 220 }),
      (host) => table(host, [
        { key: 'key', label: '共病' }, { key: 'count', label: '例數', numeric: true },
        { key: 'pct', label: '%', numeric: true },
      ], d.comorbid), true);
  }

  wrap.style.opacity = '';
}

function renderKpi(k, d) {
  const host = $('#dash-kpi');
  host.textContent = '';

  const card = (cls, num, label, sub) => {
    const el = document.createElement('div');
    el.className = 'stat-card' + (cls ? ' ' + cls : '');
    el.innerHTML = '<div class="stat-num"></div><div class="stat-label"></div>'
      + '<div class="stat-sub"></div>';
    el.querySelector('.stat-num').textContent = num;
    el.querySelector('.stat-label').textContent = label;
    el.querySelector('.stat-sub').textContent = sub || '';
    host.appendChild(el);
  };

  const allTotal = Object.values(d.group_totals || {}).reduce((a, b) => a + b, 0);
  const heroSub = !k.total ? '目前還沒有個案'
    : dash.group ? `占兩組合計 ${k.total} / ${allTotal}（${pct(k.total, allTotal)}%）`
    : `治療組 ${k.treat_group}　觀察組 ${k.observe_group}`;
  card('hero', k.total, dash.group ? '本院' + dash.group + '個案數' : '本院收案總數',
    heroSub);
  card('', k.with_followup, '已有追蹤紀錄',
    k.total ? `占 ${pct(k.with_followup, k.total)}%` : '');
  card('', k.visits_total, '追蹤紀錄總筆數', '');
  card('', k.converted, '曾經培養轉陰', '任一次追蹤痰培養陰性');
  card('', k.conversion_rate == null ? '—' : k.conversion_rate + '%', '治療組轉陰率',
    k.treat_group ? `${k.converted} / ${k.treat_group}` : '尚無治療組個案');
}

/** 分組圖的副標：兩組各自的分母，看圖時才知道長度是拿誰跟誰比。 */
function groupNote(d, kinds) {
  const t = (d.group_totals || {});
  const parts = (d.groups || []).map((g) => g + ' ' + (t[g] || 0) + ' 例');
  return parts.join('　') + (kinds ? '　/　' + kinds + ' 類' : '');
}

function pct(a, b) { return b ? Math.round((a / b) * 100) : 0; }

let dashResizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(dashResizeTimer);
  dashResizeTimer = setTimeout(() => {
    if (dash.data && !$('#view-stats').classList.contains('hidden')) paintDashboard(dash.data);
  }, 200);
});

function drawTrend(d) {
  const rows = d.trend[dash.unit] || [];
  const label = { year: '年', quarter: '季', month: '月' }[dash.unit];
  // 卡片物件要留參照 —— 只切換時間單位時不重建整張卡
  let card = dash.trendCard;
  if (!card) {
    card = dash.trendCard = makeCard('確診趨勢', '', true, 'trend-card');
    $('#dash-charts').prepend(card.section);
  }
  card.note.textContent = `依${label}統計，共 ${rows.reduce((s, r) => s + r.count, 0)} 例`;
  // 期數少用直條（比長度），多了才用折線（看走勢）
  if (rows.length <= 12) columns(card.chart, rows, { title: '確診趨勢' });
  else lineChart(card.chart, rows, { title: '確診趨勢' });
  table(card.table, [
    { key: 'key', label: label }, { key: 'count', label: '確診數', numeric: true },
  ], rows);
}

function makeCard(title, note, full, id) {
  const section = document.createElement('section');
  section.className = 'chart-card' + (full ? ' full' : '');
  if (id) section.id = id;
  const header = document.createElement('header');
  const h = document.createElement('h3');
  h.textContent = title;
  const noteEl = document.createElement('span');
  noteEl.className = 'card-note';
  noteEl.textContent = note || '';
  const actions = document.createElement('div');
  actions.className = 'card-actions seg-group';
  const bChart = document.createElement('button');
  bChart.type = 'button';
  bChart.textContent = '圖';
  bChart.className = 'on';
  const bTable = document.createElement('button');
  bTable.type = 'button';
  bTable.textContent = '表';
  actions.append(bChart, bTable);
  header.append(h, noteEl, actions);

  const chart = document.createElement('div');
  const tbl = document.createElement('div');
  tbl.className = 'hidden';
  section.append(header, chart, tbl);

  bChart.addEventListener('click', () => {
    bChart.classList.add('on'); bTable.classList.remove('on');
    chart.classList.remove('hidden'); tbl.classList.add('hidden');
  });
  bTable.addEventListener('click', () => {
    bTable.classList.add('on'); bChart.classList.remove('on');
    tbl.classList.remove('hidden'); chart.classList.add('hidden');
  });

  return { section, chart, table: tbl, note: noteEl };
}

function drawCard(title, note, drawChart, drawTable, full) {
  const card = makeCard(title, note, full);
  $('#dash-charts').appendChild(card.section);
  drawChart(card.chart);
  drawTable(card.table);
}

/* ------------------------------------------------------------------ */
/* 稽核                                                                */
/* ------------------------------------------------------------------ */
async function renderAudit() {
  const data = await api('/api/audit');
  const map = {
    login: '登入', login_failed: '登入失敗', logout: '登出',
    create: '新增個案', update: '修改個案', delete: '刪除個案', export_csv: '匯出 CSV',
  };
  $('#audit-table').querySelector('tbody').innerHTML = data.entries.map((e) =>
    `<tr><td>${esc(e.ts)}</td><td>${esc(e.username)}</td><td>${esc(e.ip)}</td>
     <td>${esc(map[e.action] || e.action)}</td><td>${esc(e.case_no || '')}</td>
     <td>${esc(e.detail || '')}</td></tr>`).join('');
}

/* ------------------------------------------------------------------ */
/* 衛教文章列印                                                        */
/* ------------------------------------------------------------------ */

/** 內容檔裡允許用 <b>…</b> 標重點；這裡自己解析，不用 innerHTML。 */
function richText(host, str) {
  String(str).split(/(<b>.*?<\/b>)/g).forEach((part) => {
    if (!part) return;
    if (part.startsWith('<b>')) {
      const b = document.createElement('strong');
      b.textContent = part.slice(3, -4);
      host.appendChild(b);
    } else {
      host.appendChild(document.createTextNode(part));
    }
  });
}

/** 今天的日期，給 <input type="date"> 用。 */
function todayISO() {
  const d = new Date();
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0')
    + '-' + String(d.getDate()).padStart(2, '0');
}

function fmtDate(v) { return v ? v.replace(/-/g, '/') : ''; }

/** 抬頭：親愛的 ○○○ 先生／女士。 */
function sheetHello(name, title) {
  const line = document.createElement('div');
  line.className = 'ho-hello';
  line.appendChild(document.createTextNode('親愛的　'));
  const nm = document.createElement('span');
  nm.className = 'ho-blank ho-blank-name';
  nm.textContent = name || ' ';
  line.appendChild(nm);
  line.appendChild(document.createTextNode(
    title ? '　' + title + '　您好：' : '　先生／女士　您好：'));
  return line;
}

function hoField(label, value) {
  const wrap = document.createElement('div');
  wrap.className = 'ho-field';
  const lb = document.createElement('span');
  lb.className = 'ho-flabel';
  lb.textContent = label + '：';
  const v = document.createElement('span');
  v.className = 'ho-blank';
  v.textContent = value || ' ';
  wrap.append(lb, v);
  return wrap;
}

/* 單張與文章共用的院所抬頭，要改科別名稱只改這一行。 */
const ORG_LINE = '臺北榮民總醫院　胸腔部 肺部感染與結核中心';

const printState = { picked: new Set(), title: '', size: 'm' };

/** 左側：要印哪幾篇。文章內容一律取自 education.js，不另外編寫。 */
function buildArticlePicker() {
  const host = $('#ho-articles');
  if (host.dataset.ready) return;
  host.dataset.ready = '1';

  EDU_ARTICLES.forEach((article, idx) => {
    const row = document.createElement('label');
    row.className = 'hs-drug';
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.value = String(idx);
    box.addEventListener('change', () => {
      if (box.checked) printState.picked.add(idx);
      else printState.picked.delete(idx);
      renderArticlePreview();
    });
    const txt = document.createElement('span');
    txt.textContent = (article.icon || '') + ' ' + article.title;
    row.append(box, txt);
    host.appendChild(row);
  });
}

function setPickAll(on) {
  printState.picked.clear();
  $('#ho-articles').querySelectorAll('input[type=checkbox]').forEach((b, i) => {
    b.checked = on;
    if (on) printState.picked.add(i);
  });
  renderArticlePreview();
}

/** 右側預覽 = 實際印出來的樣子。一篇一張，列印時自動分頁。 */
function renderArticlePreview() {
  const paper = $('#ho-paper');
  paper.textContent = '';
  paper.className = 'handout-paper fs-' + printState.size;
  $('#ho-count').textContent = '已選 ' + printState.picked.size + ' 篇';

  if (!printState.picked.size) {
    const hint = document.createElement('p');
    hint.className = 'ho-empty';
    hint.textContent = '← 請先勾選要列印的文章';
    paper.appendChild(hint);
    return;
  }

  const name = $('#ho-name').value.trim();
  const date = fmtDate($('#ho-date').value);
  const picked = EDU_ARTICLES.filter((a, i) => printState.picked.has(i));

  picked.forEach((article, n) => {
    const sheet = document.createElement('article');
    sheet.className = 'ho-sheet';

    const head = document.createElement('header');
    head.className = 'ho-head';
    const hosp = document.createElement('div');
    hosp.className = 'ho-hosp';
    hosp.textContent = ORG_LINE + '　NTM 衛教資料';
    const h1 = document.createElement('h1');
    h1.textContent = article.title;
    head.append(hosp, h1);
    sheet.appendChild(head);

    // 姓名與日期只印在第一張，後面幾張接著讀就好
    if (n === 0) {
      const meta = document.createElement('div');
      meta.className = 'ho-meta';
      meta.appendChild(sheetHello(name, printState.title));
      const ids = document.createElement('div');
      ids.className = 'ho-ids';
      ids.appendChild(hoField('日期', date));
      meta.appendChild(ids);
      sheet.appendChild(meta);
    }

    const body = document.createElement('div');
    body.className = 'ho-article';
    article.blocks.forEach((block) => {
      const el = document.createElement(block.h ? 'h2' : 'p');
      el.textContent = block.h || block.p;
      body.appendChild(el);
    });
    sheet.appendChild(body);

    const foot = document.createElement('footer');
    foot.className = 'ho-foot ho-foot-slim';
    if (article.authors && article.authors.length) {
      const by = document.createElement('p');
      by.className = 'ho-by';
      by.textContent = '撰文／' + article.authors.join('　');
      foot.appendChild(by);
    }
    const line = document.createElement('p');
    line.className = 'ho-note';
    line.textContent = ORG_LINE + '　非結核分枝桿菌管理系統'
      + (picked.length > 1 ? '　　第 ' + (n + 1) + ' 張／共 ' + picked.length + ' 張' : '');
    foot.appendChild(line);
    sheet.appendChild(foot);

    paper.appendChild(sheet);
  });
}

function openPrintPicker() {
  if (typeof EDU_ARTICLES === 'undefined' || !EDU_ARTICLES.length) {
    toast('衛教文章尚未載入');
    return;
  }
  buildArticlePicker();
  if (!$('#ho-date').value) $('#ho-date').value = todayISO();
  renderArticlePreview();
  $('#handout').classList.remove('hidden');
  document.body.classList.add('print-overlay');
  document.body.style.overflow = 'hidden';
  $('#ho-name').focus();
}

function closePrintPicker() {
  $('#handout').classList.add('hidden');
  document.body.classList.remove('print-overlay');
  document.body.style.overflow = '';
}

$('#btn-handout').addEventListener('click', openPrintPicker);
$('#ho-close').addEventListener('click', closePrintPicker);
$('#ho-print').addEventListener('click', () => {
  if (!printState.picked.size) { toast('請先勾選要列印的文章'); return; }
  window.print();
});
$('#ho-all').addEventListener('click', () => setPickAll(true));
$('#ho-none').addEventListener('click', () => setPickAll(false));
['#ho-name', '#ho-date'].forEach((sel) => {
  $(sel).addEventListener('input', renderArticlePreview);
});
$('#ho-title').addEventListener('click', (e) => segPick(e, '#ho-title', (v) => {
  printState.title = v;
  renderArticlePreview();
}, 't'));
$('#ho-size').addEventListener('click', (e) => segPick(e, '#ho-size', (v) => {
  printState.size = v;
  renderArticlePreview();
}, 's'));

/** 一整排只能選一個的小按鈕。 */
function segPick(evt, sel, apply, key) {
  const btn = evt.target.closest('button');
  if (!btn) return;
  $(sel).querySelectorAll('button').forEach((b) => b.classList.remove('on'));
  btn.classList.add('on');
  apply(btn.dataset[key]);
}

/* ------------------------------------------------------------------ */
/* 統計報表（可列印、可匯出 CSV）                                      */
/* ------------------------------------------------------------------ */

/* 報表段落。data → [{title, cols, rows}]，同一份資料同時餵給畫面與 CSV，
 * 不會出現「報表上的數字和匯出的數字不一樣」。 */
const REPORT_SECTIONS = [
  { id: 'kpi', name: '收案概況', build: reportKpi },
  { id: 'trend', name: '收案趨勢', build: reportTrend },
  { id: 'dist', name: '各項分布', build: reportDist },
  { id: 'comorbid', name: '共病', build: reportComorbid },
  { id: 'age', name: '年齡與性別分布', build: reportAge },
  { id: 'visits', name: '各追蹤時間點紀錄數', build: reportVisits },
];

const reportState = { off: new Set(), show: 'both' };   // both / chart / table

function reportKpi(d) {
  const k = d.kpi;
  const rows = [
    { key: '收案總數', value: k.total },
    { key: '治療組', value: k.treat_group },
    { key: '觀察組', value: k.observe_group },
    { key: '已有追蹤紀錄', value: k.with_followup },
    { key: '追蹤紀錄總筆數', value: k.visits_total },
    { key: '曾經培養轉陰', value: k.converted },
    { key: '治療組轉陰率', value: k.conversion_rate == null ? '—' : k.conversion_rate + '%' },
  ];
  // 概況是文字型摘要（含百分比），畫成長條沒有意義，只出表
  return [{ cols: [{ key: 'key', label: '項目' },
                   { key: 'value', label: '數值', numeric: true }],
            rows }];
}

function reportTrend(d) {
  const rows = (d.trend || {})[dash.unit] || [];
  const unitName = { year: '年', quarter: '季', month: '月' }[dash.unit] || dash.unit;
  return rows.length ? [{
    title: '依' + unitName + '統計',
    cols: [{ key: 'key', label: unitName + '別' },
           { key: 'count', label: '收案數', numeric: true }],
    rows,
    // 期數少用直條比長度，多了才用折線看走勢，跟儀表板同一套規則
    chart: (host) => (rows.length <= 12
      ? columns(host, rows, { title: '收案趨勢' })
      : lineChart(host, rows, { title: '收案趨勢' })),
  }] : [];
}

/** 兩組對照時每個欄位出兩欄，選定單一族群時只有一欄。 */
function reportDist(d) {
  const groups = d.groups || [];
  const compare = !dash.group;
  const out = [];
  Object.keys(d.by || {}).forEach((name) => {
    if (compare && name === state.schema.key.group) return;
    const label = (state.fieldMap[name] || {}).label || name;
    if (compare) {
      const rows = (d.by_group || {})[name] || [];
      if (!rows.length) return;
      out.push({
        title: label,
        cols: [{ key: 'key', label: '項目' }].concat(groups.map(
          (g) => ({ key: g, label: g, numeric: true }))),
        rows,
        chart: (host) => hbarGrouped(host, rows,
          { title: label, labelWidth: 200, groups }),
      });
    } else {
      const rows = d.by[name] || [];
      if (!rows.length) return;
      out.push({
        title: label,
        cols: [{ key: 'key', label: '項目' },
               { key: 'count', label: '個案數', numeric: true }],
        rows,
        chart: (host) => hbar(host, rows, { title: label, labelWidth: 200 }),
      });
    }
  });
  return out;
}

function reportComorbid(d) {
  const groups = d.groups || [];
  if (!dash.group) {
    const rows = d.comorbid_group || [];
    return rows.length ? [{
      title: groups.join(' vs '),
      cols: [{ key: 'key', label: '共病' }].concat(groups.map(
        (g) => ({ key: g, label: g, numeric: true }))),
      rows,
      chart: (host) => hbarGrouped(host, rows, { labelWidth: 200, groups }),
    }] : [];
  }
  const rows = d.comorbid || [];
  return rows.length ? [{
    title: '盛行率',
    cols: [{ key: 'key', label: '共病' },
           { key: 'count', label: '例數', numeric: true },
           { key: 'pct', label: '%', numeric: true }],
    rows,
    chart: (host) => hbar(host, rows, { labelWidth: 200 }),
  }] : [];
}

function reportAge(d) {
  const rows = (d.pyramid || []).filter((b) => b.male || b.female || b.other);
  return rows.length ? [{
    cols: [{ key: 'band', label: '年齡層' }, { key: 'male', label: '男', numeric: true },
           { key: 'female', label: '女', numeric: true },
           { key: 'other', label: '其他/未填', numeric: true }],
    rows,
    chart: (host) => pyramid(host, d.pyramid),
  }] : [];
}

function reportVisits(d) {
  const rows = d.visit_timeline || [];
  return rows.length ? [{
    cols: [{ key: 'key', label: '時間點' },
           { key: 'count', label: '紀錄數', numeric: true }],
    rows,
    chart: (host) => hbar(host, rows, { labelWidth: 200 }),
  }] : [];
}

/** 目前的篩選條件，報表上要寫清楚，否則數字脫離條件就沒有意義。 */
function reportConditions(d) {
  const f = d.filters || {};
  const span = (f.year_from || f.year_to)
    ? (f.year_from || '不限') + ' — ' + (f.year_to || '不限') : '全部年度';
  return [
    { key: '收案年度', value: span },
    { key: '菌種', value: f.species || '全部菌種' },
    { key: '族群', value: f.group || '治療組與觀察組對照' },
    { key: '資料來源', value: (d.site || '') + ' NTM 個案資料庫' },
  ];
}

function buildReportPanel() {
  const host = $('#rp-sections');
  if (host.dataset.ready) return;
  host.dataset.ready = '1';
  REPORT_SECTIONS.forEach((sec) => {
    const row = document.createElement('label');
    row.className = 'hs-drug';
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.checked = true;
    box.addEventListener('change', () => {
      if (box.checked) reportState.off.delete(sec.id);
      else reportState.off.add(sec.id);
      renderReport();
    });
    const txt = document.createElement('span');
    txt.textContent = sec.name;
    row.append(box, txt);
    host.appendChild(row);
  });
}

/** 報表要印的段落，畫面與 CSV 共用；空的段落自動略過，編號才不會跳號。 */
function reportTables() {
  const d = dash.data;
  if (!d) return [];
  const cn = '一二三四五六七八九十';
  const out = [];
  REPORT_SECTIONS.forEach((sec) => {
    if (reportState.off.has(sec.id)) return;
    const tables = sec.build(d).filter((t) => t.rows && t.rows.length);
    if (!tables.length) return;
    out.push({ no: cn[out.length] + '、' + sec.name, tables });
  });
  return out;
}

function renderReport() {
  const paper = $('#rp-paper');
  const d = dash.data;
  paper.textContent = '';
  if (!d) return;

  const sheet = document.createElement('div');
  sheet.className = 'ho-sheet';

  const head = document.createElement('header');
  head.className = 'ho-head';
  const hosp = document.createElement('div');
  hosp.className = 'ho-hosp';
  hosp.textContent = ORG_LINE;
  const h1 = document.createElement('h1');
  h1.textContent = $('#rp-title').value.trim() || 'NTM 個案統計報表';
  head.append(hosp, h1);
  sheet.appendChild(head);

  // 製表資訊 + 統計條件
  const meta = document.createElement('div');
  meta.className = 'rp-meta';
  const purpose = $('#rp-purpose').value.trim();
  const info = [{ key: '製表日期', value: fmtDate($('#rp-date').value) },
                { key: '製表者', value: $('#rp-by').value.trim() }];
  if (purpose) info.unshift({ key: '用途', value: purpose });
  info.concat(reportConditions(d)).forEach((it) => {
    if (!it.value) return;
    const cell = document.createElement('div');
    cell.className = 'rp-meta-item';
    const k = document.createElement('span');
    k.className = 'rp-meta-k';
    k.textContent = it.key + '：';
    const v = document.createElement('span');
    v.textContent = it.value;
    cell.append(k, v);
    meta.appendChild(cell);
  });
  sheet.appendChild(meta);

  const tables = reportTables();
  if (!tables.length) {
    const p = document.createElement('p');
    p.className = 'ho-empty';
    p.textContent = '目前的條件下沒有可呈現的資料。';
    sheet.appendChild(p);
  }

  tables.forEach((sec) => {
    const secWrap = document.createElement('section');
    secWrap.className = 'rp-sec';
    const h2 = document.createElement('h2');
    h2.textContent = sec.no;
    secWrap.appendChild(h2);
    sec.tables.forEach((t) => secWrap.appendChild(reportTableBlock(t)));
    sheet.appendChild(secWrap);
  });

  const foot = document.createElement('footer');
  foot.className = 'ho-foot ho-foot-slim';
  const note = document.createElement('p');
  note.className = 'ho-note';
  note.textContent = ORG_LINE + '　非結核分枝桿菌管理系統　'
    + '本報表僅含統計數字，不含個案識別資料；僅供院內使用。';
  foot.appendChild(note);
  sheet.appendChild(foot);

  paper.appendChild(sheet);
}

/** 一張表：小標 + 長條圖 + 表格，依「呈現方式」決定要哪些。 */
function reportTableBlock(t) {
  const block = document.createElement('div');
  block.className = 'rp-block';
  if (t.title) {
    const h3 = document.createElement('h3');
    h3.textContent = t.title;
    block.appendChild(h3);
  }

  // 圖畫不出來（摘要型段落），或只有一類、畫出來也看不出比較時，就只出表
  const worthChart = typeof t.chart === 'function' && t.rows.length > 1;
  const wantChart = reportState.show !== 'table' && worthChart;
  if (wantChart) {
    const host = document.createElement('div');
    host.className = 'rp-chart';
    block.appendChild(host);
    t.chart(host);
  }
  if (reportState.show === 'chart' && wantChart) return block;

  const tbl = document.createElement('table');
  tbl.className = 'rp-table';
  const thead = document.createElement('thead');
  const htr = document.createElement('tr');
  t.cols.forEach((c) => {
    const th = document.createElement('th');
    th.textContent = c.label;
    if (c.numeric) th.className = 'num';
    htr.appendChild(th);
  });
  thead.appendChild(htr);
  const tbody = document.createElement('tbody');
  t.rows.forEach((r) => {
    const tr = document.createElement('tr');
    t.cols.forEach((c) => {
      const td = document.createElement('td');
      const v = r[c.key];
      td.textContent = v == null ? '' : v;
      if (c.numeric) td.className = 'num';
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  tbl.append(thead, tbody);
  block.appendChild(tbl);
  return block;
}

function openReport() {
  if (!dash.data) { toast('請先讓儀表板載入資料'); return; }
  buildReportPanel();
  if (!$('#rp-date').value) $('#rp-date').value = todayISO();
  $('#rp-filters').textContent = '目前條件：'
    + reportConditions(dash.data).map((c) => c.key + ' ' + c.value).join('　/　')
    + '。要換條件請關掉這個視窗，在儀表板改完再開一次。';
  renderReport();
  $('#report').classList.remove('hidden');
  document.body.classList.add('print-overlay');
  document.body.style.overflow = 'hidden';
}

function closeReport() {
  $('#report').classList.add('hidden');
  document.body.classList.remove('print-overlay');
  document.body.style.overflow = '';
}

/** 統計表 CSV：跟報表同一份資料，給 Excel／Word 排版用。
 *  含 BOM，Excel 開中文才不會變亂碼。 */
function exportStatsCsv() {
  const d = dash.data;
  if (!d) { toast('請先讓儀表板載入資料'); return; }
  const q = (v) => '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"';
  const lines = [];
  lines.push([q($('#rp-title') ? ($('#rp-title').value.trim() || 'NTM 個案統計報表')
                               : 'NTM 個案統計報表')].join(','));
  reportConditions(d).forEach((c) => lines.push([q(c.key), q(c.value)].join(',')));
  lines.push('');

  reportTables().forEach((sec) => {
    lines.push([q(sec.no)].join(','));
    sec.tables.forEach((t) => {
      if (t.title) lines.push([q(t.title)].join(','));
      lines.push(t.cols.map((c) => q(c.label)).join(','));
      t.rows.forEach((r) => lines.push(t.cols.map((c) => q(r[c.key])).join(',')));
      lines.push('');
    });
  });

  const blob = new Blob(['﻿' + lines.join('\r\n')],
                        { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'NTM_stats_' + todayISO() + '.csv';   // ASCII 檔名最保險
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast('已下載統計表 CSV');
}

$('#btn-report').addEventListener('click', openReport);
$('#btn-stats-csv').addEventListener('click', exportStatsCsv);
$('#rp-show').addEventListener('click', (e) => segPick(e, '#rp-show', (v) => {
  reportState.show = v;
  renderReport();
}, 's'));
$('#rp-close').addEventListener('click', closeReport);
$('#rp-print').addEventListener('click', () => window.print());
$('#rp-csv').addEventListener('click', exportStatsCsv);
['#rp-title', '#rp-purpose', '#rp-by', '#rp-date'].forEach((sel) => {
  $(sel).addEventListener('input', renderReport);
});

/* ------------------------------------------------------------------ */
/* 用藥說明單張（內容為草稿，待院內衛教組審核）                        */
/* ------------------------------------------------------------------ */

const dsState = { picked: new Set(), title: '' };

function buildDrugPicker() {
  const host = $('#ds-drugs');
  if (host.dataset.ready) return;
  host.dataset.ready = '1';

  DRUGSHEET.drugs.forEach((grp) => {
    const h = document.createElement('div');
    h.className = 'hs-grp';
    h.textContent = grp.group;
    host.appendChild(h);

    grp.items.forEach((drug) => {
      const row = document.createElement('label');
      row.className = 'hs-drug';
      const box = document.createElement('input');
      box.type = 'checkbox';
      box.value = drug.en;
      box.addEventListener('change', () => {
        if (box.checked) dsState.picked.add(drug.en);
        else dsState.picked.delete(drug.en);
        renderDrugSheet();
      });
      const txt = document.createElement('span');
      txt.textContent = drug.local ? drug.local + '　' + drug.en : drug.en;
      row.append(box, txt);
      host.appendChild(row);
    });
  });
}

function renderDrugSheet() {
  const paper = $('#ds-paper');
  paper.textContent = '';

  const sheet = document.createElement('div');
  sheet.className = 'ho-sheet';

  const head = document.createElement('header');
  head.className = 'ho-head';
  const hosp = document.createElement('div');
  hosp.className = 'ho-hosp';
  hosp.textContent = ORG_LINE;
  const h1 = document.createElement('h1');
  h1.textContent = DRUGSHEET.title;
  head.append(hosp, h1);
  sheet.appendChild(head);

  const meta = document.createElement('div');
  meta.className = 'ho-meta';
  meta.appendChild(sheetHello($('#ds-name').value.trim(), dsState.title));
  const ids = document.createElement('div');
  ids.className = 'ho-ids';
  ids.appendChild(hoField('病歷號／編號', $('#ds-code').value.trim()));
  ids.appendChild(hoField('日期', fmtDate($('#ds-date').value)));
  meta.appendChild(ids);
  sheet.appendChild(meta);

  DRUGSHEET.sections.forEach((sec) => {
    const block = document.createElement('section');
    block.className = 'ho-sec';
    const h2 = document.createElement('h2');
    h2.textContent = sec.n + '、' + sec.h;
    block.appendChild(h2);

    if (sec.items) {
      const ul = document.createElement('ul');
      ul.className = 'ho-list';
      sec.items.forEach((it) => {
        const li = document.createElement('li');
        richText(li, it);
        ul.appendChild(li);
      });
      block.appendChild(ul);
    }
    if (sec.drugs) block.appendChild(dsDrugBlock());
    if (sec.checks) {
      const ul = document.createElement('ul');
      ul.className = 'ho-check-list';
      sec.checks.forEach((it) => {
        const li = document.createElement('li');
        const bx = document.createElement('span');
        bx.className = 'ho-box';
        li.appendChild(bx);
        richText(li, it);
        ul.appendChild(li);
      });
      block.appendChild(ul);
    }
    if (sec.warn) {
      const box = document.createElement('div');
      box.className = 'ho-warn';
      const ul = document.createElement('ul');
      sec.warn.forEach((it) => {
        const li = document.createElement('li');
        richText(li, it);
        ul.appendChild(li);
      });
      box.appendChild(ul);
      block.appendChild(box);
    }
    sheet.appendChild(block);
  });

  const foot = document.createElement('footer');
  foot.className = 'ho-foot';
  const grid = document.createElement('div');
  grid.className = 'ho-foot-grid';
  grid.appendChild(hoField('下次回診', $('#ds-next').value.trim()));
  grid.appendChild(hoField('聯絡電話', $('#ds-tel').value.trim()));
  grid.appendChild(hoField('衛教者', $('#ds-by').value.trim()));
  grid.appendChild(hoField('病人／家屬簽名', ''));
  foot.appendChild(grid);
  DRUGSHEET.footer.forEach((t) => {
    const p = document.createElement('p');
    p.className = 'ho-note';
    p.textContent = t;
    foot.appendChild(p);
  });
  sheet.appendChild(foot);

  paper.appendChild(sheet);
}

/** 有勾就只印勾的；完全沒勾就印全部，讓護理師當場手寫打勾。 */
function dsDrugBlock() {
  const wrap = document.createElement('div');
  const picked = dsState.picked;
  const anyPicked = picked.size > 0;

  const cap = document.createElement('p');
  cap.className = 'ho-drug-cap';
  cap.textContent = anyPicked
    ? '打勾者為您正在服用的藥：'
    : '（醫護人員會為您勾選）';
  wrap.appendChild(cap);

  DRUGSHEET.drugs.forEach((grp) => {
    const items = anyPicked ? grp.items.filter((d) => picked.has(d.en)) : grp.items;
    if (!items.length) return;

    const gh = document.createElement('div');
    gh.className = 'ho-drug-grp';
    gh.textContent = grp.group;
    wrap.appendChild(gh);

    items.forEach((drug) => {
      const row = document.createElement('div');
      row.className = 'ho-drug';

      const bx = document.createElement('span');
      bx.className = 'ho-box' + (anyPicked && picked.has(drug.en) ? ' on' : '');
      row.appendChild(bx);

      const body = document.createElement('div');
      const nameLine = document.createElement('div');
      nameLine.className = 'ho-drug-name';
      const main = document.createElement('strong');
      // 院內藥品名（藥袋上印的那個）優先，病人才對得起來
      main.textContent = drug.local || drug.en;
      const use = document.createElement('span');
      use.className = 'ho-drug-use';
      use.textContent = drug.use;
      nameLine.append(main, use);
      body.appendChild(nameLine);

      const gen = document.createElement('div');
      gen.className = 'ho-drug-en';
      // 中文一律不猜：院內藥名沒填就留一條底線，讓護理師照藥袋手寫
      gen.textContent = drug.local
        ? '學名：' + drug.en
        : '院內藥名：______________________';
      body.appendChild(gen);

      const eff = document.createElement('div');
      eff.className = 'ho-drug-eff';
      eff.appendChild(document.createTextNode('可能的副作用：'));
      drug.effects.forEach((e, i) => {
        if (i) eff.appendChild(document.createTextNode('、'));
        richText(eff, e);
      });
      body.appendChild(eff);

      row.appendChild(body);
      wrap.appendChild(row);
    });
  });

  const other = document.createElement('div');
  other.className = 'ho-drug ho-drug-other';
  const bx = document.createElement('span');
  bx.className = 'ho-box';
  const txt = document.createElement('div');
  txt.textContent = '其他藥物：__________________________　'
    + '服法：__________________________';
  other.append(bx, txt);
  wrap.appendChild(other);

  return wrap;
}

function openDrugSheet() {
  if (typeof DRUGSHEET === 'undefined') { toast('用藥單張內容未載入'); return; }
  buildDrugPicker();
  if (!$('#ds-date').value) $('#ds-date').value = todayISO();
  renderDrugSheet();
  $('#drugsheet').classList.remove('hidden');
  document.body.classList.add('print-overlay');
  document.body.style.overflow = 'hidden';
  $('#ds-name').focus();
}

function closeDrugSheet() {
  $('#drugsheet').classList.add('hidden');
  document.body.classList.remove('print-overlay');
  document.body.style.overflow = '';
}

$('#btn-drugsheet').addEventListener('click', openDrugSheet);
$('#ds-close').addEventListener('click', closeDrugSheet);
$('#ds-print').addEventListener('click', () => window.print());
$('#ds-clear').addEventListener('click', () => {
  dsState.picked.clear();
  $('#ds-drugs').querySelectorAll('input[type=checkbox]').forEach((b) => {
    b.checked = false;
  });
  renderDrugSheet();
});
['#ds-name', '#ds-code', '#ds-date', '#ds-next', '#ds-tel', '#ds-by'].forEach((sel) => {
  $(sel).addEventListener('input', renderDrugSheet);
});
$('#ds-title').addEventListener('click', (e) => segPick(e, '#ds-title', (v) => {
  dsState.title = v;
  renderDrugSheet();
}, 't'));

document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape') return;
  if (!$('#handout').classList.contains('hidden')) closePrintPicker();
  if (!$('#drugsheet').classList.contains('hidden')) closeDrugSheet();
  if (!$('#report').classList.contains('hidden')) closeReport();
});

boot();
