/* 心灵小站：读心 / 心理 / 逻辑 三个标签（解梦在 dream.html 里） */
(function () {
  'use strict';
  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function jget(k, d) { try { var v = localStorage.getItem('mind:' + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
  function jset(k, v) { try { localStorage.setItem('mind:' + k, JSON.stringify(v)); } catch (e) { } }
  function getJSON(u, cb) { var x = new XMLHttpRequest(); x.open('GET', u); x.onload = function () { var d = null; try { d = JSON.parse(x.responseText); } catch (e) { } cb(d); }; x.onerror = function () { cb(null); }; x.send(); }
  var HEAD = {
    dream: ['周公解梦', '老辈人的说法 + 心理学的角度，图个乐，也顺便了解自己'],
    read: ['读心术', '几个能当场表演的「读心魔术」，玩完再揭秘；外加察言观色的真相'],
    psy: ['心理学', '日常最常踩的心理效应和认知偏差，附投资里的表现'],
    logic: ['逻辑学', '常见逻辑谬误、推理基本功，和一组考脑子的推理题']
  };
  var MODE = 'dream', PSY = null, LOGIC = null;

  function setMode(m) {
    if (!HEAD[m]) m = 'dream';
    MODE = m;
    var bs = $('mtabs').querySelectorAll('button'), i;
    for (i = 0; i < bs.length; i++) bs[i].className = bs[i].getAttribute('data-m') === m ? 'on' : '';
    $('h1').textContent = HEAD[m][0]; $('sub').textContent = HEAD[m][1];
    $('dreamTop').hidden = $('vDream').hidden = m !== 'dream';
    $('vOther').hidden = m === 'dream';
    document.title = HEAD[m][0] + ' · 心灵小站';
    if (m === 'read') renderRead();
    else if (m === 'psy') { if (PSY) renderPsy(); else { $('vOther').innerHTML = '<div class="empty">加载中…</div>'; getJSON('mind/psy.json?v=1', function (d) { PSY = d; if (MODE === 'psy') renderPsy(); }); } }
    else if (m === 'logic') { if (LOGIC) renderLogic(); else { $('vOther').innerHTML = '<div class="empty">加载中…</div>'; getJSON('mind/logic.json?v=1', function (d) { LOGIC = d; if (MODE === 'logic') renderLogic(); }); } }
  }
  $('mtabs').onclick = function (e) { var b = e.target.closest('[data-m]'); if (!b) return; var m = b.getAttribute('data-m'); history.replaceState(null, '', m === 'dream' ? location.pathname : '#' + m); setMode(m); };

  /* ---------------- 读心 ---------------- */
  var SYMS = ['☀', '☾', '★', '♠', '♣', '♥', '♦', '☂', '☯', '♞', '⚓', '✿', '❄', '☘', '⚡', '♫', '✈', '☕', '⌛', '☎'];
  var T9 = null, BITS = 0, BSTEP = 0;
  function newGrid() {
    var magic = SYMS[Math.floor(Math.random() * SYMS.length)], g = [];
    for (var n = 99; n >= 0; n--) g.push([n, n % 9 === 0 && n <= 81 ? magic : SYMS[Math.floor(Math.random() * SYMS.length)]]);
    T9 = { magic: magic, g: g, shown: false };
  }
  function bitNums(b) { var a = []; for (var n = 1; n <= 63; n++) if (n & (1 << b)) a.push(n); return a; }
  function renderRead() {
    if (!T9) newGrid();
    var h = '<div class="sec">① 水晶球猜符号 <small>最经典的数字读心</small></div><div class="card trick"><ol class="steps">' +
      '<li>心里想一个 <b>10–99</b> 之间的两位数，比如 52。</li><li>用它减去它的两个数字之和：52 − (5+2) = 45。</li><li>在下面的表里找到你算出来的数，记住它旁边的符号。</li><li>想好了，点水晶球。</li></ol>' +
      '<div class="grid9">' + T9.g.map(function (x) { return '<span>' + x[0] + '<i>' + x[1] + '</i></span>'; }).join('') + '</div>' +
      (T9.shown ? '<div class="ball">' + T9.magic + '</div><div class="reveal" style="text-align:center">你心里想的符号是 <b style="font-size:20px">' + T9.magic + '</b>，对吧？</div>' : '<div class="ball" id="ball" style="cursor:pointer">🔮</div>') +
      '<button class="gbtn" id="t9again">再来一次（符号会全换）</button>' +
      '<details class="how"><summary>揭秘</summary>任何两位数减去它的数字之和，结果一定是 9 的倍数（9、18、27…81）。设这个数是 10a+b，减去 a+b 得 9a。表里所有 9 的倍数都配了同一个符号，其他数字的符号是随机的。每次换一套符号，别人就很难看出规律。表演时让对方别把结果说出来，效果更好。</details></div>';

    h += '<div class="sec">② 六张卡片猜数字 <small>二进制魔术</small></div><div class="card trick">';
    if (BSTEP < 6) {
      h += '<ol class="steps"><li>心里想一个 <b>1–63</b> 之间的数。</li><li>下面会出 6 张卡片，每张只要回答：你的数在不在这张卡上？</li></ol>' +
        '<div class="bcard"><b>第 ' + (BSTEP + 1) + ' / 6 张</b><div class="nums" style="margin-top:6px">' + bitNums(BSTEP).map(function (n) { return '<span>' + n + '</span>'; }).join('') + '</div>' +
        '<div class="yn"><button data-yn="1">✅ 在</button><button data-yn="0">❌ 不在</button></div></div>';
    } else {
      h += '<div class="ball">' + (BITS || '🤔') + '</div><div class="reveal" style="text-align:center">' + (BITS ? '你想的数是 <b style="font-size:20px">' + BITS + '</b>！' : '六张都不在？那你想的数不在 1–63 里吧 😄') + '</div><button class="gbtn" id="bagain">再来一次</button>';
    }
    h += '<details class="how"><summary>揭秘</summary>每张卡第一个数分别是 1、2、4、8、16、32。任何 1–63 的数都能唯一地写成这几个数之和（这就是二进制）。卡片上放的，正是「二进制这一位是 1」的所有数。对方说「在」的那几张，把第一个数加起来就是答案。自己做成纸卡，心算加法就能表演。</details></div>';

    h += '<div class="sec">③ 1089 预言 <small>纸笔就能玩</small></div><div class="card trick"><ol class="steps">' +
      '<li>想一个三位数，第一位和最后一位要差 2 以上，比如 742。</li><li>把它倒过来写（247），用大的减小的：742 − 247 = 495。</li><li>再把结果倒过来（594），和它相加：495 + 594 = ？</li></ol>' +
      '<div id="p1089"><button class="pbtn" id="b1089">揭晓我的预言</button></div>' +
      '<details class="how"><summary>揭秘</summary>设三位数是 abc（a 比 c 大 2 以上）。相减的结果中间一位一定是 9，前后两位加起来也是 9，比如 495、396、693。可能的结果只有 198、297、396、495、594、693、792、891 这几个，每个和它倒过来的数相加都正好是 1089。表演时可以事先把「1089」写在纸上折好，或者说「翻开书第 108 页第 9 行」。</details></div>';

    h += '<div class="sec">④ 察言观色：哪些是真的？ <small>按目前研究的结论</small></div><div class="card">' + [
      ['no', '说谎的人不敢看你的眼睛', '研究发现，说谎者并不比说真话的人更回避眼神；有经验的骗子反而会刻意盯着你看。'],
      ['no', '摸鼻子、摸脖子就是在撒谎', '这些动作更多反映紧张或不自在，说真话的人被怀疑时也会这样。'],
      ['no', '测谎仪能准确识破谎言', '测谎仪测的是心跳、出汗这类紧张反应，误判率高，美国大多数法庭不采信。'],
      ['half', '双手抱胸代表防备、抗拒', '有时是，但也可能只是冷、累或者习惯。要结合情境，单一动作说明不了什么。'],
      ['half', '瞳孔放大说明对你感兴趣', '兴趣和情绪激动确实会让瞳孔放大，但光线变暗影响大得多，现实里很难靠这个判断。'],
      ['half', '微表情能识破谎言', '微表情确实存在，但研究里靠它识别谎言的准确率并不比瞎猜高多少，培训效果也有限。'],
      ['ok', '真笑会牵动眼角（杜兴微笑）', '发自内心的笑通常伴随眼角肌肉收缩、出现鱼尾纹，礼貌性的假笑往往只有嘴在笑。不过有人也能刻意做出来。'],
      ['ok', '人整体上很不擅长识别谎言', '大量研究汇总显示，普通人判断真假话的准确率只比 50% 高一点点，警察和法官也差不多。']
    ].map(function (m) { return '<div class="myth"><span class="vd ' + m[0] + '">' + { ok: '靠谱', half: '看情况', no: '不靠谱' }[m[0]] + '</span><span><b>' + m[1] + '</b><br><span style="color:var(--soft)">' + m[2] + '</span></span></div>'; }).join('') + '</div>' +
      '<div class="foot">这里的读心术都是魔术和数学，没有超能力。真正的「读心」靠的是认真听、多问一句。</div>';
    $('vOther').innerHTML = h;
    if ($('ball')) $('ball').onclick = function () { T9.shown = true; renderRead(); };
    $('t9again').onclick = function () { newGrid(); renderRead(); };
    if ($('bagain')) $('bagain').onclick = function () { BITS = 0; BSTEP = 0; renderRead(); };
    var yn = $('vOther').querySelectorAll('[data-yn]'), i;
    for (i = 0; i < yn.length; i++) yn[i].onclick = function () { if (this.getAttribute('data-yn') === '1') BITS += 1 << BSTEP; BSTEP++; renderRead(); };
    $('b1089').onclick = function () { $('p1089').innerHTML = '<div class="ball">1089</div><div class="reveal" style="text-align:center">不管你一开始想的是哪个数，答案都是 <b>1089</b>。</div>'; };
  }

  /* ---------------- 心理 ---------------- */
  var PCAT = jget('pcat', '');
  function renderPsy() {
    if (!PSY) { $('vOther').innerHTML = '<div class="empty">加载失败，刷新试试</div>'; return; }
    var cats = [], cnt = {};
    PSY.items.forEach(function (e) { if (!cnt[e.c]) { cats.push(e.c); cnt[e.c] = 0; } cnt[e.c]++; });
    var list = PSY.items.filter(function (e) { return !PCAT || e.c === PCAT; });
    var h = '<div class="cats" id="pcats"><button data-c="" class="' + (PCAT ? '' : 'on') + '">全部<small>' + PSY.items.length + '</small></button>' +
      cats.map(function (c) { return '<button data-c="' + esc(c) + '" class="' + (c === PCAT ? 'on' : '') + '">' + esc(c) + '<small>' + cnt[c] + '</small></button>'; }).join('') + '</div>';
    h += list.map(function (e) {
      return '<div class="card"><div class="top"><h3>' + esc(e.k) + '</h3><span class="cat">' + esc(e.en) + '</span></div>' +
        '<div class="row"><span class="lb t">是什么</span><span>' + esc(e.d) + '</span></div>' +
        '<div class="row"><span class="lb x">例子</span><span>' + esc(e.e) + '</span></div>' +
        '<div class="row"><span class="lb x">避坑</span><span>' + esc(e.tip) + '</span></div>' +
        (e.inv ? '<div class="inv">📈 投资里：' + esc(e.inv) + '</div>' : '') + '</div>';
    }).join('');
    h += '<div class="foot">只收录研究比较扎实的效应；有争议的已在文中说明。</div>';
    $('vOther').innerHTML = h;
    $('pcats').onclick = function (e) { var b = e.target.closest('[data-c]'); if (!b) return; PCAT = b.getAttribute('data-c'); jset('pcat', PCAT); renderPsy(); };
  }

  /* ---------------- 逻辑 ---------------- */
  var LSUB = jget('lsub', 'quiz'), ANS = jget('ans', {}), MH = null, MHS = jget('mhs', { sw: [0, 0], st: [0, 0] });
  function renderLogic() {
    if (!LOGIC) { $('vOther').innerHTML = '<div class="empty">加载失败，刷新试试</div>'; return; }
    var subs = [['quiz', '🧩 推理题'], ['monty', '🚪 三门问题'], ['fal', '⚠️ 逻辑谬误'], ['basic', '📐 基本功']], h;
    h = '<div class="cats" id="lsubs">' + subs.map(function (x) { return '<button data-s="' + x[0] + '" class="' + (x[0] === LSUB ? 'on' : '') + '">' + x[1] + '</button>'; }).join('') + '</div>';
    if (LSUB === 'quiz') {
      var right = 0, done = 0;
      LOGIC.puzzles.forEach(function (p, i) { if (ANS[i] != null) { done++; if (ANS[i] === p.a) right++; } });
      h += '<div class="score">共 ' + LOGIC.puzzles.length + ' 题 · 已答 ' + done + ' · 答对 ' + right + (done ? ' <button class="gbtn" id="reset" style="margin:0 0 0 6px;padding:2px 10px">重做</button>' : '') + '</div>';
      LOGIC.puzzles.forEach(function (p, i) {
        var a = ANS[i];
        h += '<div class="card"><div style="font-weight:700;font-size:13px;color:var(--faint)">第 ' + (i + 1) + ' 题</div><div style="margin-top:4px">' + esc(p.q) + '</div>' +
          p.opts.map(function (o, j) { var c = a == null ? '' : j === p.a ? ' right' : j === a ? ' wrong' : ''; return '<button class="opt' + c + '" data-q="' + i + '" data-o="' + j + '"' + (a != null ? ' disabled' : '') + '>' + esc(o) + '</button>'; }).join('') +
          (a != null ? '<div class="reveal">' + (a === p.a ? '✅ 答对了！' : '❌ 正确答案是：' + esc(p.opts[p.a])) + '<br>' + esc(p.why) + '</div>' : '') + '</div>';
      });
    } else if (LSUB === 'monty') {
      if (!MH) MH = { car: Math.floor(Math.random() * 3), pick: null, open: null, final: null };
      var st = MH.final != null ? '揭晓！' + (MH.final === MH.car ? '🚗 你赢了车！' : '🐐 是只羊……') : MH.open != null ? '主持人打开了 ' + (MH.open + 1) + ' 号门，是只羊。你要换到另一扇门，还是坚持？' : '三扇门后面有一辆车和两只羊，先选一扇门。';
      h += '<div class="card"><div style="text-align:center;font-size:14.5px">' + st + '</div><div class="doors">' + [0, 1, 2].map(function (d) {
        var open = d === MH.open || MH.final != null, txt = open ? (d === MH.car ? '🚗' : '🐐') : d + 1;
        return '<button data-door="' + d + '" class="' + (open ? 'open ' : '') + (d === (MH.final != null ? MH.final : MH.pick) ? 'pick' : '') + '">' + txt + '</button>';
      }).join('') + '</div>' +
        (MH.open != null && MH.final == null ? '<div style="text-align:center"><button class="pbtn" id="mhSw">换门</button><button class="gbtn" id="mhSt">不换</button></div>' : '') +
        (MH.final != null ? '<div style="text-align:center"><button class="pbtn" id="mhNew">再玩一局</button></div>' : '') +
        '<div class="reveal">你的战绩：换门 ' + MHS.sw[0] + '/' + MHS.sw[1] + ' 次赢，不换 ' + MHS.st[0] + '/' + MHS.st[1] + ' 次赢。<br><button class="gbtn" id="mhSim" style="margin-top:6px">让电脑各玩 1 万局</button><span id="simOut"></span></div>' +
        '<details class="how" open><summary>为什么换门更好？</summary>一开始选中车的概率是 1/3。主持人知道车在哪，他一定会开一扇羊门，这不改变你最初那 1/3。剩下的 2/3 全部集中到了另一扇没开的门上，所以换门赢的概率是 2/3。想象成 100 扇门：你选 1 扇，主持人打开其他 98 扇羊门，你还会坚持吗？</details></div>';
    } else if (LSUB === 'fal') {
      h += LOGIC.fallacies.map(function (f) {
        return '<div class="card"><div class="top"><h3>' + esc(f.k) + '</h3><span class="cat">' + esc(f.en) + '</span></div>' +
          '<div class="row"><span class="lb t">是什么</span><span>' + esc(f.d) + '</span></div><div class="row"><span class="lb x">例子</span><span>' + esc(f.e) + '</span></div><div class="row"><span class="lb x">识破</span><span>' + esc(f.fix) + '</span></div></div>';
      }).join('');
    } else {
      h += LOGIC.basics.map(function (b) { return '<div class="card"><div class="top"><h3>' + esc(b.k) + '</h3></div><div class="row"><span class="lb t">解释</span><span>' + esc(b.d) + '</span></div><div class="row"><span class="lb x">例子</span><span>' + esc(b.e) + '</span></div></div>'; }).join('');
    }
    $('vOther').innerHTML = h;
    $('lsubs').onclick = function (e) { var b = e.target.closest('[data-s]'); if (!b) return; LSUB = b.getAttribute('data-s'); jset('lsub', LSUB); renderLogic(); };
    $('vOther').onclick = function (e) {
      var o = e.target.closest('[data-o]');
      if (o) { ANS[+o.getAttribute('data-q')] = +o.getAttribute('data-o'); jset('ans', ANS); var y = window.pageYOffset; renderLogic(); window.scrollTo(0, y); return; }
      var d = e.target.closest('[data-door]');
      if (d && MH && MH.pick == null) {
        MH.pick = +d.getAttribute('data-door');
        var cands = [0, 1, 2].filter(function (x) { return x !== MH.pick && x !== MH.car; });
        MH.open = cands[Math.floor(Math.random() * cands.length)]; renderLogic(); return;
      }
      if (e.target.id === 'mhSw' || e.target.id === 'mhSt') {
        var sw = e.target.id === 'mhSw';
        MH.final = sw ? [0, 1, 2].filter(function (x) { return x !== MH.pick && x !== MH.open; })[0] : MH.pick;
        var rec = sw ? MHS.sw : MHS.st; rec[1]++; if (MH.final === MH.car) rec[0]++; jset('mhs', MHS); renderLogic(); return;
      }
      if (e.target.id === 'mhNew') { MH = null; renderLogic(); return; }
      if (e.target.id === 'mhSim') {
        var w1 = 0, w2 = 0, N = 10000, k;
        for (k = 0; k < N; k++) { var car = Math.floor(Math.random() * 3), pick = Math.floor(Math.random() * 3); if (pick === car) w2++; else w1++; }
        $('simOut').innerHTML = '<br>换门赢了 <b>' + (w1 / 100).toFixed(1) + '%</b>，不换赢了 <b>' + (w2 / 100).toFixed(1) + '%</b>'; return;
      }
      if (e.target.id === 'reset') { ANS = {}; jset('ans', ANS); renderLogic(); }
    };
  }

  setMode((location.hash || '').replace('#', '') || 'dream');
})();
