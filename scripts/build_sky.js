#!/usr/bin/env node
/* 首页「天象」用的数据 → kb/sky.json
   用和知识库《天象日历》同一个库（vendor/astronomy-engine）按 Upland 算未来 15 个月的天象。
   GitHub Actions（kb.yml）每月跑一次；本地：node scripts/build_sky.js */
'use strict';
var path = require('path'), fs = require('fs');
var A = require(path.join(__dirname, '..', 'vendor', 'astronomy-engine-2.1.19.min.js'));
var TZ = 'America/Los_Angeles', HOME = { lat: 34.0975, lon: -117.6484, h: 370 };
var obs = new A.Observer(HOME.lat, HOME.lon, HOME.h);
var SHOWERS = [['象限仪座流星雨', 1, 4, 3, '80–120', '极大很短，看运气'], ['天琴座流星雨', 4, 22, 3, '18', ''], ['宝瓶座η流星雨', 5, 6, 4, '50', '北半球偏少，黎明前看'],
  ['英仙座流星雨', 8, 13, 2, '100', '最适合入门'], ['猎户座流星雨', 10, 22, 3, '20', '哈雷彗星的碎屑'], ['狮子座流星雨', 11, 18, 3, '15', ''], ['双子座流星雨', 12, 14, 1, '120–150', '一年里最稳最多的一场']];

