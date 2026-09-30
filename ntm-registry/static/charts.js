/* 圖表元件 — 純 inline SVG，無任何外部函式庫。
 *
 * 配色說明：
 *   類別色（男/女）取自已驗證的雙色組合，色盲模擬下的分離度 ΔE 24.7，遠高於門檻 8。
 *   名目類別（菌種、共病…）一律用單一藍色，不用深淺漸層 —— 長度已經表達了大小，
 *   再用顏色編一次同樣的資訊只會浪費唯一的自由通道。
 *   藥敏 S/I/R 用狀態色（綠/黃/紅），因為那三個值的意義本來就是好／中間／壞，
 *   並且一律附上文字標籤，不讓顏色單獨承載意義。
 */
'use strict';

const VIZ = {
  s1: '#2a78d6',        // 類別色 1
  s2: '#eb6834',        // 類別色 2
  good: '#0ca30c', warn: '#fab219', bad: '#d03b3b',   // 狀態色
  grid: '#e1e0d9', axis: '#c3c2b7', muted: '#898781',
  ink: '#1c2333', ink2: '#52514e', surface: '#ffffff',
  /* 有序類別（抹片價數 0 → 4+）用同色系由淺到深，
     讓「愈深＝菌量愈多」可以直接讀出來；陰性用灰色，與有菌量的藍階分開。 */
  ramp: ['#9aa3ad', '#c2dcf7', '#8fbeee', '#5b9ce4', '#2a78d6', '#17457e'],
};

const NS = 'http://www.w3.org/2000/svg';

/** 圖表依容器目前的實際寬度繪製 —— 縮放 viewBox 會連字級一起縮，小卡就看不清了。 */
function hostWidth(host) {
  return Math.max(320, Math.round(host.clientWidth || host.parentNode?.clientWidth || 720));
}

function el(tag, attrs, text) {
  const node = document.createElementNS(NS, tag);
  for (const k in attrs) node.setAttribute(k, attrs[k]);
  if (text != null) node.textContent = text;   // 標籤是資料，一律用 textContent
  return node;
}

function makeSvg(W, height, label) {
  return el('svg', {
    viewBox: `0 0 ${W} ${height}`, width: W, height: height,
    role: 'img', 'aria-label': label, class: 'viz',
  });
}

/** 長條路徑：資料端 4px 圓角，基線端維持方角。 */
function barPath(x, y, w, h, dir) {
  const r = Math.max(0, Math.min(4, dir === 'right' ? w : h, (dir === 'right' ? h : w) / 2));
  if (r < 0.5) return `M${x},${y}h${w}v${h}h${-w}z`;
  if (dir === 'right') {
    return `M${x},${y} H${x + w - r} A${r},${r} 0 0 1 ${x + w},${y + r}`
         + ` V${y + h - r} A${r},${r} 0 0 1 ${x + w - r},${y + h} H${x} Z`;
  }
  return `M${x},${y + h} V${y + r} A${r},${r} 0 0 1 ${x + r},${y}`
       + ` H${x + w - r} A${r},${r} 0 0 1 ${x + w},${y + r} V${y + h} Z`;
}

/** 座標軸刻度取整數且不超過 maxTicks 格。 */
function niceTicks(max, maxTicks) {
  if (max <= 0) return [0, 1];
  const raw = max / (maxTicks || 4);
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || mag * 10;
  // 頂端刻度一定要 >= max，否則最長的長條會畫到座標區外面
  const top = Math.ceil(max / step) * step;
  const ticks = [];
  for (let v = 0; v <= top + step * 0.001; v += step) ticks.push(Math.round(v * 100) / 100);
  return ticks;
}

/* ------------------------------------------------------------------ */
/* 提示框                                                              */
/* ------------------------------------------------------------------ */
let tipEl;
function tip() {
  if (!tipEl) {
    tipEl = document.createElement('div');
    tipEl.className = 'viz-tip hidden';
    document.body.appendChild(tipEl);
  }
  return tipEl;
}

