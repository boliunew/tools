/* rankings-ui.js — 排行榜互动版（整合进 kb.html 用）
 *
 * 用法：kb.html 的 openArt() 拦截 slug 为 top500-movies / top500-music 时
 * 调用 window.RankingsUI.render('movie' | 'music')，脚本把三个榜渲染进
 * 文章容器 #body。其他文章一律走 kb.html 原有的 Markdown 渲染。
 *
 * 数据来源（运行时拉取，不写死）：
 *   - 电影：rankings/data/movies.json（rankings/build.py 每周更新）
 *   - 音乐：rankings/data/music.json（同上）
 *   - 年代经典：rankings/data/classics.json（静态精选，不随每周更新）
 * 样式：复用 kb.html 已有的 .tags / .srch / .tbl / .cpy / .empty / .ameta /
 * .md 表格样式；本文件只注入 .rk-* 一组小样式，且只用 kb.html 原有的
 * CSS 变量（--line / --paper / --soft / --ink / --chip / --accent）。
 *
 * 复制说明：kb.html 自带的 document 级 .cpy 处理会拦截所有 .cpy 元素
 * （包括 <a class="cpy"> 的 YouTube 链接，会导致链接打不开），所以本文件
 * 用 capture 阶段的处理器只处理 button.cpy[data-copy]，并 stopPropagation
 * 阻止 kb.html 的处理器重复触发；YouTube ▶️ 链接不再用 .cpy 类。
 * 复制本身用 navigator.clipboard，失败时降级到 textarea + execCommand，
 * 提示复用 kb.html 的 #toast 元素（.toast / .toast.on 样式已在 kb.html）。
 */
