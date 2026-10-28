/* 宽屏适配：平板 / 电脑上不再是手机宽度的一窄条。
   - 手机（窄于 760px）：什么都不做。
   - 找到被限制成手机宽度的主体容器（max-width 480–960 且居中），放宽到屏幕宽度（最多约 1240px）。
   - 里面的卡片列表在够宽时排成两列（很宽且卡片小时三列）；标题、分组名等非卡片元素占满一整行；
     含地图 / 大图 / 表格 / 画布的卡片也占满一整行。
   - 大段文字的区域限制行宽，方便阅读。
   - 任何元素加 data-tw="no" 就不处理它和它里面的东西。
   内容是后来渲染出来的也会跟上（MutationObserver，节流）。 */
(function () {
  'use strict';
  var MIN = 760;
  var css = '' +
    '.tw-cols{display:grid!important;grid-template-columns:repeat(var(--tw-n,2),minmax(0,1fr));gap:12px 14px;align-items:start}' +
    '.tw-cols>*{margin-top:0!important;margin-bottom:0!important;min-width:0}' +
    '.tw-cols>.tw-span{grid-column:1/-1}' +
    '.tw-cols>.tw-span:not(:first-child){margin-top:6px!important}' +
    '.tw-read{max-width:860px!important;margin-left:auto!important;margin-right:auto!important}';
  var st = document.createElement('style'); st.id = 'tw-css'; st.textContent = css;
  (document.head || document.documentElement).appendChild(st);

  var wrapped = [], timer = 0, lastW = 0, busy = false;

  function px(v) { return parseFloat(v) || 0; }
  function off(el) { return el.closest && el.closest('[data-tw="no"]'); }
  function target(vw) { return vw >= 1100 ? Math.min(1240, Math.round(vw * 0.92)) : Math.round(vw - 40); }

  // 1. 放宽主体容器：靠近顶层、max-width 在 480–960、宽度接近 max-width（即被它卡住）
  function widen(vw) {
    var cands = [], i, el;
    (function walk(node, depth) {
      for (var c = node.firstElementChild; c; c = c.nextElementSibling) {
        if (/^(SCRIPT|STYLE|LINK|META|TEMPLATE|SVG|CANVAS)$/i.test(c.tagName)) continue;
        cands.push(c);
        if (depth < 3) walk(c, depth + 1);
      }
    })(document.body, 0);
    for (i = 0; i < cands.length; i++) {
      el = cands[i];
      if (el.__twW || off(el)) continue;
      var cs = getComputedStyle(el);
      if (cs.position === 'fixed' || cs.position === 'absolute' || cs.display === 'none') continue;
      var mw = px(cs.maxWidth);
      if (!(mw >= 480 && mw <= 960)) continue;
      var p = el.parentElement, pw = p ? p.getBoundingClientRect().width : vw;
      if (pw < vw * 0.9) continue;                         // 只放宽占满整屏的父元素里的那一层
      if (el.getBoundingClientRect().width < mw - 2) continue;
      el.__twW = mw; wrapped.push(el);
    }
    var t = target(vw);
    for (i = 0; i < wrapped.length; i++) {
      el = wrapped[i];
      el.style.maxWidth = vw >= MIN ? Math.max(el.__twW, t) + 'px' : '';
    }
  }

  function cardLike(c) {
    if (c.nodeType !== 1 || /^(SCRIPT|STYLE|TEMPLATE|BR|HR)$/i.test(c.tagName)) return false;
    var cs = getComputedStyle(c);
    if (cs.display === 'none' || cs.position === 'absolute' || cs.position === 'fixed') return false;
    var r = px(cs.borderTopLeftRadius);
    var framed = px(cs.borderTopWidth) > 0 || cs.boxShadow !== 'none' ||
      (cs.backgroundColor && cs.backgroundColor !== 'rgba(0, 0, 0, 0)' && cs.backgroundColor !== 'transparent');
    return r >= 6 && framed && c.getBoundingClientRect().height > 36;
  }
  function needsFull(c) {
    if (c.querySelector('canvas,video,iframe,table,.leaflet-container,[data-tw-full]')) return true;
    var imgs = c.getElementsByTagName('img');
    for (var i = 0; i < imgs.length; i++) if (imgs[i].getBoundingClientRect().width > 320) return true;
    return c.hasAttribute('data-tw-full');
  }

  // 2. 卡片列表排成多列；3. 长文字限制行宽
  function columns(vw) {
    for (var w = 0; w < wrapped.length; w++) {
      var root = wrapped[w];
      var all = [root].concat(Array.prototype.slice.call(root.querySelectorAll('div,section,main,ul,ol,article,nav')));
      for (var i = 0; i < all.length; i++) {
        var box = all[i];
        if (off(box)) continue;
        if (box.classList.contains('tw-cols')) { tag(box); continue; }
        var kids = box.children; if (kids.length < 3) continue;
        var cs = getComputedStyle(box);
        if (cs.display === 'none' || cs.position === 'fixed') continue;
        var flexRow = (cs.display.indexOf('flex') >= 0 && cs.flexDirection.indexOf('row') === 0) ||
                      (cs.display.indexOf('grid') >= 0 && cs.gridTemplateColumns.split(' ').length > 1);
        if (flexRow) continue;
        var n = 0, vis = 0, ps = 0;
        for (var k = 0; k < kids.length; k++) {
          var c = kids[k];
          if (/^(P|H2|H3)$/.test(c.tagName)) ps++;
          if (getComputedStyle(c).display === 'none') continue;
          vis++; if (cardLike(c)) n++;
        }
        if (n >= 3 && n >= vis * 0.6) {
          box.classList.add('tw-cols'); box.__twCols = 1; tag(box);
        } else if (ps >= 3 && !box.querySelector('.tw-cols')) {
          box.classList.add('tw-read');
        }
      }
    }
    var list = document.querySelectorAll('.tw-cols');
    for (var j = 0; j < list.length; j++) {
      var bw = list[j].getBoundingClientRect().width || 0;
      var on = vw >= MIN && bw >= 700;
      list[j].style.display = on ? '' : 'block';
      list[j].classList.toggle('tw-off', !on);
      if (!on) { list[j].style.setProperty('display', 'block', 'important'); continue; }
      list[j].style.removeProperty('display');
      // 某张卡片比同组的高出一大截：让它独占一行，免得旁边空一大块（记住决定，避免来回跳）
      var hsArr = [], kk = list[j].children;
      for (var t = 0; t < kk.length; t++) if (!kk[t].classList.contains('tw-span')) hsArr.push(kk[t].getBoundingClientRect().height);
      if (hsArr.length >= 2) {
        var srt = hsArr.slice().sort(function (a, b) { return a - b; }), med = srt[Math.floor(srt.length / 2)];
        if (srt.length === 2) med = srt[0];
        for (var t2 = 0; t2 < kk.length; t2++) {
          var hh = kk[t2].getBoundingClientRect().height;
          if (!kk[t2].classList.contains('tw-span') && hh > Math.max(420, 2.4 * med)) { kk[t2].__twTall = 1; kk[t2].classList.add('tw-span'); }
        }
      }
      // 卡片都很矮又很宽的时候排三列
      var hs = 0, cnt = 0, kids2 = list[j].children;
      for (var m = 0; m < kids2.length; m++) if (!kids2[m].classList.contains('tw-span')) { hs += kids2[m].getBoundingClientRect().height; cnt++; }
      list[j].style.setProperty('--tw-n', bw >= 1100 && cnt && hs / cnt < 130 ? 3 : 2);
    }
  }
  function tag(box) {
    for (var k = 0; k < box.children.length; k++) {
      var c = box.children[k];
      c.classList.toggle('tw-span', !!c.__twTall || !cardLike(c) || needsFull(c));
    }
  }

  function run() {
    if (busy) return; busy = true;
    try {
      var vw = window.innerWidth;
      if (vw < MIN && lastW < MIN && !wrapped.length) { busy = false; return; }   // 手机：完全不动
      widen(vw);
      if (vw >= MIN) columns(vw);
      else { var l = document.querySelectorAll('.tw-cols'); for (var i = 0; i < l.length; i++) l[i].style.setProperty('display', 'block', 'important'); }
      if (Math.abs(vw - lastW) > 40) { lastW = vw; setTimeout(function () { window.dispatchEvent(new Event('resize')); }, 60); }   // 让地图等重新量尺寸
    } catch (e) { }
    busy = false;
  }
  function soon() { clearTimeout(timer); timer = setTimeout(run, 250); }

  run();
  window.addEventListener('load', soon);
  var rt = 0; window.addEventListener('resize', function () { if (busy) return; clearTimeout(rt); rt = setTimeout(run, 200); });
  try {
    new MutationObserver(function (ms) {
      for (var i = 0; i < ms.length; i++) { var t = ms[i].target; if (t.id !== 'tw-css' && !(t.closest && t.closest('.tnav-dr'))) { soon(); return; } }
    }).observe(document.body, { childList: true, subtree: true });
  } catch (e) { }
  window.TW = { run: run };
})();