/** rows: [{swatch, name, value}]；數值是主角，名稱次之。 */
function showTip(target, title, rows) {
  const t = tip();
  t.textContent = '';
  const h = document.createElement('div');
  h.className = 'viz-tip-title';
  h.textContent = title;
  t.appendChild(h);
  rows.forEach((r) => {
    const line = document.createElement('div');
    line.className = 'viz-tip-row';
    if (r.swatch) {
      const key = document.createElement('span');
      key.className = 'viz-tip-key';
      key.style.background = r.swatch;
      line.appendChild(key);
    }
    const val = document.createElement('b');
    val.textContent = r.value;
    const nm = document.createElement('span');
    nm.className = 'viz-tip-name';
    nm.textContent = r.name;
    line.append(val, nm);
    t.appendChild(line);
  });
  t.classList.remove('hidden');
  const box = target.getBoundingClientRect();
  const tb = t.getBoundingClientRect();
  let left = box.left + box.width / 2 - tb.width / 2;
  left = Math.max(8, Math.min(left, window.innerWidth - tb.width - 8));
  let top = box.top - tb.height - 10;
  if (top < 8) top = box.bottom + 10;
  t.style.left = left + 'px';
  t.style.top = top + 'px';
}

function hideTip() { if (tipEl) tipEl.classList.add('hidden'); }

/** 讓標記可用滑鼠與鍵盤取得同樣的資訊。 */
function hoverable(node, title, rows) {
  node.setAttribute('tabindex', '0');
  node.setAttribute('focusable', 'true');
  const show = () => showTip(node, title, rows);
  node.addEventListener('pointerenter', show);
  node.addEventListener('focus', show);
  node.addEventListener('pointerleave', hideTip);
  node.addEventListener('blur', hideTip);
}

/* ------------------------------------------------------------------ */
/* 橫向長條圖 —— 名目類別比大小                                        */
/* ------------------------------------------------------------------ */
/** 左側標籤放不下時截短，避免文字溢出卡片外。
 *  沒有 canvas 可量測（也不想為了量字多開一個），用字寬估算就夠：
 *  中日韓與全形字約一個字高，西文與數字約 0.55 倍。
 *  截短的只是畫面，滑鼠移上去的提示仍然是完整名稱。 */
function fitLabel(text, maxPx, fontPx) {
  fontPx = fontPx || 12;
  const wide = (ch) => ch.charCodeAt(0) > 0x2E80;
  const width = (str) => Array.from(str)
    .reduce((sum, ch) => sum + (wide(ch) ? fontPx : fontPx * 0.55), 0);
  if (width(text) <= maxPx) return text;
  let out = '';
  for (const ch of Array.from(text)) {
    if (width(out + ch) + fontPx > maxPx) break;
    out += ch;
  }
  return out.replace(/\s+$/, '') + '…';
}

function hbar(host, rows, opts) {
  opts = opts || {};
  host.textContent = '';
  if (!rows.length) return empty(host);

  const W = hostWidth(host);
  const labelW = Math.min(opts.labelWidth || 190, Math.round(W * 0.42));
  const rowH = 28, barH = 18, padTop = 8, padBottom = 26, valueW = 54;
  const plotW = W - labelW - valueW - 12;
  const height = padTop + rows.length * rowH + padBottom;
  const max = Math.max(...rows.map((r) => r.count), 1);
  const ticks = niceTicks(max, 4);
  const scale = (v) => (v / ticks[ticks.length - 1]) * plotW;
  const svg = makeSvg(W, height, opts.title || '長條圖');

  ticks.forEach((t) => {
    const x = labelW + scale(t);
    svg.appendChild(el('line', {
      x1: x, x2: x, y1: padTop, y2: padTop + rows.length * rowH,
      stroke: t === 0 ? VIZ.axis : VIZ.grid, 'stroke-width': 1,
    }));
    svg.appendChild(el('text', {
      x, y: height - 10, 'text-anchor': 'middle', class: 'viz-tick',
    }, t));
  });

  rows.forEach((r, i) => {
    const y = padTop + i * rowH;
    const labelNode = el('text', {
      x: labelW - 10, y: y + rowH / 2 + 4, 'text-anchor': 'end', class: 'viz-label',
    }, fitLabel(r.key, labelW - 14));
    labelNode.appendChild(el('title', {}, r.key));   // 截短了還是查得到全名
    svg.appendChild(labelNode);
    const w = scale(r.count);
    const bar = el('path', {
      d: barPath(labelW, y + (rowH - barH) / 2, Math.max(w, 1), barH, 'right'),
      fill: VIZ.s1, class: 'viz-mark',
    });
    hoverable(bar, r.key, [{
      swatch: VIZ.s1, value: opts.unit === 'pct' ? r.count + '%' : r.count + ' 例',
      name: opts.seriesName || '個案數',
    }]);
    svg.appendChild(bar);
    svg.appendChild(el('text', {
      x: labelW + w + 8, y: y + rowH / 2 + 4, class: 'viz-value',
    }, opts.unit === 'pct' ? r.count + '%' : r.count));
  });

  host.appendChild(svg);
}

