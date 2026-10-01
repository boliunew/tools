/* 🌀 穿越按钮 — a small tab on the left edge of every tool page that opens a drawer to jump to any other page.
   Drag the tab up/down to move it; the position is remembered. ES5, self-contained, no dependencies. */
(function () {
  'use strict';
  if (window.__tnav) return;
  window.__tnav = 1;

  var GROUPS = [
    ['🎧 听', [['radio.html', '🚗', '通勤电台', '开车听：天气、大盘、新闻、单词'], ['fm.html', '📻', '环球网络电台', '俄德英美中，显示正在播的歌'], ['books.html', '🎧', '听书 · 广播剧', 'LibriVox 有声书和老广播剧'], ['sleep.html', '🌙', '夜之声 · 助眠', '白噪音、声景旅程、温柔唤醒'], ['player.html', '🎬', '探测播放器', '']]],
    ['📚 学', [['hanzi.html', '字', '汉字练习', '儿童识字 · HSK'], ['english.html', '🔤', '英语练习', '单词、句子、习语口头禅'], ['spanish.html', '🇲🇽', '西班牙语练习', '墨西哥发音，el / la 看图记'], ['vocab.html', '📖', '语境词库', '20000 词，语境里记单词'], ['sublingo.html', '🎞️', 'SubLingo', '字幕和文章逐句分析'], ['news.html', '📰', '英文新闻精选', '']]],
    ['💰 钱', [['deals.html', '🏷️', '打折雷达', '45 家店本周广告 + 比价'], ['stocks.html', '📈', '今日股票池', ''], ['earnings.html', '📅', '财报与经济日历', '']]],
    ['🛠️ 工具', [['monitor.html', '🔔', '网页监控', '']]]
  ];
  var ALL = {}, g, i;
  for (g = 0; g < GROUPS.length; g++) for (i = 0; i < GROUPS[g][1].length; i++) ALL[GROUPS[g][1][i][0]] = GROUPS[g][1][i];

  function here() { var p = (window.location.pathname || '').split('/').pop(); return p || 'index.html'; }
  function get(k, d) { try { var v = window.localStorage.getItem('tnav:' + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } }
  function put(k, v) { try { window.localStorage.setItem('tnav:' + k, JSON.stringify(v)); } catch (e) { } }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  var cur = here();
  // remember where we have been (most recent first)
  var hist = get('hist', []), k;
  for (k = hist.length - 1; k >= 0; k--) if (hist[k] === cur) hist.splice(k, 1);
  var prev = hist.length ? hist[0] : null;
  if (ALL[cur]) hist.unshift(cur);
  put('hist', hist.slice(0, 8));

  var css = '' +
    '.tnav-tab{position:fixed;left:0;z-index:29;width:24px;height:44px;border:0;padding:0 1px 0 0;border-radius:0 22px 22px 0;background:rgba(28,28,30,.45);color:#fff;font-size:15px;line-height:44px;text-align:center;box-shadow:0 2px 10px rgba(0,0,0,.18);-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);opacity:.65;touch-action:none;cursor:pointer;-webkit-tap-highlight-color:transparent;transition:opacity .2s,width .15s}' +
    '.tnav-tab:hover,.tnav-tab.drag{opacity:1;width:34px}' +
    '@media (prefers-color-scheme: dark){.tnav-tab{background:rgba(255,255,255,.2)}}' +
    '.tnav-bg{position:fixed;inset:0;left:0;top:0;right:0;bottom:0;z-index:2147483000;background:rgba(0,0,0,.35);opacity:0;pointer-events:none;transition:opacity .2s}' +
    '.tnav-bg.on{opacity:1;pointer-events:auto}' +
    '.tnav-dr{position:fixed;left:0;top:0;bottom:0;z-index:2147483001;width:300px;max-width:84vw;background:#FBFAF7;color:#1C1B19;box-shadow:4px 0 24px rgba(0,0,0,.2);transform:translateX(-105%);transition:transform .22s ease;overflow-y:auto;-webkit-overflow-scrolling:touch;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif;font-size:15px;line-height:1.4;padding-bottom:24px}' +
    '.tnav-dr.on{transform:translateX(0)}' +
    '.tnav-hd{display:flex;align-items:center;padding:14px 12px 8px 16px;position:sticky;top:0;background:inherit}' +
    '.tnav-hd b{flex:1;font-size:17px}' +
    '.tnav-x{border:0;background:none;color:inherit;font-size:22px;padding:4px 10px;cursor:pointer;opacity:.6}' +
    '.tnav-back{display:flex;align-items:center;gap:10px;margin:2px 12px 6px;padding:10px 12px;border-radius:12px;background:#FDE7DA;color:#9A3412;text-decoration:none;font-weight:600}' +
    '.tnav-g{font-size:12.5px;color:#8A847A;margin:12px 16px 4px;font-weight:600;letter-spacing:.04em}' +
    '.tnav-a{display:flex;align-items:center;gap:12px;padding:9px 16px;color:inherit;text-decoration:none}' +
    '.tnav-a:active{background:rgba(0,0,0,.06)}' +
    '.tnav-a i{font-style:normal;width:30px;height:30px;border-radius:9px;background:#EFEBE4;display:flex;align-items:center;justify-content:center;font-size:17px;flex:0 0 auto;font-weight:700}' +
    '.tnav-a span{flex:1;min-width:0}' +
    '.tnav-a small{display:block;font-size:12px;color:#8A847A;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}' +
    '.tnav-a.cur{opacity:.55;pointer-events:none}' +
    '.tnav-a.cur span:after{content:" · 当前";font-size:12px;color:#8A847A}' +
    '.tnav-home{margin:14px 16px 0;display:block;text-align:center;padding:10px;border-radius:12px;border:1px solid #E3DED4;color:inherit;text-decoration:none}' +
    '.tnav-tip{font-size:11.5px;color:#9C958A;text-align:center;margin-top:10px}' +
    '@media (prefers-color-scheme: dark){.tnav-dr{background:#1F1D19;color:#EEEAE2}.tnav-a i{background:#2E2B25}.tnav-back{background:#3A2416;color:#FDBA8C}.tnav-home{border-color:#3A362F}.tnav-a:active{background:rgba(255,255,255,.06)}}';

  function build() {
    if (document.getElementById('tnav-tab')) return;
    var st = document.createElement('style'); st.id = 'tnav-css'; st.textContent = css; document.head.appendChild(st);

    var tab = document.createElement('button');
    tab.id = 'tnav-tab'; tab.className = 'tnav-tab'; tab.type = 'button';
    tab.setAttribute('aria-label', '穿越到其他页面'); tab.title = '穿越到其他页面（可上下拖动）';
    tab.textContent = '🌀';
    var y = get('y', 0.58);
    var place = function (f) { var h = window.innerHeight || 600; f = Math.max(0.08, Math.min(0.9, f)); tab.style.top = Math.round(f * h - 24) + 'px'; return f; };
    y = place(y);

    var bg = document.createElement('div'); bg.className = 'tnav-bg';
    var dr = document.createElement('nav'); dr.className = 'tnav-dr'; dr.setAttribute('aria-label', '穿越');
    var h = '<div class="tnav-hd"><b>🌀 穿越到…</b><button class="tnav-x" type="button" aria-label="关闭">×</button></div>';
    if (prev && ALL[prev] && prev !== cur) h += '<a class="tnav-back" href="' + esc(prev) + '">↩️ 回到刚才：' + ALL[prev][1] + ' ' + esc(ALL[prev][2]) + '</a>';
    for (g = 0; g < GROUPS.length; g++) {
      h += '<div class="tnav-g">' + GROUPS[g][0] + '</div>';
      for (i = 0; i < GROUPS[g][1].length; i++) {
        var p = GROUPS[g][1][i];
        h += '<a class="tnav-a' + (p[0] === cur ? ' cur' : '') + '" href="' + esc(p[0]) + '"><i>' + p[1] + '</i><span>' + esc(p[2]) + (p[3] ? '<small>' + esc(p[3]) + '</small>' : '') + '</span></a>';
      }
    }
    h += '<a class="tnav-home" href="./">🏠 回主页</a><div class="tnav-tip">左边的 🌀 可以上下拖动，挡住东西时挪开它</div>';
    dr.innerHTML = h;
    document.body.appendChild(tab); document.body.appendChild(bg); document.body.appendChild(dr);

    var isOpen = false, pushed = false;
    var open = function () {
      isOpen = true; bg.className = 'tnav-bg on'; dr.className = 'tnav-dr on';
      try { window.history.pushState({ tnav: 1 }, ''); pushed = true; } catch (e) { pushed = false; }
    };
    var close = function (fromPop) {
      if (!isOpen) return;
      isOpen = false; bg.className = 'tnav-bg'; dr.className = 'tnav-dr';
      if (pushed && !fromPop) { pushed = false; try { window.history.back(); } catch (e) { } }
      pushed = false;
    };
    window.addEventListener('popstate', function () { if (isOpen) { pushed = false; close(true); } });
    bg.onclick = function () { close(); };
    dr.querySelector('.tnav-x').onclick = function () { close(); };
    document.addEventListener('keydown', function (e) { if (isOpen && (e.key === 'Escape' || e.keyCode === 27)) close(); });
    // links: leave without the extra history entry
    var as = dr.querySelectorAll('a');
    for (i = 0; i < as.length; i++) as[i].onclick = function (e) {
      var href = this.getAttribute('href');
      e.preventDefault();
      isOpen = false;
      if (pushed) { pushed = false; window.location.replace(href); } else window.location.href = href;
    };

    // tap opens, vertical drag moves the tab
    var startY = 0, startF = 0, moved = false, down = false;
    var pt = function (e) { return e.touches && e.touches.length ? e.touches[0].clientY : e.clientY; };
    var onDown = function (e) { down = true; moved = false; startY = pt(e); startF = y; };
    var onMove = function (e) {
      if (!down) return;
      var dy = pt(e) - startY;
      if (!moved && Math.abs(dy) > 6) { moved = true; tab.className = 'tnav-tab drag'; }
      if (moved) { y = place(startF + dy / (window.innerHeight || 600)); if (e.cancelable) e.preventDefault(); }
    };
    var onUp = function () {
      if (!down) return;
      down = false; tab.className = 'tnav-tab';
      if (moved) put('y', y);
    };
    tab.addEventListener('touchstart', onDown, { passive: true });
    tab.addEventListener('touchmove', onMove, { passive: false });
    tab.addEventListener('touchend', onUp);
    tab.addEventListener('mousedown', onDown);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    tab.addEventListener('click', function () { if (moved) { moved = false; return; } open(); });
    window.addEventListener('resize', function () { place(y); });
  }
  if (document.body) build(); else document.addEventListener('DOMContentLoaded', build);
})();
