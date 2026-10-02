/* 🏠 Home-server sync. On GitHub Pages this file does nothing.
   When the site is served by selfhost/server.py (your mini PC), the progress pages keep in the browser
   (语境词库, 自选股, 购物清单, 收藏的电台 …) is mirrored to the server, so phone and computer see the same thing.
   Rule: per key, the newest write wins. Loaded synchronously in <head>, before the page reads its data. ES5. */
(function () {
  'use strict';
  var host = location.hostname || '';
  window.TOOLS_LOCAL = !(/github\.io$/i.test(host) || location.protocol === 'file:');
  if (!window.TOOLS_LOCAL || window.__toolsSync) return;
  window.__toolsSync = 1;
  var ls;
  try { ls = window.localStorage; ls.getItem('x'); } catch (e) { return; }
  var SKIP = /^(sync:|tnav:|home:unlock$|tb:v:|deals:lite$)|cache/i, MAX = 3 * 1024 * 1024;
  var base = (function () { var p = location.pathname; return p.slice(0, p.lastIndexOf('/') + 1); })();
  var setI = Storage.prototype.setItem, rmI = Storage.prototype.removeItem, getI = Storage.prototype.getItem;
  function mtKey(k) { return 'sync:mt:' + k; }
  function localMt(k) { return +getI.call(ls, mtKey(k)) || 0; }
  function syncable(k) { return k && !SKIP.test(k); }

  function req(method, url, body, async, cb) {
    try {
      var x = new XMLHttpRequest();
      x.open(method, base + url, async);
      if (body) x.setRequestHeader('Content-Type', 'application/json');
      if (async) x.onload = function () { cb && cb(x.status, x.responseText); };
      if (async) x.onerror = function () { cb && cb(0, ''); };
      x.send(body ? JSON.stringify(body) : null);
      if (!async) return x.status === 200 ? JSON.parse(x.responseText) : null;
    } catch (e) { if (async && cb) cb(0, ''); }
    return null;
  }

  /* 1. pull: anything newer on the server replaces the copy in this browser (before the page starts) */
  var server = req('GET', 'api/kv', null, false) || {}, want = [], k, i;
  for (k in server) if (server.hasOwnProperty(k) && syncable(k) && server[k] > localMt(k)) want.push(k);
  if (want.length) {
    var got = req('GET', 'api/kv?keys=' + encodeURIComponent(want.join(',')), null, false) || {};
    for (k in got) if (got.hasOwnProperty(k)) {
      try {
        if (got[k].v == null) rmI.call(ls, k); else setI.call(ls, k, got[k].v);
        setI.call(ls, mtKey(k), String(got[k].mt));
      } catch (e) { }
    }
  }

  /* 2. push: what this browser has that the server lacks or has older (first visit after the move, offline edits) */
  var dirty = {}, timer = null;
  for (i = 0; i < ls.length; i++) {
    k = ls.key(i);
    if (!syncable(k)) continue;
    var m = localMt(k);
    if (!(k in server) || m > server[k]) dirty[k] = 1;
  }
  function payload() {
    var out = {}, n = 0, key;
    for (key in dirty) if (dirty.hasOwnProperty(key)) {
      var v = getI.call(ls, key);
      if (v != null && v.length > MAX) continue;
      out[key] = { v: v, mt: localMt(key) || 1 }; n++;
    }
    return n ? out : null;
  }
  function push() {
    clearTimeout(timer); timer = null;
    var body = payload(); if (!body) return;
    var sent = dirty; dirty = {};
    req('POST', 'api/kv', body, true, function (st) { if (st !== 200) { for (var kk in sent) if (sent.hasOwnProperty(kk)) dirty[kk] = 1; } });
  }
  function soon() { clearTimeout(timer); timer = setTimeout(push, 1200); }
  if (payload()) soon();

  /* 3. watch writes: every setItem / removeItem on a synced key is stamped and pushed shortly after */
  Storage.prototype.setItem = function (key, val) {
    setI.call(this, key, val);
    if (this === ls && syncable(key)) { setI.call(ls, mtKey(key), String(Date.now())); dirty[key] = 1; soon(); }
  };
  Storage.prototype.removeItem = function (key) {
    rmI.call(this, key);
    if (this === ls && syncable(key)) { setI.call(ls, mtKey(key), String(Date.now())); dirty[key] = 1; soon(); }
  };
  function flush() {
    var body = payload(); if (!body) return;
    dirty = {};
    try { if (navigator.sendBeacon && navigator.sendBeacon(base + 'api/kv', new Blob([JSON.stringify(body)], { type: 'application/json' }))) return; } catch (e) { }
    req('POST', 'api/kv', body, true);
  }
  document.addEventListener('visibilitychange', function () { if (document.hidden) flush(); });
  window.addEventListener('pagehide', flush);
  // coming back to a tab that was open in the background: reload if another device changed something
  var lastCheck = Date.now();
  document.addEventListener('visibilitychange', function () {
    if (document.hidden || Date.now() - lastCheck < 30000) return;
    lastCheck = Date.now();
    req('GET', 'api/kv', null, true, function (st, txt) {
      if (st !== 200) return;
      var s; try { s = JSON.parse(txt); } catch (e) { return; }
      for (var kk in s) if (s.hasOwnProperty(kk) && syncable(kk) && s[kk] > localMt(kk) && !dirty[kk]) {
        if (!document.querySelector('.dw,.am.on,.sheet.on')) location.reload();   // don't interrupt an open card / dialog
        return;
      }
    });
  });
})();