/* ------------------------------------------------------------------ */
/* 分組長條圖 —— 兩個族群並排比較（治療組 / 觀察組）                   */
/* ------------------------------------------------------------------ */

/** rows: [{key, <組名1>: n, <組名2>: n}]，opts.groups 給兩個組名。
 *  兩組用已驗證的雙色組合（同金字塔的男/女），色盲模擬下仍分得開；
 *  並排而不是堆疊，因為要比較的是「兩組各自的分布」，不是總和。 */
function fmtGrouped(row, group, opts) {
  const v = row[group] || 0;
  if (opts.unit !== 'pct') return v + ' 例';
  const n = (row.raw || {})[group];
  return v + '%' + (n == null ? '' : '（' + n + ' 例）');
}

function hbarGrouped(host, rows, opts) {
  opts = opts || {};
  host.textContent = '';
  if (!rows.length) return empty(host);

  const groups = opts.groups || ['A', 'B'];
  const colors = [VIZ.s1, VIZ.s2];
  const W = hostWidth(host);
  const labelW = Math.min(opts.labelWidth || 200, Math.round(W * 0.4));
  const barH = 12, gap = 4, rowPad = 14;
  const rowH = barH * 2 + gap + rowPad;
  const padTop = 8, padBottom = 26, valueW = 46;
  const plotW = W - labelW - valueW - 12;
  const height = padTop + rows.length * rowH + padBottom;
  const max = Math.max(1, ...rows.map((r) => Math.max(r[groups[0]] || 0, r[groups[1]] || 0)));
  const ticks = niceTicks(max, 4);
  const scale = (v) => (v / ticks[ticks.length - 1]) * plotW;
  const svg = makeSvg(W, height, opts.title || '分組長條圖');

  ticks.forEach((t) => {
    const x = labelW + scale(t);
    svg.appendChild(el('line', {
      x1: x, x2: x, y1: padTop, y2: padTop + rows.length * rowH,
      stroke: t === 0 ? VIZ.axis : VIZ.grid, 'stroke-width': 1,
    }));
    svg.appendChild(el('text', {
      x, y: height - 10, 'text-anchor': 'middle', class: 'viz-tick',
    }, t));
  });

  rows.forEach((r, i) => {
    const top = padTop + i * rowH + rowPad / 2;
    const labelNode = el('text', {
      x: labelW - 10, y: top + barH + gap / 2 + 3, 'text-anchor': 'end', class: 'viz-label',
    }, fitLabel(r.key, labelW - 14));
    labelNode.appendChild(el('title', {}, r.key));
    svg.appendChild(labelNode);

    groups.forEach((g, gi) => {
      const v = r[g] || 0;
      const y = top + gi * (barH + gap);
      const w = scale(v);
      const bar = el('path', {
        d: barPath(labelW, y, Math.max(w, 1), barH, 'right'),
        fill: colors[gi], class: 'viz-mark',
      });
      hoverable(bar, r.key, groups.map((g2, j) => ({
        swatch: colors[j], name: g2, value: fmtGrouped(r, g2, opts),
      })));
      svg.appendChild(bar);
      svg.appendChild(el('text', {
        x: labelW + w + 6, y: y + barH - 1, class: 'viz-value',
      }, opts.unit === 'pct' ? v + '%' : v));
    });
  });

  host.appendChild(svg);
  host.appendChild(legend(groups.map((g, i) => ({ name: g, color: colors[i] }))));
}

