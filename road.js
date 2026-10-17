/* 🚗 湾区路况：高速路线图 + 实时事故 / 封路 / 路牌行车时间 + 分区拥堵概况（sf.html、sj.html 共用）
 * 数据：bay/roads.json（OpenStreetMap 高速走向，每月更新）
 *       live-data 分支 bay/live.json（GitHub Actions 每 15 分钟从 CHP、Caltrans 抓一次）
 *       可选：TomTom 实时车速图层（用户自己填免费密钥，只存在本机）
 */
(function () {
  'use strict';
  var LIVE = 'https://raw.githubusercontent.com/boliunew/tools/live-data/bay/live.json';
  var RO = null, LV = null, MAPR = null, CTX = null, TIMER = null, TTL = null;
  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function ls(k, v) { try { if (v === undefined) return JSON.parse(localStorage.getItem('bay:' + k) || 'null'); localStorage.setItem('bay:' + k, JSON.stringify(v)); } catch (e) { return null; } }
  var LY = ls('road') || { hw: 1, inc: 1, lcs: 1, cms: 1, tt: 0 };
  var LAYERS = [['hw', '🛣️ 高速路线'], ['inc', '🚨 事故'], ['lcs', '🚧 封路施工'], ['cms', '🪧 路牌行车时间'], ['tt', '🔴 实时车速（需密钥）']];
  var DIR = { North: '北向', South: '南向', East: '东向', West: '西向', 'Both Directions': '双向', Both: '双向' };
  var CLO = { Full: '全封', Lane: '封车道', 'One-Way Traffic': '单向放行', 'Alternating Lanes': '轮流封道', Moving: '移动施工', Shoulder: '封路肩' };
  var FAC = { Mainline: '主线', Connector: '立交连接道', 'On Ramp': '入口匝道', 'Off Ramp': '出口匝道', 'Collector-Distributor': '辅道' };
  var WORK = { 'Highway Construction': '道路施工', 'Electrical Work': '电力作业', 'AC Paving/Overlay': '铺沥青', 'Paving Operation': '铺路', 'Bridge Repair': '桥梁维修', 'Utility Work': '管线作业', 'Striping Operation': '画标线', 'Demolition': '拆除', 'Pavement Repair': '路面修补', 'Tree Work': '修树', 'Median Barrier Work': '中央隔离带施工', 'Roadway Excavation': '开挖', 'Drainage Work': '排水施工', 'Sweeping Operation': '扫路', 'Emergency Work': '紧急抢修', 'K-rail Installation': '装隔离墩', 'Horizontal Boring': '地下钻孔', 'Guardrail Work': '护栏施工', 'Sign Work': '路牌施工', 'Landscaping': '绿化' };
  var AREAS = ['旧金山', '半岛', '南湾', '东湾', '北湾'];

  function area(ll) {   // 大致分区（按经纬度粗分）
    var la = ll[0], lo = ll[1];
    if (la > 37.995 || (la > 37.825 && lo < -122.40)) return '北湾';
    if (la >= 37.705 && la <= 37.835 && lo < -122.355) return '旧金山';
    if (la < 37.465) return '南湾';
    var line = -122.38 + (37.62 - la) * (0.18 / 0.13);   // SFO → 红木城 一线以西是半岛
    if (la < 37.705 && lo < Math.min(line, -122.15)) return '半岛';
    return '东湾';
  }
  function laTime(ep) {
    try { return new Date(ep * 1000).toLocaleString('zh-CN', { timeZone: 'America/Los_Angeles', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }); } catch (e) { return ''; }
  }
  function laNow() {
    var p = {}; try { new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', weekday: 'short', hour: 'numeric', minute: 'numeric', hourCycle: 'h23' }).formatToParts(new Date()).forEach(function (x) { p[x.type] = x.value; }); } catch (e) { }
    return { wd: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].indexOf(p.weekday), m: (+p.hour || 0) * 60 + (+p.minute || 0) };
  }
  function ratio(t) { return t.base ? t.m / t.base : null; }
  function lvl(r) { return r == null ? 0 : r >= 1.6 ? 3 : r >= 1.25 ? 2 : 1; }
  var LC = ['#9AA1A9', '#2E9D4F', '#E0A100', '#D33A2C'];
  var LZ = ['数据不足', '顺畅', '有点慢', '拥堵'];
  function minor(i) { return /协助|动物|杂物/.test(i.zh) || /assist/i.test(i.t); }

  function rush() {   // 按星期和时间给出通常最堵的方向（经验规律，不是实时数据）
    var n = laNow(), wk = n.wd >= 1 && n.wd <= 5, m = n.m;
    if (wk && m >= 360 && m < 600) return '⏰ 工作日早高峰：通常最堵的是 101 北向（圣何塞→半岛）、880 北向、80 西向海湾大桥收费站、680 南向 Sunol 段、580 西向 Altamont。';
    if (wk && m >= 900 && m < 1170) return '⏰ 工作日晚高峰：通常最堵的是 101 南向、880 南向、80 东向（海湾大桥出城）、680 北向 Sunol 段、85 / 87 南向、92 西向圣马特奥大桥' + (n.wd === 5 ? '。周五傍晚出城去太浩湖、纳帕的 80 东向、580 东向、101 北向更堵。' : '。');
    if (!wk && m >= 600 && m < 1140) return '⏰ 周末白天：80 东向往萨克拉门托 / 太浩湖、17 号公路去圣克鲁兹、金门大桥一带容易堵；周日下午回城方向更堵。';
    if (m >= 1260 || m < 300) return '🌙 夜里车少，但很多路段晚上施工封车道，留意地图上的 🚧。';
    return '';
  }

  function summary() {
    var box = $('rsum'); if (!box) return;
    if (!LV) { box.innerHTML = '<div class="rs-h">实时数据加载中…</div>'; return; }
    var A = {}; AREAS.forEach(function (a) { A[a] = { inc: [], lcs: 0, tt: [], lv: 1 }; });
    (LV.inc || []).forEach(function (i) { var a = A[area(i.ll)]; if (a && !minor(i)) a.inc.push(i); });
    (LV.lcs || []).forEach(function (c) { var a = A[area(c.ll)]; if (a && c.fac === 'Mainline') a.lcs++; });
    (LV.cms || []).forEach(function (s) { var a = A[area(s.ll)]; if (a) s.tt.forEach(function (t) { if (t.base) a.tt.push([ratio(t), t, s]); }); });
    var h = '<div class="rs-h"><b>🚗 现在湾区路况</b><small>' + (LV.generated ? '更新于 ' + esc(laTime(LV.generated)) : '') + ' · 每 15 分钟</small></div>';
    AREAS.forEach(function (k) {
      var a = A[k]; a.tt.sort(function (x, y) { return y[0] - x[0]; });
      var worst = a.tt[0], lv = worst ? lvl(worst[0]) : 1, col = a.inc.filter(function (i) { return /车祸|逃逸|SigAlert|逆行|起火/.test(i.zh); }).length;
      var lab = LZ[lv];
      if (a.inc.some(function (i) { return /SigAlert/.test(i.zh); })) { lv = 3; lab = 'SigAlert'; }
      else if (lv < 2 && col) { lv = 2; lab = '有事故'; }
      else if (!worst) lab = '正常';
      var bits = [];
      if (worst && worst[0] >= 1.25) bits.push(esc(worst[2].rt + ' ' + (DIR[worst[2].dir] || '')) + ' 往 ' + esc(worst[1].to) + ' <b>' + worst[1].m + ' 分</b>（平时 ' + worst[1].base + '）');
      if (a.inc.length) bits.push('🚨 ' + a.inc.length + ' 起事件' + (col ? '（车祸 ' + col + '）' : ''));
      if (a.lcs) bits.push('🚧 ' + a.lcs + ' 处封道');
      h += '<div class="rs-r" data-area="' + k + '"><i style="background:' + LC[lv] + '"></i><b>' + k + '</b><span class="rs-l" style="color:' + LC[lv] + '">' + lab + '</span><small>' + (bits.join(' · ') || '没有事故报告') + '</small></div>';
    });
    var r = rush(); if (r) h += '<div class="rs-n">' + r + '</div>';
    if (LV.err && LV.err.length) h += '<div class="rs-n">部分数据这次没取到：' + esc(LV.err.join('、')) + '</div>';
    box.innerHTML = h;
    box.onclick = function (e) {
      var row = e.target.closest('[data-area]'); if (!row || !MAPR) return;
      var c = { '旧金山': [37.765, -122.43, 12], '半岛': [37.56, -122.3, 11], '南湾': [37.35, -121.93, 11], '东湾': [37.75, -122.12, 10], '北湾': [38.0, -122.5, 10] }[row.getAttribute('data-area')];
      MAPR.setView([c[0], c[1]], c[2]); $('rmap').scrollIntoView({ block: 'center', behavior: 'smooth' });
    };
  }

  function icon(html, cls, sz) { return L.divIcon({ className: 'rdi ' + (cls || ''), html: html, iconSize: [sz || 26, sz || 26], iconAnchor: [(sz || 26) / 2, (sz || 26) / 2] }); }
  function shield(r) {
    var t = r.split('-'), cls = t[0] === 'I' ? 'si' : t[0] === 'US' ? 'su' : 'ss';
    return L.divIcon({ className: 'rsh ' + cls, html: '<span>' + t[1] + '</span>', iconSize: [30, 20], iconAnchor: [15, 10] });
  }
  var HC = { I: '#3F51B5', US: '#7B4BB7', SR: '#2C8C99' };

  function draw() {
    if (!MAPR) return;
    MAPR.g = MAPR.g || {};
    Object.keys(MAPR.g).forEach(function (k) { MAPR.removeLayer(MAPR.g[k]); });
    MAPR.g = {};
    var key = ls('ttkey'), z = MAPR.getZoom();
    if (LY.tt && key) {
      if (!TTL) TTL = L.tileLayer('https://api.tomtom.com/traffic/map/4/tile/flow/relative0/{z}/{x}/{y}.png?key=' + encodeURIComponent(key), { maxZoom: 19, opacity: .9, zIndex: 5, attribution: '车速 © TomTom' });
      TTL.addTo(MAPR);
    } else if (TTL) { MAPR.removeLayer(TTL); TTL = null; }
    if (LY.hw && RO) {
      var g = L.layerGroup(), dim = LY.tt && key;
      RO.routes.forEach(function (r) {
        var c = HC[r.r.split('-')[0]], w = r.r.indexOf('SR') === 0 ? 2.5 : 3.5, best = null;
        r.seg.forEach(function (s) {
          g.addLayer(L.polyline(s, { color: c, weight: w, opacity: dim ? .35 : .85, interactive: true }).bindTooltip(r.r + (r.zh ? '：' + r.zh : ''), { sticky: true }));
          if (!best || s.length > best.length) best = s;
        });
        if (best && best.length > 4) {
          var picks = best.length > 60 ? [Math.floor(best.length * .25), Math.floor(best.length * .75)] : [Math.floor(best.length / 2)];
          picks.forEach(function (i) { g.addLayer(L.marker(best[i], { icon: shield(r.r), interactive: false, zIndexOffset: -100 })); });
        }
      });
      g.addTo(MAPR); MAPR.g.hw = g;
    }
    if (!LV) return;
    if (LY.lcs) {
      var g2 = L.layerGroup();
      LV.lcs.forEach(function (c) {
        var main = c.fac === 'Mainline', full = c.type === 'Full';
        if (z < 11 && !main) return;   // 拉远时只画主线封道，放大再显示匝道
        var pop = '<div class="tipp"><b>🚧 ' + esc(c.rt) + ' ' + (DIR[c.dir] || esc(c.dir)) + ' · ' + (CLO[c.type] || esc(c.type)) + '</b>' +
          esc(FAC[c.fac] || c.fac) + ' · ' + esc(WORK[c.work] || c.work) + '<br>' + (c.lanes && c.lanes !== 'All' ? '封了 ' + esc(c.lanes) + (c.total ? ' / ' + esc(c.total) : '') + ' 条车道<br>' : full ? '全部车道封闭<br>' : '') +
          (c.near ? '在 ' + esc(c.near) + ' 附近<br>' : '') + (c.end ? '预计 ' + esc(laTime(c.end)) + ' 结束' : '') + '</div>';
        if (c.ll2 && (c.ll2[0] !== c.ll[0] || c.ll2[1] !== c.ll[1])) g2.addLayer(L.polyline([c.ll, c.ll2], { color: full ? '#C0362C' : '#E07B00', weight: 5, opacity: .8, dashArray: '6 5' }).bindPopup(pop));
        g2.addLayer(L.marker(c.ll, { icon: icon('🚧', main ? (full ? 'rd-full' : 'rd-lane') : 'rd-ramp', main ? 24 : 18), zIndexOffset: 300 }).bindPopup(pop, { maxWidth: 260 }));
      });
      g2.addTo(MAPR); MAPR.g.lcs = g2;
    }
    if (LY.cms) {
      var g3 = L.layerGroup();
      LV.cms.forEach(function (s) {
        var best = 0; s.tt.forEach(function (t) { best = Math.max(best, lvl(ratio(t))); });
        if (!s.tt.length && (!s.msg.length || z < 11)) return;
        var pop = '<div class="tipp"><b>🪧 ' + esc(s.rt) + ' ' + (DIR[s.dir] || esc(s.dir)) + (s.near ? ' · ' + esc(s.near) : '') + '</b>' +
          '<div class="rd-sign">' + s.msg.map(esc).join('<br>') + '</div>' +
          (s.tt.length ? s.tt.map(function (t) { var l = lvl(ratio(t)); return '<div><i style="display:inline-block;width:9px;height:9px;border-radius:5px;background:' + LC[l] + ';margin-right:5px"></i>到 ' + esc(t.to) + '：<b>' + t.m + ' 分钟</b>' + (t.base ? '（平时最快 ' + t.base + '）' : '（基准还在积累）') + '</div>'; }).join('') : '') + '</div>';
        g3.addLayer(L.marker(s.ll, { icon: icon(s.tt.length ? '<b style="background:' + LC[best] + '">' + (s.tt[0] ? s.tt[0].m : '') + '</b>' : '🪧', s.tt.length ? 'rd-tt' : 'rd-cms', s.tt.length ? 28 : 18), zIndexOffset: s.tt.length ? 400 : 100 }).bindPopup(pop, { maxWidth: 270 }));
      });
      g3.addTo(MAPR); MAPR.g.cms = g3;
    }
    if (LY.inc) {
      var g4 = L.layerGroup();
      LV.inc.forEach(function (i) {
        var big = /车祸|逃逸|SigAlert|逆行|起火/.test(i.zh);
        if (!big && z < 10) return;
        g4.addLayer(L.marker(i.ll, { icon: icon(big ? '🚨' : '⚠️', big ? 'rd-inc' : 'rd-inc2', big ? 28 : 22), zIndexOffset: big ? 600 : 500 })
          .bindPopup('<div class="tipp"><b>' + (big ? '🚨 ' : '⚠️ ') + esc(i.zh || i.t) + '</b>' + (i.zh ? '<small style="color:#888">' + esc(i.t) + '</small><br>' : '') + esc(i.loc) + '<br><small>' + esc(i.at) + ' · CHP 报告 · ' + area(i.ll) + '</small></div>', { maxWidth: 260 }));
      });
      g4.addTo(MAPR); MAPR.g.inc = g4;
    }
  }

  function loadLive(cb) {
    var x = new XMLHttpRequest(); x.open('GET', LIVE + '?t=' + Math.floor(Date.now() / 120000)); x.timeout = 20000;
    x.onload = function () { try { LV = JSON.parse(x.responseText); } catch (e) { } summary(); draw(); if (cb) cb(); };
    x.onerror = x.ontimeout = function () { var b = $('rsum'); if (b && !LV) b.innerHTML = '<div class="rs-h">实时数据暂时取不到，稍后刷新。</div>'; };
    x.send();
  }
  function tick() {
    clearTimeout(TIMER);
    TIMER = setTimeout(function () { if (!$('rmap')) return; if (!document.hidden) { loadLive(); if (TTL) TTL.redraw(); } tick(); }, 180000);
  }

  function html() {
    var key = ls('ttkey');
    return '<div class="rsum" id="rsum"><div class="rs-h">加载中…</div></div>' +
      '<div class="mtabs" id="rlay2">' + LAYERS.map(function (x) { return '<button data-rl="' + x[0] + '" class="' + (LY[x[0]] ? 'on' : '') + '">' + (LY[x[0]] ? '✓ ' : '') + x[1] + '</button>'; }).join('') + '</div>' +
      '<div class="mapbox" id="rmap" style="cursor:auto"></div>' +
      '<div class="mtabs" style="margin-top:8px"><button id="rgBay">🌉 整个湾区</button><button id="rgSF">🌁 旧金山</button><button id="rgSJ">🌴 圣何塞</button><button id="rgMe">📍 我的位置</button><button id="rgRe">🔄 刷新</button></div>' +
      '<details class="rkey"' + (key ? '' : '') + '><summary>🔴 想看每条路实时的红黄绿车速？' + (key ? '（已开启）' : '') + '</summary>' +
      '<div class="mnote" style="margin-top:4px">需要一个免费的 TomTom 地图密钥（个人用免费额度足够）：<br>① 打开 <a href="https://developer.tomtom.com/user/register" target="_blank" rel="noopener">developer.tomtom.com</a> 免费注册；② 在 Dashboard 里复制 API Key；③ 粘贴到下面。密钥只存在这台手机上，不会上传。</div>' +
      '<div class="mtabs"><input id="rkey" class="fsel" style="flex:1;min-width:0" placeholder="粘贴 TomTom API Key" value="' + esc(key || '') + '"><button id="rkeyOk">保存</button>' + (key ? '<button id="rkeyDel">删除</button>' : '') + '</div></details>' +
      '<div class="mnote">分区颜色怎么来的：Caltrans 高速路牌上显示的行车时间，和这块路牌过去显示过的最快时间比较（慢 25% 以上算「有点慢」，慢 60% 以上算「拥堵」），再加上 CHP 报告的车祸。路牌多在白天显示行车时间，刚上线的几天「平时」基准还在积累。' +
      '<br>数据：<a href="https://quickmap.dot.ca.gov/" target="_blank" rel="noopener">Caltrans QuickMap</a>（CHP 事故、封路、路牌），高速走向 © OpenStreetMap，底图 © CARTO。出发前用谷歌地图或 Waze 再确认。</div>';
  }

  function init(ctx) {
    CTX = ctx; TTL = null; MAPR = null;
    $('rlay2').onclick = function (e) {
      var b = e.target.closest('[data-rl]'); if (!b) return; var k = b.getAttribute('data-rl');
      if (k === 'tt' && !ls('ttkey') && !LY.tt) { var d = document.querySelector('.rkey'); if (d) { d.open = true; d.scrollIntoView({ block: 'center', behavior: 'smooth' }); } }
      LY[k] = LY[k] ? 0 : 1; ls('road', LY); b.className = LY[k] ? 'on' : ''; b.textContent = (LY[k] ? '✓ ' : '') + b.textContent.replace(/^✓ /, ''); draw();
    };
    $('rkeyOk').onclick = function () { var v = $('rkey').value.trim(); ls('ttkey', v || null); LY.tt = v ? 1 : 0; ls('road', LY); TTL = null; CTX.rerender(); };
    if ($('rkeyDel')) $('rkeyDel').onclick = function () { ls('ttkey', null); TTL = null; CTX.rerender(); };
    summary();
    CTX.loadLeaflet(function () {
      var dark = window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches && document.documentElement.getAttribute('data-theme') !== 'light';
      MAPR = L.map('rmap', { zoomControl: true }).setView(ctx.center || [37.62, -122.15], ctx.zoom || 9);
      L.tileLayer('https://{s}.basemaps.cartocdn.com/' + (dark ? 'dark_all' : 'light_all') + '/{z}/{x}/{y}{r}.png', { maxZoom: 19, subdomains: 'abcd', attribution: '© OpenStreetMap · © CARTO' }).addTo(MAPR);
      $('rgBay').onclick = function () { MAPR.setView([37.62, -122.15], 9); };
      $('rgSF').onclick = function () { MAPR.setView([37.765, -122.43], 12); };
      $('rgSJ').onclick = function () { MAPR.setView([37.35, -121.92], 11); };
      $('rgRe').onclick = function () { loadLive(); if (TTL) TTL.redraw(); };
      $('rgMe').onclick = function () {
        if (!navigator.geolocation) return;
        navigator.geolocation.getCurrentPosition(function (p) {
          var ll = [p.coords.latitude, p.coords.longitude];
          if (MAPR.me) MAPR.removeLayer(MAPR.me);
          MAPR.me = L.circleMarker(ll, { radius: 8, color: '#fff', weight: 3, fillColor: '#2F6F8F', fillOpacity: 1 }).addTo(MAPR).bindPopup('你在这里（' + area(ll) + '）');
          MAPR.setView(ll, 12);
        }, function () { }, { timeout: 15000 });
      };
      MAPR.on('zoomend', function () { var z = MAPR.getZoom(), b = z < 10 ? 0 : z < 11 ? 1 : 2; if (b !== MAPR.zb) { MAPR.zb = b; draw(); } });
      MAPR.zb = MAPR.getZoom() < 10 ? 0 : MAPR.getZoom() < 11 ? 1 : 2;
      draw();
      if (!RO) { var x = new XMLHttpRequest(); x.open('GET', 'bay/roads.json?v=1'); x.onload = function () { try { RO = JSON.parse(x.responseText); } catch (e) { } draw(); }; x.send(); }
      loadLive(); tick();
    });
  }
  document.addEventListener('visibilitychange', function () { if (!document.hidden && $('rmap') && MAPR) { loadLive(); if (TTL) TTL.redraw(); } });
  window.BayRoad = { html: html, init: init, area: area };
})();
