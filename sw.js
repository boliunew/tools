/* 离线缓存：先上网拿最新的，网络不通（或 5 秒没回应）就用上次存下的。
   只缓存本站文件；音频视频、跨站请求、断点续传都直接放行，不进缓存。 */
var CACHE = 'tools-v1';
var CORE = ['./', 'index.html', 'work.html', 'search.html', 'kb.html', 'tips.html', 'kitchen.html', 'convert.html', 'news.html',
  'nav.js?v=9', 'sync.js?v=1', 'tools.webmanifest', 'icons/icon-192.png'];
var SKIP = /\.(mp3|m4a|aac|ogg|opus|wav|flac|mp4|webm|m3u8|ts)(\?|$)/i;

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) {
    // 一个失败不影响其他的
    return Promise.all(CORE.map(function (u) { return c.add(u).catch(function () { }); }));
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
        done = true;
        resolve(hit || (r.mode === 'navigate' ? offlinePage() : Response.error()));
      });
    });
  }));
});
function offlinePage() {
  return new Response('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>没网</title>' +
    '<body style="font-family:-apple-system,sans-serif;padding:40px 20px;text-align:center;color:#444"><h2>📵 现在没网</h2>' +
    '<p>这一页之前没打开过，所以没存下来。</p><p><a href="work.html">现场工具</a> · <a href="index.html">首页</a> 这些打开过的页面没网也能用。</p></body>',
    { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
}
