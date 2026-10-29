// ==UserScript==
// @name         🧰 工具箱助手
// @namespace    https://boliunew.github.io/tools/
// @version      1.0.2
// @description  让「我的工具」网页直接读取夸克分享、拿下载地址、推送到 torrent_hub、把字幕交给 SubLingo。只在工具箱页面上工作。
// @author       boliunew
// @match        https://boliunew.github.io/tools/*
// @match        http://localhost:*/*
// @match        http://127.0.0.1:*/*
// @match        https://pan.quark.cn/*
// @connect      quark.cn
// @connect      localhost
// @connect      127.0.0.1
// @grant        GM_xmlhttpRequest
// @grant        GM_cookie
// @grant        GM_getValue
// @grant        GM_setValue
// @run-at       document-start
// @updateURL    https://boliunew.github.io/tools/tbx.user.js
// @downloadURL  https://boliunew.github.io/tools/tbx.user.js
// ==/UserScript==

/* 工作方式：工具箱页面发 document 事件「tbx-req」（detail 是 JSON 字符串 {id, op, args}），
   这个脚本用油猴的跨站请求（带上你在夸克的登录状态）去办，办完发「tbx-res」回去。
   只做这几件事：读夸克分享、拿夸克下载地址、读夸克上的字幕文本、推给本机 torrent_hub。别的网站一概不碰。 */
