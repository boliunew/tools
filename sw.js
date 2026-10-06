/* 离线缓存：先上网拿最新的，网络不通（或 5 秒没回应）就用上次存下的。
   只缓存本站文件；音频视频、跨站请求、断点续传都直接放行，不进缓存。
   装好时先把常用页面和数据存一份，没打开过的页面在没信号时也能看。 */
var CACHE = 'tools-v3';
var NAMES = {
  'index.html': '🏠 首页', 'work.html': '🦺 现场工具', 'search.html': '🔍 全站搜索', 'kb.html': '🗂️ 知识库', 'tips.html': '💡 技巧与科普',
  'kitchen.html': '🍳 厨房与养生', 'convert.html': '💱 汇率与单位换算', 'news.html': '📰 新闻', 'stocks.html': '📈 今日股票池',
  'earnings.html': '📅 财报与经济日历', 'deals.html': '🏷️ 打折雷达', 'toolbox.html': '🧰 工具箱', 'people.html': '⭐ 人物专栏',
  'dream.html': '🌙 心灵小站', 'speak.html': '🗣️ 开口说', 'card.html': '🎴 每日一句', 'radio.html': '🚗 通勤电台',
  'fm.html': '📻 环球网络电台', 'books.html': '🎧 听书', 'sleep.html': '😴 夜之声', 'player.html': '🎬 探测播放器',
  'monitor.html': '🔔 网页监控', 'english.html': '🔤 英语练习', 'spanish.html': '🇲🇽 西班牙语练习', 'sublingo.html': '🎞️ SubLingo',
  'vocab.html': '📖 语境词库', 'hanzi.html': '字 汉字练习'
};
// vocab.html（3.7 MB）和 hanzi.html（1.8 MB）太大，不预先存；打开过一次以后照样能离线用
var PAGES = Object.keys(NAMES).filter(function (p) { return p !== 'vocab.html' && p !== 'hanzi.html'; });
var CORE = ['./', 'nav.js?v=11', 'sync.js?v=1', 'lookup.js', 'tools.webmanifest', 'icons/icon-192.png', 'mind/mind.js'].concat(PAGES);
var DATA = [
  'news/data/today.json', 'card/today.json', 'card/daily.json', 'stocks/data/latest.json', 'earnings/data/latest.json',
  'kitchen/wellness.json', 'kitchen/recipes_cn.json', 'kitchen/recipes_cn2.json', 'kitchen/recipes_cn3.json',
  'kitchen/recipes_west.json', 'kitchen/recipes_west2.json', 'kitchen/recipes_west3.json',
  'tips/tips.json', 'kb/index.json', 'dream/dreams.json', 'mind/logic.json', 'mind/psy.json',
  'people/gm.json', 'people/sushi_a.json', 'people/sushi_b.json',
  'speak/en_work.json', 'speak/en_life.json', 'speak/en_spoken.json', 'speak/es_yard.json'
];
var SKIP = /\.(mp3|m4a|aac|ogg|opus|wav|flac|mp4|webm|m3u8|ts)(\?|$)/i;

function addAll(c, list) {
  // 一个失败不影响其他的
  return Promise.all(list.map(function (u) { return c.add(u).catch(function () { }); }));
}
self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) {
    return addAll(c, CORE.concat(DATA)).then(function () {
      // 知识库的每篇文章：按目录里的 slug 存 .md
      return c.match('kb/index.json').then(function (r) { return r ? r.json() : null; }).then(function (d) {
        var list = d && d.articles ? d.articles.map(function (a) { return 'kb/' + encodeURIComponent(a.slug) + '.md'; }) : [];
        return addAll(c, list);
      }).catch(function () { });
    });
  }).then(function () { return self.skipWaiting(); }));
});
self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (ks) {
    return Promise.all(ks.filter(function (k) { return k.indexOf('tools-') === 0 && k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});
self.addEventListener('fetch', function (e) {
  var r = e.request, u = new URL(r.url);
  if (r.method !== 'GET' || u.origin !== self.location.origin || r.headers.has('range') || SKIP.test(u.pathname)) return;
  if (u.pathname.indexOf('/api/') >= 0) return;   // 家里主机的接口不缓存
  e.respondWith(new Promise(function (resolve) {
    var done = false;
    function fromCache() {
      return caches.match(r, { ignoreSearch: false }).then(function (hit) {
        return hit || caches.match(r, { ignoreSearch: true });
      });
    }
    var timer = setTimeout(function () {
      fromCache().then(function (hit) { if (hit && !done) { done = true; resolve(hit); } });
    }, 5000);
    fetch(r).then(function (res) {
      clearTimeout(timer);
      if (res && res.status === 200 && res.type === 'basic') {
        var copy = res.clone(), key = /[?&](t|_)=\d/.test(u.search) ? u.origin + u.pathname : r;   // 带时间戳防缓存的只存一份
        caches.open(CACHE).then(function (c) { c.put(key, copy); });
      }
      if (!done) { done = true; resolve(res); }
    }, function () {
      clearTimeout(timer);
      fromCache().then(function (hit) {
        if (done) return;
        if (hit) { done = true; resolve(hit); return; }
        if (r.mode !== 'navigate') { done = true; resolve(Response.error()); return; }
        offlinePage().then(function (p) { if (!done) { done = true; resolve(p); } });
      });
    });
  }));
});
function offlinePage() {
  // 列出这台设备上已经存下来的页面，没网时也能直接点过去
  return caches.open(CACHE).then(function (c) { return c.keys(); }).then(function (ks) {
    var seen = {}, links = '';
    ks.forEach(function (q) {
      var f = new URL(q.url).pathname.split('/').pop() || 'index.html';
      if (NAMES[f] && !seen[f]) { seen[f] = 1; links += '<a href="' + f + '">' + NAMES[f] + '</a>'; }
    });
    return links;
  }).catch(function () { return ''; }).then(function (links) {
    return new Response('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>没网</title>' +
      '<style>body{font-family:-apple-system,"PingFang SC",sans-serif;padding:36px 16px;max-width:520px;margin:0 auto;color:#16212B;background:#F4F6F7}' +
      '@media (prefers-color-scheme:dark){body{color:#E8EEF1;background:#12181D}a{background:#1B242B!important;border-color:#2A363F!important}}' +
      'h2{margin:0 0 6px}p{color:#5C6B77;margin:0 0 18px}a{display:block;padding:12px 14px;margin-bottom:8px;border-radius:12px;background:#fff;border:1px solid #D7DEE2;color:inherit;text-decoration:none}</style>' +
      '<h2>📵 现在没网</h2><p>这一页还没存下来。下面这些已经存在这台设备上，没网也能打开：</p>' +
      (links || '<a href="index.html">🏠 首页</a>'),
      { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
  });
}