/* ------------------------------------------------------------------ */
/* 直條圖 —— 期間別個案數                                              */
/* ------------------------------------------------------------------ */
function columns(host, rows, opts) {
  opts = opts || {};
  host.textContent = '';
  if (!rows.length) return empty(host);

  const W = hostWidth(host);
  const padL = 44, padR = 12, padTop = 16, padBottom = 34;
  const height = 260;
  const plotW = W - padL - padR;
  const plotH = height - padTop - padBottom;
  const max = Math.max(...rows.map((r) => r.count), 1);
  const ticks = niceTicks(max, 4);
  const top = ticks[ticks.length - 1];
  const band = plotW / rows.length;
  const barW = Math.min(24, band * 0.6);
  const svg = makeSvg(W, height, opts.title || '直條圖');

  ticks.forEach((t) => {
    const y = padTop + plotH - (t / top) * plotH;
    svg.appendChild(el('line', {
      x1: padL, x2: padL + plotW, y1: y, y2: y,
      stroke: t === 0 ? VIZ.axis : VIZ.grid, 'stroke-width': 1,
    }));
    svg.appendChild(el('text', {
      x: padL - 8, y: y + 4, 'text-anchor': 'end', class: 'viz-tick',
    }, t));
  });

  const skip = Math.ceil(rows.length / 14);
  rows.forEach((r, i) => {
    const x = padL + band * i + (band - barW) / 2;
    const h = (r.count / top) * plotH;
    const y = padTop + plotH - h;
    if (r.count > 0) {
      const bar = el('path', {
        d: barPath(x, y, barW, h, 'up'), fill: VIZ.s1, class: 'viz-mark',
      });
      hoverable(bar, r.key, [{ swatch: VIZ.s1, value: r.count + ' 例', name: '確診數' }]);
      svg.appendChild(bar);
    }
    if (i % skip === 0) {
      svg.appendChild(el('text', {
        x: x + barW / 2, y: height - 12, 'text-anchor': 'middle', class: 'viz-tick',
      }, r.key));
    }
  });

  // 只標最高點，不是每根都標
  const peak = rows.reduce((a, b) => (b.count > a.count ? b : a), rows[0]);
  if (peak.count > 0) {
    const pi = rows.indexOf(peak);
    svg.appendChild(el('text', {
      x: padL + band * pi + band / 2,
      y: padTop + plotH - (peak.count / top) * plotH - 8,
      'text-anchor': 'middle', class: 'viz-value',
    }, peak.count));
  }
  host.appendChild(svg);
}

/* ------------------------------------------------------------------ */
/* 折線圖 —— 期間較多時的趨勢                                          */
/* ------------------------------------------------------------------ */
function lineChart(host, rows, opts) {
  opts = opts || {};
  host.textContent = '';
  if (!rows.length) return empty(host);
  if (rows.length === 1) return columns(host, rows, opts);

  const W = hostWidth(host);
  const padL = 44, padR = 16, padTop = 16, padBottom = 34;
  const height = 260;
  const plotW = W - padL - padR;
  const plotH = height - padTop - padBottom;
  const max = Math.max(...rows.map((r) => r.count), 1);
  const ticks = niceTicks(max, 4);
  const top = ticks[ticks.length - 1];
  const X = (i) => padL + (rows.length === 1 ? plotW / 2 : (i / (rows.length - 1)) * plotW);
  const Y = (v) => padTop + plotH - (v / top) * plotH;
  const svg = makeSvg(W, height, opts.title || '趨勢圖');

  ticks.forEach((t) => {
    svg.appendChild(el('line', {
      x1: padL, x2: padL + plotW, y1: Y(t), y2: Y(t),
      stroke: t === 0 ? VIZ.axis : VIZ.grid, 'stroke-width': 1,
    }));
    svg.appendChild(el('text', {
      x: padL - 8, y: Y(t) + 4, 'text-anchor': 'end', class: 'viz-tick',
    }, t));
  });

  const d = rows.map((r, i) => `${i ? 'L' : 'M'}${X(i)},${Y(r.count)}`).join(' ');
  svg.appendChild(el('path', {
    d, fill: 'none', stroke: VIZ.s1, 'stroke-width': 2,
    'stroke-linejoin': 'round', 'stroke-linecap': 'round',
  }));

  const skip = Math.ceil(rows.length / 12);
  rows.forEach((r, i) => {
    if (i % skip === 0 || i === rows.length - 1) {
      svg.appendChild(el('text', {
        x: X(i), y: height - 12, 'text-anchor': 'middle', class: 'viz-tick',
      }, r.key));
    }
    // 標記帶 2px 底色外環，交疊時仍清楚
    svg.appendChild(el('circle', {
      cx: X(i), cy: Y(r.count), r: 4.5, fill: VIZ.s1,
      stroke: VIZ.surface, 'stroke-width': 2,
    }));
    // 命中區域比標記大，滑鼠不必對準
    const hit = el('circle', { cx: X(i), cy: Y(r.count), r: 14, fill: 'transparent', class: 'viz-mark' });
    hoverable(hit, r.key, [{ swatch: VIZ.s1, value: r.count + ' 例', name: '確診數' }]);
    svg.appendChild(hit);
  });

  const last = rows[rows.length - 1];
  svg.appendChild(el('text', {
    x: X(rows.length - 1), y: Y(last.count) - 12, 'text-anchor': 'end', class: 'viz-value',
  }, last.count));

  host.appendChild(svg);
}