// 洛杉矶时间的显示和构造（Actions 上的机器是 UTC）
var fmt = new Intl.DateTimeFormat('en-US', { timeZone: TZ, hourCycle: 'h23', year: 'numeric', month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric' });
function parts(d) { var o = {}; fmt.formatToParts(d).forEach(function (p) { o[p.type] = +p.value; }); return o; }
function hm(d) { var p = parts(d); return ('0' + p.hour).slice(-2) + ':' + ('0' + p.minute).slice(-2); }
function ymd(d) { var p = parts(d); return p.year + '-' + ('0' + p.month).slice(-2) + '-' + ('0' + p.day).slice(-2); }
function la(y, m, d, h) {   // 洛杉矶当地 y-m-d h:00 对应的 Date
  var guess = Date.UTC(y, m - 1, d, h), p = parts(new Date(guess));
  var off = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute) - guess;
  return new Date(guess - off);
}
function altOf(body, date) { var eq = A.Equator(body, date, obs, true, true); return A.Horizon(date, obs, eq.ra, eq.dec, 'normal').altitude; }

var now = new Date(), start = new Date(now.getTime() - 2 * 864e5), end = new Date(now.getTime() + 460 * 864e5), ev = [];
// day = 当地日期（首页按它判断「今天 / 明天」）；k = 种类，首页按种类决定提前几天提示
function add(date, day, k, icon, t, s) { ev.push({ day: day, at: date.toISOString(), k: k, icon: icon, t: t, s: s || '' }); }

// 新月、满月
var q = A.SearchMoonQuarter(start);
for (var n = 0; q && q.time.date < end && n < 80; n++) {
  if (q.quarter === 0) add(q.time.date, ymd(q.time.date), 'moon', '🌑', '新月', '前后几晚没有月光，最适合看星星和银河');
  if (q.quarter === 2) add(q.time.date, ymd(q.time.date), 'moon', '🌕', '满月', hm(q.time.date) + ' 最圆，整晚都亮');
  q = A.NextMoonQuarter(q);
}
// 二分二至
[parts(now).year, parts(now).year + 1].forEach(function (y) {
  var s = A.Seasons(y);
  [[s.mar_equinox, '🌸', '春分'], [s.jun_solstice, '☀️', '夏至', '白天最长'], [s.sep_equinox, '🍂', '秋分'], [s.dec_solstice, '❄️', '冬至', '白天最短']].forEach(function (x) {
    var d = x[0].date; if (d > start && d < end) add(d, ymd(d), 'season', x[1], x[2], x[3] || '');
  });
});
// 月食（这里看得到的）
var KL = { penumbral: '半影月食', partial: '月偏食', total: '月全食' }, le = A.SearchLunarEclipse(start);
for (n = 0; n < 40 && le.peak.date < end; n++) {
  var pk = le.peak.date, alt = altOf(A.Body.Moon, pk), sd = le.sd_partial || le.sd_penum;
  var a1 = altOf(A.Body.Moon, new Date(pk.getTime() - sd * 6e4)), a2 = altOf(A.Body.Moon, new Date(pk.getTime() + sd * 6e4));
  if (alt > 0 || a1 > 0 || a2 > 0) {
    var sub = (le.kind === 'total' ? '全食 ' + hm(new Date(pk.getTime() - le.sd_total * 6e4)) + '–' + hm(new Date(pk.getTime() + le.sd_total * 6e4)) + '，' : '') +
      '食甚 ' + hm(pk) + (alt > 0 ? '，月亮高 ' + Math.round(alt) + '°' : '，这里只能看到一部分') + (le.kind === 'penumbral' ? '。半影月食肉眼几乎看不出' : '。肉眼直接看');
    add(pk, ymd(pk), le.kind === 'penumbral' ? 'minor' : 'eclipse', '🌘', KL[le.kind], sub);
  }
  le = A.NextLunarEclipse(le.peak);
}
// 日食（这里看得到的）
var KS = { partial: '日偏食', annular: '日环食', total: '日全食' }, se = A.SearchLocalSolarEclipse(start, obs);
for (n = 0; n < 20 && se.peak.time.date < end; n++) {
  if (se.peak.altitude > 0) {
    var d = se.peak.time.date, pct = Math.round(se.obscuration * 100);
    add(d, ymd(d), pct >= 10 ? 'eclipse' : 'minor', '🌒', KS[se.kind], hm(d) + ' 遮住太阳 ' + pct + '%。一定要戴日食眼镜');
  }
  se = A.NextLocalSolarEclipse(se.peak.time, obs);
}
// 行星冲日
[['Mars', '火星'], ['Jupiter', '木星'], ['Saturn', '土星']].forEach(function (p) {
  var t = A.SearchRelativeLongitude(A.Body[p[0]], 0, start);
  for (var i = 0; i < 2 && t && t.date < end; i++) {
    add(t.date, ymd(t.date), 'planet', '🪐', p[1] + '冲日', '整夜可见、一年里最亮（' + A.Illumination(A.Body[p[0]], t).mag.toFixed(1) + ' 等），前后一两个月都好看');
    t = A.SearchRelativeLongitude(A.Body[p[0]], 0, t.AddDays(30));
  }
});
// 金星、水星大距
[['Mercury', '水星'], ['Venus', '金星']].forEach(function (p) {
  var e = A.SearchMaxElongation(A.Body[p[0]], start);
  for (var i = 0; i < 12 && e && e.time.date < end; i++) {
    var eve = e.visibility === 'evening', d = e.time.date;
    add(d, ymd(d), 'planet', eve ? '🌇' : '🌅', p[1] + (eve ? '东大距' : '西大距'), (eve ? '傍晚日落后在西边' : '黎明前在东边') + '，离太阳 ' + Math.round(e.elongation) + '°' + (p[0] === 'Mercury' ? '，很低，找视野开阔的地方' : ''));
    e = A.SearchMaxElongation(A.Body[p[0]], e.time.AddDays(5));
  }
});
// 流星雨：极大那天凌晨的月光；首页按「前一天晚上」提示
[parts(now).year, parts(now).year + 1, parts(now).year + 2].forEach(function (y) {
  SHOWERS.forEach(function (s) {
    var peak = la(y, s[1], s[2], s[3]);
    if (peak < start || peak > end) return;
    var il = A.Illumination(A.Body.Moon, peak).phase_fraction, up = altOf(A.Body.Moon, peak) > 0;
    var moon = !up || il < 0.3 ? '月光不碍事' : il < 0.7 ? '有些月光' : '月光干扰大';
    var eve = la(y, s[1], s[2] - 1, 21);
    add(eve, ymd(eve), 'shower', '🌠', s[0], ymd(eve).slice(5).replace('-', '/') + ' 夜里到次日凌晨 · ' + moon + '（月亮 ' + Math.round(il * 100) + '%）· 理想每小时 ' + s[4] + ' 颗' + (s[5] ? ' · ' + s[5] : ''));
  });
});

ev.sort(function (a, b) { return a.at < b.at ? -1 : 1; });
var out = { generated: now.toISOString(), loc: 'Upland, CA', tz: TZ, events: ev };
fs.writeFileSync(path.join(__dirname, '..', 'kb', 'sky.json'), JSON.stringify(out));
console.log(ev.length + ' events → kb/sky.json, through ' + ev[ev.length - 1].day);