(function () {
  'use strict';
  // 在夸克网盘网页上：只记下 __pugs 这一个 cookie（夸克下载地址认它），别的什么都不做
  if (location.hostname === 'pan.quark.cn') {
    var grab = function () { var m = /(?:^|;\s*)__pugs=([^;]+)/.exec(document.cookie || ''); if (m) { GM_setValue('quark_pugs_jar', m[1]); GM_setValue('quark_pugs_at', Date.now()); } };
    grab(); setTimeout(grab, 3000); setTimeout(grab, 10000);
    return;
  }
  var VER = '1.0.2';
  var UA_PC = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 QuarkPC/6.9.7.761 QuarkCloudDrivePC/6.9.7.761 quark-cloud-drive/2.5.40';
  var API = 'https://drive-pc.quark.cn/1/clouddrive/';
  var Q = '?pr=ucpro&fr=pc&sys=win32&ve=6.9.7.761';

  function gm(opt) {
    return new Promise(function (resolve, reject) {
      GM_xmlhttpRequest({
        method: opt.method || 'GET', url: opt.url, headers: opt.headers || {}, data: opt.data, anonymous: false, timeout: opt.timeout || 30000,
        onload: function (r) { resolve(r); },
        onerror: function (e) { reject(new Error('网络请求失败' + (e && e.error ? '：' + e.error : ''))); },
        ontimeout: function () { reject(new Error('请求超时')); }
      });
    });
  }
  function hdrs(raw) {
    var o = {};
    String(raw || '').split(/\r?\n/).forEach(function (l) { var i = l.indexOf(':'); if (i > 0) { var k = l.slice(0, i).trim().toLowerCase(); o[k] = o[k] ? o[k] + '\n' + l.slice(i + 1).trim() : l.slice(i + 1).trim(); } });
    return o;
  }
  function okHost(u, re) { var m = /^https?:\/\/([^\/:?#]+)/i.exec(u || ''); return !!(m && re.test(m[1])); }
  var QUARK = /(^|\.)quark\.cn$/i, LOCAL = /^(localhost|127\.0\.0\.1)$/i;

  // ---- 夸克的登录 cookie：油猴支持 GM_cookie 就整串读出来（推给 torrent_hub 下载时要带上）
  function quarkCookies() {
    return new Promise(function (resolve) {
      try {
        if (typeof GM_cookie === 'undefined' || !GM_cookie.list) return resolve('');
        GM_cookie.list({ url: 'https://drive-pc.quark.cn/' }, function (list, err) {
          if (err || !list || !list.length) return resolve('');
          resolve(list.map(function (c) { return c.name + '=' + c.value; }).join('; '));
        });
        setTimeout(function () { resolve(''); }, 3000);
      } catch (e) { resolve(''); }
    });
  }
  // 下载地址和 __pugs 绑在一起：优先用浏览器里真正的那个（打开夸克网页时记下的），没有才用接口回给的
  var LASTSET = '';
  function pugs(set) { if (set) GM_setValue('quark_pugs', set); return GM_getValue('quark_pugs_jar', '') || GM_getValue('quark_pugs', ''); }
  function grabPugs(r) {
    var sc = hdrs(r.responseHeaders)['set-cookie'] || '';
    var m = /__pugs=([^;\s]+)/.exec(sc);
    if (m) { pugs(m[1]); LASTSET = m[1]; }
  }
  async function qjson(method, path, body, extra) {
    var h = Object.assign({ 'Accept': 'application/json, text/plain, */*', 'Referer': 'https://pan.quark.cn/', 'Origin': 'https://pan.quark.cn' }, extra || {});
    if (body) h['Content-Type'] = 'application/json;charset=UTF-8';
    var r = await gm({ method: method, url: (/^https?:/.test(path) ? path : API + path), headers: h, data: body ? JSON.stringify(body) : undefined });
    grabPugs(r);
    var j = null; try { j = JSON.parse(r.responseText); } catch (e) { }
    if (!j) throw new Error('夸克返回了看不懂的内容（HTTP ' + r.status + '）');
    if (j.code === 31001) throw new Error('要先在这个浏览器里登录夸克网盘（打开 pan.quark.cn 登录一次）');
    if (j.code !== 0) {
      var msg = j.message || '';
      if (/passcode|提取码|密码/i.test(msg) || j.code === 41008) msg = '提取码不对或者没填';
      else if (j.code === 41012 || /expire|失效|过期/i.test(msg)) msg = '这个分享已经失效了';
      else if (j.code === 41004 || /not.?exist|不存在|删除/i.test(msg)) msg = '分享不存在或者被删了';
      else if (j.code === 23018) msg = '文件太大，游客拿不到地址：在这个浏览器登录夸克网盘再试';
      var e = new Error(msg + '（代码 ' + j.code + '）'); e.code = j.code; throw e;
    }
    return j;
  }

  // ---- 读分享：拿 stoken，再列文件
  var STOKEN = {};
  async function stoken(pwd_id, passcode) {
    var k = pwd_id + '|' + (passcode || '');
    if (STOKEN[k]) return STOKEN[k];
    var j = await qjson('POST', 'share/sharepage/token' + Q, { pwd_id: pwd_id, passcode: passcode || '' });
    STOKEN[k] = { stoken: j.data.stoken, title: j.data.title || '', author: (j.data.author && j.data.author.nick_name) || '' };
    return STOKEN[k];
  }
  async function list(a) {
    var t = await stoken(a.pwd_id, a.passcode);
    var out = [], page = 1, total = 0;
    do {
      var j = await qjson('GET', 'share/sharepage/detail' + Q + '&pwd_id=' + encodeURIComponent(a.pwd_id) + '&stoken=' + encodeURIComponent(t.stoken) +
        '&pdir_fid=' + encodeURIComponent(a.pdir_fid || '0') + '&force=0&_page=' + page + '&_size=100&_fetch_banner=0&_fetch_share=0&_fetch_total=1&_sort=file_type:asc,file_name:asc');
      (j.data && j.data.list || []).forEach(function (x) {
        out.push({ fid: x.fid, name: x.file_name, dir: !!x.dir || x.file === false, size: x.size || 0, token: x.share_fid_token, cat: x.obj_category || '', n: x.include_items || 0 });
      });
      total = (j.metadata && j.metadata._total) || out.length;
      page++;
    } while (out.length < total && page <= 20);
    return { title: t.title, author: t.author, stoken: t.stoken, list: out };
  }
  // 整个文件夹：一层层往下找文件（最多 600 个），带上相对路径
  async function walk(a) {
    var res = [], queue = [{ fid: a.fid, path: a.path || '' }];
    while (queue.length && res.length < 600) {
      var d = queue.shift();
      var l = await list({ pwd_id: a.pwd_id, passcode: a.passcode, pdir_fid: d.fid });
      l.list.forEach(function (x) {
        if (x.dir) queue.push({ fid: x.fid, path: d.path + x.name + '/' });
        else { x.path = d.path; res.push(x); }
      });
    }
    return res;
  }
  async function socialToken() {
    var c = GM_getValue('quark_social', null);
    if (c && c.token && c.expired_timestamp > Date.now() + 60000) return c.token;
    try {
      var t = Math.floor(Date.now() / 1e3);
      var j = await qjson('POST', 'https://drive-social-api.quark.cn/1/clouddrive/chat/conv/file/acquire_dl_token' + Q + '&la=zh-CN', { conversation_id: '300000' + t, conversation_type: 3, msg_id: t + '000' }, { 'User-Agent': UA_PC });
      GM_setValue('quark_social', j.data);
      return j.data.token || '';
    } catch (e) { return ''; }
  }
  // ---- 拿下载地址（分享里直接拿，不用先存到自己网盘）
  async function links(a) {
    var t = await stoken(a.pwd_id, a.passcode), out = [], files = a.files || [];
    for (var i = 0; i < files.length; i += 15) {
      var b = files.slice(i, i + 15);
      var tok = await socialToken();
      var extra = { 'User-Agent': UA_PC };
      if (pugs()) extra.Cookie = '__pugs=' + pugs();
      LASTSET = '';
      var j = await qjson('POST', 'file/download' + Q, { fids: b.map(function (x) { return x.fid; }), fids_token: b.map(function (x) { return x.token; }), pwd_id: a.pwd_id, stoken: t.stoken, speedup_session: '', token: tok }, extra);
      (j.data || []).forEach(function (d) {
        var src = b.filter(function (x) { return x.fid === d.fid; })[0] || {};
        out.push({ fid: d.fid, name: src.name || d.file_name, path: src.path || '', size: d.size || src.size, url: d.download_url });
      });
      if (i + 15 < files.length) await new Promise(function (r) { setTimeout(r, 800); });
    }
    var ck = await quarkCookies();
    var pg = LASTSET || pugs(), jar = GM_getValue('quark_pugs_jar', ''), set = GM_getValue('quark_pugs', '');
    // 夸克对下载请求挑剔：几种带法挨个试（只要 1 个字节），哪种能下就用哪种
    var base = { 'User-Agent': UA_PC, 'Referer': 'https://pan.quark.cn/' }, cands = [], seen = {};
    function cand(name, h) { var k = JSON.stringify(h); if (seen[k]) return; seen[k] = 1; cands.push({ name: name, h: h }); }
    if (pg) cand('pugs', Object.assign({ Cookie: '__pugs=' + pg }, base));
    if (jar && jar !== pg) cand('pugs-jar', Object.assign({ Cookie: '__pugs=' + jar }, base));
    if (set && set !== pg && set !== jar) cand('pugs-set', Object.assign({ Cookie: '__pugs=' + set }, base));
    if (ck) cand('full', Object.assign({ Cookie: ck }, base));
    cand('none', Object.assign({}, base));
    if (pg) cand('pugs-noref', { 'User-Agent': UA_PC, Cookie: '__pugs=' + pg });
    if (pg) cand('pugs-browserUA', { 'User-Agent': navigator.userAgent, Referer: 'https://pan.quark.cn/', Cookie: '__pugs=' + pg });
    var diag = [], pick = null;
    if (out.length && !a.noProbe) {
      for (var c = 0; c < cands.length && !pick; c++) {
        var st = await probe(out[0].url, cands[c].h);
        diag.push(cands[c].name + ':' + st);
        if (st === 200 || st === 206) pick = cands[c];
      }
    }
    if (out.length && !a.noProbe && !pick) { var er = new Error('夸克不让下载（试了 ' + diag.length + ' 种方式都不行：' + diag.join(' ') + '）'); throw er; }
    return { links: out, headers: (pick || cands[0]).h, way: pick ? pick.name : '', diag: diag, fullCookie: !!ck };
  }
  function probe(url, h) {
    return new Promise(function (resolve) {
      var hh = Object.assign({ Range: 'bytes=0-0' }, h), ck = hh.Cookie; delete hh.Cookie;
      var opt = { method: 'GET', url: url, headers: hh, anonymous: true, timeout: 20000, responseType: 'arraybuffer',
        onload: function (r) { resolve(r.status); }, onerror: function () { resolve('网络错误'); }, ontimeout: function () { resolve('超时'); } };
      if (ck) { opt.cookie = ck; opt.headers.Cookie = ck; }
      try { GM_xmlhttpRequest(opt); } catch (e) { resolve('出错'); }
    });
  }
  // ---- 读字幕文本（小文件，直接读进来）
  async function text(a) {
    if (!okHost(a.url, QUARK) && !/\.quark\.cn\//.test(a.url)) throw new Error('只读夸克的文件');
    var r = await new Promise(function (resolve, reject) {
      GM_xmlhttpRequest({ method: 'GET', url: a.url, headers: a.headers || {}, responseType: 'arraybuffer', anonymous: false, timeout: 60000,
        onload: resolve, onerror: function () { reject(new Error('下载字幕失败')); }, ontimeout: function () { reject(new Error('下载字幕超时')); } });
    });
    if (r.status !== 200 && r.status !== 206) throw new Error('下载字幕失败（HTTP ' + r.status + '）');
    var buf = new Uint8Array(r.response), enc = 'utf-8';
    if (buf.length > 8 * 1024 * 1024) throw new Error('字幕文件太大');
    if (buf[0] === 0xFF && buf[1] === 0xFE) enc = 'utf-16le'; else if (buf[0] === 0xFE && buf[1] === 0xFF) enc = 'utf-16be';
    var s = new TextDecoder(enc).decode(buf);
    if ((s.match(/�/g) || []).length > 2) { try { var g = new TextDecoder('gbk').decode(buf); if ((g.match(/�/g) || []).length < (s.match(/�/g) || []).length) s = g; } catch (e) { } }
    return { text: s.replace(/^﻿/, '') };
  }
  // ---- 推给本机 torrent_hub（假装 Aria2）
  async function push(a) {
    var port = +a.port || 8800, out = [];
    for (var i = 0; i < (a.items || []).length; i++) {
      var it = a.items[i];
      var hd = Object.keys(it.headers || {}).map(function (k) { return k + ': ' + it.headers[k]; });
      var r = await gm({ method: 'POST', url: 'http://127.0.0.1:' + port + '/jsonrpc', headers: { 'Content-Type': 'application/json' },
        data: JSON.stringify({ jsonrpc: '2.0', id: Date.now(), method: 'aria2.addUri', params: [[it.url], { out: (it.path || '') + it.name, header: hd }] }), timeout: 15000 });
      var j = null; try { j = JSON.parse(r.responseText); } catch (e) { }
      if (!j || !j.result) throw new Error('torrent_hub 没收下：' + ((j && j.error && j.error.message) || ('HTTP ' + r.status)) + '（它开着吗？要 3.1.2 以上）');
      out.push(j.result);
    }
    return { ids: out };
  }
  async function thPing(a) {
    var r = await gm({ method: 'POST', url: 'http://127.0.0.1:' + (+a.port || 8800) + '/jsonrpc', headers: { 'Content-Type': 'application/json' }, data: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'aria2.getVersion', params: [] }), timeout: 3000 });
    var j = JSON.parse(r.responseText); return j.result;
  }

  var OPS = {
    ping: async function () { var ck = await quarkCookies(); return { ver: VER, cookie: !!ck, jar: !!GM_getValue('quark_pugs_jar', ''), jarAt: GM_getValue('quark_pugs_at', 0) }; },
    list: list, walk: walk, links: links, text: text, push: push, thPing: thPing
  };
  document.addEventListener('tbx-req', function (ev) {
    var d = {}; try { d = JSON.parse(ev.detail); } catch (e) { return; }
    var f = OPS[d.op];
    function reply(o) { o.id = d.id; document.dispatchEvent(new CustomEvent('tbx-res', { detail: JSON.stringify(o) })); }
    if (!f) return reply({ error: '不认识的操作：' + d.op });
    Promise.resolve().then(function () { return f(d.args || {}); }).then(function (r) { reply({ ok: r }); }, function (e) { reply({ error: (e && e.message) || String(e) }); });
  });
  function hello() { if (!document.documentElement) return; document.documentElement.setAttribute('data-tbx', VER); document.dispatchEvent(new CustomEvent('tbx-ready', { detail: VER })); }
  hello(); document.addEventListener('DOMContentLoaded', hello);
})();
