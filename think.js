/* 🧠 思考本的共用部分：读写笔记、从新闻提取关键词、判断一条新闻和哪条笔记有关。
   news.html（「💭 记一笔」和「你之前想过」）、think.html、index.html（首页卡片）都用它。ES5，存在 localStorage「think:notes」。 */
(function () {
  'use strict';
  if (window.Think) return;
  var KEY = 'think:notes';
  var STOP = ('the a an and or but of to in on at for from by with as is are was were be been being has have had will would can could should may might must not no it its this that these those ' +
    'he she they them his her their our we you your who whom whose which what when where why how than then there here into onto over under after before about against between during ' +
    'without within up down out off says said say new more most some any all many much also just still amid report reports update live video watch photos year years day days week weeks ' +
    'month months first last two three one people man woman men women told amid after over could would says latest news first since what will says calls call make makes made take takes ' +
    'set sets back home time times government officials official country countries world global state states minister president leader leaders plan plans deal talks').split(' ');
  var SW = {}; STOP.forEach(function (w) { SW[w] = 1; });
  // 国家、首都、民族名不当关键词：国家已经单独按「国家标签」比对了，用它当关键词会把所有提到这个国家的新闻都连上
  ('china chinese beijing america american washington japan japanese tokyo india indian delhi russia russian moscow kremlin ukraine ukrainian kyiv israel israeli iran iranian ' +
   'taiwan taiwanese korea korean seoul philippine filipino manila britain british london france french paris germany german berlin canada canadian ottawa mexico mexican ' +
   'brazil brazilian australia australian vietnam vietnamese pakistan europe european gaza palestinian lebanon syria saudi turkey turkish asia asian africa african').split(' ').forEach(function (w) { SW[w] = 1; });

  function load() { try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch (e) { return []; } }
  function save(list) { try { localStorage.setItem(KEY, JSON.stringify(list)); return true; } catch (e) { return false; } }
  function stem(w) { w = w.toLowerCase().replace(/[’']s$/, ''); if (w.length > 5 && /ies$/.test(w)) return w.slice(0, -3) + 'y'; if (w.length > 4 && /s$/.test(w) && !/ss$/.test(w)) return w.slice(0, -1); return w; }
  function words(text) {
    var out = [], seen = {};
    String(text || '').replace(/[A-Za-z][A-Za-z\-]{2,}/g, function (w) {
      var s = stem(w);
      if (s.length < 4 || SW[s] || seen[s]) return w;
      seen[s] = 1; out.push(s); return w;
    });
    return out;
  }
  // 从英文标题里挑关键词：标题里的词优先，最多 6 个
  function keywords(en, summary) {
    var t = words(en), s = words(summary), out = t.slice(0, 6);
    for (var i = 0; i < s.length && out.length < 6; i++) if (out.indexOf(s[i]) < 0) out.push(s[i]);
    return out;
  }
  // 一条新闻（{e: 英文标题, es: 英文摘要, c: [国家], i: [影响]}）和一条笔记有多相关；0 表示无关
  function score(note, st) {
    if (!note || !note.kw || !note.kw.length) return 0;
    var ws = {}; words((st.e || '') + ' ' + (st.es || '')).forEach(function (w) { ws[w] = 1; });
    var k = 0; note.kw.forEach(function (w) { var x = stem(w); if (!SW[x] && ws[x]) k++; });
    if (!k) return 0;
    var c = 0; (note.c || []).forEach(function (x) { if ((st.c || []).indexOf(x) >= 0) c++; });
    var i = 0; (note.imp || []).forEach(function (x) { if ((st.i || []).indexOf(x) >= 0) i++; });
    // 三个以上关键词对上就算；少于三个时国家要一样（「无人机袭击」到处都有），只对上一个词时影响领域也要一样
    if (k >= 3 || (c >= 1 && (k >= 2 || i >= 1))) return 2 * k + c + i;
    return 0;
  }
  function related(st, list) {
    list = list || load();
    return list.map(function (n) { return [score(n, st), n]; }).filter(function (x) { return x[0] > 0; }).sort(function (a, b) { return b[0] - a[0]; }).map(function (x) { return x[1]; });
  }
  function id() { return 'n' + Date.now().toString(36) + Math.random().toString(36).slice(2, 5); }
  // 从一条新闻起一份草稿，跳到思考本
  function draft(st) {
    try { localStorage.setItem('think:draft', JSON.stringify(st)); } catch (e) { }
    location.href = 'think.html#new';
  }
  window.Think = { load: load, save: save, keywords: keywords, words: words, score: score, related: related, id: id, draft: draft, stem: stem };
})();
