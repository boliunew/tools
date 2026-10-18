/* 📍 附近车站：右下角一个按钮，点开定位，列出最近的 Amtrak / Metrolink / BART / Muni / VTA / Caltrain 车站，
   显示距离、下一班车（Amtrak 按时刻表，BART 实时），一键用谷歌地图导航（步行 / 公交 / 开车）。
   数据：stations/near.json（scripts/build_stations.py 每周生成）。用法：<script src="nearby.js?v=1" defer></script>；也可以 window.Nearby.open()。ES5，自带样式。 */
(function () {
  'use strict';
  if (window.Nearby) return;
  var KIND = {
    amtrak: ['🚆', 'Amtrak', '#1B5E96'], metrolink: ['🚈', 'Metrolink', '#00728F'], bart: ['🚇', 'BART', '#0099D8'],
    muni: ['🚋', 'Muni 轻轨', '#C0362C'], vta: ['🚋', 'VTA 轻轨', '#0072CE'], caltrain: ['🚆', 'Caltrain', '#E31837']
  };
  var FILT = [['all', '全部'], ['amtrak', '🚆 Amtrak'], ['metrolink', '🚈 Metrolink'], ['bart', '🚇 BART'], ['rail', '🚋 轻轨'], ['caltrain', '🚆 Caltrain']];
  var HOME = { lat: 34.0975, lon: -117.6484, name: 'Upland（家）' };
  var BKEY = 'MW9S-E7SL-26DU-VV8V';
  var D = null, POS = null, F = get('f') || 'all', BUSY = false, OPEN = {};
  function get(k) { try { return JSON.parse(localStorage.getItem('near:' + k) || 'null'); } catch (e) { return null; } }
  function put(k, v) { try { localStorage.setItem('near:' + k, JSON.stringify(v)); } catch (e) { } }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function $(id) { return document.getElementById(id); }

  var css = '' +
    '.nb-btn{position:fixed;right:14px;bottom:calc(18px + env(safe-area-inset-bottom));z-index:40;border:0;border-radius:999px;padding:10px 15px 10px 12px;background:#1B5E96;color:#fff;font:600 14px/1 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;box-shadow:0 4px 16px rgba(0,0,0,.28);display:flex;align-items:center;gap:6px;cursor:pointer}' +
    '.nb-btn b{font-size:17px}' +
    '.nb-bg{position:fixed;inset:0;z-index:60;background:rgba(0,0,0,.4);opacity:0;pointer-events:none;transition:opacity .2s}' +
    '.nb-bg.on{opacity:1;pointer-events:auto}' +
    '.nb-sh{position:fixed;left:0;right:0;bottom:0;z-index:61;max-height:86vh;overflow-y:auto;-webkit-overflow-scrolling:touch;background:#F6F6F3;color:#1C2128;border-radius:20px 20px 0 0;box-shadow:0 -8px 40px rgba(0,0,0,.3);transform:translateY(105%);transition:transform .25s cubic-bezier(.2,.8,.2,1);font:15px/1.55 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;padding:0 14px calc(18px + env(safe-area-inset-bottom))}' +
    '.nb-sh.on{transform:none}' +
    '.nb-in{max-width:680px;margin:0 auto}' +
    '.nb-hd{position:sticky;top:0;background:#F6F6F3;padding:10px 0 6px;z-index:1}' +
    '.nb-grab{width:40px;height:5px;border-radius:3px;background:#CCC;margin:0 auto 8px}' +
    '.nb-t{display:flex;align-items:center;gap:8px}.nb-t b{font-size:18px;flex:1}' +
    '.nb-t button{border:1px solid #DDD;background:#fff;border-radius:999px;padding:4px 11px;font-size:13px;color:#444;cursor:pointer}' +
    '.nb-st{font-size:12.5px;color:#777;margin:4px 0 6px}' +
    '.nb-f{display:flex;gap:6px;overflow-x:auto;scrollbar-width:none;padding-bottom:2px}.nb-f::-webkit-scrollbar{display:none}' +
    '.nb-f button{flex:0 0 auto;border:1px solid #DDD;background:#fff;border-radius:999px;padding:4px 11px;font-size:13px;color:#555;cursor:pointer}' +
    '.nb-f button.on{background:#1B5E96;border-color:#1B5E96;color:#fff;font-weight:600}' +
    '.nb-c{background:#fff;border:1px solid #E3E3DE;border-radius:14px;margin-top:8px;overflow:hidden}' +
    '.nb-r{display:flex;gap:10px;padding:10px 12px;align-items:flex-start;cursor:pointer}' +
    '.nb-i{flex:0 0 34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;color:#fff}' +
    '.nb-m{flex:1;min-width:0}.nb-m b{font-size:15.5px}.nb-m small{display:block;color:#777;font-size:12.5px;line-height:1.45}' +
    '.nb-d{text-align:right;font-size:13px;color:#333;white-space:nowrap}.nb-d b{display:block;font-size:16px}.nb-d small{color:#888;font-size:11.5px}' +
    '.nb-x{padding:0 12px 12px 56px;display:none}.nb-c.open .nb-x{display:block}' +
    '.nb-go{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}' +
    '.nb-go a{flex:1 1 0;min-width:80px;text-align:center;text-decoration:none;border-radius:10px;padding:8px 4px;font-size:13.5px;font-weight:600;background:#1B5E96;color:#fff}' +
    '.nb-go a.s{background:#EEF2F6;color:#1B5E96}' +
    '.nb-nx{font-size:13px;line-height:1.7;color:#333}.nb-nx b{font-variant-numeric:tabular-nums}.nb-nx small{color:#888}' +
    '.nb-l{font-size:12px;color:#666;margin-bottom:6px}' +
    '.nb-e{color:#888;text-align:center;padding:24px 0;font-size:14px}' +
    '.nb-e button{margin-top:10px;border:0;border-radius:999px;padding:8px 16px;background:#1B5E96;color:#fff;font-size:14px;cursor:pointer}' +
    '@media (prefers-color-scheme: dark){:root:not([data-theme="light"]) .nb-sh,:root:not([data-theme="light"]) .nb-hd{background:#171B21;color:#E6E9ED}:root:not([data-theme="light"]) .nb-c,:root:not([data-theme="light"]) .nb-f button,:root:not([data-theme="light"]) .nb-t button{background:#20262E;border-color:#2E353F;color:#D5DAE0}:root:not([data-theme="light"]) .nb-d,:root:not([data-theme="light"]) .nb-nx{color:#D5DAE0}:root:not([data-theme="light"]) .nb-go a.s{background:#22303F;color:#9CC6EE}}' +
    ':root[data-theme="dark"] .nb-sh,:root[data-theme="dark"] .nb-hd{background:#171B21;color:#E6E9ED}:root[data-theme="dark"] .nb-c,:root[data-theme="dark"] .nb-f button,:root[data-theme="dark"] .nb-t button{background:#20262E;border-color:#2E353F;color:#D5DAE0}:root[data-theme="dark"] .nb-d,:root[data-theme="dark"] .nb-nx{color:#D5DAE0}';

  function dist(a, b, c, d) {   // 英里
    var R = 3958.8, toR = Math.PI / 180, dl = (c - a) * toR, dn = (d - b) * toR;
    var x = Math.sin(dl / 2) * Math.sin(dl / 2) + Math.cos(a * toR) * Math.cos(c * toR) * Math.sin(dn / 2) * Math.sin(dn / 2);
    return 2 * R * Math.asin(Math.sqrt(x));
  }
  function gm(s, mode) { return 'https://www.google.com/maps/dir/?api=1&destination=' + s.ll[0] + '%2C' + s.ll[1] + '&travelmode=' + mode; }
  function ago(t) { var m = Math.round((Date.now() - t) / 60000); return m < 1 ? '刚刚' : m < 60 ? m + ' 分钟前' : Math.round(m / 60) + ' 小时前'; }
  function laNow() {
    var p = {}; try { new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', weekday: 'short', hour: 'numeric', minute: 'numeric', hourCycle: 'h23' }).formatToParts(new Date()).forEach(function (x) { p[x.type] = x.value; }); } catch (e) { }
    return { wd: (['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].indexOf(p.weekday) + 7) % 7, m: (+p.hour || 0) * 60 + (+p.minute || 0) };
  }
  function nextDeps(s) {   // Amtrak：今天（和明天）接下来的班次
    var n = laNow(), out = [];
    for (var day = 0; day < 3 && out.length < 4; day++) {
      var wd = (n.wd + day) % 7;
      s.dep.forEach(function (x) {
        if (x[4].charAt(wd) !== '1') return;
        var t = x[0].split(':'), m = +t[0] * 60 + +t[1];
        if (day === 0 && m < n.m) return;
        out.push([day, m, x]);
      });
    }
    out.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
    return out.slice(0, 4);
  }

  function build() {
    var st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
    var b = document.createElement('button'); b.className = 'nb-btn'; b.innerHTML = '<b>📍</b>附近车站'; b.onclick = open; document.body.appendChild(b);
    var bg = document.createElement('div'); bg.className = 'nb-bg'; bg.id = 'nbBg'; bg.onclick = close; document.body.appendChild(bg);
    var sh = document.createElement('div'); sh.className = 'nb-sh'; sh.id = 'nbSh';
    sh.innerHTML = '<div class="nb-in"><div class="nb-hd"><div class="nb-grab"></div><div class="nb-t"><b>📍 我附近的车站</b><button id="nbRe">🔄 重新定位</button><button id="nbX">✕</button></div><div class="nb-st" id="nbSt"></div><div class="nb-f" id="nbF"></div></div><div id="nbL"></div>' +
      '<div class="nb-st" style="margin-top:10px">距离是直线距离，步行时间按每小时 3 英里、绕路多算两成估的。点「步行 / 公交 / 开车」直接打开谷歌地图导航。Amtrak 的下一班按官方时刻表，BART 是实时到站；临时改点以官方 App 为准。位置只在这台手机上用，不会上传。</div></div>';
    document.body.appendChild(sh);
    $('nbX').onclick = close;
    $('nbRe').onclick = function () { locate(true); };
    $('nbF').onclick = function (e) { var x = e.target.closest('[data-f]'); if (!x) return; F = x.getAttribute('data-f'); put('f', F); draw(); };
    $('nbL').onclick = function (e) {
      var a = e.target.closest('[data-home]'); if (a) { POS = { lat: HOME.lat, lon: HOME.lon, t: Date.now(), home: 1 }; put('pos', POS); draw(); return; }
      a = e.target.closest('[data-retry]'); if (a) { locate(true); return; }
      a = e.target.closest('[data-bart]'); if (a) { bart(a.getAttribute('data-bart'), a.parentNode); return; }
      var r = e.target.closest('.nb-r'); if (r) { var c = r.parentNode, id = c.getAttribute('data-id'); OPEN[id] = !c.classList.contains('open'); c.classList.toggle('open', OPEN[id]); }
    };
    var y0 = null;   // 往下拖关闭
    sh.addEventListener('touchstart', function (e) { y0 = sh.scrollTop <= 0 ? e.touches[0].clientY : null; }, { passive: true });
    sh.addEventListener('touchmove', function (e) { if (y0 != null && e.touches[0].clientY - y0 > 90) { y0 = null; close(); } }, { passive: true });
  }
  function open() {
    $('nbBg').classList.add('on'); $('nbSh').classList.add('on');
    POS = POS || get('pos');
    if (!D) load(); else draw();
    if (!POS || POS.home || Date.now() - POS.t > 5 * 60000) locate(false);
  }
  function close() { $('nbBg').classList.remove('on'); $('nbSh').classList.remove('on'); }
  function load() {
    var x = new XMLHttpRequest(); x.open('GET', 'stations/near.json?t=' + Math.floor(Date.now() / 864e5));
    x.onload = function () { try { D = JSON.parse(x.responseText); } catch (e) { } draw(); };
    x.onerror = function () { $('nbL').innerHTML = '<div class="nb-e">车站数据加载失败，检查网络后再试。</div>'; };
    x.send();
  }
  function locate(force) {
    if (BUSY) return;
    if (!navigator.geolocation) { status('这个浏览器不支持定位。'); return; }
    BUSY = true; status('📡 正在定位…');
    navigator.geolocation.getCurrentPosition(function (p) {
      BUSY = false; POS = { lat: p.coords.latitude, lon: p.coords.longitude, acc: p.coords.accuracy, t: Date.now() }; put('pos', POS); draw();
    }, function (err) {
      BUSY = false;
      if (POS) { draw(); status((err && err.code === 1 ? '没有定位权限' : '这次没定位成功') + '，先用' + (POS.home ? 'Upland 家的位置' : '上次的位置（' + ago(POS.t) + '）') + '。'); return; }
      $('nbL').innerHTML = '<div class="nb-e">' + (err && err.code === 1 ? '浏览器没有允许定位。<br>在浏览器的网站设置里允许「位置」，再点「重新定位」。' : '暂时没定位成功（室内信号差时常见）。') +
        '<br><button data-retry="1">再试一次</button> <button data-home="1">先用 Upland 家的位置</button></div>';
      status('');
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: force ? 0 : 60000 });
  }
  function status(t) { var s = $('nbSt'); if (s) s.innerHTML = t; }
  function draw() {
    $('nbF').innerHTML = FILT.map(function (x) { return '<button data-f="' + x[0] + '" class="' + (x[0] === F ? 'on' : '') + '">' + x[1] + '</button>'; }).join('');
    if (!D) { $('nbL').innerHTML = '<div class="nb-e">加载车站…</div>'; return; }
    if (!POS) { if (!BUSY) $('nbL').innerHTML = '<div class="nb-e">点「重新定位」找附近的车站。<br><button data-retry="1">📍 定位</button> <button data-home="1">用 Upland 家的位置</button></div>'; return; }
    if (!BUSY) status(POS.home ? '🏠 用的是 Upland 家的位置。点「重新定位」用你现在的位置。' : '📍 你的位置（' + ago(POS.t) + (POS.acc ? '，精度约 ' + Math.round(POS.acc) + ' 米' : '') + '）');
    var L = D.st.filter(function (s) { return F === 'all' || s.k === F || (F === 'rail' && (s.k === 'muni' || s.k === 'vta')); })
      .map(function (s) { return [dist(POS.lat, POS.lon, s.ll[0], s.ll[1]), s]; })
      .sort(function (a, b) { return a[0] - b[0]; });
    // 同一个地方的同类车站（比如两个方向的站台）只留一个
    var seen = {}, out = [];
    for (var i = 0; i < L.length && out.length < 10; i++) { var k = L[i][1].k + '|' + L[i][1].ll[0].toFixed(3) + L[i][1].ll[1].toFixed(3); if (!seen[k]) { seen[k] = 1; out.push(L[i]); } }
    if (!out.length) { $('nbL').innerHTML = '<div class="nb-e">没有这类车站。</div>'; return; }
    var far = out[0][0] > 60;
    $('nbL').innerHTML = (far ? '<div class="nb-e" style="padding:10px 0">离最近的车站也有 ' + Math.round(out[0][0]) + ' 英里，这里的车站数据只覆盖加州和 Amtrak 沿线。</div>' : '') + out.map(function (x) {
      var d = x[0], s = x[1], K = KIND[s.k] || ['🚉', s.k, '#555'], id = s.k + ':' + s.id;
      var walk = Math.round(d * 1.2 / 3 * 60), dtx = d < 0.1 ? Math.round(d * 5280) + ' 英尺' : d.toFixed(d < 10 ? 1 : 0) + ' 英里';
      var sub = (s.zh ? esc(s.n) + ' · ' : '') + K[1] + (s.l && s.l.length ? ' · ' + esc(s.l.slice(0, 3).join('、')) : '');
      var modes = d < 2 ? [['walking', '🚶 步行'], ['transit', '🚌 公交'], ['driving', '🚗 开车']] : [['driving', '🚗 开车'], ['transit', '🚌 公交'], ['walking', '🚶 步行']];
      var x2 = '<div class="nb-x"><div class="nb-go">' + modes.map(function (m, j) { return '<a href="' + gm(s, m[0]) + '" target="_blank" rel="noopener"' + (j ? ' class="s"' : '') + '>' + m[1] + '</a>'; }).join('') + '</div>';
      if (s.l && s.l.length > 3) x2 += '<div class="nb-l">经过：' + esc(s.l.join('、')) + '</div>';
      if (s.k === 'amtrak' && s.dep) {
        var nx = nextDeps(s);
        x2 += '<div class="nb-nx">' + (nx.length ? '接下来的车：<br>' + nx.map(function (y) { return '<b>' + (y[0] === 1 ? '明天 ' : y[0] === 2 ? '后天 ' : '') + y[2][0] + '</b> ' + esc(y[2][2]) + ' ' + esc(y[2][1]) + ' 次 → ' + esc(y[2][3]); }).join('<br>') : '这几天没有车（这里可能只停大巴）。') + '<br><small>按官方时刻表；查任意两站在 <a href="amtrak.html#time">Amtrak 页「查时刻」</a></small></div>';
      } else if (s.k === 'bart') {
        x2 += '<div class="nb-nx"><a href="javascript:void 0" data-bart="' + esc(s.id) + '">⏱️ 看实时到站</a></div>';
      } else if (s.k === 'metrolink') {
        x2 += '<div class="nb-nx"><a href="https://metrolinktrains.com/schedules/" target="_blank" rel="noopener">Metrolink 时刻表</a> · 也可以点「公交」让谷歌地图排班次<br><small>周末班次少，出门前查一下。</small></div>';
      } else {
        x2 += '<div class="nb-nx"><small>下一班车点「🚌 公交」在谷歌地图里看。</small></div>';
      }
      x2 += '</div>';
      return '<div class="nb-c' + (OPEN[id] ? ' open' : '') + '" data-id="' + esc(id) + '"><div class="nb-r"><div class="nb-i" style="background:' + K[2] + '">' + K[0] + '</div><div class="nb-m"><b>' + esc(s.zh || s.n) + '</b><small>' + sub + '</small></div><div class="nb-d"><b>' + dtx + '</b><small>' + (d < 2 ? '步行约 ' + walk + ' 分' : '开车 / 公交') + '</small></div></div>' + x2 + '</div>';
    }).join('');
    if (!Object.keys(OPEN).length) { var f = $('nbL').querySelector('.nb-c'); if (f) f.classList.add('open'); }
  }
  function bart(abbr, box) {
    box.innerHTML = '加载实时到站…';
    var x = new XMLHttpRequest(); x.open('GET', 'https://api.bart.gov/api/etd.aspx?cmd=etd&orig=' + encodeURIComponent(abbr) + '&key=' + BKEY + '&json=y'); x.timeout = 12000;
    x.onload = function () {
      try {
        var st = JSON.parse(x.responseText).root.station[0], rows = [];
        (st.etd || []).forEach(function (d) { (d.estimate || []).slice(0, 2).forEach(function (e) { rows.push([e.minutes === 'Leaving' ? 0 : +e.minutes, d.destination, e.hexcolor, e.direction]); }); });
        rows.sort(function (a, b) { return a[0] - b[0]; });
        box.innerHTML = rows.length ? '⏱️ 实时到站：<br>' + rows.slice(0, 6).map(function (r) { return '<span style="display:inline-block;width:9px;height:9px;border-radius:5px;background:' + r[2] + ';margin-right:5px"></span><b>' + (r[0] ? r[0] + ' 分' : '进站中') + '</b> → ' + esc(r[1]) + ' <small>' + (r[3] === 'North' ? '北行' : '南行') + '</small>'; }).join('<br>') : '现在没有车（可能已收班）。';
      } catch (e) { box.textContent = '实时数据格式不对，稍后再试。'; }
    };
    x.onerror = x.ontimeout = function () { box.textContent = '连不上 BART，稍后再试。'; };
    x.send();
  }
  window.Nearby = { open: function () { if (!$('nbSh')) build(); open(); } };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build); else build();
})();
