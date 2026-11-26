/* 司机签到指引 —— 查看页和设置页共用的东西：读配置、三语文字、自动翻译、画场地图 */
var CI = (function () {
  var LANGS = ['en', 'zh', 'es'];

  /* ---------- 文字 ---------- */
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function T(o) { // 旧格式（纯字符串）也认
    if (o == null) return { en: '', zh: '', es: '' };
    if (typeof o === 'string') return { en: o, zh: '', es: '' };
    return { en: o.en || '', zh: o.zh || '', es: o.es || '' };
  }
  function title(company) {
    var c = company || 'Company';
    return { en: c + ' Driver Check-in Guide', zh: c + ' 司机签到指引', es: 'Guía de registro para choferes · ' + c };
  }

  /* ---------- 自动翻译（英文 → 中文 / 西语），先谷歌，不行再 MyMemory ---------- */
  var TL = { zh: 'zh-CN', es: 'es' };
  function cacheGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function cacheSet(k, v) { try { localStorage.setItem(k, v); } catch (e) { } }
  async function translate(text, to) {
    text = (text || '').trim();
    if (!text) return '';
    var key = 'ci:tr:' + to + ':' + text;
    var hit = cacheGet(key); if (hit) return hit;
    var out = '';
    try {
      var r = await fetch('https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=' + TL[to] + '&dt=t&q=' + encodeURIComponent(text));
      var j = await r.json();
      out = (j[0] || []).map(function (x) { return x[0]; }).join('');
    } catch (e) { }
    if (!out) {
      try {
        var r2 = await fetch('https://api.mymemory.translated.net/get?q=' + encodeURIComponent(text) + '&langpair=en|' + TL[to]);
        var j2 = await r2.json();
        out = (j2.responseData && j2.responseData.translatedText) || '';
      } catch (e) { }
    }
    if (out) cacheSet(key, out);
    return out;
  }

  /* ---------- 配置读取：#c=链接 > 预览草稿 > ?site= > 默认 ---------- */
  function b64u(bytes) { var s = ''; for (var i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]); return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, ''); }
  function unb64u(s) { s = s.replace(/-/g, '+').replace(/_/g, '/'); while (s.length % 4) s += '='; var b = atob(s), a = new Uint8Array(b.length); for (var i = 0; i < b.length; i++) a[i] = b.charCodeAt(i); return a; }
  async function pack(cfg) {
    var raw = new TextEncoder().encode(JSON.stringify(cfg));
    if (window.CompressionStream) {
      var gz = new Uint8Array(await new Response(new Blob([raw]).stream().pipeThrough(new CompressionStream('gzip'))).arrayBuffer());
      return 'z' + b64u(gz);
    }
    return 'j' + b64u(raw);
  }
  async function unpack(s) {
    var bytes = unb64u(s.slice(1));
    if (s[0] === 'z') bytes = new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer());
    return JSON.parse(new TextDecoder().decode(bytes));
  }
  async function load() {
    var q = new URLSearchParams(location.search);
    var h = new URLSearchParams(location.hash.slice(1));
    if (h.get('c')) return unpack(h.get('c'));
    if (q.get('preview')) { var d = cacheGet('ci:draft'); if (d) return JSON.parse(d); }
    var id = q.get('site');
    if (!id) {
      var idx = await fetch('sites/index.json', { cache: 'no-cache' }).then(function (r) { return r.json(); });
      id = idx.default || (idx.sites[0] && idx.sites[0].id);
    }
    var r = await fetch('sites/' + encodeURIComponent(id) + '.json', { cache: 'no-cache' });
    if (!r.ok) throw new Error('Site "' + id + '" not found');
    return r.json();
  }

  /* ---------- 场地图（SVG） ---------- */
  var KIND = { checkin: null, door: '#ffce40', entry: '#22c55e', exit: '#a855f7', info: '#3b82f6', stop: '#ef4444' };
  var KIND_ICON = { checkin: '📝', door: '🚪', entry: '➡️', exit: '⬅️', info: 'ℹ️', stop: '🛑' };
  function pinColor(it, cfg) { return it.color || KIND[it.kind] || cfg.color || '#e1251b'; }
  function routeD(pts) { return pts.length ? 'M' + pts.map(function (p) { return p[0] + ' ' + p[1]; }).join(' L') : ''; }
  function mapSVG(cfg, opt) {
    opt = opt || {};
    var m = cfg.map || { w: 400, h: 600, items: [], route: [] };
    var W = m.w || 400, H = m.h || 600, out = [];
    out.push('<svg class="ci-map" viewBox="0 0 ' + W + ' ' + H + '" xmlns="http://www.w3.org/2000/svg">');
    out.push('<rect width="' + W + '" height="' + H + '" fill="#22332f"/>');
    var order = { area: 0, road: 1, bldg: 2, pin: 4 };
    var items = (m.items || []).map(function (it, i) { return [it, i]; }).sort(function (a, b) { return (order[a[0].t] || 0) - (order[b[0].t] || 0); });
    items.forEach(function (p) {
      var it = p[0], i = p[1], sel = opt.sel === i ? ' data-sel="1"' : '';
      var g = '<g data-i="' + i + '"' + sel + ' class="ci-it ci-' + it.t + '">';
      if (it.t === 'road' || it.t === 'area' || it.t === 'bldg') {
        var fill = it.t === 'road' ? '#4a5466' : it.t === 'area' ? '#3a4352' : (it.color || '#d9dde3');
        g += '<rect x="' + it.x + '" y="' + it.y + '" width="' + it.w + '" height="' + it.h + '" fill="' + fill + '" rx="' + (it.t === 'bldg' ? 2 : 0) + '"/>';
        if (it.t === 'road' && it.main) {
          var v = it.h > it.w;
          g += v ? '<line x1="' + (it.x + it.w / 2) + '" y1="' + it.y + '" x2="' + (it.x + it.w / 2) + '" y2="' + (it.y + it.h) + '" stroke="#ffce40" stroke-width="1.6" stroke-dasharray="8 7"/>'
            : '<line x1="' + it.x + '" y1="' + (it.y + it.h / 2) + '" x2="' + (it.x + it.w) + '" y2="' + (it.y + it.h / 2) + '" stroke="#ffce40" stroke-width="1.6" stroke-dasharray="8 7"/>';
        }
        if (it.label) {
          var cx = it.x + it.w / 2, cy = it.y + it.h / 2, vert = it.h > it.w * 1.6 && it.t !== 'bldg';
          var col = it.t === 'bldg' ? (it.color ? '#fff' : '#3b4454') : '#fff';
          var fs = it.t === 'bldg' ? Math.max(9, Math.min(15, it.w / 8)) : 11;
          var lines = String(it.label).split('\n');
          g += '<text x="' + cx + '" y="' + cy + '" fill="' + col + '" font-size="' + fs + '" font-weight="700" text-anchor="middle" dominant-baseline="middle"' + (it.t === 'road' ? ' stroke="#4a5466" stroke-width="4" paint-order="stroke"' : '') +
            (vert ? ' transform="rotate(-90 ' + cx + ' ' + cy + ')"' : '') + '>' +
            lines.map(function (l, k) { return '<tspan x="' + cx + '" dy="' + (k === 0 ? -(lines.length - 1) * fs * 0.6 : fs * 1.2) + '">' + esc(l) + '</tspan>'; }).join('') + '</text>';
        }
      } else if (it.t === 'pin') {
        var c = pinColor(it, cfg);
        g += '<circle class="ci-pulse" cx="' + it.x + '" cy="' + it.y + '" r="11" fill="none" stroke="' + c + '" stroke-width="2"/>';
        g += '<circle cx="' + it.x + '" cy="' + it.y + '" r="8" fill="' + c + '" stroke="#fff" stroke-width="2"/>';
        if (it.label) {
          var lw = Math.max(40, String(it.label).length * 6.6 + 26), lx = Math.min(Math.max(it.x - lw / 2, 2), W - lw - 2);
          var ly = it.below ? it.y + 14 : it.y - 36;
          g += '<rect x="' + lx + '" y="' + ly + '" width="' + lw + '" height="22" rx="6" fill="#0b0f16" fill-opacity=".88" stroke="' + c + '"/>';
          g += '<text x="' + (lx + lw / 2) + '" y="' + (ly + 11.5) + '" fill="#fff" font-size="11" font-weight="700" text-anchor="middle" dominant-baseline="middle">' + (KIND_ICON[it.kind] || '📍') + ' ' + esc(it.label) + '</text>';
        }
      }
      out.push(g + '</g>');
    });
    var r = m.route || [];
    if (r.length > 1) {
      var d = routeD(r);
      out.push('<path d="' + d + '" fill="none" stroke="#000" stroke-opacity=".45" stroke-width="9" stroke-linejoin="round" stroke-linecap="round"/>');
      out.push('<path class="ci-route-bg" d="' + d + '" fill="none" stroke="' + (cfg.color || '#e1251b') + '" stroke-opacity=".28" stroke-width="5" stroke-linejoin="round" stroke-dasharray="3 6"/>');
      out.push('<path class="ci-route" d="' + d + '" fill="none" stroke="' + (cfg.color || '#e1251b') + '" stroke-width="5.5" stroke-linejoin="round" stroke-linecap="round"/>');
    }
    if (opt.edit) r.forEach(function (p, k) {
      out.push('<g class="ci-rp" data-r="' + k + '"><circle cx="' + p[0] + '" cy="' + p[1] + '" r="7" fill="#fff" stroke="' + (cfg.color || '#e1251b') + '" stroke-width="2.5"/><text x="' + p[0] + '" y="' + (p[1] + .5) + '" font-size="8" font-weight="800" text-anchor="middle" dominant-baseline="middle" fill="#000">' + k + '</text></g>');
    });
    if (!opt.edit && r.length > 1) out.push('<g class="ci-truck"><rect x="-13" y="-5.5" width="18" height="11" rx="2" fill="#fff" stroke="#000" stroke-width="1.5"/><rect x="6" y="-4.5" width="8" height="9" rx="2" fill="' + (cfg.color || '#e1251b') + '" stroke="#000" stroke-width="1.5"/></g>');
    // 指北针
    out.push('<g transform="translate(' + (W - 22) + ' 24) rotate(' + (m.north || 0) + ')"><circle r="14" fill="#0b0f16" fill-opacity=".6" stroke="#fff" stroke-width="1.5"/><path d="M0 -10 L-5 4 L5 4 Z" fill="#fff"/><text y="11" font-size="7" fill="#fff" text-anchor="middle" font-weight="700">N</text></g>');
    out.push('</svg>');
    return out.join('');
  }

  /* 卡车沿路线跑；经过某个步骤的停靠点时回调，并停一会儿 */
  function animate(svg, cfg, onStep) {
    var path = svg.querySelector('.ci-route'), truck = svg.querySelector('.ci-truck');
    if (!path || !truck) return { stop: function () { } };
    var pts = (cfg.map && cfg.map.route) || [], L = path.getTotalLength();
    var cum = [0]; for (var i = 1; i < pts.length; i++) cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
    var scale = L / (cum[cum.length - 1] || 1);
    // 每个步骤停在哪个路线点
    var steps = cfg.steps || [], stops = [];
    steps.forEach(function (s, k) {
      var at = s.at != null && s.at !== '' ? Math.min(+s.at, pts.length - 1) : Math.round((k + 1) * (pts.length - 1) / steps.length);
      stops.push({ k: k, d: cum[at] * scale });
    });
    var speed = L / 7, hold = 1700, start = null, dist = 0, holding = 0, next = 0, ended = false, raf, stopped = false;
    path.style.strokeDasharray = L; path.style.strokeDashoffset = L;
    function place(d) {
      d = Math.max(0, Math.min(L, d));
      var a0 = Math.min(d, L - 1.5), p = path.getPointAtLength(a0), q = path.getPointAtLength(a0 + 1.5);
      var a = Math.atan2(q.y - p.y, q.x - p.x) * 180 / Math.PI;
      var pt = path.getPointAtLength(d);
      truck.setAttribute('transform', 'translate(' + pt.x + ' ' + pt.y + ') rotate(' + a + ')');
      path.style.strokeDashoffset = L - Math.min(d, L);
    }
    function tick(t) {
      if (stopped) return;
      if (start == null) start = t;
      var dt = Math.min(64, t - start); start = t;
      if (holding > 0) holding -= dt;
      else if (ended) { ended = false; dist = 0; next = 0; onStep && onStep(-1); }
      else if (next < stops.length && dist >= stops[next].d) { dist = stops[next].d; onStep && onStep(stops[next].k); next++; holding = hold; }
      else if (dist >= L) { dist = L; ended = true; holding = 2600; }
      else dist = Math.min(L, dist + speed * dt / 1000);
      place(dist);
      raf = requestAnimationFrame(tick);
    }
    onStep && onStep(-1);
    raf = requestAnimationFrame(tick);
    return { stop: function () { stopped = true; cancelAnimationFrame(raf); } };
  }

  function mapsLink(cfg) { return 'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(cfg.mapsQuery || cfg.address || ''); }

  return { LANGS: LANGS, esc: esc, T: T, title: title, translate: translate, load: load, pack: pack, unpack: unpack, mapSVG: mapSVG, animate: animate, mapsLink: mapsLink, KIND_ICON: KIND_ICON };
})();