/* ------------------------------------------------------------------ */
/* 年齡性別金字塔                                                      */
/* ------------------------------------------------------------------ */
function pyramid(host, bands, opts) {
  opts = opts || {};
  host.textContent = '';
  const total = bands.reduce((s, b) => s + b.male + b.female + b.other, 0);
  if (!total) return empty(host);

  const W = hostWidth(host);
  const rowH = 30, barH = 18, padTop = 8, padBottom = 28;
  const gutter = 76;                       // 中間放年齡層標籤
  const half = (W - gutter) / 2 - 34;
  const height = padTop + bands.length * rowH + padBottom;
  const max = Math.max(...bands.map((b) => Math.max(b.male, b.female)), 1);
  const ticks = niceTicks(max, 3);
  const topTick = ticks[ticks.length - 1];
  const cx = W / 2;
  const svg = makeSvg(W, height, '年齡性別分布金字塔');

  ticks.forEach((t) => {
    const dx = (t / topTick) * half;
    [-1, 1].forEach((sign) => {
      if (t === 0 && sign === 1) return;
      const x = cx + sign * (gutter / 2 + dx);
      svg.appendChild(el('line', {
        x1: x, x2: x, y1: padTop, y2: padTop + bands.length * rowH,
        stroke: t === 0 ? VIZ.axis : VIZ.grid, 'stroke-width': 1,
      }));
      svg.appendChild(el('text', {
        x, y: height - 10, 'text-anchor': 'middle', class: 'viz-tick',
      }, t));
    });
  });

  bands.forEach((b, i) => {
    const y = padTop + i * rowH;
    const by = y + (rowH - barH) / 2;
    svg.appendChild(el('text', {
      x: cx, y: y + rowH / 2 + 4, 'text-anchor': 'middle', class: 'viz-label',
    }, b.band));

    if (b.male > 0) {
      const w = (b.male / topTick) * half;
      const x = cx - gutter / 2 - w;
      // 左側長條的資料端在左，圓角也要在左，所以用鏡射版路徑
      const bar = el('path', {
        d: mirrorBar(cx - gutter / 2, w, by, barH), fill: VIZ.s1, class: 'viz-mark',
      });
      hoverable(bar, b.band + ' 歲', [{ swatch: VIZ.s1, value: b.male + ' 例', name: '男性' }]);
      svg.appendChild(bar);
      svg.appendChild(el('text', {
        x: x - 8, y: by + barH / 2 + 4, 'text-anchor': 'end', class: 'viz-value',
      }, b.male));
    }
    if (b.female > 0) {
      const w = (b.female / topTick) * half;
      const x = cx + gutter / 2;
      const bar = el('path', { d: barPath(x, by, w, barH, 'right'), fill: VIZ.s2, class: 'viz-mark' });
      hoverable(bar, b.band + ' 歲', [{ swatch: VIZ.s2, value: b.female + ' 例', name: '女性' }]);
      svg.appendChild(bar);
      svg.appendChild(el('text', {
        x: x + w + 8, y: by + barH / 2 + 4, class: 'viz-value',
      }, b.female));
    }
  });

  host.appendChild(svg);
  host.appendChild(legend([
    { color: VIZ.s1, name: '男性' }, { color: VIZ.s2, name: '女性' },
  ]));
}

