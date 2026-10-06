/* 点词查词小面板：WordSheet.open(词, 所在句子, 来源)
   查本站 dict/en 词典（离线也能用，打开过就缓存），能朗读，能一键收进语境词库（和 SubLingo 用同一个收件箱）。
   页面里给要点的词加 data-w 属性，再调用 WordSheet.bind(容器, 取句子的函数) 即可。 */
(function () {
  'use strict';
  if (window.WordSheet) return;
  var DICT = {}, Q = {}, VOICE = null, sheet = null, CUR = null;
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function css() {
    var st = document.createElement('style');
    st.textContent = '.ws-mask{position:fixed;left:0;top:0;right:0;bottom:0;background:rgba(0,0,0,.25);z-index:90}' +
      '.ws{position:fixed;left:0;right:0;bottom:0;z-index:91;background:var(--paper,#fff);color:var(--ink,#111);border-radius:18px 18px 0 0;box-shadow:0 -6px 30px rgba(0,0,0,.18);padding:14px 18px calc(16px + env(safe-area-inset-bottom));max-height:70vh;overflow:auto;max-width:680px;margin:0 auto;font-size:15px;line-height:1.55}' +
      '.ws h4{margin:0;font-size:22px;font-family:Georgia,serif;display:flex;align-items:center;gap:8px}' +
      '.ws h4 button{border:0;background:var(--chip,#eee);border-radius:999px;width:34px;height:34px;font-size:16px;cursor:pointer}' +
      '.ws .ph{color:var(--faint,#999);font-size:14px;margin-left:2px}.ws .via{font-size:12.5px;color:var(--faint,#999);margin-top:2px}' +
      '.ws .zh{margin-top:8px}.ws .zh b{color:var(--accent,#1F6F66);margin-right:4px}' +
      '.ws .sent{margin-top:10px;font-size:13.5px;color:var(--soft,#666);font-family:Georgia,serif;border-left:3px solid var(--line,#ddd);padding-left:9px}' +
      '.ws .sent mark{background:transparent;color:var(--ink,#111);font-weight:700;border-bottom:2px solid var(--accent,#1F6F66)}' +
      '.ws .acts{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}' +
      '.ws .acts button,.ws .acts a{border:1px solid var(--line,#ddd);background:var(--paper,#fff);color:var(--ink,#111);border-radius:10px;padding:7px 12px;font-size:13.5px;text-decoration:none;cursor:pointer}' +
      '.ws .acts .pri{background:var(--accent,#1F6F66);border-color:var(--accent,#1F6F66);color:var(--accent-ink,#fff);font-weight:600}' +
      '[data-w]{cursor:pointer;border-radius:3px}[data-w]:active,[data-w].ws-on{background:var(--accent-soft,#DCEEEA)}';
    document.head.appendChild(st);
  }
  function pickVoice() {
    if (!window.speechSynthesis) return;
    var vs = speechSynthesis.getVoices() || [], i;
    for (i = 0; i < vs.length; i++) if (vs[i].lang === 'en-US' || vs[i].lang === 'en_US') { VOICE = vs[i]; return; }
    for (i = 0; i < vs.length; i++) if (/^en/i.test(vs[i].lang)) { VOICE = vs[i]; return; }
  }
  if (window.speechSynthesis) { pickVoice(); try { speechSynthesis.addEventListener('voiceschanged', pickVoice); } catch (e) { } }
  function speak(t, rate) {
    if (!window.speechSynthesis || !t) return;
    try { speechSynthesis.cancel(); var u = new SpeechSynthesisUtterance(t); u.lang = 'en-US'; if (VOICE) u.voice = VOICE; u.rate = rate || 0.95; speechSynthesis.speak(u); } catch (e) { }
  }
  function shard(w) { return (w.slice(0, 2) + '__').slice(0, 2).replace(/[^a-z]/g, '_'); }
  function load(p, cb) {
    if (DICT[p]) { cb(DICT[p]); return; }
    if (Q[p]) { Q[p].push(cb); return; }
    Q[p] = [cb];
    var x = new XMLHttpRequest(); x.open('GET', 'dict/en/' + p + '.json');
    x.onload = function () { var d = {}; if (x.status === 200) { try { d = JSON.parse(x.responseText); } catch (e) { } } DICT[p] = d; var q = Q[p]; delete Q[p]; for (var i = 0; i < q.length; i++) q[i](d); };
    x.onerror = function () { var q = Q[p]; delete Q[p]; for (var i = 0; i < q.length; i++) q[i](null); };
    x.send();
  }
  // 候选：原词 → 去掉常见词尾猜原形
  function cands(w) {
    var out = [w], m;
    if ((m = /^(.+)'s$/.exec(w))) out.push(m[1]);
    if ((m = /^(.+)ies$/.exec(w))) out.push(m[1] + 'y');
    if ((m = /^(.+)(es|s)$/.exec(w))) { out.push(m[1] + (m[2] === 'es' ? 'e' : '')); if (m[2] === 'es') out.push(m[1]); }
    if ((m = /^(.+)ied$/.exec(w))) out.push(m[1] + 'y');
    if ((m = /^(.+)ed$/.exec(w))) { out.push(m[1], m[1] + 'e'); if (/(.)\1$/.test(m[1])) out.push(m[1].slice(0, -1)); }
    if ((m = /^(.+)ing$/.exec(w))) { out.push(m[1], m[1] + 'e'); if (/(.)\1$/.test(m[1])) out.push(m[1].slice(0, -1)); }
    if ((m = /^(.+)(er|est)$/.exec(w))) out.push(m[1], m[1] + 'e');
    if ((m = /^(.+)ly$/.exec(w))) out.push(m[1]);
    return out;
  }
  function get(list, cb, via) {
    if (!list.length) { cb(null); return; }
    var w = list[0];
    if (!/^[a-z]/.test(w)) { get(list.slice(1), cb, via); return; }
    load(shard(w), function (d) {
      var e = d && d[w];
      if (typeof e === 'string' && e.charAt(0) === '@') { get([e.slice(1)], cb, via || w); return; }
      if (e) { cb({ w: w, e: e, via: via || '' }); return; }
      get(list.slice(1), cb, via);
    });
  }
  function inVocab(w) { try { var d = JSON.parse(localStorage.getItem('ctxvocab-v1') || '{}'); var c = d.cards && d.cards[w]; return !c ? '' : c.k ? '已掌握' : '学习中'; } catch (e) { return ''; } }
  function close() { if (sheet) { document.body.removeChild(sheet.m); document.body.removeChild(sheet.s); sheet = null; } var on = document.querySelector('.ws-on'); if (on) on.className = on.className.replace(/\s*ws-on/, ''); }
  function render(r, orig, sent, src) {
    var h = '', w = r ? r.w : orig.toLowerCase();
    h += '<h4>' + esc(w) + (r && r.e[0] ? '<span class="ph">/' + esc(r.e[0]) + '/</span>' : '') + '<button data-a="say" aria-label="朗读">🔊</button></h4>';
    if (r && (r.via || orig.toLowerCase() !== r.w)) h += '<div class="via">' + esc(r.via || orig) + ' → 原形 <b>' + esc(r.w) + '</b></div>';
    if (!r) h += '<div class="zh">本地词典里没有这个词。</div>';
    else {
      h += '<div class="zh">';
      var zh = (r.e[1] || '').split('\n');
      for (var i = 0; i < zh.length && i < 5; i++) { var m = /^([a-z]+\.(?:\s*[a-z]+\.)?)\s*(.*)$/i.exec(zh[i]); h += '<div>' + (m ? '<b>' + esc(m[1]) + '</b>' + esc(m[2]) : esc(zh[i])) + '</div>'; }
      h += '</div>';
    }
    if (sent) {
      var re = new RegExp('\\b(' + orig.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')\\b', 'i');
      h += '<div class="sent">' + esc(sent).replace(re, '<mark>$1</mark>') + '</div>';
    }
    var st = inVocab(w);
    h += '<div class="acts">' + (sent ? '<button data-a="sent">🔊 读整句</button>' : '') +
      '<button class="pri" data-a="add">' + (st ? '✓ ' + st + '（加这句为新语境）' : '＋ 收进语境词库') + '</button>' +
      '<a href="https://www.oxfordlearnersdictionaries.com/search/english/?q=' + encodeURIComponent(w) + '" target="_blank" rel="noopener">牛津词典</a>' +
      '<button data-a="x">关闭</button></div>';
    sheet.s.innerHTML = h;
    CUR = { w: w, r: r, sent: sent, src: src };
  }
  function add(btn) {
    var c = CUR; if (!c) return;
    var r = c.r, forms = [];
    if (r && r.e[6]) { var p = r.e[6].split('/'); for (var i = 0; i < p.length; i++) { var kv = p[i].split(':'); if (kv[1] && /^[pdi3sr]$/.test(kv[0])) forms.push(kv[1]); } }
    var item = { w: c.w, en: c.sent || '', src: c.src || '', ph: r ? r.e[0] : '', zh: r ? r.e[1].split('\n').slice(0, 3).join('\n') : '', forms: forms, t: Date.now() };
    try {
      var box = JSON.parse(localStorage.getItem('ctxvocab-inbox') || '[]'); box.push(item); localStorage.setItem('ctxvocab-inbox', JSON.stringify(box));
      btn.textContent = '✓ 已收进，打开词库时自动加入'; btn.disabled = true;
    } catch (e) { btn.textContent = '保存失败（浏览器存储不可用）'; }
  }
  function open(word, sent, src) {
    var orig = String(word || '').replace(/[’]/g, "'").replace(/^[^A-Za-z]+|[^A-Za-z']+$/g, '').replace(/'+$/, '');
    if (!orig) return;
    close();
    if (!document.getElementById('ws-css')) { css(); var mk = document.createElement('i'); mk.id = 'ws-css'; mk.hidden = true; document.body.appendChild(mk); }
    var m = document.createElement('div'); m.className = 'ws-mask';
    var s = document.createElement('div'); s.className = 'ws'; s.innerHTML = '<h4>' + esc(orig) + '</h4><div class="zh">查词中…</div>';
    document.body.appendChild(m); document.body.appendChild(s);
    sheet = { m: m, s: s };
    m.onclick = close;
    s.onclick = function (e) {
      var a = e.target.getAttribute && e.target.getAttribute('data-a');
      if (a === 'x') close(); else if (a === 'say' && CUR) speak(CUR.w, 0.85); else if (a === 'sent' && CUR) speak(CUR.sent); else if (a === 'add') add(e.target);
    };
    speak(orig.toLowerCase(), 0.85);
    get(cands(orig.toLowerCase()), function (r) { if (sheet && sheet.s === s) render(r, orig, sent, src); });
  }
  // 把一段英文切成可点的词
  function wrap(text) {   // split first, then escape — escaping first would turn &quot; into a clickable "quot"
    var parts = String(text == null ? '' : text).split(/([A-Za-z][A-Za-z'’-]*)/), out = '', i;
    for (i = 0; i < parts.length; i++) out += i % 2 ? '<span data-w="' + esc(parts[i]) + '">' + esc(parts[i]) + '</span>' : esc(parts[i]);
    return out;
  }
  function sentenceAround(text, word) {
    var parts = String(text).match(/[^.!?]+[.!?]*["”’)]*\s*/g) || [text];
    for (var i = 0; i < parts.length; i++) if (new RegExp('\\b' + word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b').test(parts[i])) return parts[i].replace(/^\s+|\s+$/g, '');
    return String(text).slice(0, 200);
  }
  function bind(root, getCtx) {
    root.addEventListener('click', function (e) {
      var el = e.target;
      if (!el.getAttribute || el.getAttribute('data-w') == null) return;
      e.preventDefault(); e.stopPropagation();
      el.className += ' ws-on';
      var ctx = getCtx ? getCtx(el) : null, w = el.getAttribute('data-w');
      open(w, ctx && ctx.text ? sentenceAround(ctx.text, w) : '', ctx ? ctx.src : '');
    });
  }
  window.WordSheet = { open: open, close: close, wrap: wrap, bind: bind, speak: speak, sentenceAround: sentenceAround };
})();