(function () {
  'use strict';

  var STYLE_DONE = false;
  function injectStyle() {
    if (STYLE_DONE) return;
    STYLE_DONE = true;
    var css = [
      '.rk .rk-switch{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0}',
      '.rk .rk-switch button{border:1px solid var(--line);background:var(--paper);border-radius:999px;padding:6px 14px;font-size:14px}',
      '.rk .rk-switch button.on{background:var(--ink);border-color:var(--ink);color:var(--paper);font-weight:700}',
      '.rk .rk-flabel{font-size:13px;color:var(--soft);margin:10px 2px 0}',
      '.rk .rk-countrow{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:14px 2px 0;font-size:13.5px;color:var(--soft)}',
      '.rk .rk-countrow b{color:var(--ink)}',
      '.rk .rk-countrow button{border:1px solid var(--line);background:var(--paper);border-radius:999px;padding:5px 12px;font-size:13.5px}',
      '.rk .rk-navlist{display:flex;flex-direction:column;gap:8px;margin:10px 0 4px}',
      '.rk .rk-navlist button{display:flex;justify-content:space-between;align-items:center;gap:10px;width:100%;border:1px solid var(--line);background:var(--paper);border-radius:12px;padding:12px;text-align:left}',
      '.rk .rk-navlist .sub{font-size:12.5px;color:var(--soft)}',
      '.rk .rk-navlist .meta{font-size:12.5px;color:var(--soft);white-space:nowrap}',
      '.rk .rk-backrow{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0 4px}',
      '.rk .rk-backrow button{border:1px solid var(--line);background:var(--paper);border-radius:999px;padding:5px 12px;font-size:13.5px}',
      '.rk td.r,.rk th.r{text-align:right;white-space:nowrap}',
      '.rk td.c,.rk th.c{text-align:center;white-space:nowrap}',
      '.rk td.yr{white-space:nowrap}',
      '.rk td .en{color:var(--soft)}',
      '.rk .rk-yt{text-decoration:none}'
    ].join('\n');
    var st = document.createElement('style');
    st.setAttribute('data-rk', '1');
    st.textContent = css;
    document.head.appendChild(st);
  }

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function flag(cc) {
    if (!cc || !/^[A-Z]{2}$/.test(cc)) return '🌐';
    return String.fromCodePoint(0x1F1E6 + cc.charCodeAt(0) - 65, 0x1F1E6 + cc.charCodeAt(1) - 65);
  }
  function fmtVotes(v) {
    v = +v || 0;
    return v >= 1e5 ? Math.round(v / 1e4) + '万' : (v / 1e4).toFixed(1) + '万';
  }

  var toastT = null;
  function toast(s) {
    var t = $('toast');
    if (!t) return;
    t.textContent = s;
    t.className = 'toast on';
    clearTimeout(toastT);
    toastT = setTimeout(function () { t.className = 'toast'; }, 1600);
  }
  function copyText(txt) {
    if (txt == null || txt === '') return;
    function legacy() {
      var a = document.createElement('textarea');
      a.value = txt;
      a.setAttribute('readonly', '');
      a.style.cssText = 'position:fixed;top:-9999px;opacity:0';
      document.body.appendChild(a);
      a.focus(); a.select();
      try { a.setSelectionRange(0, a.value.length); } catch (e) {}
      var done = false;
      try { done = document.execCommand('copy'); } catch (e) {}
      document.body.removeChild(a);
      toast(done ? ('已复制：' + txt) : '复制失败');
    }
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
      try { navigator.clipboard.writeText(txt).then(function () { toast('已复制：' + txt); }, legacy); }
      catch (e) { legacy(); }
    } else { legacy(); }
  }
  /* capture 阶段拦截，避免 kb.html 的 .cpy 处理重复触发（见文件头注释）。 */
  document.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('button.cpy[data-copy]') : null;
    if (!b) return;
    e.preventDefault();
    e.stopPropagation();
    copyText(b.getAttribute('data-copy'));
  }, true);

  function fetchJSON(url) {
    var u = url + (url.indexOf('?') < 0 ? '?' : '&') + 'v=' + Math.floor(Date.now() / 6e5);
    return fetch(u).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    }).then(function (j) {
      return Array.isArray(j) ? j : (j.items || []);
    });
  }

  function buildTags(el, options, current, onPick) {
    el.innerHTML = '';
    options.forEach(function (o) {
      var b = document.createElement('button');
      b.type = 'button';
      if (o.value === current) b.className = 'on';
      b.innerHTML = esc(o.label) + (o.count != null ? '<small>' + o.count + '</small>' : '');
      b.addEventListener('click', function () { onPick(o.value); });
      el.appendChild(b);
    });
  }
  function countryOptions(items) {
    var map = {}, order = [];
    items.forEach(function (it) {
      if (!map[it.cc]) { map[it.cc] = { value: it.cc, label: flag(it.cc) + ' ' + it.cname, count: 0 }; order.push(it.cc); }
      map[it.cc].count++;
    });
    var list = order.map(function (k) { return map[k]; }).sort(function (a, b) { return b.count - a.count; });
    return [{ value: '', label: '全部', count: items.length }].concat(list);
  }

  /* ---------------- 电影 ---------------- */
  var mState = { q: '', cc: '', dec: '' };
  var DECADES = [
    { value: '', label: '全部年份' },
    { value: '2020', label: '2020 年代' },
    { value: '2010', label: '2010 年代' },
    { value: '2000', label: '2000 年代' },
    { value: '1990', label: '1990 年代' },
    { value: '1980', label: '1980 年代' },
    { value: '1970', label: '1970 年代' },
    { value: '1960', label: '1960 年代' },
    { value: '1950', label: '1950 年代' },
    { value: 'old', label: '1950 年以前' }
  ];
  var MOVIES = [];
  function movieMatch(it) {
    if (mState.cc && it.cc !== mState.cc) return false;
    if (mState.dec) {
      var y = +it.year;
      if (mState.dec === 'old') { if (y >= 1950) return false; }
      else if (Math.floor(y / 10) * 10 !== +mState.dec) return false;
    }
    if (mState.q) {
      var q = mState.q.toLowerCase();
      var hay = ((it.zh || '') + ' ' + (it.title || '') + ' ' + (it.cname || '') + ' ' + it.year).toLowerCase();
      if (hay.indexOf(q) < 0) return false;
    }
    return true;
  }
  function renderMovies() {
    var decs = DECADES.map(function (d) {
      if (!d.value) return { value: '', label: '全部年份', count: MOVIES.length };
      return {
        value: d.value, label: d.label,
        count: MOVIES.filter(function (it) {
          var y = +it.year;
          return d.value === 'old' ? y < 1950 : Math.floor(y / 10) * 10 === +d.value;
        }).length
      };
    });
    buildTags($('rk-mCountries'), countryOptions(MOVIES), mState.cc, function (v) { mState.cc = v; renderMovies(); });
    buildTags($('rk-mYears'), decs, mState.dec, function (v) { mState.dec = v; renderMovies(); });
    var list = MOVIES.filter(movieMatch);
    var html = '';
    list.forEach(function (it) {
      var name = it.zh || it.title;
      var yt = 'https://www.youtube.com/results?search_query=' + encodeURIComponent(it.title + ' ' + it.year + ' trailer');
      html += '<tr><td class="r">' + it.rank + '</td>'
        + '<td><a href="https://www.imdb.com/title/' + esc(it.id) + '/" target="_blank" rel="noopener"><strong>' + esc(name) + '</strong></a>'
        + (it.zh && it.title ? '<span class="en"> · ' + esc(it.title) + '</span>' : '')
        + '<span class="en"> · ' + flag(it.cc) + ' ' + esc(it.cname) + '</span></td>'
        + '<td class="yr">' + esc(it.year) + '</td>'
        + '<td class="r">' + (+it.rating).toFixed(1) + '</td>'
        + '<td class="r">' + fmtVotes(it.votes) + '</td>'
        + '<td class="c"><a class="rk-yt" href="' + yt + '" target="_blank" rel="noopener" title="在 YouTube 看预告片">▶️</a> <button type="button" class="cpy" data-copy="' + esc(name) + '" title="复制：' + esc(name) + '">📋</button></td></tr>';
    });
    $('rk-mBody').innerHTML = html;
    $('rk-mEmpty').hidden = list.length > 0;
    $('rk-mCount').innerHTML = '显示 <b>' + list.length + '</b> / ' + MOVIES.length + ' 条';
    $('rk-mClear').hidden = !(mState.q || mState.cc || mState.dec);
  }

  /* ---------------- 音乐 ---------------- */
  var sState = { q: '', cc: '', grp: '' };
  var CHART_GROUPS = [
    { value: '', label: '全部' },
    { value: '1', label: '1 个地区' },
    { value: '2-3', label: '2–3 个地区' },
    { value: '4-5', label: '4–5 个地区' },
    { value: '6-9', label: '6–9 个地区' },
    { value: '10+', label: '10 个以上' }
  ];
  var MUSIC = [];
  function chartN(it) { return Object.keys(it.charts || {}).length; }
  function inGroup(n, g) {
    if (g === '1') return n === 1;
    if (g === '2-3') return n >= 2 && n <= 3;
    if (g === '4-5') return n >= 4 && n <= 5;
    if (g === '6-9') return n >= 6 && n <= 9;
    if (g === '10+') return n >= 10;
    return true;
  }
  function musicMatch(it) {
    if (sState.cc && it.cc !== sState.cc) return false;
    if (sState.grp && !inGroup(chartN(it), sState.grp)) return false;
    if (sState.q) {
      var q = sState.q.toLowerCase();
      var hay = ((it.name || '') + ' ' + (it.artist || '') + ' ' + (it.cname || '')).toLowerCase();
      if (hay.indexOf(q) < 0) return false;
    }
    return true;
  }
  function renderMusic() {
    var groups = CHART_GROUPS.map(function (g) {
      return { value: g.value, label: g.label, count: g.value ? MUSIC.filter(function (it) { return inGroup(chartN(it), g.value); }).length : MUSIC.length };
    });
    buildTags($('rk-sCountries'), countryOptions(MUSIC), sState.cc, function (v) { sState.cc = v; renderMusic(); });
    buildTags($('rk-sCharts'), groups, sState.grp, function (v) { sState.grp = v; renderMusic(); });
    var list = MUSIC.filter(musicMatch);
    var html = '';
    list.forEach(function (it) {
      var n = chartN(it);
      var yt = 'https://www.youtube.com/results?search_query=' + encodeURIComponent(it.name + ' ' + it.artist);
      var copy = it.name + ' — ' + it.artist;
      html += '<tr><td class="r">' + it.rank + '</td>'
        + '<td><a href="https://music.apple.com/us/song/' + esc(it.id) + '" target="_blank" rel="noopener"><strong>' + esc(it.name) + '</strong></a><span class="en"> · ' + esc(it.artist) + '</span></td>'
        + '<td>' + flag(it.cc) + ' ' + esc(it.cname) + (it.approx ? '≈' : '') + '</td>'
        + '<td class="r">' + n + '</td>'
        + '<td class="c"><a class="rk-yt" href="' + yt + '" target="_blank" rel="noopener" title="在 YouTube 搜这首歌">▶️</a> <button type="button" class="cpy" data-copy="' + esc(copy) + '" title="复制：' + esc(copy) + '">📋</button></td></tr>';
    });
    $('rk-sBody').innerHTML = html;
    $('rk-sEmpty').hidden = list.length > 0;
    $('rk-sCount').innerHTML = '显示 <b>' + list.length + '</b> / ' + MUSIC.length + ' 条';
    $('rk-sClear').hidden = !(sState.q || sState.cc || sState.grp);
  }

  /* ---------------- 年代经典榜（静态精选，两级进入） ---------------- */
  var C_DECADES = [1960, 1970, 1980, 1990, 2000, 2010, 2020];
  var CLASSICS = [];
  var cNav = { dec: null, cc: null };
  function cCountriesOf(dec) {
    var map = {}, order = [];
    CLASSICS.forEach(function (it) {
      if (it.decade !== dec) return;
      if (!map[it.cc]) { map[it.cc] = { cc: it.cc, cname: it.country, count: 0 }; order.push(it.cc); }
      map[it.cc].count++;
    });
    return order.map(function (k) { return map[k]; }).sort(function (a, b) { return b.count - a.count || (a.cname < b.cname ? -1 : 1); });
  }
  function renderClassics() {
    var html = '';
    if (cNav.dec == null) {
      $('rk-cCount').innerHTML = '共 <b>' + CLASSICS.length + '</b> 首 · 7 个年代 · 点一个年代进入';
      html += '<h3>年代清单 · 选择年代</h3><div class="rk-navlist">';
      C_DECADES.forEach(function (dec) {
        var cs = cCountriesOf(dec);
        var total = cs.reduce(function (s, c) { return s + c.count; }, 0);
        var names = cs.map(function (c) { return flag(c.cc) + ' ' + esc(c.cname); }).join('、');
        html += '<button type="button" data-dec="' + dec + '"><span><strong>' + dec + ' 年代</strong><br><span class="sub">' + names + '</span></span><span class="meta">' + cs.length + ' 个国家 · ' + total + ' 首 →</span></button>';
      });
      html += '</div>';
    } else if (cNav.cc == null) {
      var cs = cCountriesOf(cNav.dec);
      var total = cs.reduce(function (s, c) { return s + c.count; }, 0);
      $('rk-cCount').innerHTML = '<b>' + cNav.dec + ' 年代</b> · ' + cs.length + ' 个国家 · ' + total + ' 首 · 点一个国家进入歌单';
      html += '<div class="rk-backrow"><button type="button" data-back="decades">← 返回年代清单</button></div>';
      html += '<h3>' + cNav.dec + ' 年代 · 选择国家</h3><div class="rk-navlist">';
      cs.forEach(function (c) {
        html += '<button type="button" data-cc="' + c.cc + '"><span>' + flag(c.cc) + ' <strong>' + esc(c.cname) + '</strong></span><span class="meta">' + c.count + ' 首 →</span></button>';
      });
      html += '</div>';
    } else {
      var items = CLASSICS.filter(function (it) { return it.decade === cNav.dec && it.cc === cNav.cc; })
        .slice().sort(function (a, b) { return a.year - b.year || (a.name < b.name ? -1 : 1); });
      var cname = items.length ? items[0].country : '';
      $('rk-cCount').innerHTML = '<b>' + cNav.dec + ' 年代</b> · ' + flag(cNav.cc) + ' ' + esc(cname) + ' · <b>' + items.length + '</b> 首';
      html += '<div class="rk-backrow"><button type="button" data-back="countries">← 返回国家列表</button><button type="button" data-back="decades">← 返回年代清单</button></div>';
      html += '<h3>' + cNav.dec + ' 年代 · ' + flag(cNav.cc) + ' ' + esc(cname) + ' · ' + items.length + ' 首</h3>';
      html += '<div class="tbl"><table><thead><tr><th>歌名</th><th>歌手</th><th>发行年份</th><th>歌手国家</th><th class="c">复制</th></tr></thead><tbody>';
      items.forEach(function (it) {
        var ccopy = it.name + ' — ' + it.artist;
        html += '<tr><td><strong>' + esc(it.name) + '</strong></td><td>' + esc(it.artist) + '</td><td class="yr">' + it.year + '</td><td>' + flag(it.cc) + ' ' + esc(it.country) + '</td><td class="c"><button type="button" class="cpy" data-copy="' + esc(ccopy) + '" title="复制：' + esc(ccopy) + '">📋</button></td></tr>';
      });
      html += '</tbody></table></div>';
    }
    $('rk-cBody').innerHTML = html;
  }

  /* ---------------- 面板切换与入口 ---------------- */
  var DATA_PROMISE = null;
  var TOKEN = 0;
  function showPanel(which) {
    $('rk-panelMovie').hidden = which !== 'movie';
    $('rk-panelMusic').hidden = which !== 'music';
    $('rk-panelClassics').hidden = which !== 'classics';
    $('rk-tabMovie').className = which === 'movie' ? 'on' : '';
    $('rk-tabMusic').className = which === 'music' ? 'on' : '';
    $('rk-tabClassics').className = which === 'classics' ? 'on' : '';
  }
  function loadData() {
    if (!DATA_PROMISE) {
      DATA_PROMISE = Promise.all([
        fetchJSON('rankings/data/movies.json').catch(function () { return []; }),
        fetchJSON('rankings/data/music.json').catch(function () { return []; }),
        fetchJSON('rankings/data/classics.json').catch(function () { return []; })
      ]).then(function (res) { MOVIES = res[0]; MUSIC = res[1]; CLASSICS = res[2]; return res; });
    }
    return DATA_PROMISE;
  }
  function render(initial) {
    injectStyle();
    var myToken = ++TOKEN;
    var body = $('body');
    body.innerHTML =
      '<div class="rk" id="rk-root">'
      + '<h1>排行榜 Top 500</h1>'
      + '<div class="ameta"><span>互动版 · 可筛选</span><span>动态榜每周随 rankings/data 更新</span><span>年代经典为静态精选</span></div>'
      + '<blockquote>'
      + '<p><strong>电影怎么排的</strong>：从 IMDb 官方公开数据里，挑出评分人数 ≥ 25,000 的全部电影，按和 IMDb Top 250 相同的<strong>加权评分</strong>排序。国家是 Wikidata 里的<strong>出品国</strong>，中文片名来自 Wikidata，没有的显示英文名。片名链接到 IMDb。</p>'
      + '<p><strong>音乐怎么排的</strong>：取 Apple Music 在 25 个国家和地区的「最多播放」歌曲榜（每个前 100 名），每上一个地区的榜得 0.01–1 分（第 1 名 1 分，第 100 名 0.01 分），加起来排出全球前 500。国家是<strong>歌手</strong>所属国（来自 Wikidata），查不到的按它排名最高的那个地区归类，标「≈」。「上榜」= 上了几个地区的榜。歌名链接到 Apple Music。</p>'
      + '</blockquote>'
      + '<div class="rk-switch" role="tablist" aria-label="切换榜单">'
      + '<button type="button" id="rk-tabMovie">电影 Top 500</button>'
      + '<button type="button" id="rk-tabMusic">音乐 Top 500</button>'
      + '<button type="button" id="rk-tabClassics">年代经典榜</button>'
      + '</div>'
      + '<section id="rk-panelMovie">'
      + '<h2>电影 Top 500（按国家分类）</h2>'
      + '<div class="srch"><input id="rk-mq" type="search" placeholder="搜片名（中文 / 英文）…" autocomplete="off" aria-label="搜电影片名"></div>'
      + '<div class="rk-flabel">国家</div><div class="tags" id="rk-mCountries"></div>'
      + '<div class="rk-flabel">年份</div><div class="tags" id="rk-mYears"></div>'
      + '<div class="rk-countrow"><span id="rk-mCount"></span><button type="button" id="rk-mClear" hidden>清除筛选</button></div>'
      + '<div class="tbl"><table><thead><tr><th class="r">#</th><th>片名</th><th>年份</th><th class="r">评分</th><th class="r">人数</th><th class="c">预告片 · 复制</th></tr></thead><tbody id="rk-mBody"></tbody></table></div>'
      + '<div class="empty" id="rk-mEmpty" hidden>没有符合条件的电影，换个关键词或清除筛选试试。</div>'
      + '</section>'
      + '<section id="rk-panelMusic" hidden>'
      + '<h2>音乐 Top 500（按国家分类）</h2>'
      + '<div class="srch"><input id="rk-sq" type="search" placeholder="搜歌名 / 歌手…" autocomplete="off" aria-label="搜歌名或歌手"></div>'
      + '<div class="rk-flabel">歌手国家</div><div class="tags" id="rk-sCountries"></div>'
      + '<div class="rk-flabel">上榜地区数</div><div class="tags" id="rk-sCharts"></div>'
      + '<div class="rk-countrow"><span id="rk-sCount"></span><button type="button" id="rk-sClear" hidden>清除筛选</button></div>'
      + '<div class="tbl"><table><thead><tr><th class="r">#</th><th>歌曲 · 歌手</th><th>国家</th><th class="r">上榜</th><th class="c">YouTube · 复制</th></tr></thead><tbody id="rk-sBody"></tbody></table></div>'
      + '<div class="empty" id="rk-sEmpty" hidden>没有符合条件的歌曲，换个关键词或清除筛选试试。</div>'
      + '</section>'
      + '<section id="rk-panelClassics" hidden>'
      + '<h2>年代经典榜（静态精选）</h2>'
      + '<blockquote>'
      + '<p><strong>这是一张精选静态榜，不随每周更新</strong>，也不是从动态音乐 Top 500 里算出来的——动态榜是每周按 Apple Music 播放数据重排的，这张是按年代人工精选的经典榜，两张榜互不影响。</p>'
      + '<p><strong>选曲来源</strong>：主要依据公开权威的历代经典榜单——Rolling Stone《500 首历代最佳歌曲》（2021 年版）、Billboard「历代 Hot 100 歌曲榜」（2021 年更新版）与 Grammy 年度制作（Record of the Year）等；2020 年代的近年作品另参考 Grammy 年度制作与 Billboard Hot 100 的冠军表现。歌名、歌手、发行年份、歌手国家逐条按上述来源与公开资料核对；年份以来源榜单所标年份／专辑首次发行年为准，国家为歌手所属国、乐队起源国。</p>'
      + '<p>进入方式是两级：先在年代清单里点一个年代，再在该年代的国家列表里点一个国家，进入该国家在该年代的歌单。只列出能凑满至少 20 首的国家——每个列出的国家歌单都有 20 首，美国、英国每个年代都在列；1970 年代另有牙买加、1980 年代另有澳大利亚。共 7 个年代、16 个国家歌单、合计 320 首。</p>'
      + '</blockquote>'
      + '<div class="rk-countrow"><span id="rk-cCount"></span></div>'
      + '<div id="rk-cBody"></div>'
      + '<p style="font-size:.85em;color:var(--soft)">来源链接：<a href="https://en.wikipedia.org/wiki/Rolling_Stone%27s_500_Greatest_Songs_of_All_Time" target="_blank" rel="noopener">Rolling Stone《500 首历代最佳歌曲》</a> · <a href="https://www.billboard.com/charts/greatest-hot-100-singles/" target="_blank" rel="noopener">Billboard 官方「历代 Hot 100 歌曲榜」（2021 年更新版）</a> · <a href="https://en.wikipedia.org/wiki/Grammy_Award_for_Record_of_the_Year" target="_blank" rel="noopener">Grammy 历届年度制作获奖名单</a>。本榜为静态精选，收录时（2026-10）核对，不随每周动态榜更新。</p>'
      + '</section>'
      + '<div class="foot">动态榜数据来自仓库 <code>rankings/data/movies.json</code> 与 <code>music.json</code>（每周随 rankings/build.py 更新，互动版自动跟上）；年代经典榜数据来自 <code>rankings/data/classics.json</code>（静态精选）。</div>'
      + '</div>';
    $('rk-mq').addEventListener('input', function () { mState.q = this.value.trim(); renderMovies(); });
    $('rk-mClear').addEventListener('click', function () { mState = { q: '', cc: '', dec: '' }; $('rk-mq').value = ''; renderMovies(); });
    $('rk-sq').addEventListener('input', function () { sState.q = this.value.trim(); renderMusic(); });
    $('rk-sClear').addEventListener('click', function () { sState = { q: '', cc: '', grp: '' }; $('rk-sq').value = ''; renderMusic(); });
    $('rk-tabMovie').addEventListener('click', function () { showPanel('movie'); });
    $('rk-tabMusic').addEventListener('click', function () { showPanel('music'); });
    $('rk-tabClassics').addEventListener('click', function () { showPanel('classics'); });
    $('rk-cBody').addEventListener('click', function (e) {
      var t = e.target.closest ? e.target.closest('button[data-dec],button[data-cc],button[data-back]') : null;
      if (!t) return;
      if (t.hasAttribute('data-dec')) { cNav.dec = +t.getAttribute('data-dec'); cNav.cc = null; }
      else if (t.hasAttribute('data-cc')) { cNav.cc = t.getAttribute('data-cc'); }
      else if (t.getAttribute('data-back') === 'countries') { cNav.cc = null; }
      else if (t.getAttribute('data-back') === 'decades') { cNav.dec = null; cNav.cc = null; }
      else return;
      renderClassics();
      var root = $('rk-root');
      if (root && root.scrollIntoView) root.scrollIntoView({ block: 'start' });
    });
    showPanel(initial === 'music' ? 'music' : 'movie');
    $('rk-mCount').textContent = '加载中…';
    $('rk-sCount').textContent = '加载中…';
    $('rk-cCount').textContent = '加载中…';
    loadData().then(function () {
      if (myToken !== TOKEN || !$('rk-root')) return;
      if (!MOVIES.length) { $('rk-mCount').textContent = '动态电影数据加载失败，检查 rankings/data/movies.json 后刷新试试'; }
      else renderMovies();
      if (!MUSIC.length) { $('rk-sCount').textContent = '动态音乐数据加载失败，检查 rankings/data/music.json 后刷新试试'; }
      else renderMusic();
      if (!CLASSICS.length) { $('rk-cCount').textContent = '年代经典数据加载失败，检查 rankings/data/classics.json 后刷新试试'; }
      else { cNav = { dec: null, cc: null }; renderClassics(); }
    });
  }

  window.RankingsUI = { render: render };
})();
