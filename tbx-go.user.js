// ==UserScript==
// @name         🧭 工具箱随身
// @namespace    https://boliunew.github.io/tools/
// @version      1.0.2
// @description  把「我的工具」带到别的网站上：网页图片一键下原图、YouTube 字幕送 SubLingo、英文网页选中一句就讲语法 / 单词存进语境词库、股票页显示股票池信号、推特图片视频一键下到 torrent_hub。
// @author       boliunew
// @match        *://*/*
// @connect      tools-api.boliunew.workers.dev
// @connect      boliunew.github.io
// @connect      api.fxtwitter.com
// @connect      youtube.com
// @connect      127.0.0.1
// @connect      localhost
// @connect      *
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_openInTab
// @grant        GM_registerMenuCommand
// @grant        unsafeWindow
// @run-at       document-start
// @noframes
// @updateURL    https://boliunew.github.io/tools/tbx-go.user.js
// @downloadURL  https://boliunew.github.io/tools/tbx-go.user.js
// ==/UserScript==

(function () {
  'use strict';
  var VER = '1.0.2', SITE = 'https://boliunew.github.io/tools/', TH = 'http://127.0.0.1:8800';
  var host = location.hostname, path = location.pathname;
  try { console.log('[工具箱随身] v' + VER + ' 在 ' + host + ' 上运行'); } catch (e) { }
  function gm(o) {
    return new Promise(function (res, rej) {
      GM_xmlhttpRequest(Object.assign({ timeout: 30000 }, o, {
        onload: function (r) { res(r); }, onerror: function () { rej(new Error('网络请求失败')); }, ontimeout: function () { rej(new Error('请求超时')); }
      }));
    });
  }
  function gjson(url) { return gm({ method: 'GET', url: url + (url.indexOf('?') < 0 ? '?' : '&') + 't=' + Math.floor(Date.now() / 300000) }).then(function (r) { return JSON.parse(r.responseText); }); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function ready(f) { if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', f); else f(); }

  /* =================== 在工具箱自己的页面上：交接数据 =================== */
  if (host === 'boliunew.github.io' && path.indexOf('/tools') === 0) {
    var mark = function () { if (document.documentElement) document.documentElement.setAttribute('data-tbxgo', VER); };
    mark(); document.addEventListener('DOMContentLoaded', mark);
    try {
      var k = localStorage.getItem('home:unlock'); if (k) GM_setValue('key', k);          // AI 讲解要用的钥匙
      var h = GM_getValue('sl_handoff', null);                                               // YouTube 字幕 → SubLingo
      if (h && /sublingo\.html$/.test(path)) { localStorage.setItem('sl:handoff', JSON.stringify(h)); GM_setValue('sl_handoff', null); }
      var box = GM_getValue('vocab_inbox', []);                                              // 网页上存的生词 → 语境词库
      if (box && box.length) {
        var cur = JSON.parse(localStorage.getItem('ctxvocab-inbox') || '[]');
        localStorage.setItem('ctxvocab-inbox', JSON.stringify(cur.concat(box)));
        GM_setValue('vocab_inbox', []);
      }
    } catch (e) { }
    return;
  }

  /* =================== 公用：浮动小面板（Shadow DOM，不受网站样式影响） =================== */
  var ROOT = null, SH = null;
  var CSS = ':host{all:initial}*{box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}' +
    '.bub{position:fixed;z-index:2147483646;background:#1D2430;color:#fff;border-radius:10px;padding:5px 10px;font-size:13px;cursor:pointer;box-shadow:0 4px 16px rgba(0,0,0,.3);user-select:none;display:flex;gap:6px}' +
    '.bub span{cursor:pointer;padding:1px 3px;border-radius:6px}.bub span:hover{background:rgba(255,255,255,.15)}' +
    '.pop{position:fixed;z-index:2147483647;width:min(420px,calc(100vw - 20px));max-height:min(70vh,560px);overflow:auto;background:#fff;color:#1E2228;border-radius:14px;box-shadow:0 10px 40px rgba(0,0,0,.28);padding:12px 14px;font-size:14px;line-height:1.65;border:1px solid #E1DFDA}' +
    '@media (prefers-color-scheme:dark){.pop{background:#1C2026;color:#E8EBEE;border-color:#2C3139}.sec b{color:#7FA8F0}.chip{background:#262B32}.src{color:#A9B1BA}}' +
    '.hd{display:flex;align-items:center;gap:8px;margin-bottom:6px}.hd b{flex:1;font-size:15px}.x{border:0;background:transparent;font-size:16px;cursor:pointer;color:inherit;opacity:.6}' +
    '.src{font-size:13px;color:#5E6670;border-left:3px solid #2E6BD8;padding-left:8px;margin:4px 0 8px}' +
    '.sec{margin:6px 0}.sec b{color:#2E6BD8;font-size:13px;display:block}.row{margin:3px 0}.chip{display:inline-block;background:#ECEAE5;border-radius:6px;padding:0 6px;margin-right:4px;font-size:13px}' +
    '.btn{border:0;border-radius:9px;padding:6px 12px;font-size:13.5px;font-weight:600;background:#2E6BD8;color:#fff;cursor:pointer}.btn2{background:transparent;color:inherit;border:1px solid #E1DFDA;font-weight:500}' +
    '.acts{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}.ok{color:#2E9D4F}.err{color:#C0362C}' +
    '.fab{position:fixed;z-index:2147483645;right:16px;bottom:88px;background:#1D2430;color:#fff;border-radius:22px;padding:9px 14px;font-size:14px;box-shadow:0 4px 16px rgba(0,0,0,.3);cursor:pointer;border:0}' +
    '.toast{position:fixed;z-index:2147483647;left:50%;transform:translateX(-50%);bottom:40px;background:#1D2430;color:#fff;border-radius:12px;padding:9px 16px;font-size:14px;box-shadow:0 4px 16px rgba(0,0,0,.3);max-width:90vw}';
  function root() {
    if (SH && ROOT && ROOT.isConnected) return SH;
    if (SH && ROOT && !ROOT.isConnected) { (document.body || document.documentElement).appendChild(ROOT); return SH; }
    ROOT = document.createElement('tbx-go'); (document.body || document.documentElement).appendChild(ROOT);
    SH = ROOT.attachShadow({ mode: 'open' }); var st = document.createElement('style'); st.textContent = CSS; SH.appendChild(st);
    return SH;
  }
  // YouTube 这类网站开了 Trusted Types：直接写 innerHTML 会被浏览器拦下，要先过一个「放行策略」
  var TT = null;
  try { if (window.trustedTypes && trustedTypes.createPolicy) TT = trustedTypes.createPolicy('tbxgo', { createHTML: function (x) { return x; } }); } catch (e) { TT = null; }
  function setHTML(node, html) {
    try { node.innerHTML = TT ? TT.createHTML(html) : html; return; } catch (e) { }
    // 策略也建不了：退一步，用纯文本（去掉标签）
    while (node.firstChild) node.removeChild(node.firstChild);
    node.appendChild(document.createTextNode(String(html).replace(/<br\s*\/?>/g, '\n').replace(/<[^>]+>/g, '').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&amp;/g, '&')));
    node.style.whiteSpace = 'pre-wrap';
  }
  function mk(tag, cls, text, parent) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; (parent || root()).appendChild(e); return e; }
  function el(html) { var d = document.createElement('div'); setHTML(d, html); var e = d.firstChild; root().appendChild(e); return e; }
  var toastT; function toast(msg, ms) { var t = root().querySelector('.toast'); if (!t) { t = document.createElement('div'); t.className = 'toast'; root().appendChild(t); } t.textContent = msg; t.style.display = 'block'; clearTimeout(toastT); toastT = setTimeout(function () { t.style.display = 'none'; }, ms || 3000); }

  /* =================== 1. YouTube 字幕 → SubLingo =================== */
  if (/(^|\.)youtube\.com$/.test(host)) {
    var CAP = {};   // videoId → {lang: json3 文本}
    function vid() { var m = /[?&]v=([\w-]{11})/.exec(location.search) || /\/shorts\/([\w-]{11})/.exec(location.pathname); return m ? m[1] : ''; }
    function keep(url, text) {
      try {
        var u = new URL(url, location.href), v = u.searchParams.get('v'), lang = u.searchParams.get('tlang') || u.searchParams.get('lang') || '?';
        if (v && text && text.length > 50) { (CAP[v] = CAP[v] || {})[lang] = text; }
      } catch (e) { }
    }
    // 播放器自己去拿字幕时顺手记下来（YouTube 现在要带验证参数，只有播放器拿得到）
    try {
      var W = unsafeWindow, of = W.fetch;
      W.fetch = function (inp) {
        var p = of.apply(this, arguments), url = typeof inp === 'string' ? inp : (inp && inp.url) || '';
        if (/\/api\/timedtext/.test(url)) p.then(function (r) { r.clone().text().then(function (t) { keep(url, t); }); }).catch(function () { });
        return p;
      };
      var oo = W.XMLHttpRequest.prototype.open, os = W.XMLHttpRequest.prototype.send;
      W.XMLHttpRequest.prototype.open = function (m, url) { this.__tbxu = url; return oo.apply(this, arguments); };
      W.XMLHttpRequest.prototype.send = function () {
        var x = this;
        if (/\/api\/timedtext/.test(String(x.__tbxu || ''))) x.addEventListener('load', function () { try { keep(String(x.__tbxu), typeof x.response === 'string' ? x.response : x.responseText); } catch (e) { } });
        return os.apply(this, arguments);
      };
    } catch (e) { }
    function json3ToSrt(t) {
      var j; try { j = JSON.parse(t); } catch (e) { return /-->/.test(t) ? t : ''; }
      var n = 0, out = [];
      function ts(ms) { ms = Math.max(0, Math.round(ms)); var h = Math.floor(ms / 3600000), m = Math.floor(ms % 3600000 / 60000), s = Math.floor(ms % 60000 / 1000), z = ms % 1000; return (h < 10 ? '0' : '') + h + ':' + (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s + ',' + ('00' + z).slice(-3); }
      (j.events || []).forEach(function (e, i, all) {
        if (!e.segs) return;
        var txt = e.segs.map(function (s) { return s.utf8 || ''; }).join('').replace(/\s*\n\s*/g, ' ').trim();
        if (!txt) return;
        var st = e.tStartMs || 0, en = st + (e.dDurationMs || 2000);
        var nx = all[i + 1]; if (nx && nx.tStartMs && nx.tStartMs < en && e.wWinId == null) en = nx.tStartMs;
        out.push(++n + '\n' + ts(st) + ' --> ' + ts(en) + '\n' + txt + '\n');
      });
      return out.join('\n');
    }
    function pickTrack(caps) {
      var langs = Object.keys(caps || {}); if (!langs.length) return null;
      var en = langs.filter(function (l) { return /^en/.test(l); })[0];
      return en || langs[0];
    }
    async function grabCaptions() {
      var v = vid(); if (!v) throw new Error('先打开一个视频');
      var have = CAP[v], lang = pickTrack(have);
      if (lang) return { srt: json3ToSrt(have[lang]), lang: lang };
      // 没记到：试一下页面里的字幕列表（有的视频不用验证参数也能拿）
      var pr = unsafeWindow.ytInitialPlayerResponse;
      try { var mp = document.querySelector('#movie_player'); if (mp && mp.getPlayerResponse) pr = mp.getPlayerResponse() || pr; } catch (e) { }
      var tracks = pr && pr.captions && pr.captions.playerCaptionsTracklistRenderer && pr.captions.playerCaptionsTracklistRenderer.captionTracks || [];
      if (!tracks.length) throw new Error('这个视频没有字幕');
      var tr = tracks.filter(function (t) { return /^en/.test(t.languageCode) && t.kind !== 'asr'; })[0] || tracks.filter(function (t) { return /^en/.test(t.languageCode); })[0] || tracks[0];
      var r = await gm({ method: 'GET', url: tr.baseUrl + '&fmt=json3' });
      var srt = r.status === 200 ? json3ToSrt(r.responseText) : '';
      if (!srt) throw new Error('NEEDCC');
      return { srt: srt, lang: tr.languageCode };
    }
    var busyYT = false;
    function sendToSL(btn) {
      if (busyYT) return; busyYT = true;
      if (btn) btn.textContent = '⏳ 拿字幕…';
      grabCaptions().then(function (c) {
        var title = (document.title || '').replace(/\s*-\s*YouTube\s*$/, '');
        GM_setValue('sl_handoff', { t: Date.now(), sub: c.srt, subName: title + '.' + c.lang + '.srt', media: '', title: title, pos: 0 });
        GM_openInTab(SITE + 'sublingo.html#handoff', { active: true });
      }, function (e) {
        var msg = e.message === 'NEEDCC' ? '先点播放器上的「CC 字幕」按钮打开英文字幕，等字幕出来，再点一次' : e.message;
        try { toast(msg, 6000); } catch (x) { alert(msg); }
      }).then(function () { busyYT = false; if (btn) btn.textContent = '🎞️ SubLingo 精读'; });
    }
    // 篡改猴菜单里也放一个（万一页面上的按钮被网站挡住了）
    try { GM_registerMenuCommand('🎞️ 把这个视频的字幕送进 SubLingo', function () { sendToSL(null); }); } catch (e) { }
    ready(function () {
      var fab = null;
      function makeFab() {
        try {
          fab = document.createElement('button'); fab.className = 'fab'; fab.title = '把这个视频的字幕送进 SubLingo 逐句精读'; fab.textContent = '🎞️ SubLingo 精读'; root().appendChild(fab);
        } catch (e) {
          // 影子 DOM 用不了：直接挂在页面上
          console.log('[工具箱随身] 影子 DOM 不行，改直接挂按钮', e);
          fab = document.createElement('button'); fab.textContent = '🎞️ SubLingo 精读';
          fab.setAttribute('style', 'position:fixed;z-index:2147483645;right:16px;bottom:88px;background:#1D2430;color:#fff;border-radius:22px;padding:9px 14px;font-size:14px;border:0;cursor:pointer;box-shadow:0 4px 16px rgba(0,0,0,.3)');
          document.documentElement.appendChild(fab);
        }
        fab.onclick = function () { sendToSL(fab); };
      }
      function sync() {
        try {
          var on = !!vid();
          if (on && !fab) makeFab();
          if (fab) fab.style.display = on ? '' : 'none';
          if (fab && !fab.isConnected) { fab = null; }      // 被网站删掉了就重建
        } catch (e) { console.log('[工具箱随身] YouTube 按钮出错', e); }
      }
      sync(); setInterval(sync, 1500);
    });
  }

  /* =================== 2. 英文网页：选中一句 → 讲讲这句；选中一个词 → 存生词 =================== */
  var API = '';
  function api() { if (API) return Promise.resolve(API); return gjson(SITE + 'cf.json').then(function (j) { API = j.api; return API; }); }
  function explain(sentence, ctx) {
    var key = GM_getValue('key', '');
    if (!key) return Promise.reject(new Error('NOKEY'));
    var ck = 'ex:' + sentence.slice(0, 300), cache = GM_getValue('ex_cache', {});
    if (cache[ck]) return Promise.resolve(cache[ck]);
    return api().then(function (a) {
      return gm({ method: 'POST', url: a + '/explain', headers: { 'Content-Type': 'application/json', 'X-Tools-Key': key }, data: JSON.stringify({ sentence: sentence, context: ctx || '' }), timeout: 90000 });
    }).then(function (r) {
      var j = JSON.parse(r.responseText);
      if (r.status === 401) throw new Error('NOKEY');
      if (r.status !== 200) throw new Error(j.msg || ('出错了（' + r.status + '）'));
      var ks = Object.keys(cache); if (ks.length > 120) delete cache[ks[0]];
      cache[ck] = j; GM_setValue('ex_cache', cache);
      return j;
    });
  }
  function exHTML(j) {
    var h = '<div class="sec"><b>💬 意思</b>' + esc(j.meaning) + '</div>';
    if (j.trunk) h += '<div class="sec"><b>🌳 主干</b>' + esc(j.trunk) + '</div>';
    if (j.parts && j.parts.length) h += '<div class="sec"><b>🧩 结构</b>' + j.parts.map(function (p) { return '<div class="row"><span class="chip">' + esc(p.role) + '</span>' + esc(p.text) + (p.note ? '<div class="src" style="border:0;padding:0;margin:0">' + esc(p.note) + '</div>' : '') + '</div>'; }).join('') + '</div>';
    if (j.verbs && j.verbs.length) h += '<div class="sec"><b>⏱️ 动词</b>' + j.verbs.map(function (v) { return '<div class="row"><span class="chip">' + esc(v.text) + '</span>' + esc(v.form) + (v.why ? '：' + esc(v.why) : '') + '</div>'; }).join('') + '</div>';
    if (j.phrases && j.phrases.length) h += '<div class="sec"><b>🔗 短语</b>' + j.phrases.map(function (p) { return '<div class="row"><span class="chip">' + esc(p.text) + '</span>' + esc(p.meaning) + '</div>'; }).join('') + '</div>';
    if (j.tip) h += '<div class="sec"><b>💡 注意</b>' + esc(j.tip) + '</div>';
    return h;
  }
  function sentenceAround(sel) {
    try {
      var n = sel.anchorNode, blk = n && (n.nodeType === 3 ? n.parentNode : n);
      while (blk && blk.parentNode && /^(A|SPAN|B|I|EM|STRONG|MARK|CODE|SMALL|SUB|SUP|U)$/.test(blk.tagName)) blk = blk.parentNode;
      var txt = (blk && blk.innerText || '').replace(/\s+/g, ' '), w = sel.toString().trim();
      var i = txt.indexOf(w); if (i < 0) return { sent: w, ctx: '' };
      var st = Math.max(txt.lastIndexOf('. ', i), txt.lastIndexOf('? ', i), txt.lastIndexOf('! ', i)); st = st < 0 ? 0 : st + 2;
      var en = txt.slice(i + w.length).search(/[.?!](\s|$)/); en = en < 0 ? txt.length : i + w.length + en + 1;
      return { sent: txt.slice(st, en).trim().slice(0, 500), ctx: txt.slice(Math.max(0, st - 300), Math.min(txt.length, en + 300)) };
    } catch (e) { return { sent: sel.toString().trim(), ctx: '' }; }
  }
  var BUB = null, POP = null, LAST = null;
  function hideBub() { if (BUB) BUB.style.display = 'none'; }
  function closePop() { if (POP) { POP.remove(); POP = null; } }
  function place(e, x, y, w, hgt) { e.style.left = Math.max(8, Math.min(window.innerWidth - (w || 120) - 8, x)) + 'px'; e.style.top = Math.max(8, Math.min(window.innerHeight - (hgt || 40) - 8, y)) + 'px'; }
  function onSelect() {
    var sel = window.getSelection(), t = sel ? sel.toString().replace(/\s+/g, ' ').trim() : '';
    var a = document.activeElement;
    if (!t || t.length > 600 || (a && (/^(INPUT|TEXTAREA)$/.test(a.tagName) || a.isContentEditable))) { hideBub(); return; }
    var latin = (t.match(/[A-Za-z]/g) || []).length, cjk = (t.match(/[一-鿿]/g) || []).length;
    if (latin < 3 || cjk > latin / 4) { hideBub(); return; }
    var words = t.split(' ').filter(Boolean), single = words.length <= 2 && /^[A-Za-z][A-Za-z'\-]*( [A-Za-z][A-Za-z'\-]*)?$/.test(t);
    if (!single && words.length < 3) { hideBub(); return; }
    var r = sel.getRangeAt(0).getBoundingClientRect();
    LAST = { text: t, single: single, around: sentenceAround(sel) };
    if (!BUB) {
      BUB = mk('div', 'bub');
      BUB.addEventListener('mousedown', function (e) { e.preventDefault(); });
      BUB.addEventListener('click', function (e) { var b = e.target.closest('[data-a]'); if (b) act(b.getAttribute('data-a')); });
    }
    while (BUB.firstChild) BUB.removeChild(BUB.firstChild);
    if (single) mk('span', '', '⭐ 存进词库', BUB).setAttribute('data-a', 'save');
    mk('span', '', '📖 讲讲这句', BUB).setAttribute('data-a', 'ex');
    BUB.style.display = 'flex';
    place(BUB, r.left + r.width / 2 - 60, r.bottom + 8 > window.innerHeight - 40 ? r.top - 40 : r.bottom + 8, 200);
  }
  function act(a) {
    var L = LAST; if (!L) return; hideBub();
    if (a === 'save') {
      var w = L.text.toLowerCase(), box = GM_getValue('vocab_inbox', []);
      box.push({ w: w, en: L.around.sent, src: '🌐 ' + (document.title || host).slice(0, 60), t: Date.now() });
      GM_setValue('vocab_inbox', box.slice(-300));
      toast('⭐ 「' + w + '」存好了，打开工具箱的语境词库就会出现（连同这句例句）');
      return;
    }
    // 选了半句也按整句讲（整句太长就只讲选中的）
    var sent = L.single || (L.around.sent && L.around.sent.indexOf(L.text) >= 0 && L.around.sent.length <= 500) ? L.around.sent : L.text;
    closePop();
    POP = mk('div', 'pop'); var hd = mk('div', 'hd', null, POP); mk('b', '', '📖 讲讲这句', hd); mk('button', 'x', '✕', hd);
    mk('div', 'src', sent, POP); mk('div', 'body', '⏳ AI 正在读这句…（第一次大概 5–10 秒）', POP);
    POP.querySelector('.x').onclick = closePop;
    place(POP, window.innerWidth / 2 - 210, 70, 420, 400);
    explain(sent, L.around.ctx).then(function (j) {
      if (!POP) return;
      setHTML(POP.querySelector('.body'), exHTML(j) + '<div class="acts"><button class="btn btn2" data-sl="1">🎞️ 整篇送进 SubLingo</button></div>');
      var slb = POP.querySelector('[data-sl]') || mk('button', 'btn btn2', '🎞️ 整篇送进 SubLingo', POP);
      slb.onclick = function () {
        var art = (document.querySelector('article') || document.body).innerText.replace(/\n{3,}/g, '\n\n').slice(0, 30000);
        GM_setValue('sl_handoff', { t: Date.now(), art: art, title: document.title, src: location.href });
        GM_openInTab(SITE + 'sublingo.html#handoff', { active: true });
      };
    }, function (e) {
      if (!POP) return;
      setHTML(POP.querySelector('.body'), e.message === 'NOKEY'
        ? '<div class="err">🔑 先在这个浏览器打开一次<a href="' + SITE + '" target="_blank">工具箱首页</a>，输密码并勾「记住我」，再回来选一次。</div>'
        : '<div class="err">❌ ' + esc(e.message) + '</div>');
    });
  }
  document.addEventListener('mouseup', function (e) { if (ROOT && e.composedPath && e.composedPath().indexOf(ROOT) >= 0) return; setTimeout(onSelect, 10); });
  document.addEventListener('touchend', function () { setTimeout(onSelect, 300); });
  document.addEventListener('mousedown', function (e) { if (ROOT && e.composedPath && e.composedPath().indexOf(ROOT) >= 0) return; hideBub(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { closePop(); hideBub(); } });


  /* =================== 5. 任何网页：图片上「⬇ 原图」 =================== */
  // 把网站给的缩略图地址换成原图地址（常见网站的规律），再按顺序试，哪个能下就下哪个
  function origCandidates(img) {
    var list = [], src = img.currentSrc || img.src || '';
    function add(u) { if (u && /^https?:/i.test(u) && list.indexOf(u) < 0) list.push(u); }
    // srcset / 父级 <picture> 里最大的那张
    var best = '', bw = 0;
    var sets = [img.getAttribute('srcset') || ''];
    var pic = img.closest && img.closest('picture'); if (pic) [].forEach.call(pic.querySelectorAll('source[srcset]'), function (s) { sets.push(s.getAttribute('srcset')); });
    sets.join(',').split(/,\s+(?=\S)/).forEach(function (part) { var m = /^(\S+)\s+(\d+)w/.exec(part.trim()); if (m && +m[2] > bw) { bw = +m[2]; best = new URL(m[1], location.href).href; } });
    var u = best || src;
    try {
      var U = new URL(u, location.href), h = U.hostname;
      if (/pbs\.twimg\.com$/.test(h) && /\/media\//.test(U.pathname)) { U.searchParams.set('name', 'orig'); if (!U.searchParams.get('format')) { var e = /\.(\w+)$/.exec(U.pathname); if (!e) U.searchParams.set('format', 'jpg'); } add(U.href); }
      if (/pinimg\.com$/.test(h)) add(u.replace(/\/\d+x(\d+)?\//, '/originals/'));
      if (/sinaimg\.cn$/.test(h)) { add(u.replace(/\/(orj\d+|mw\d+|thumb\d+|bmiddle|small|square|crop\.[^/]+)\//, '/large/')); }
      if (/preview\.redd\.it$/.test(h)) add('https://i.redd.it' + U.pathname);
      if (/googleusercontent\.com$|ggpht\.com$/.test(h)) add(u.replace(/=[swh]\d+[^/]*$/, '=s0').replace(/\/[swh]\d+(-[a-z-]+)?\//, '/s0/'));
      if (/(^|\.)ytimg\.com$/.test(h)) add(u.replace(/\/(hq|mq|sd|hq720|maxres)?default(_live)?\.(jpg|webp)/, '/maxresdefault.jpg'));
      if (/(^|\.)cdninstagram\.com$|fbcdn\.net$/.test(h)) add(u);       // ins / 脸书：srcset 里最大的就是能拿到的最大
      if (/(^|\.)shopify\.com$/.test(h)) add(u.replace(/_(\d+x\d*|\d*x\d+|pico|icon|thumb|small|compact|medium|large|grande)(@\dx)?(?=\.\w+(\?|$))/, ''));
      if (/\/wp-content\/uploads\//.test(U.pathname)) add(u.replace(/-\d+x\d+(?=\.\w+(\?|$))/, '').replace(/-scaled(?=\.\w+)/, ''));
      if (/images\.unsplash\.com$/.test(h)) { var V = new URL(u); ['w', 'h', 'q', 'fit', 'crop', 'auto', 'ixlib', 'dpr'].forEach(function (k) { V.searchParams.delete(k); }); add(V.href); }
      if (/(^|\.)(media\.)?(cnn|nytimes|bbc|guim|reuters)\./.test(h) || /[?&](w|width|h|height|resize|quality|q)=\d/.test(U.search)) {
        var W = new URL(u); ['w', 'width', 'h', 'height', 'resize', 'quality', 'q', 'fit', 'crop', 'dpr', 'auto'].forEach(function (k) { W.searchParams.delete(k); }); add(W.href);
      }
    } catch (e) { }
    add(best); add(src);
    return list;
  }
  function extOf(ct, url) {
    var m = /image\/(jpeg|jpg|png|gif|webp|avif|bmp|svg\+xml|heic)/.exec(ct || '');
    if (m) return { jpeg: 'jpg', 'svg+xml': 'svg' }[m[1]] || m[1];
    m = /\.(jpe?g|png|gif|webp|avif|bmp)(?:[?#]|$)/i.exec(url); return m ? m[1].toLowerCase().replace('jpeg', 'jpg') : 'jpg';
  }
  function fetchImg(url) {
    return new Promise(function (res) {
      GM_xmlhttpRequest({ method: 'GET', url: url, responseType: 'blob', timeout: 60000, headers: { Referer: location.href },
        onload: function (r) {
          var ct = (/content-type:\s*([^\r\n;]+)/i.exec(r.responseHeaders || '') || [])[1] || (r.response && r.response.type) || '';
          res(r.status === 200 && r.response && r.response.size > 500 && /^image\//.test(ct) ? { blob: r.response, ct: ct } : null);
        }, onerror: function () { res(null); }, ontimeout: function () { res(null); } });
    });
  }
  function saveBlob(blob, name) {
    var a = document.createElement('a'), u = URL.createObjectURL(blob);
    a.href = u; a.download = name; a.style.display = 'none'; (document.body || document.documentElement).appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(u); a.remove(); }, 30000);
  }
  function fsize(n) { return n >= 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.round(n / 1024) + ' KB'; }
  async function downloadOriginal(img, btn) {
    var cands = origCandidates(img), got = null, used = '';
    for (var i = 0; i < cands.length && !got; i++) { got = await fetchImg(cands[i]); used = cands[i]; }
    if (!got) {   // 都下不了（防盗链之类）：至少把屏幕上这张存下来
      try {
        var c = document.createElement('canvas'); c.width = img.naturalWidth; c.height = img.naturalHeight; c.getContext('2d').drawImage(img, 0, 0);
        got = await new Promise(function (r) { c.toBlob(function (b) { r(b ? { blob: b, ct: 'image/png' } : null); }, 'image/png'); }); used = img.src;
      } catch (e) { }
    }
    if (!got) throw new Error('这张图下不了（网站不让外面读）');
    var base = '';
    try { base = decodeURIComponent(new URL(used).pathname.split('/').pop() || '').replace(/\.\w+$/, ''); } catch (e) { }
    if (!base || base.length < 3 || /^(image|img|photo|media|default|maxresdefault|large|orig)$/i.test(base)) base = (document.title || host).replace(/[\\/:*?"<>|]+/g, '_').slice(0, 40) + '_' + Date.now().toString(36);
    base = base.replace(/[\\/:*?"<>|]+/g, '_').slice(0, 80);
    saveBlob(got.blob, base + '.' + extOf(got.ct, used));
    var dim = '';
    try { var bm = await createImageBitmap(got.blob); dim = bm.width + '×' + bm.height + ' · '; bm.close && bm.close(); } catch (e) { }
    toast('✅ 已保存原图：' + dim + fsize(got.blob.size) + (used === (img.currentSrc || img.src) && cands.length > 1 ? '（这个网站没有更大的版本）' : ''));
  }
  var IMGBTN = null, IMGCUR = null, IMGT = 0;
  function imgBtn() {
    if (IMGBTN && IMGBTN.isConnected) return IMGBTN;
    IMGBTN = mk('button', 'bub'); IMGBTN.textContent = '⬇ 原图'; IMGBTN.style.display = 'none'; IMGBTN.style.padding = '4px 9px';
    IMGBTN.addEventListener('mouseenter', function () { clearTimeout(IMGT); });
    IMGBTN.addEventListener('mouseleave', function () { IMGT = setTimeout(function () { IMGBTN.style.display = 'none'; }, 400); });
    IMGBTN.addEventListener('click', function (e) {
      e.preventDefault(); e.stopPropagation();
      var img = IMGCUR; if (!img) return;
      IMGBTN.textContent = '⏳';
      downloadOriginal(img, IMGBTN).catch(function (er) { toast('❌ ' + er.message, 5000); }).then(function () { IMGBTN.textContent = '⬇ 原图'; });
    });
    return IMGBTN;
  }
  function findImg(t) {
    if (!t || !t.closest) return null;
    if (t.tagName === 'IMG') return t;
    // 推特、Ins 这类网站在图片上盖了一层透明的东西：往下找
    var r2 = t.getBoundingClientRect(), box = t;
    for (var k = 0; k < 5 && box; k++, box = box.parentElement) {
      var ims = box.querySelectorAll ? box.querySelectorAll('img') : [];
      for (var i = 0; i < ims.length && i < 6; i++) {
        var r1 = ims[i].getBoundingClientRect();
        if (Math.abs(r1.width - r2.width) < 40 && Math.abs(r1.height - r2.height) < 40 && Math.abs(r1.left - r2.left) < 40 && Math.abs(r1.top - r2.top) < 40) return ims[i];
      }
    }
    return null;
  }
  document.addEventListener('mouseover', function (e) {
    if (ROOT && e.composedPath && e.composedPath().indexOf(ROOT) >= 0) return;
    var img = findImg(e.target); if (!img) return;
    var r = img.getBoundingClientRect();
    if (r.width < 160 || r.height < 120) return;
    clearTimeout(IMGT); IMGCUR = img;
    var b = imgBtn(); b.style.display = 'flex';
    b.style.left = Math.max(4, Math.min(window.innerWidth - 80, r.right - 78)) + 'px';
    b.style.top = Math.max(4, Math.min(window.innerHeight - 34, r.top + 8)) + 'px';
  }, true);
  document.addEventListener('mouseout', function (e) {
    if (!IMGBTN || IMGBTN.style.display === 'none') return;
    if (findImg(e.target) === IMGCUR) { IMGT = setTimeout(function () { if (IMGBTN) IMGBTN.style.display = 'none'; }, 500); }
  }, true);
  window.addEventListener('scroll', function () { if (IMGBTN) IMGBTN.style.display = 'none'; }, true);

  /* =================== 3. 股票页：显示你的股票池信号 =================== */
  function tickerHere() {
    var m;
    if (/finance\.yahoo\.com$/.test(host) && (m = /\/quote\/([A-Z.\-^=]{1,10})/i.exec(path))) return m[1].toUpperCase();
    if (/tradingview\.com$/.test(host)) {
      if ((m = /\/symbols\/(?:[A-Z]+-)?([A-Z.]{1,10})\/?/i.exec(path))) return m[1].toUpperCase();
      if ((m = /[?&]symbol=(?:[A-Z]+(?:%3A|:))?([A-Z.]{1,10})/i.exec(location.search))) return m[1].toUpperCase();
    }
    if (/finviz\.com$/.test(host) && (m = /[?&]t=([A-Z.\-]{1,10})/i.exec(location.search))) return m[1].toUpperCase();
    return '';
  }
  if (/finance\.yahoo\.com$|tradingview\.com$|finviz\.com$/.test(host)) {
    var DATA = null, shown = '', card = null;
    function pct(x) { return x == null ? '—' : (x >= 0 ? '+' : '') + (x * 100).toFixed(1) + '%'; }
    function load() { if (DATA) return Promise.resolve(DATA); return Promise.all([gjson(SITE + 'stocks/data/snap.json'), gjson(SITE + 'stocks/data/latest.json')]).then(function (a) { DATA = { snap: a[0], latest: a[1] }; return DATA; }); }
    function show(t) {
      load().then(function (D) {
        var r = (D.snap.rows || {})[t], cand = (D.latest.candidates || []).filter(function (c) { return c.t === t; })[0];
        var tl = D.latest.tracking || []; tl = Array.isArray(tl) ? tl : (tl.rows || []);
        var trk = tl.filter(function (c) { return c.t === t && c.status !== '已结束'; })[0];
        if (!card) {
          card = mk('div', 'pop'); card.setAttribute('style', 'width:min(300px,calc(100vw - 20px));right:16px;left:auto;top:auto;bottom:90px;padding:10px 12px');
        }
        var h = '<div class="hd"><b>📈 ' + esc(t) + ' · 我的股票池</b><button class="x">✕</button></div>';
        if (!r && !cand) h += '<div class="src" style="border:0;padding:0">不在扫描范围里（扫的是标普 500 + 你的关注列表）。</div>';
        if (cand) h += '<div class="row ok"><b>🔥 今天的候选</b>：' + esc((cand.tags || []).join('、') || cand.primary || '') + (cand.stop ? '<br>止损 ' + esc(cand.stop) + (cand.target ? ' · 目标 ' + esc(cand.target) : '') : '') + '</div>';
        if (trk) h += '<div class="row">👀 信号跟踪中：' + esc(trk.date || '') + ' 入选（' + esc(trk.sig || '') + '），至今 ' + pct(trk.ret) + '</div>';
        if (r) {
          h += '<div class="row">' + esc(r.n || '') + (r.s ? ' · ' + esc(r.s) : '') + '</div>' +
            '<div class="row"><span class="chip">今天 ' + pct(r.d) + '</span><span class="chip">1 月 ' + pct(r.m1) + '</span><span class="chip">1 年 ' + pct(r.y) + '</span></div>' +
            '<div class="row"><span class="chip">RSI ' + (r.rsi != null ? r.rsi : '—') + '</span><span class="chip">相对强度 ' + (r.rs != null ? r.rs : '—') + '</span><span class="chip">离一年高点 ' + pct(r.h) + '</span></div>' +
            '<div class="row">' + (r.a50 ? '✅ 在 50 日线上' : '⚠️ 在 50 日线下') + ' · ' + (r.a200 ? '✅ 在 200 日线上' : '⚠️ 在 200 日线下') + '</div>' +
            (r.sig && r.sig.length ? '<div class="row ok">📣 信号：' + esc(r.sig.join('、')) + '</div>' : '');
        }
        h += '<div class="src" style="border:0;padding:0;margin-top:4px">数据日期 ' + esc(D.snap.date || '') + '</div>' +
          '<div class="acts"><button class="btn" data-al="1">🔔 设提醒</button><a class="btn btn2" style="text-decoration:none" href="' + SITE + 'stocks.html" target="_blank">打开股票池</a></div>';
        setHTML(card, h); card.style.display = 'block';
        var cx = card.querySelector('.x'); if (cx) cx.onclick = function () { card.style.display = 'none'; };
        var alb = card.querySelector('[data-al]') || mk('button', 'btn', '🔔 设提醒', card);
        alb.onclick = function () {
          var v = prompt('「' + t + '」什么时候提醒你？\n写「跌到 650」或「涨到 900」（价格），或者「回撤 10」（离高点跌 10%）', '跌到 ');
          if (!v) return;
          var m = /(跌到|涨到|回撤|单日涨跌)\s*([\d.]+)/.exec(v); if (!m) { alert('没看懂，照「跌到 650」这样写'); return; }
          var title = '股价提醒: ' + t + ' ' + m[1] + ' ' + m[2];
          GM_openInTab('https://github.com/boliunew/tools/issues/new?template=stock-alert.yml&labels=stock-alert&title=' + encodeURIComponent(title) + '&ticker=' + encodeURIComponent(t) + '&cond=' + encodeURIComponent(m[1]) + '&value=' + encodeURIComponent(m[2]), { active: true });
          toast('在打开的 GitHub 页面点「Create」就登记好了，盘中会推到 Telegram');
        };
      }).catch(function () { });
    }
    ready(function () { setInterval(function () { var t = tickerHere(); if (t && t !== shown) { shown = t; show(t); } }, 1500); });
  }

  /* =================== 4. 推特：图片 / 视频一键下到 torrent_hub =================== */
  if (/(^|\.)(x|twitter)\.com$/.test(host)) {
    function thPush(items) {
      return items.reduce(function (p, it) {
        return p.then(function (ids) {
          return gm({ method: 'POST', url: TH + '/jsonrpc', headers: { 'Content-Type': 'application/json' }, timeout: 8000,
            data: JSON.stringify({ jsonrpc: '2.0', id: Date.now(), method: 'aria2.addUri', params: [[it.url], { out: it.out }] }) })
            .then(function (r) { var j = JSON.parse(r.responseText); if (!j.result) throw new Error((j.error && j.error.message) || '没收下'); return ids.concat(j.result); });
        });
      }, Promise.resolve([]));
    }
    async function grabX(id) {
      var r = await gm({ method: 'GET', url: 'https://api.fxtwitter.com/status/' + id });
      var d = JSON.parse(r.responseText), t = d.tweet; if (!t) throw new Error('读不到这条帖子');
      var all = (t.media && (t.media.all || [].concat(t.media.photos || [], t.media.videos || []))) || [];
      if (!all.length && t.quote && t.quote.media) all = t.quote.media.all || [];
      var who = t.author ? t.author.screen_name : 'x';
      return all.map(function (m, i) {
        var url = m.url, ext = 'jpg';
        if (m.type === 'photo') { var b = m.url.split('?')[0]; url = /pbs\.twimg\.com\/media\//.test(b) ? b + '?name=orig' : m.url; ext = (/\.(png|webp)$/.exec(b) || [, 'jpg'])[1]; }
        else { var vs = (m.variants || []).filter(function (v) { return /mp4/.test(v.content_type || v.url || ''); }).sort(function (a, b) { return (b.bitrate || 0) - (a.bitrate || 0); }); if (vs.length) url = vs[0].url; ext = 'mp4'; }
        return { url: url, out: 'X推特/' + who + '_' + id + (all.length > 1 ? '_' + (i + 1) : '') + '.' + ext };
      });
    }
    function decorate() {
      var arts = document.querySelectorAll('article[data-testid="tweet"]:not([data-tbx])');
      for (var i = 0; i < arts.length; i++) {
        var a = arts[i]; a.setAttribute('data-tbx', '1');
        if (!a.querySelector('[data-testid="tweetPhoto"], video, [data-testid="videoPlayer"]')) continue;
        var link = a.querySelector('a[href*="/status/"] time'); link = link && link.closest('a');
        var m = link && /\/status\/(\d+)/.exec(link.getAttribute('href')); if (!m) continue;
        var bar = a.querySelector('[role="group"]'); if (!bar) continue;
        var b = document.createElement('button');
        b.textContent = '📥'; b.title = '下到电脑（torrent_hub）';
        b.setAttribute('style', 'border:0;background:transparent;cursor:pointer;font-size:17px;padding:0 8px;opacity:.75');
        (function (b, id) {
          b.onclick = function (e) {
            e.preventDefault(); e.stopPropagation(); b.textContent = '⏳';
            grabX(id).then(function (items) { if (!items.length) throw new Error('这条没有图片或视频'); return thPush(items).then(function (ids) { b.textContent = '✅'; toast('📥 已推送 ' + ids.length + ' 个到 torrent_hub（下载目录的「X推特」文件夹）'); }); })
              .catch(function (er) { b.textContent = '📥'; toast(/网络请求失败|超时/.test(er.message) ? '连不上 torrent_hub：电脑上先把它打开' : '❌ ' + er.message, 5000); });
          };
        })(b, m[1]);
        bar.appendChild(b);
      }
    }
    ready(function () { new MutationObserver(function () { decorate(); }).observe(document.body, { childList: true, subtree: true }); decorate(); });
  }
  if (/(^|\.)instagram\.com$/.test(host)) {
    ready(function () {
      var fab = null;
      setInterval(function () {
        var on = /^\/(p|reel|reels|tv)\//.test(location.pathname);
        if (on && !fab) { fab = document.createElement('button'); fab.className = 'fab'; fab.textContent = '📥 用工具箱下载'; root().appendChild(fab); fab.onclick = function () { GM_openInTab(SITE + 'media.html?url=' + encodeURIComponent(location.href.split('?')[0]), { active: true }); }; }
        if (fab) fab.style.display = on ? '' : 'none';
      }, 1500);
    });
  }
})();