/** 左側長條：資料端在左，圓角也在左。 */
function mirrorBar(baseX, w, y, h) {
  const r = Math.max(0, Math.min(4, w, h / 2));
  const x = baseX - w;
  if (r < 0.5) return `M${x},${y}h${w}v${h}h${-w}z`;
  return `M${baseX},${y} H${x + r} A${r},${r} 0 0 0 ${x},${y + r}`
       + ` V${y + h - r} A${r},${r} 0 0 0 ${x + r},${y + h} H${baseX} Z`;
}

/* ------------------------------------------------------------------ */
/* 堆疊長條 —— 藥敏 S / I / R                                          */
/* ------------------------------------------------------------------ */
/* ------------------------------------------------------------------ */
/* 堆疊長條 —— 每一列的組成比例（抹片價數分布）                        */
/* ------------------------------------------------------------------ */

/** rows: [{key, total, <段名>: n}]，segs: [{key, color, name}]。
 *  比的是「同一列裡各段的占比」，所以每列都拉到等長，尾端標 n。 */
function stackedBars(host, rows, segs, opts) {
  opts = opts || {};
  host.textContent = '';
  if (!rows.length || !segs.length) return empty(host, opts.emptyText);

  const W = hostWidth(host);
  const labelW = Math.min(opts.labelWidth || 170, Math.round(W * 0.36));
  const rowH = 30, barH = 18, padTop = 8, padBottom = 10, tailW = 66;
  const plotW = W - labelW - tailW - 12;
  const height = padTop + rows.length * rowH + padBottom;
  const svg = makeSvg(W, height, opts.title || '堆疊長條圖');

  rows.forEach((r, i) => {
    const y = padTop + i * rowH, by = y + (rowH - barH) / 2;
    const labelNode = el('text', {
      x: labelW - 10, y: y + rowH / 2 + 4, 'text-anchor': 'end', class: 'viz-label',
    }, fitLabel(r.key, labelW - 14));
    labelNode.appendChild(el('title', {}, r.key));
    svg.appendChild(labelNode);

    const total = r.total || segs.reduce((sum, sg) => sum + (r[sg.key] || 0), 0);
    let x = labelW;
    const drawn = segs.filter((sg) => (r[sg.key] || 0) > 0);
    drawn.forEach((sg, si) => {
      const raw = total ? (r[sg.key] / total) * plotW : 0;
      const gap = si < drawn.length - 1 ? 2 : 0;    // 2px 底色間隙分隔相鄰色塊
      const w = Math.max(raw - gap, 1);
      const d = si === drawn.length - 1
        ? barPath(x, by, w, barH, 'right')
        : `M${x},${by}h${w}v${barH}h${-w}z`;
      const seg = el('path', { d, fill: sg.color, class: 'viz-mark' });
      hoverable(seg, r.key, drawn.map((s2) => ({
        swatch: s2.color, name: s2.name,
        value: (r[s2.key] || 0) + ' 例（' + Math.round((r[s2.key] / total) * 100) + '%）',
      })));
      svg.appendChild(seg);
      if (w > 26) {          // 塞不下就不放段內標籤，絕不裁字
        svg.appendChild(el('text', {
          x: x + w / 2, y: by + barH / 2 + 4, 'text-anchor': 'middle',
          class: 'viz-seg-label', fill: readableInk(sg.color),
        }, sg.name));
      }
      x += raw;
    });
    svg.appendChild(el('text', {
      x: labelW + plotW + 10, y: y + rowH / 2 + 4, class: 'viz-value',
    }, 'n=' + total));
  });

  host.appendChild(svg);
  host.appendChild(legend(segs.map((sg) => ({ color: sg.color, name: sg.name }))));
}

/** 色塊上的字要看得見：亮底用深字，暗底用白字。 */
function readableInk(hex) {
  const n = parseInt(hex.slice(1), 16);
  const lum = (0.299 * ((n >> 16) & 255) + 0.587 * ((n >> 8) & 255)
               + 0.114 * (n & 255)) / 255;
  return lum > 0.6 ? '#1c2333' : '#ffffff';
}

