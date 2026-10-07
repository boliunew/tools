/* 🎨 全站主题：5 套风景配色。放在每个页面 <head> 里同步执行，先于页面渲染，不闪屏。
   用法：THEME.set('forest')；THEME.set('') 回到各页面自己的默认配色。选择存在 localStorage 'theme'。
   做法：给 <html> 加 data-theme，再用更高优先级覆盖各页面共用的 CSS 变量（--bg --paper --card --ink …），
   并在页面最底层画一层「天空渐变 + 远景剪影」。ES5。 */
(function () {
  'use strict';
  if (window.THEME) return;
  var KEY = 'theme';

  // 每套：[名字, 图标, 一句话, 浅色, 深色]；配色字段：bg 背景 paper 卡片 chip 标签 ink 正文 soft 次要 faint 更淡 line 分隔线 ac 强调 acs 强调浅底 aci 强调上的字 sky 天空 sil 剪影
  var T = {
    alpine: ['雪山晨光', '🏔️', '清晨的雪山，冷蓝底色配一抹日出的橘红',
      { bg: '#EDF1F5', paper: '#FFFFFF', chip: '#E1E7EE', ink: '#1D2733', soft: '#5A6878', faint: '#93A0AE', line: '#D5DDE6', ac: '#C8553D', acs: '#F7E0D8', aci: '#FFFFFF', sky: '#F7DCCB', sil: '#8FA3B8' },
      { bg: '#121820', paper: '#1A222D', chip: '#232D3A', ink: '#E6ECF2', soft: '#A5B2C0', faint: '#6E7C8C', line: '#2C3846', ac: '#F08A6C', acs: '#3A231D', aci: '#1A0E0A', sky: '#1F2C3D', sil: '#2E4157' }],
    forest: ['红杉森林', '🌲', '林间的绿和苔藓，安静、护眼',
      { bg: '#EDF1E9', paper: '#FBFCF8', chip: '#E0E8D9', ink: '#1F2A20', soft: '#566555', faint: '#8E9B8C', line: '#D4DECC', ac: '#2F6E44', acs: '#DAEADB', aci: '#FFFFFF', sky: '#DCEBD3', sil: '#6F8F6A' },
      { bg: '#0F150E', paper: '#172016', chip: '#202B1F', ink: '#E3EBDF', soft: '#A3B39F', faint: '#6B7A68', line: '#273225', ac: '#7FC28E', acs: '#1D3322', aci: '#0B1A0F', sky: '#16241A', sil: '#26402A' }],
    coast: ['太平洋海岸', '🌊', '一号公路边的海，蓝绿色和浪花白',
      { bg: '#E9F3F5', paper: '#FCFEFE', chip: '#DAEAEE', ink: '#14303A', soft: '#4E6B75', faint: '#8AA3AB', line: '#CDE1E6', ac: '#137C8F', acs: '#D1EBF0', aci: '#FFFFFF', sky: '#CFE8F1', sil: '#7FB3C2' },
      { bg: '#0B161B', paper: '#122129', chip: '#1A2C35', ink: '#DFEEF2', soft: '#9DB9C2', faint: '#64808A', line: '#22353E', ac: '#5CC3D3', acs: '#123640', aci: '#06191D', sky: '#10242D', sil: '#1E4350' }],
    desert: ['沙漠黄昏', '🏜️', '约书亚树的日落，沙色、陶土红和仙人掌',
      { bg: '#F6ECE1', paper: '#FFFBF5', chip: '#EEE0CF', ink: '#3A2A1F', soft: '#7D6352', faint: '#B09A88', line: '#E8D8C4', ac: '#C2562C', acs: '#F6DACB', aci: '#FFFFFF', sky: '#F8D2AE', sil: '#C99A73' },
      { bg: '#19120D', paper: '#231A13', chip: '#2E231A', ink: '#F1E5D8', soft: '#C3AB96', faint: '#87715F', line: '#392C21', ac: '#EE8D5E', acs: '#3C2317', aci: '#1E0E05', sky: '#2C1A11', sil: '#4A3122' }],
    stars: ['山顶星空', '🌌', '深蓝夜空和星光金，夜里看最舒服（一直是深色）',
      { bg: '#0D1222', paper: '#161D33', chip: '#1F2843', ink: '#E7EBF7', soft: '#A9B3D0', faint: '#6E7896', line: '#262F4B', ac: '#E8C468', acs: '#3A321A', aci: '#1A1300', sky: '#1C2450', sil: '#070B17' }, null]
  };
  var ORDER = ['alpine', 'forest', 'coast', 'desert', 'stars'];

  function svgUrl(svg) { return 'url("data:image/svg+xml,' + encodeURIComponent(svg) + '")'; }
  // 远景剪影：宽 1200 高 220，贴在屏幕最下面
  function scene(k, c) {
    var s = c.sil, h = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 220" preserveAspectRatio="xMidYMax slice">';
    if (k === 'alpine' || k === 'stars') {
      h += '<path fill="' + s + '" opacity=".45" d="M0 150 L120 90 L210 130 L330 40 L430 120 L520 80 L640 140 L760 50 L880 120 L980 70 L1100 130 L1200 90 V220 H0Z"/>';
      if (k === 'alpine') h += '<path fill="#fff" opacity=".55" d="M330 40 L300 68 L318 64 L332 74 L346 62 L362 66Z M760 50 L732 76 L750 72 L764 82 L778 70 L792 74Z M980 70 L958 90 L972 88 L984 96 L996 86 L1006 88Z"/>';
      h += '<path fill="' + s + '" opacity=".8" d="M0 190 L90 150 L190 175 L300 130 L420 180 L560 140 L700 185 L820 150 L950 182 L1080 145 L1200 175 V220 H0Z"/>';
    } else if (k === 'forest') {
      var t = '', x, y, w;
      for (x = 10; x < 1200; x += 46) { y = 120 + ((x * 7) % 50); w = 22 + ((x * 3) % 12); t += 'M' + x + ' 220 L' + x + ' ' + (y + 40) + ' L' + (x + w) + ' ' + y + ' L' + (x + 2 * w) + ' ' + (y + 40) + ' L' + (x + 2 * w) + ' 220Z'; }
      h += '<path fill="' + s + '" opacity=".4" d="M0 170 Q300 120 600 160 T1200 150 V220 H0Z"/><path fill="' + s + '" opacity=".75" d="' + t + '"/>';
    } else if (k === 'coast') {
      h += '<path fill="' + s + '" opacity=".35" d="M0 120 Q150 100 300 120 T600 120 T900 120 T1200 120 V220 H0Z"/>' +
        '<path fill="' + s + '" opacity=".55" d="M0 155 Q100 135 200 155 T400 155 T600 155 T800 155 T1000 155 T1200 155 V220 H0Z"/>' +
        '<path fill="' + s + '" opacity=".85" d="M0 190 Q75 175 150 190 T300 190 T450 190 T600 190 T750 190 T900 190 T1050 190 T1200 190 V220 H0Z"/>' +
        '<path fill="' + s + '" opacity=".9" d="M1010 220 L1030 120 L1060 100 L1110 110 L1150 150 L1200 140 V220Z"/>';
    } else if (k === 'desert') {
      h += '<path fill="' + s + '" opacity=".4" d="M0 150 Q200 110 420 150 T840 140 T1200 150 V220 H0Z"/>' +
        '<path fill="' + s + '" opacity=".75" d="M0 185 Q260 150 560 185 T1200 180 V220 H0Z"/>' +
        '<g fill="' + s + '" opacity=".95"><rect x="896" y="100" width="18" height="90" rx="9"/><rect x="868" y="128" width="14" height="40" rx="7"/><rect x="868" y="156" width="36" height="12" rx="6"/><rect x="928" y="118" width="14" height="36" rx="7"/><rect x="906" y="146" width="36" height="12" rx="6"/>' +
        '<rect x="246" y="140" width="12" height="52" rx="6"/><rect x="228" y="156" width="10" height="24" rx="5"/><rect x="228" y="174" width="24" height="8" rx="4"/></g>';
    }
    return svgUrl(h + '</svg>');
  }
  function stars() {   // 星星：一组小圆点平铺在天空里
    var h = '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240">', i, x, y, r;
    for (i = 0; i < 28; i++) { x = (i * 97) % 240; y = (i * 53 + i * i * 7) % 240; r = i % 7 === 0 ? 1.4 : i % 3 === 0 ? 0.9 : 0.6; h += '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="#fff" opacity="' + (0.35 + (i % 5) * 0.12) + '"/>'; }
    return svgUrl(h + '</svg>');
  }
  function vars(sel, c) {
    return sel + '{--bg:' + c.bg + ';--paper:' + c.paper + ';--card:' + c.paper + ';--panel:' + c.paper + ';--chip:' + c.chip + ';--ink:' + c.ink + ';--soft:' + c.soft + ';--faint:' + c.faint +
      ';--line:' + c.line + ';--accent:' + c.ac + ';--accent-soft:' + c.acs + ';--accent-ink:' + c.aci + ';--shadow:0 1px 2px rgba(0,0,0,.05),0 6px 18px rgba(0,0,0,.05);background:' + c.bg + '!important}';
  }
  function layer(sel, k, c) {
    var bg = scene(k, c) + ' center bottom/100% auto no-repeat,' + (k === 'stars' ? stars() + ' 0 0/240px 240px repeat,' : '') +
      'linear-gradient(180deg,' + c.sky + ' 0%,' + c.bg + ' 42%,' + c.bg + ' 100%)';
    return sel + ' body::before{content:"";position:fixed;left:0;top:0;right:0;bottom:0;z-index:-1;pointer-events:none;background:' + bg + '}';
  }
  function css() {
    var out = '', k, i, t, sel;
    for (i = 0; i < ORDER.length; i++) {
      k = ORDER[i]; t = T[k]; sel = 'html[data-theme="' + k + '"]';
      out += vars(sel, t[3]) + layer(sel, k, t[3]);
      if (t[4]) out += '@media (prefers-color-scheme: dark){' + vars(sel, t[4]) + layer(sel, k, t[4]) + '}';
      else out += sel + '{color-scheme:dark}';
    }
    // 页面自己的 body 背景改成透明，才能看到底下那层风景
    out += 'html[data-theme] body{background:transparent!important}';
    return out;
  }

  function get() { try { var v = window.localStorage.getItem(KEY); return v && T[v] ? v : ''; } catch (e) { return ''; } }
  function themeColor(k) {
    var m = document.querySelector('meta[name="theme-color"]:not([media])') || document.querySelector('meta[name="theme-color"]');
    if (!k) { if (m && m.getAttribute('data-orig')) m.setAttribute('content', m.getAttribute('data-orig')); return; }
    var dark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches, c = (dark && T[k][4]) || T[k][3];
    if (!m) { m = document.createElement('meta'); m.name = 'theme-color'; document.head.appendChild(m); }
    if (!m.getAttribute('data-orig')) m.setAttribute('data-orig', m.getAttribute('content') || '');
    m.setAttribute('content', c.sky);
  }
  function apply(k) {
    var de = document.documentElement;
    if (k) de.setAttribute('data-theme', k); else de.removeAttribute('data-theme');
    try { themeColor(k); } catch (e) { }
  }
  function set(k) {
    k = T[k] ? k : '';
    try { if (k) window.localStorage.setItem(KEY, k); else window.localStorage.removeItem(KEY); } catch (e) { }
    apply(k);
  }

  var st = document.createElement('style'); st.id = 'theme-css'; st.textContent = css();
  (document.head || document.documentElement).appendChild(st);
  apply(get());
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { apply(get()); });
  window.addEventListener('storage', function (e) { if (e.key === KEY) apply(get()); });   // 别的标签页换了主题，这里跟着换

  window.THEME = {
    get: get, set: set,
    list: function () { return ORDER.map(function (k) { var t = T[k], c = t[3]; return { k: k, name: t[0], icon: t[1], desc: t[2], bg: c.bg, ac: c.ac, sky: c.sky, sil: c.sil }; }); }
  };
})();
