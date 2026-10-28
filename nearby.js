/* 📍 附近车站：右下角一个按钮，点开定位，列出最近的 Amtrak / Metrolink / BART / Muni / VTA / Caltrain 车站，
   显示距离、下一班车（Amtrak 按时刻表，BART 实时），一键用谷歌地图导航（步行 / 公交 / 开车）。
   数据：stations/near.json（scripts/build_stations.py 每周生成）。用法：<script src="nearby.js?v=1" defer></script>；也可以 window.Nearby.open()。ES5，自带样式。 */
(function () {
  'use strict';
  if (window.Nearby) return;
  var KIND = {
    amtrak: ['🚆', 'Amtrak', '#1B5E96'], metrolink: ['🚈', 'Metrolink', '#00728F'], bart: ['🚇', 'BART', '#0099D8'],
    muni: ['🚋', 'Muni 轻轨', '#C0362C'], vta: ['🚋', 'VTA 轻轨', '#0072CE'], caltrain: ['🚆', 'Caltrain', '#E31837'],
    nysub: ['🚇', '纽约地铁', '#0039A6'], lametro: ['🚇', 'LA Metro', '#E16710']
  };
  var FILT = [['all', '全部'], ['amtrak', 'Amtrak'], ['metrolink', 'Metrolink'], ['sub', '地铁'], ['rail', '轻轨'], ['caltrain', 'Caltrain']];
  var HOME = { lat: 34.0975, lon: -117.6484, name: 'Upland（家）' };
  var BKEY = 'MW9S-E7SL-26DU-VV8V';
  var D = null, POS = null, F = get('f') || 'all'; if (F === 'bart') F = 'sub'; var BUSY = false, OPEN = {}, DET = null, DAY = 0, DEPS = null, DMAP = null;
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
    '.nb-more{display:block;width:100%;margin-top:8px;border:1px solid #D7DEE6;background:#F3F7FB;color:#1B5E96;border-radius:10px;padding:8px;font-size:13.5px;font-weight:600;cursor:pointer;text-align:center}' +
    '.nb-back{border:0;background:none;color:#1B5E96;font-size:14.5px;padding:6px 0;cursor:pointer;font-weight:600}' +
    '.nb-dh{display:flex;gap:12px;align-items:center;margin:4px 0 8px}.nb-dh .nb-i{flex:0 0 46px;height:46px;font-size:24px;border-radius:13px}' +
    '.nb-dh b{display:block;font-size:19px;line-height:1.3}.nb-dh small{color:#777;font-size:13px}' +
    '.nb-ch{display:flex;gap:5px;flex-wrap:wrap;margin:2px 0 8px}.nb-ch span{font-size:12px;border-radius:999px;padding:1px 9px;background:#EEF2F6;color:#36506B}' +
    '.nb-map{height:210px;border-radius:14px;overflow:hidden;border:1px solid #E3E3DE;margin:6px 0 10px;background:#DDE3E8;position:relative;z-index:0}' +
    '.nb-sec{background:#fff;border:1px solid #E3E3DE;border-radius:14px;padding:10px 12px;margin-top:10px}' +
    '.nb-sec h4{margin:0 0 6px;font-size:14.5px}' +
    '.nb-tt{width:100%;border-collapse:collapse;font-size:13.5px;font-variant-numeric:tabular-nums}' +
    '.nb-tt td{padding:5px 4px;border-top:1px solid #EEE;vertical-align:top}.nb-tt tr:first-child td{border-top:0}' +
    '.nb-tt td:first-child{font-weight:700;width:52px;white-space:nowrap}' +
    '.nb-tt tr.past td{color:#AAA}.nb-tt tr.nx td{background:#FFF4D6}' +
    '.nb-tt small{color:#888}' +
    '.nb-dy{display:flex;gap:6px;margin:4px 0 6px}.nb-dy button{border:1px solid #DDD;background:#fff;border-radius:999px;padding:3px 11px;font-size:13px;cursor:pointer;color:#555}.nb-dy button.on{background:#1B5E96;border-color:#1B5E96;color:#fff}' +
    '.nb-tip{font-size:13px;line-height:1.7;color:#444}.nb-tip li{margin-bottom:3px}' +
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
    if (!window.NEARBY_NOBTN) { var b = document.createElement('button'); b.className = 'nb-btn'; b.innerHTML = '<b>📍</b>附近车站'; b.onclick = open; document.body.appendChild(b); }
    var bg = document.createElement('div'); bg.className = 'nb-bg'; bg.id = 'nbBg'; bg.onclick = close; document.body.appendChild(bg);
    var sh = document.createElement('div'); sh.className = 'nb-sh'; sh.id = 'nbSh';
    sh.innerHTML = '<div class="nb-in"><div class="nb-hd"><div class="nb-grab"></div><div class="nb-t"><b>我附近的车站</b><button id="nbRe">重新定位</button><button id="nbX">✕</button></div><div class="nb-st" id="nbSt"></div><div class="nb-f" id="nbF"></div></div><div id="nbL"></div>' +
      '<div class="nb-st" style="margin-top:10px">距离是直线距离，步行时间按每小时 3 英里、绕路多算两成估的。点「步行 / 公交 / 开车」直接打开谷歌地图导航。Amtrak 的下一班按官方时刻表，BART 是实时到站；临时改点以官方 App 为准。位置只在这台手机上用，不会上传。' + (/coast\.html$/.test(location.pathname) ? '' : '<br><a href="coast.html#near" style="color:inherit">附近的海边景点 ›</a> · <a href="amtrak.html" style="color:inherit">Amtrak 查时刻 ›</a>') + '</div></div>';
    document.body.appendChild(sh);
    $('nbX').onclick = close;
    $('nbRe').onclick = function () { locate(true); };
    $('nbF').onclick = function (e) { var x = e.target.closest('[data-f]'); if (!x) return; F = x.getAttribute('data-f'); put('f', F); draw(); };
    $('nbL').onclick = function (e) {
      var a = e.target.closest('[data-home]'); if (a) { POS = { lat: HOME.lat, lon: HOME.lon, t: Date.now(), home: 1 }; put('pos', POS); draw(); return; }
      a = e.target.closest('[data-retry]'); if (a) { locate(true); return; }
      a = e.target.closest('[data-bart]'); if (a) { bart(a.getAttribute('data-bart'), a.parentNode); return; }
      a = e.target.closest('[data-det]'); if (a) { detail(a.getAttribute('data-det')); return; }
      a = e.target.closest('[data-q]'); if (a) { try { var q = JSON.parse(localStorage.getItem('amtk:q') || 'null') || {}; q.a = a.getAttribute('data-q'); if (q.b === q.a || !q.b) q.b = q.a === 'LAX' ? 'SBA' : 'LAX'; localStorage.setItem('amtk:q', JSON.stringify(q)); localStorage.setItem('amtk:tab', '"time"'); } catch (er) { } if (/amtrak\.html/.test(location.pathname)) { close(); location.hash = 'time'; location.reload(); e.preventDefault(); } return; }
      a = e.target.closest('[data-back]'); if (a) { DET = null; draw(); $('nbSh').scrollTop = 0; return; }
      a = e.target.closest('[data-day]'); if (a) { DAY = +a.getAttribute('data-day'); detail(DET); return; }
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
    BUSY = true; status('正在定位…');
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
    if (DET) return detail(DET);
    $('nbF').innerHTML = FILT.map(function (x) { return '<button data-f="' + x[0] + '" class="' + (x[0] === F ? 'on' : '') + '">' + x[1] + '</button>'; }).join('');
    if (!D) { $('nbL').innerHTML = '<div class="nb-e">加载车站…</div>'; return; }
    if (!POS) { if (!BUSY) $('nbL').innerHTML = '<div class="nb-e">点「重新定位」找附近的车站。<br><button data-retry="1">定位</button> <button data-home="1">用 Upland 家的位置</button></div>'; return; }
    if (!BUSY) status(POS.home ? '用的是 Upland 家的位置。点「重新定位」用你现在的位置。' : '你的位置（' + ago(POS.t) + (POS.acc ? '，精度约 ' + Math.round(POS.acc) + ' 米' : '') + '）');
    var L = D.st.filter(function (s) { return F === 'all' || s.k === F || (F === 'rail' && (s.k === 'muni' || s.k === 'vta')) || (F === 'sub' && (s.k === 'bart' || s.k === 'nysub' || s.k === 'lametro')); })
      .map(function (s) { return [dist(POS.lat, POS.lon, s.ll[0], s.ll[1]), s]; })
      .sort(function (a, b) { return a[0] - b[0]; });
    // 同一个地方的同类车站（比如两个方向的站台）只留一个
    var seen = {}, out = [];
    for (var i = 0; i < L.length && out.length < 10; i++) { var k = L[i][1].k + '|' + L[i][1].ll[0].toFixed(3) + L[i][1].ll[1].toFixed(3); if (!seen[k]) { seen[k] = 1; out.push(L[i]); } }
    if (!out.length) { $('nbL').innerHTML = '<div class="nb-e">没有这类车站。</div>'; return; }
    var far = out[0][0] > 60;
    $('nbL').innerHTML = (far ? '<div class="nb-e" style="padding:10px 0">离最近的车站也有 ' + Math.round(out[0][0]) + ' 英里，这里的车站数据覆盖 Amtrak 全线、加州（湾区、洛杉矶）和纽约地铁。</div>' : '') + out.map(function (x) {
      var d = x[0], s = x[1], K = KIND[s.k] || ['🚉', s.k, '#555'], id = s.k + ':' + s.id;
      var walk = Math.round(d * 1.2 / 3 * 60), dtx = d < 0.1 ? Math.round(d * 5280) + ' 英尺' : d.toFixed(d < 10 ? 1 : 0) + ' 英里';
      var sub = (s.zh ? esc(s.n) + ' · ' : '') + K[1] + (s.l && s.l.length ? ' · ' + esc(s.l.slice(0, 3).join('、')) : '');
      var modes = d < 2 ? [['walking', '步行'], ['transit', '公交'], ['driving', '开车']] : [['driving', '开车'], ['transit', '公交'], ['walking', '步行']];
      var x2 = '<div class="nb-x"><div class="nb-go">' + modes.map(function (m, j) { return '<a href="' + gm(s, m[0]) + '" target="_blank" rel="noopener"' + (j ? ' class="s"' : '') + '>' + m[1] + '</a>'; }).join('') + '</div>';
      if (s.l && s.l.length > 3) x2 += '<div class="nb-l">经过：' + esc(s.l.join('、')) + '</div>';
      if (s.k === 'amtrak' && s.dep) {
        var nx = nextDeps(s);
        x2 += '<div class="nb-nx">' + (nx.length ? '接下来的车：<br>' + nx.map(function (y) { return '<b>' + (y[0] === 1 ? '明天 ' : y[0] === 2 ? '后天 ' : '') + y[2][0] + '</b> ' + esc(y[2][2]) + ' ' + esc(y[2][1]) + ' 次 → ' + esc(y[2][3]); }).join('<br>') : '这几天没有车（这里可能只停大巴）。') + '<br><small>按官方时刻表；查任意两站在 <a href="amtrak.html#time">Amtrak 页「查时刻」</a></small></div>';
      } else if (s.k === 'bart') {
        x2 += '<div class="nb-nx"><a href="javascript:void 0" data-bart="' + esc(s.id) + '">看实时到站</a></div>';
      } else if (s.k === 'metrolink') {
        x2 += '<div class="nb-nx"><a href="https://metrolinktrains.com/schedules/" target="_blank" rel="noopener">Metrolink 时刻表</a> · 也可以点「公交」让谷歌地图排班次<br><small>周末班次少，出门前查一下。</small></div>';
      } else {
        x2 += '<div class="nb-nx"><small>下一班车点「🚌 公交」在谷歌地图里看。</small></div>';
      }
      x2 += '<button class="nb-more" data-det="' + esc(id) + '">车站详情：全部班次、地图、街景 ›</button></div>';
      return '<div class="nb-c' + (OPEN[id] ? ' open' : '') + '" data-id="' + esc(id) + '"><div class="nb-r"><div class="nb-i" style="background:' + K[2] + '">' + K[0] + '</div><div class="nb-m"><b>' + esc(s.zh || s.n) + '</b><small>' + sub + '</small></div><div class="nb-d"><b>' + dtx + '</b><small>' + (d < 2 ? '步行约 ' + walk + ' 分' : '开车 / 公交') + '</small></div></div>' + x2 + '</div>';
    }).join('');
    if (!Object.keys(OPEN).length) { var f = $('nbL').querySelector('.nb-c'); if (f) f.classList.add('open'); }
  }
  // ================= 车站详情 =================
  var LINK = {
    amtrak: function (s) { return ['Amtrak 车站页', 'https://www.amtrak.com/stations/' + s.id.toLowerCase()]; },
    metrolink: function () { return ['Metrolink 车站和时刻', 'https://metrolinktrains.com/schedules/']; },
    bart: function (s) { return ['BART 车站页', 'https://www.bart.gov/stations/' + s.id.toLowerCase()]; },
    caltrain: function () { return ['Caltrain 车站', 'https://www.caltrain.com/stations']; },
    muni: function () { return ['Muni 线路图', 'https://www.sfmta.com/maps/muni-metro-map']; },
    vta: function () { return ['VTA 轻轨', 'https://www.vta.org/go/maps']; },
    nysub: function () { return ['MTA 地铁地图和服务变更', 'https://new.mta.info/maps']; },
    lametro: function () { return ['LA Metro 线路图', 'https://www.metro.net/riding/guide/system-maps/']; }
  };
  var KTIP = {
    amtrak: ['开车前 30 分钟左右到站；小站没有售票窗口，提前在 Amtrak App 买票。', '大站在大屏幕上看站台（Track）；小站一般就一个站台，车停的时间很短，提前在站台等。', '长途车晚点很常见，看下面的「实时」再出门。'],
    metrolink: ['上车前在站台的售票机或 Metrolink App 买票，车上不卖票，查票没票会罚款。', '工作日班次多，周末明显少，看准下面的时刻。', '大多数车站有免费停车场（以现场告示为准）。', '到洛杉矶联合车站可以换 Amtrak、地铁 B/D 线、L 线。'],
    bart: ['进出站都要刷 Clipper（卡或手机），按距离收费，余额不够出不了站，闸内有补票机。', '看清列车终点站再上车，几条线共用轨道。'],
    caltrain: ['上车前在站台刷 Clipper「tag on」，下车后「tag off」，忘了下车刷会按最远收费。', '快车（Limited / Express）不是每站都停，看清车次。', '周末班次少。'],
    muni: ['前门后门都能上（刷了 Clipper 或有电子票），2 小时内换乘免费。', '地下站进站要刷卡。'],
    vta: ['在站台售票机或 Clipper 刷卡后上车，2 小时内换乘免费。', '市中心一段和汽车混行，比较慢。'],
    nysub: ['进站用 OMNY：直接刷手机或信用卡，7 天内刷满一定次数后本周免费（封顶）。', '看清是快车（Express）还是慢车（Local），快车跳站。', '周末和深夜常改线、停站，进站前看 MTA App 或站内告示。', '同一个站名可能有好几个不相通的站，看清线路颜色和字母数字。'],
    lametro: ['进站前刷 TAP 卡或手机钱包里的 TAP，2 小时内换乘免费，有每日每周封顶。', '联合车站可以换 Metrolink 和 Amtrak；A 线往东通到 Pomona North，离 Upland 不远。', '夜里人少时坐靠近司机的车厢。']
  };
  var STIP = {
    'ML:125': ['从家走到这里最近：Upland 站在市中心 A St 和 2nd Ave 附近，旁边就是 Upland 老城（Historic Downtown）的餐厅和咖啡馆。', '坐 San Bernardino 线往西，大约一小时到洛杉矶联合车站，再换 Amtrak。'],
    'LAX': ['洛杉矶联合车站：所有西部长途车和太平洋冲浪者号的起点。坐卧铺可以用 Metropolitan Lounge 贵宾休息室。', '大厅本身值得逛；马路对面是 Olvera Street，往北几分钟是唐人街。'],
    'ONA': ['安大略站无人值守、只有站台，日落特快在深夜或凌晨停，提前在 App 买票，安排好接送。'],
    'POS': ['波莫纳站无人值守，日落特快在深夜或凌晨停。'],
    'SBA': ['下车走 10 分钟就是 State St 和海边的 Stearns 码头。']
  };
  function findSt(id) { var p = id.indexOf(':'), k = id.slice(0, p), sid = id.slice(p + 1); return D.st.filter(function (s) { return s.k === k && s.id === sid; })[0]; }
  function loadLeaf(cb) {
    if (window.L) return cb();
    var c = document.createElement('link'); c.rel = 'stylesheet'; c.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'; document.head.appendChild(c);
    var j = document.createElement('script'); j.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'; j.onload = cb; document.head.appendChild(j);
  }
  function hm(m) { m = ((m % 1440) + 1440) % 1440; return ('0' + Math.floor(m / 60)).slice(-2) + ':' + ('0' + m % 60).slice(-2); }
  function dayLabel(i) { var n = new Date(); n.setDate(n.getDate() + i); return (i === 0 ? '今天' : i === 1 ? '明天' : '后天') + ' ' + (n.getMonth() + 1) + '/' + n.getDate() + ' 周' + '日一二三四五六'.charAt(n.getDay()); }
  function detail(id) {
    DET = id; var s = findSt(id); if (!s) { DET = null; return draw(); }
    var K = KIND[s.k] || ['🚉', s.k, '#555'], d = POS ? dist(POS.lat, POS.lon, s.ll[0], s.ll[1]) : null, lk = LINK[s.k] ? LINK[s.k](s) : null;
    var tips = (STIP[s.id] || []).concat(KTIP[s.k] || []);
    var h = '<button class="nb-back" data-back="1">‹ 返回附近车站</button>' +
      '<div class="nb-dh"><div class="nb-i" style="background:' + K[2] + '">' + K[0] + '</div><div><b>' + esc(s.zh || s.n) + '</b><small>' + (s.zh ? esc(s.n) + ' · ' : '') + K[1] + (d != null ? ' · 离你 ' + (d < 0.1 ? Math.round(d * 5280) + ' 英尺' : d.toFixed(1) + ' 英里') + (d < 2 ? '，步行约 ' + Math.round(d * 1.2 / 3 * 60) + ' 分' : '') : '') + '</small></div></div>' +
      (s.l && s.l.length ? '<div class="nb-ch">' + s.l.map(function (x) { return '<span>' + esc(x) + '</span>'; }).join('') + '</div>' : '') +
      '<div class="nb-map" id="nbMap"></div>' +
      '<div class="nb-go">' + (d != null && d >= 2 ? [['driving', '开车'], ['transit', '公交'], ['walking', '步行']] : [['walking', '步行'], ['transit', '公交'], ['driving', '开车']]).map(function (m, j) { return '<a href="' + gm(s, m[0]) + '" target="_blank" rel="noopener"' + (j ? ' class="s"' : '') + '>' + m[1] + '</a>'; }).join('') + '</div>' +
      '<div class="nb-go"><a class="s" target="_blank" rel="noopener" href="https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=' + s.ll[0] + '%2C' + s.ll[1] + '">街景：先看看长什么样</a><a class="s" target="_blank" rel="noopener" href="https://www.google.com/maps/search/?api=1&query=' + s.ll[0] + '%2C' + s.ll[1] + '">谷歌地图里看</a></div>' +
      (lk ? '<div class="nb-go"><a class="s" target="_blank" rel="noopener" href="' + lk[1] + '">🔗 ' + lk[0] + '</a>' + (s.k === 'amtrak' ? '<a class="s" href="amtrak.html#time" data-q="' + esc(s.id) + '">从这站查时刻</a>' : '') + '</div>' : '') +
      '<div id="nbDep"></div>' +
      (tips.length ? '<div class="nb-sec"><h4>小提示</h4><ul class="nb-tip" style="margin:0;padding-left:18px">' + tips.map(function (t) { return '<li>' + esc(t) + '</li>'; }).join('') + '</ul></div>' : '');
    $('nbL').innerHTML = h; status('');
    // 地图
    loadLeaf(function () {
      var el = $('nbMap'); if (!el || !window.L) return;
      if (DMAP) { try { DMAP.remove(); } catch (e) { } }
      DMAP = L.map(el, { zoomControl: false, attributionControl: true });
      L.layerGroup((function (d, k) { var E = 'https://server.arcgisonline.com/ArcGIS/rest/services/', a = { maxZoom: 19, maxNativeZoom: 16, attribution: '底图 © Esri' }, b = { maxZoom: 19, maxNativeZoom: 16 }; return d ? [L.tileLayer(E + 'Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', a), L.tileLayer(E + 'Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}', b)] : k === 'gray' ? [L.tileLayer(E + 'Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', a), L.tileLayer(E + 'Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}', b)] : [L.tileLayer(E + 'World_Street_Map/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19, attribution: '底图 © Esri' })]; })(false, 'street')).addTo(DMAP);
      L.marker(s.ll, { icon: L.divIcon({ className: '', html: '<div style="width:30px;height:30px;border-radius:9px;background:' + K[2] + ';color:#fff;display:flex;align-items:center;justify-content:center;font-size:16px;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.4)">' + K[0] + '</div>', iconSize: [30, 30], iconAnchor: [15, 15] }) }).addTo(DMAP);
      if (POS && d != null && d < 40) {
        var me = [POS.lat, POS.lon];
        L.circleMarker(me, { radius: 7, color: '#fff', weight: 3, fillColor: '#2F80ED', fillOpacity: 1 }).addTo(DMAP).bindTooltip(POS.home ? '家' : '你');
        L.polyline([me, s.ll], { color: '#2F80ED', weight: 3, dashArray: '6 6', opacity: .8 }).addTo(DMAP);
        DMAP.fitBounds([me, s.ll], { padding: [30, 30], maxZoom: 16 });
      } else DMAP.setView(s.ll, 15);
    });
    // 班次
    var box = $('nbDep');
    if (s.k === 'bart') { box.innerHTML = '<div class="nb-sec"><h4>实时到站</h4><div class="nb-nx" id="nbB">加载中…</div></div>'; bart(s.id, $('nbB')); return; }
    if (s.k === 'amtrak') { amtrakDetail(s, box); return; }
    if (s.k === 'metrolink' || s.k === 'caltrain') { gtfsDetail(s, box); return; }
    box.innerHTML = '<div class="nb-sec"><h4>班次</h4><div class="nb-tip">轻轨白天一般 10–20 分钟一班，晚上和周末少一些。点上面的「🚌 公交」，谷歌地图会给出具体的下一班和换乘。</div></div>';
  }
  function dayChips() { return '<div class="nb-dy">' + [0, 1, 2].map(function (i) { return '<button data-day="' + i + '" class="' + (i === DAY ? 'on' : '') + '">' + dayLabel(i).split(' ')[0] + '</button>'; }).join('') + '</div>'; }
  function gtfsDetail(s, box) {
    box.innerHTML = '<div class="nb-sec"><h4>时刻表</h4><div class="nb-nx">加载中…</div></div>';
    function go() {
      var list = (DEPS && DEPS.d[s.id]) || [], b = DEPS ? DEPS.base : '', bd = b ? new Date(+b.slice(0, 4), +b.slice(4, 6) - 1, +b.slice(6, 8)) : new Date();
      var today = new Date(); today.setHours(0, 0, 0, 0);
      var di = Math.round((today - bd) / 864e5) + DAY, nowM = new Date().getHours() * 60 + new Date().getMinutes();
      var rows = [];
      list.forEach(function (x) {
        var sv = DEPS.svc[x[3]] || [], t = x[0].split(':'), m = +t[0] * 60 + +t[1];
        if (m < 1440 && sv.indexOf(di) >= 0) rows.push([m, x]);
        else if (m >= 1440 && sv.indexOf(di - 1) >= 0) rows.push([m - 1440, x]);   // 前一天跨午夜的班次
      });
      rows.sort(function (a, b) { return a[0] - b[0]; });
      var groups = {}; rows.forEach(function (r) { (groups[r[1][2]] = groups[r[1][2]] || []).push(r); });
      var gk = Object.keys(groups).sort(function (a, b) { return groups[b].length - groups[a].length; });
      var h = '<div class="nb-sec"><h4>🕐 ' + dayLabel(DAY) + ' 的班次</h4>' + dayChips();
      if (!rows.length) h += '<div class="nb-nx">' + (di < 0 || di > 20 ? '时刻表数据只到未来 3 周。' : '这一天这站没有车。') + '</div>';
      gk.forEach(function (g) {
        var L2 = groups[g], nxi = -1;
        if (DAY === 0) for (var i = 0; i < L2.length; i++) if (L2[i][0] >= nowM) { nxi = i; break; }
        h += '<div style="font-weight:700;font-size:13.5px;margin:10px 0 4px">往 ' + esc(g) + ' <small style="font-weight:400;color:#888">' + L2.length + ' 班' + (nxi >= 0 ? ' · 下一班还有 ' + (L2[nxi][0] - nowM) + ' 分钟' : DAY === 0 ? ' · 今天开完了' : '') + '</small></div><table class="nb-tt">' +
          L2.map(function (r, i) { return '<tr class="' + (DAY === 0 && r[0] < nowM ? 'past' : '') + (i === nxi ? ' nx' : '') + '"><td>' + hm(r[0]) + '</td><td>' + esc(r[1][1]) + (r[1][4] ? ' <small>' + esc(r[1][4]) + ' 次</small>' : '') + '</td></tr>'; }).join('') + '</table>';
      });
      h += '<div class="nb-st" style="margin:8px 0 0">按官方公开时刻表，每周更新；临时改点、节假日以官方 App 为准。</div></div>';
      box.innerHTML = h;
    }
    if (DEPS) go(); else { var x = new XMLHttpRequest(); x.open('GET', 'stations/deps.json?t=' + Math.floor(Date.now() / 864e5)); x.onload = function () { try { DEPS = JSON.parse(x.responseText); } catch (e) { } if (DET === s.k + ':' + s.id) go(); }; x.send(); }
  }
  function amtrakDetail(s, box) {
    var n = laNow(), wd = (n.wd + DAY) % 7, L2 = (s.dep || []).filter(function (x) { return x[4].charAt(wd) === '1'; });
    var h = '<div class="nb-sec"><h4>实时：正在开过来的车</h4><div class="nb-nx" id="nbLive">加载中…</div></div>' +
      '<div class="nb-sec"><h4>🕐 ' + dayLabel(DAY) + ' 的时刻表</h4>' + dayChips() + (L2.length ? '<table class="nb-tt">' + L2.map(function (x) {
        var t = x[0].split(':'), m = +t[0] * 60 + +t[1], past = DAY === 0 && m < n.m;
        return '<tr class="' + (past ? 'past' : '') + '"><td>' + x[0] + '</td><td>' + esc(x[2]) + ' ' + esc(x[1]) + ' 次 → ' + esc(x[3]) + '</td></tr>';
      }).join('') + '</table>' : '<div class="nb-nx">这一天没有车从这站开。</div>') + '<div class="nb-st" style="margin:8px 0 0">按 Amtrak 官方时刻表（当地时间）。</div></div>';
    box.innerHTML = h;
    var x = new XMLHttpRequest(); x.open('GET', 'https://api-v3.amtraker.com/v3/stations/' + s.id); x.timeout = 15000;
    x.onerror = x.ontimeout = function () { var b = $('nbLive'); if (b) b.textContent = '实时数据暂时取不到。'; };
    x.onload = function () {
      var ids = []; try { var j = JSON.parse(x.responseText); ids = (j[s.id] || j[Object.keys(j)[0]] || {}).trains || []; } catch (e) { }
      if (!ids.length) { var b0 = $('nbLive'); if (b0) b0.textContent = '现在没有正在开往这站的车。'; return; }
      var res = [], left = Math.min(8, ids.length);
      ids.slice(0, 8).forEach(function (tid) {
        var y = new XMLHttpRequest(); y.open('GET', 'https://api-v3.amtraker.com/v3/trains/' + encodeURIComponent(tid)); y.timeout = 15000;
        y.onloadend = function () {
          try {
            var j = JSON.parse(y.responseText), arr = j[Object.keys(j)[0]] || [];
            (Array.isArray(arr) ? arr : [arr]).forEach(function (t) {
              (t.stations || []).forEach(function (st) {
                if (st.code !== s.id || st.status === 'Departed') return;
                var sch = Date.parse(st.schDep || st.schArr), est = Date.parse(st.dep || st.arr);
                res.push({ no: t.trainNum, r: t.routeName, sch: sch, est: est, tz: st.tz, dest: (t.stations[t.stations.length - 1] || {}).name, now: st.status === 'Station' });
              });
            });
          } catch (e) { }
          if (--left <= 0) show();
        };
        y.send();
      });
      function show() {
        var b = $('nbLive'); if (!b) return;
        res.sort(function (a, b) { return (a.est || a.sch) - (b.est || b.sch); });
        b.innerHTML = res.length ? res.map(function (r) {
          var dl = r.est && r.sch ? Math.round((r.est - r.sch) / 60000) : 0, c = dl <= 5 ? '#2E9D4F' : dl <= 30 ? '#C98A12' : '#C0362C';
          var tm = function (v) { try { return new Date(v).toLocaleTimeString('zh-CN', { timeZone: r.tz || 'America/Los_Angeles', hour: '2-digit', minute: '2-digit', hour12: false }); } catch (e) { return ''; } };
          return '<b>' + esc(r.no) + ' 次</b> ' + esc(r.r) + ' → ' + esc(r.dest || '') + '<br>' + (r.now ? '🚉 <b style="color:#2E9D4F">正在站内</b>' : '预计 <b>' + tm(r.est || r.sch) + '</b>') + ' <span style="color:' + c + ';font-weight:700">' + (dl <= 1 ? '准点' : '晚 ' + (dl >= 60 ? Math.floor(dl / 60) + ' 小时 ' : '') + dl % 60 + ' 分') + '</span> <small>（时刻表 ' + tm(r.sch) + '）</small>';
        }).join('<br>') : '现在没有正在开往这站的车。';
      }
    };
    x.send();
  }
  function bart(abbr, box) {
    box.innerHTML = '加载实时到站…';
    var x = new XMLHttpRequest(); x.open('GET', 'https://api.bart.gov/api/etd.aspx?cmd=etd&orig=' + encodeURIComponent(abbr) + '&key=' + BKEY + '&json=y'); x.timeout = 12000;
    x.onload = function () {
      try {
        var st = JSON.parse(x.responseText).root.station[0], rows = [];
        (st.etd || []).forEach(function (d) { (d.estimate || []).slice(0, 2).forEach(function (e) { rows.push([e.minutes === 'Leaving' ? 0 : +e.minutes, d.destination, e.hexcolor, e.direction]); }); });
        rows.sort(function (a, b) { return a[0] - b[0]; });
        box.innerHTML = rows.length ? '实时到站：<br>' + rows.slice(0, 6).map(function (r) { return '<span style="display:inline-block;width:9px;height:9px;border-radius:5px;background:' + r[2] + ';margin-right:5px"></span><b>' + (r[0] ? r[0] + ' 分' : '进站中') + '</b> → ' + esc(r[1]) + ' <small>' + (r[3] === 'North' ? '北行' : '南行') + '</small>'; }).join('<br>') : '现在没有车（可能已收班）。';
      } catch (e) { box.textContent = '实时数据格式不对，稍后再试。'; }
    };
    x.onerror = x.ontimeout = function () { box.textContent = '连不上 BART，稍后再试。'; };
    x.send();
  }
  window.Nearby = { open: function () { if (!$('nbSh')) build(); open(); } };
  function boot() { build(); if (location.hash === '#stations') setTimeout(function () { window.Nearby.open(); }, 300); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