function stackedSIR(host, rows) {
  host.textContent = '';
  if (!rows.length) return empty(host, '尚未登錄藥敏結果');

  const W = hostWidth(host);
  const labelW = Math.min(150, Math.round(W * 0.32));
  const rowH = 30, barH = 18, padTop = 8, padBottom = 10, tailW = 66;
  const plotW = W - labelW - tailW - 12;
  const height = padTop + rows.length * rowH + padBottom;
  const svg = makeSvg(W, height, '藥物敏感性分布');
  const segs = [
    { key: 'S', color: VIZ.good, name: 'S 敏感' },
    { key: 'I', color: VIZ.warn, name: 'I 中間' },
    { key: 'R', color: VIZ.bad, name: 'R 抗藥' },
  ];

  rows.forEach((r, i) => {
    const y = padTop + i * rowH, by = y + (rowH - barH) / 2;
    const labelNode = el('text', {
      x: labelW - 10, y: y + rowH / 2 + 4, 'text-anchor': 'end', class: 'viz-label',
    }, fitLabel(r.key, labelW - 14));
    labelNode.appendChild(el('title', {}, r.key));   // 截短了還是查得到全名
    svg.appendChild(labelNode);

    let x = labelW;
    const drawn = segs.filter((s) => r[s.key] > 0);
    drawn.forEach((s, si) => {
      const raw = (r[s.key] / r.tested) * plotW;
      const gap = si < drawn.length - 1 ? 2 : 0;   // 2px 底色間隙分隔相鄰色塊
      const w = Math.max(raw - gap, 1);
      const isFirst = si === 0, isLast = si === drawn.length - 1;
      const d = isLast ? barPath(x, by, w, barH, 'right')
        : isFirst ? `M${x},${by}h${w}v${barH}h${-w}z` : `M${x},${by}h${w}v${barH}h${-w}z`;
      const seg = el('path', { d, fill: s.color, class: 'viz-mark' });
      const pct = Math.round((r[s.key] / r.tested) * 100);
      hoverable(seg, r.key, [{ swatch: s.color, value: `${r[s.key]} 例（${pct}%）`, name: s.name }]);
      svg.appendChild(seg);
      // 只有塞得下才放段內標籤，絕不裁字
      if (w > 26) {
        svg.appendChild(el('text', {
          x: x + w / 2, y: by + barH / 2 + 4, 'text-anchor': 'middle',
          class: 'viz-seg-label', fill: s.key === 'I' ? '#3d2c00' : '#ffffff',
        }, s.key));
      }
      x += raw;
    });
    svg.appendChild(el('text', {
      x: labelW + plotW + 10, y: y + rowH / 2 + 4, class: 'viz-value',
    }, `n=${r.tested}`));
  });

  host.appendChild(svg);
  host.appendChild(legend(segs.map((s) => ({ color: s.color, name: s.name }))));
}

/* ------------------------------------------------------------------ */
/* 共用小元件                                                          */
/* ------------------------------------------------------------------ */
function legend(items) {
  const box = document.createElement('div');
  box.className = 'viz-legend';
  items.forEach((it) => {
    const chip = document.createElement('span');
    chip.className = 'viz-legend-item';
    const sw = document.createElement('span');
    sw.className = 'viz-swatch';
    sw.style.background = it.color;
    const tx = document.createElement('span');
    tx.textContent = it.name;
    chip.append(sw, tx);
    box.appendChild(chip);
  });
  return box;
}

function empty(host, msg) {
  const p = document.createElement('p');
  p.className = 'viz-empty';
  p.textContent = msg || '尚無資料';
  host.appendChild(p);
  return p;
}

/** 每張圖都有等價的表格版本，數值不會只存在於圖上。 */
function table(host, cols, rows) {
  host.textContent = '';
  if (!rows.length) return empty(host);
  const t = document.createElement('table');
  t.className = 'viz-table';
  const thead = document.createElement('thead');
  const htr = document.createElement('tr');
  cols.forEach((c) => {
    const th = document.createElement('th');
    th.textContent = c.label;
    if (c.numeric) th.className = 'num';
    htr.appendChild(th);
  });
  thead.appendChild(htr);
  const tbody = document.createElement('tbody');
  rows.forEach((r) => {
    const tr = document.createElement('tr');
    cols.forEach((c) => {
      const td = document.createElement('td');
      td.textContent = r[c.key] == null ? '' : r[c.key];
      if (c.numeric) td.className = 'num';
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  t.append(thead, tbody);
  host.appendChild(t);
}
