/* 🌤️ 天气 + 注意事项（首页、通勤电台共用）
   WX.load(function (w) { ... })   w = { line, sub, tips: [{ lv: 'warn' | 'info' | 'ok', i: '图标', t: '文字' }] }
   数据来自 open-meteo（免费、不用密钥），按 Upland 算；20 分钟内重复打开用缓存。ES5。 */
(function () {
  'use strict';
  if (window.WX) return;
  var LOC = { name: 'Upland', lat: 34.0975, lon: -117.6484 }, KEY = 'wx:cache', TTL = 20 * 60000;
  var SKY = { 0: ['☀️', '晴'], 1: ['🌤️', '大致晴'], 2: ['⛅', '多云'], 3: ['☁️', '阴'], 45: ['🌫️', '有雾'], 48: ['🌫️', '雾凇'],
    51: ['🌦️', '毛毛雨'], 53: ['🌦️', '毛毛雨'], 55: ['🌧️', '毛毛雨'], 61: ['🌧️', '小雨'], 63: ['🌧️', '中雨'], 65: ['🌧️', '大雨'],
    80: ['🌦️', '阵雨'], 81: ['🌧️', '阵雨'], 82: ['⛈️', '强阵雨'], 95: ['⛈️', '雷阵雨'], 96: ['⛈️', '雷雨冰雹'], 99: ['⛈️', '雷雨冰雹'] };
  function sky(c) { return SKY[c] || (c >= 71 && c <= 86 ? ['🌨️', '雪'] : ['🌡️', '']); }
  function c(f) { return Math.round((f - 32) * 5 / 9); }
  function r(x) { return Math.round(x); }
  function hm(iso) { var m = /T(\d\d):(\d\d)/.exec(iso || ''); if (!m) return ''; var h = +m[1]; return (h > 12 ? h - 12 : h) + ':' + m[2] + (h >= 12 ? ' PM' : ' AM'); }
  function getJ(u, cb) {
    var x = new XMLHttpRequest(); x.open('GET', u); x.timeout = 10000;
    x.onload = function () { var d = null; if (x.status < 400) try { d = JSON.parse(x.responseText); } catch (e) { } cb(d); };
    x.onerror = x.ontimeout = function () { cb(null); }; x.send();
  }

  // 根据预报列出今天要注意的事。顺序：危险的在前，温馨提示在后
  function advise(W, A) {
    var cur = W.current || {}, d = W.daily || {}, t = [], g = function (k, i) { return d[k] ? d[k][i || 0] : null; };
    var hi = g('temperature_2m_max'), lo = g('temperature_2m_min'), feel = g('apparent_temperature_max'), code = g('weather_code');
    var rain = g('precipitation_probability_max'), mm = g('precipitation_sum'), uv = g('uv_index_max'), gust = g('wind_gusts_10m_max');
    var aqi = A && A.current ? A.current.us_aqi : null, hour = new Date().getHours(), late = hour >= 17 || hour < 4;
    if (late && d.temperature_2m_max && d.temperature_2m_max.length > 1) {   // 傍晚以后：白天的热、紫外线已经过去，改看明天
      var g1 = function (k) { return d[k] ? d[k][1] : null; };
      hi = g1('temperature_2m_max'); lo = g1('temperature_2m_min'); feel = g1('apparent_temperature_max'); code = g1('weather_code');
      rain = g1('precipitation_probability_max'); mm = g1('precipitation_sum'); uv = g1('uv_index_max'); gust = g1('wind_gusts_10m_max');
    }
    var day = late ? '明天' : '今天';
    function add(lv, i, s) { t.push({ lv: lv, i: i, t: s }); }

    // 热
    var hot = Math.max(hi || 0, feel || 0);
    if (hot >= 100) add('warn', '🥵', day + '酷热（最高 ' + r(hi) + '°F / ' + c(hi) + '°C）：一小时至少喝一瓶水；户外干活多歇几次，头晕、恶心、不出汗了马上到阴凉处；车里会到 140°F 以上，手机、充电宝、孩子和宠物都别留在车里');
    else if (hot >= 90) add('warn', '☀️', day + '很热（最高 ' + r(hi) + '°F）：多带水，中午少在太阳底下待；停车尽量找阴凉，方向盘和座椅会很烫');
    // 冷
    if (lo != null && lo <= 40) add('warn', '🥶', (late ? '明天' : '') + '早上很冷（最低 ' + r(lo) + '°F / ' + c(lo) + '°C）：穿厚外套、戴手套；挡风玻璃可能结霜，提前几分钟热车除霜');
    else if (lo != null && lo <= 50) add('info', '🧥', (late ? '明早' : '早晚') + '凉（最低 ' + r(lo) + '°F）：出门带件外套');
    // 温差
    if (hi != null && lo != null && hi - lo >= 25 && lo < 65) add('info', '🌡️', '早晚温差 ' + r(hi - lo) + '°F：穿能脱的外套，中午热了脱、傍晚再穿上');
    // 雨、雷、雾
    if (code >= 95) add('warn', '⛈️', day + '有雷雨：别在空旷地或大树下停留，打雷时待在车里或室内；可能有冰雹和短时大雨');
    if (rain != null && rain >= 50) add('warn', '☔', day + '下雨概率 ' + r(rain) + '%' + (mm ? '（约 ' + (Math.round(mm / 25.4 * 10) / 10) + ' 英寸）' : '') + '：带伞；南加州难得下雨，头一场雨路面积了油特别滑，车距拉大、开大灯、刹车提早');
    else if (rain != null && rain >= 25) add('info', '🌂', day + '可能会下雨（' + r(rain) + '%）：包里放把伞');
    if (cur.weather_code === 45 || cur.weather_code === 48 || code === 45 || code === 48) add('warn', '🌫️', '有雾：开近光灯和雾灯，慢点开，别跟车太近');
    // 风
    if (gust != null && gust >= 40) add('warn', '🌬️', '大风（阵风 ' + r(gust) + ' mph）' + (rain != null && rain < 20 ? '：干燥大风，可能是圣安娜风，山火风险高' : '') + '；开车握稳方向盘，尤其是高的厢车和拖车；小心掉下来的树枝，院子里的东西收好');
    else if (gust != null && gust >= 25) add('info', '💨', '有风（阵风 ' + r(gust) + ' mph）：骑车、开高车留意侧风，空气干，多喝水、擦润唇膏');
    // 紫外线、空气
    if (uv != null && uv >= 8) add('warn', '🧴', day + '紫外线很强（' + r(uv) + '）：戴帽子墨镜、抹防晒，10 点到 4 点晒得最厉害');
    else if (uv != null && uv >= 6) add('info', '🕶️', day + '紫外线偏强（' + r(uv) + '）：在外面久的话抹点防晒');
    if (aqi != null && aqi > 150) add('warn', '😷', '空气不健康（AQI ' + aqi + '）：少在外面运动，出门可以戴 N95；车里开内循环，关好门窗');
    else if (aqi != null && aqi > 100) add('warn', '😮‍💨', '空气对敏感人群不好（AQI ' + aqi + '）：有哮喘、鼻炎的少在外面剧烈运动，车里开内循环');
    // 天黑
    var ss = g('sunset'), m = /T(\d\d):(\d\d)/.exec(ss || '');
    if (m && (+m[1] < 17 || (+m[1] === 17 && +m[2] <= 30))) add('info', '🌆', '天黑得早（' + hm(ss) + ' 日落）：下班开车开大灯，过路口多看一眼行人');

    // 温馨提示：没什么要注意的时候也说点有用的
    var dry3 = d.precipitation_probability_max && Math.max.apply(null, d.precipitation_probability_max) < 20;
    if (!t.length) {
      if (hi != null && hi >= 65 && hi <= 85) add('ok', '😊', '天气舒服（' + r(lo) + '°–' + r(hi) + '°F），适合下班散散步、遛遛狗');
      else add('ok', '👍', '今天天气没什么要特别注意的');
    }
    if (dry3 && !(rain >= 25)) add('ok', '🚗', '接下来三天都不下雨，想洗车可以洗');
    if (hour >= 5 && hour < 11) add('ok', '💧', '出门前灌满水瓶；' + (hi >= 85 ? '今天热，午饭别吃太油' : '早餐吃了再走'));
    else if (hour >= 17 && hour < 23) {
      var tl = W.daily && W.daily.temperature_2m_min ? W.daily.temperature_2m_min[1] : null, tc = W.daily && W.daily.weather_code ? W.daily.weather_code[1] : null;
      if (tl != null && !t.some(function (x) { return x.lv !== 'ok'; })) add('ok', '🌙', '明天 ' + sky(tc)[1] + '，最低 ' + r(tl) + '°F，最高 ' + r(W.daily.temperature_2m_max[1]) + '°F' + (W.daily.precipitation_probability_max[1] >= 40 ? '，可能下雨，伞今晚先放门口' : ''));
    }
    var rank = { warn: 0, info: 1, ok: 2 };
    t.forEach(function (x, i) { x.k = i; });
    t.sort(function (a, b) { return rank[a.lv] - rank[b.lv] || a.k - b.k; });   // 要注意的排前面
    return t;
  }

  function build(W, A) {
    var cur = W.current || {}, d = W.daily || {}, s = sky(cur.weather_code != null ? cur.weather_code : (d.weather_code || [])[0]);
    if (cur.is_day === 0) {   // 夜里：晴天显示月亮
      var NIGHT = { '☀️': ['🌙', '晴夜'], '🌤️': ['🌙', '大致晴'], '⛅': ['☁️', '多云'] };
      if (NIGHT[s[0]]) s = NIGHT[s[0]];
    }
    var hi = d.temperature_2m_max ? d.temperature_2m_max[0] : null, lo = d.temperature_2m_min ? d.temperature_2m_min[0] : null;
    var line = s[0] + ' ' + LOC.name + ' ' + s[1] + (cur.temperature_2m != null ? ' · 现在 ' + r(cur.temperature_2m) + '°F（' + c(cur.temperature_2m) + '°C）' : '');
    var sub = (hi != null ? '今天 ' + r(lo) + '°–' + r(hi) + '°F' : '') + (cur.apparent_temperature != null && Math.abs(cur.apparent_temperature - cur.temperature_2m) >= 4 ? ' · 体感 ' + r(cur.apparent_temperature) + '°' : '') +
      (A && A.current && A.current.us_aqi != null ? ' · 空气 ' + A.current.us_aqi : '') + (d.sunset ? ' · 日落 ' + hm(d.sunset[0]) : '');
    var at = W.__at || Date.now(), ago = Math.round((Date.now() - at) / 60000);
    return { line: line, sub: sub + ' · ' + (ago < 1 ? '刚刚更新' : ago + ' 分钟前更新'), tips: advise(W, A), t: at };
  }

  function load(cb) {
    try { var c0 = JSON.parse(window.localStorage.getItem(KEY) || 'null'); if (c0 && Date.now() - c0.at < TTL && c0.W && c0.W.current && 'is_day' in c0.W.current) { c0.W.__at = c0.at; cb(build(c0.W, c0.A)); return; } } catch (e) { }
    var W = null, A = null, n = 2;
    function done() {
      if (--n) return;
      if (!W) { cb(null); return; }
      W.__at = Date.now();
      try { window.localStorage.setItem(KEY, JSON.stringify({ at: W.__at, W: W, A: A })); } catch (e) { }
      cb(build(W, A));
    }
    getJ('https://api.open-meteo.com/v1/forecast?latitude=' + LOC.lat + '&longitude=' + LOC.lon +
      '&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m,is_day' +
      '&daily=weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,precipitation_probability_max,precipitation_sum,uv_index_max,wind_gusts_10m_max,sunset' +
      '&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=mm&timezone=America%2FLos_Angeles&forecast_days=3', function (d) { W = d; done(); });
    getJ('https://air-quality-api.open-meteo.com/v1/air-quality?latitude=' + LOC.lat + '&longitude=' + LOC.lon + '&current=us_aqi&timezone=America%2FLos_Angeles', function (d) { A = d; done(); });
  }
  window.WX = { load: load, advise: advise, build: build };
})();
