/* 🌀 穿越按钮 — a small tab on the left edge of every tool page that opens a drawer to jump to any other page.
   Drag the tab up/down to move it; the position is remembered. ES5, self-contained, no dependencies. */
(function () {
  'use strict';
  if (window.__tnav) return;
  window.__tnav = 1;

  var LOCAL = !!window.TOOLS_LOCAL;   // 家里主机上才显示的页面
  var GROUPS = [
    ['🔍 常用', [['search.html', '🔍', '全站搜索', '技巧、菜谱、知识库、诗词、梦……一起搜'], ['work.html', '🦺', '现场工具', '柜号校验 · 装柜计算 · 换算 · 验柜拍照 · 工作日志']]],
    ['🎧 听', [['radio.html', '🚗', '通勤电台', '开车听：天气、大盘、新闻、单词'], ['fm.html', '📻', '环球网络电台', '俄德英美中，显示正在播的歌'], ['books.html', '🎧', '听书 · 广播剧', 'LibriVox 有声书和老广播剧'], ['sleep.html', '😴', '夜之声 · 助眠', '白噪音、声景旅程、温柔唤醒'], ['player.html', '🎬', '探测播放器', '']]],
    ['📚 学', [['speak.html', '🗣️', '开口说 · 跟读', '工作/生活英语 · 美式口语 · 现场西语，跟读打分'], ['hanzi.html', '字', '汉字练习', '儿童识字 · HSK'], ['english.html', '🔤', '英语练习', '单词、句子、习语口头禅'], ['spanish.html', '🇲🇽', '西班牙语练习', '墨西哥发音，el / la 看图记'], ['card.html', '🎴', '每日一句 · 单词抽卡', '名言 / 习语 + 从词库抽卡复习'], ['vocab.html', '📖', '语境词库', '20000 词，语境里记单词'], ['sublingo.html', '🎞️', 'SubLingo', '字幕和文章逐句分析']]],
    ['📰 读', [['brief.html', '☀️', '每日简报', 'AI 科技 · 美股 · 宏观 · 世界大事，10 分钟看完'], ['news.html', '📰', '新闻', '今日大事 · 国际局势（分大洲）· 趣闻 · 历史上的今天 · 英文精选'], ['think.html', '🧠', '思考本', '我的判断 · 证据 · 没想通的问题 · 关注事件的时间线'], ['kb.html', '🗂️', '知识库', '天文 · 投资 · 物流 · FBA · 主机 · 人文'], ['kb.html#uw-index', '🧭', '理解世界', '历史 · 政治 · 经济 · 中国 · 美国史 · 中东 · 移民与税'], ['tips.html', '💡', '技巧与科普', '手机 · 电脑 · 防骗 · 生活 · 风土习俗 · 旅游景点'], ['people.html', '⭐', '人物专栏', '苏轼 · George Michael · 阿西莫夫 · 人生七年 · 疑犯追踪 · 怪诞小镇']]],
    ['💰 钱', [['stocks.html', '📈', '今日股票池', '短线信号 · 自选提醒 · VOO 体检'], ['earnings.html', '📅', '财报与经济日历', ''], ['deals.html', '🏷️', '打折雷达', '本周广告 + 比价 + 🔔 关注'], ['convert.html', '💱', '汇率与单位换算', '实时汇率 · 长度重量体积 · 温度油耗胎压']]],
    ['🏠 生活', [['usa.html', '🇺🇸', '美国生活指南', '办证 · 租房 · 开车 · 银行 · 看病 · 工作 · 购物 · 防骗 · 法律 · 家务'], ['kitchen.html', '🍳', '厨房与养生', '238 道中西菜和面食 · 做菜计时 · 节气养生'], ['amtrak.html', '🚆', 'Amtrak 火车旅行', '线路 · 时刻 · 实时列车 · 订票 · 卧铺 · 行程'], ['flights.html', '✈️', '机票比价', '一键查 6 家 · 常飞航线 · 省钱技巧 · 出发清单'], ['coast.html', '🌊', '加州海岸线', '红杉到边境墙 · 地图 · 自驾路线 · 季节 · 路况 · 打卡'], ['sf.html', '🌆', '城市生活', '旧金山 · 圣何塞 · 纽约 · 洛杉矶 · 内陆帝国：街区 · 吃喝 · 秘籍 · 故事 · 交通图'], ['holidays.html', '🗓️', '节假日倒计时', '中国放假调休 · 美国联邦假日 · 美股休市'], ['dream.html', '🌙', '心灵小站', '周公解梦 · 读心魔术 · 心理效应 · 逻辑推理']]],
    ['🛠️ 工具', [['status.html', '🩺', '系统状态', '数据有没有按时更新 · 自动任务 · 地图接口 · 每月备份'], ['darkroom.html', '🎞️', '暗房', '照片微调 · 一键美化 · 裁剪 · 偏光 · 导出保留拍摄信息'], ['polar.html', '🕶️', '偏光滤镜', '模拟偏光墨镜观感 · 天空加深 · 压反光 · 降低灰雾'], ['toolbox.html', '🧰', '工具箱', '文本 · 对比 · JSON · Base64 · 哈希 · 时间戳 · 正则'], ['dl.html', '📥', '媒体下载', '𝕏 推特 · Instagram 照片和视频'], ['monitor.html', '🔔', '网页监控', ''], ['pan.html', '☁️', '夸克网盘搜索', '搜分享链接 · 拆提取码 · 收藏']].concat(LOCAL ? [['issues.html', '📬', '通知中心', '股价提醒和监控的记录'], ['migrate.html', '🧳', '搬家', '导出 / 导入全部进度']] : [])]
  ];
  var ALL = {}, g, i;
  for (g = 0; g < GROUPS.length; g++) for (i = 0; i < GROUPS[g][1].length; i++) ALL[GROUPS[g][1][i][0]] = GROUPS[g][1][i];

  function here() { var p = (window.location.pathname || '').split('/').pop(); return p || 'index.html'; }
  function get(k, d) { try { var v = window.localStorage.getItem('tnav:' + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } }
  function put(k, v) { try { window.localStorage.setItem('tnav:' + k, JSON.stringify(v)); } catch (e) { } }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  var cur = here();

  // 🔗 相关：每个页面跟哪些工具、知识库文章相通（页面底部一条 + 穿越抽屉顶部）
  var K = function (slug, t) { return ['kb.html#' + slug, '📘', t]; };
  var CITY = [['coast.html', '🌊', '加州海岸线'], ['amtrak.html', '🚆', 'Amtrak'], ['usa.html', '🇺🇸', '美国生活指南'], K('travel-road-trip', '公路旅行和租车'), K('travel-scams', '旅行防骗'), ['holidays.html', '🗓️', '节假日']];
  var LANG = [['speak.html', '🗣️', '开口说'], ['vocab.html', '📖', '语境词库'], ['card.html', '🎴', '单词抽卡'], ['english.html', '🔤', '英语练习'], ['sublingo.html', '🎞️', 'SubLingo'], ['news.html#en', '📰', '英文新闻精选']];
  var LISTEN = [['radio.html', '🚗', '通勤电台'], ['fm.html', '📻', '网络电台'], ['books.html', '🎧', '听书'], ['sleep.html', '😴', '助眠'], ['player.html', '🎬', '播放器']];
  var REL = {
    'work.html': [K('yard-terms-glossary', '码头堆场术语'), K('iso-6346-check-digit', '柜号校验原理'), K('container-type-codes', '箱型代码'), K('truck-trailer-types', '卡车和拖车类型'), K('hazmat-placards', '危险品标牌'), K('load-planning-cbm', '装柜计算'), K('la-lb-ports-guide', '洛杉矶/长滩港'), K('container-logistics-101', '集装箱物流入门'), ['ie.html#work', '🍊', 'IE 物流和防暑'], ['news.html#world', '🌍', '国际局势（航运影响）'], ['spanish.html', '🇲🇽', '现场西语']],
    'stocks.html': [['earnings.html', '📅', '财报与经济日历'], ['news.html#world', '🌍', '国际局势和影响'], K('stock-pool-signals', '股票池信号怎么看'), K('my-trading-systems', '我的交易系统'), K('economic-indicators', '经济数据'), K('index-fund-dca', '指数基金定投'), K('investing-psychology', '投资心理'), K('market-crash-history', '股灾史'), K('us-investment-accounts-tax', '投资账户与税'), ['convert.html', '💱', '汇率换算']],
    'earnings.html': [['stocks.html', '📈', '今日股票池'], ['news.html#world', '🌍', '国际局势'], K('economic-indicators', '经济数据怎么看'), K('stock-pool-signals', '股票池信号')],
    'think.html': [['news.html#world', '🌍', '国际局势'], K('uw-index', '🧭 理解世界'), ['kb.html', '🗂️', '知识库'], ['stocks.html', '📈', '股票池'], K('investing-psychology', '投资心理（判断和偏差）'), ['migrate.html', '🧳', '搬家（备份）']],
    'news.html': [['think.html', '🧠', '思考本'], K('uw-index', '🧭 理解世界'), ['stocks.html', '📈', '股票池'], ['earnings.html', '📅', '财报日历'], K('la-lb-ports-guide', '港口指南'), K('customs-tariff-basics', '关税基础'), ['convert.html', '💱', '汇率'], ['sublingo.html', '🎞️', 'SubLingo 精读'], ['vocab.html', '📖', '语境词库']],
    'kb.html': [K('uw-index', '🧭 理解世界'), ['search.html', '🔍', '全站搜索'], ['tips.html', '💡', '技巧与科普'], ['usa.html', '🇺🇸', '美国生活指南']],
    'tips.html': [['kb.html', '🗂️', '知识库'], ['usa.html', '🇺🇸', '美国生活指南'], ['search.html', '🔍', '全站搜索']],
    'search.html': [['kb.html', '🗂️', '知识库'], ['tips.html', '💡', '技巧'], ['usa.html', '🇺🇸', '美国生活指南']],
    'usa.html': [K('camry-2025-hybrid', '我的凯美瑞'), K('car-basics', '汽车零基础'), K('w2-tax-basics', '报税入门'), K('us-health-insurance-terms', '医保名词'), K('earthquake-prep', '地震准备'), K('wildfire-smoke-santa-ana', '山火季'), ['tips.html#safe', '🛡️', '安全防骗'], ['tips.html#money', '💵', '钱和账单'], ['holidays.html', '🗓️', '节假日'], ['deals.html', '🏷️', '打折'], ['ie.html', '🍊', '内陆帝国']],
    'kitchen.html': [['deals.html', '🏷️', '打折雷达'], ['usa.html#shop', '🛒', '去哪买菜'], ['holidays.html', '🗓️', '节假日'], ['convert.html', '💱', '单位换算']],
    'amtrak.html': [['coast.html', '🌊', '加州海岸线'], K('amtrak-guide', 'Amtrak 完全攻略'), ['sf.html', '🌉', '旧金山'], ['la.html', '🌇', '洛杉矶'], ['ie.html', '🍊', '内陆帝国'], K('travel-hotels', '订酒店'), K('travel-money-safety-packing', '打包清单')],
    'coast.html': [K('california-coast', '海岸线总攻略'), ['amtrak.html', '🚆', 'Amtrak 看海'], ['la.html', '🌇', '洛杉矶'], ['sf.html', '🌉', '旧金山'], K('travel-road-trip', '公路旅行和租车'), K('car-roadside-emergencies', '路上出状况'), K('camping-basics', '露营'), K('socal-hiking-trails', '徒步路线'), K('travel-hotels', '订酒店')],
    'sf.html': CITY, 'sj.html': CITY, 'ny.html': CITY,
    'la.html': [['coast.html', '🌊', '加州海岸线'], ['ie.html', '🍊', '内陆帝国'], K('la-lb-ports-guide', '洛杉矶/长滩港'), ['amtrak.html', '🚆', 'Amtrak'], ['usa.html', '🇺🇸', '美国生活指南']].concat(CITY.slice(3)),
    'ie.html': [['usa.html', '🇺🇸', '美国生活指南'], ['work.html', '🦺', '现场工具'], K('socal-hiking-trails', 'Upland 附近徒步'), K('earthquake-prep', '地震准备'), K('wildfire-smoke-santa-ana', '山火季'), K('container-logistics-101', '集装箱物流'), ['coast.html', '🌊', '加州海岸线'], ['amtrak.html', '🚆', 'Amtrak'], ['la.html', '🌇', '洛杉矶']],
    'holidays.html': [['kitchen.html', '🍳', '节日做菜'], ['usa.html#social', '🎉', '节日礼节'], ['deals.html', '🏷️', '节日打折'], ['coast.html', '🌊', '放假去海边']],
    'deals.html': [['convert.html', '💱', '换算'], ['usa.html#shop', '🛒', '购物指南'], ['holidays.html', '🗓️', '大促节日']],
    'convert.html': [['deals.html', '🏷️', '打折'], ['stocks.html', '📈', '股票池'], ['work.html', '🦺', '装柜换算']],
    'speak.html': LANG, 'vocab.html': LANG, 'card.html': LANG, 'english.html': LANG, 'sublingo.html': LANG, 'spanish.html': [['speak.html', '🗣️', '开口说'], ['work.html', '🦺', '现场工具']].concat(LANG.slice(1)),
    'hanzi.html': [['people.html', '⭐', '人物专栏'], K('su-shi', '苏轼'), ['card.html', '🎴', '每日一句']],
    'radio.html': LISTEN.slice(1).concat([['news.html', '📰', '新闻'], ['stocks.html', '📈', '股票池']]), 'fm.html': LISTEN, 'books.html': LISTEN, 'sleep.html': LISTEN.concat([['dream.html', '🌙', '心灵小站']]), 'player.html': LISTEN,
    'people.html': [K('su-shi', '苏轼'), ['books.html', '🎧', '听书'], K('top500-movies', '电影 500'), K('top500-music', '音乐 500')],
    'dream.html': [['sleep.html', '😴', '助眠'], ['kitchen.html#well', '🌿', '节气养生']],
    'darkroom.html': [['polar.html', '🕶️', '偏光滤镜'], ['work.html', '🦺', '现场工具'], ['toolbox.html', '🧰', '工具箱']],
    'polar.html': [['darkroom.html', '🎞️', '暗房'], ['toolbox.html', '🧰', '工具箱'], ['coast.html', '🌊', '加州海岸线'], ['work.html', '🦺', '现场工具']],
    'toolbox.html': [['polar.html', '🕶️', '偏光滤镜'], ['dl.html', '📥', '媒体下载'], ['pan.html', '☁️', '网盘搜索'], ['monitor.html', '🔔', '网页监控'], ['convert.html', '💱', '换算']],
    'dl.html': [['player.html', '🎬', '播放器'], ['toolbox.html', '🧰', '工具箱'], ['pan.html', '☁️', '网盘搜索']],
    'pan.html': [['dl.html', '📥', '媒体下载'], ['player.html', '🎬', '播放器']],
    'status.html': [['migrate.html', '🧳', '搬家（导出手机上的记录）'], ['monitor.html', '🔔', '网页监控'], ['news.html', '📰', '新闻'], ['stocks.html', '📈', '股票池']],
    'monitor.html': [['toolbox.html', '🧰', '工具箱'], ['deals.html', '🏷️', '打折雷达']]
  };
  var rel = (REL[cur] || []).filter(function (r) { return r[0].split('#')[0] !== cur; });
  function relHTML(cls) { return rel.length ? '<div class="' + cls + '">' + rel.map(function (r) { return '<a href="' + esc(r[0]) + '">' + r[1] + ' ' + esc(r[2]) + '</a>'; }).join('') + '</div>' : ''; }
  // remember where we have been (most recent first)
  var hist = get('hist', []), k;
  for (k = hist.length - 1; k >= 0; k--) if (hist[k] === cur) hist.splice(k, 1);
  var prev = hist.length ? hist[0] : null;
  if (ALL[cur]) hist.unshift(cur);
  put('hist', hist.slice(0, 8));
  // 🌟 常用：每个页面打开了几次（同一页 10 分钟内只算一次），首页「我常用的」用
  if (ALL[cur]) {
    var cnt = get('cnt', {}), c0 = cnt[cur] || [0, 0], nowT = Date.now();
    if (nowT - c0[1] > 6e5) { cnt[cur] = [c0[0] + 1, nowT]; put('cnt', cnt); }
  }
  window.TNAV = { all: ALL, top: function (n) {
    var cnt = get('cnt', {}), half = 30 * 864e5, nowT = Date.now();
    return Object.keys(cnt).filter(function (p) { return ALL[p] && p !== 'index.html'; })
      .map(function (p) { var c = cnt[p], w = c[0] * Math.pow(0.5, (nowT - c[1]) / half); return [w, p]; })   // 最近用得多的排前面，一个月不用就慢慢沉下去
      .sort(function (a, b) { return b[0] - a[0]; }).slice(0, n || 6).map(function (x) { return ALL[x[1]]; });
  } };

  var css = '' +
    '.tnav-rel{max-width:760px;margin:22px auto 12px;padding:12px 16px 4px;border-top:1px dashed rgba(128,128,128,.35);font:13px/1.5 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}' +
    '.tnav-rel b{display:block;font-size:12.5px;opacity:.6;margin-bottom:6px;font-weight:600}' +
    '.tnav-rel a{display:inline-block;margin:0 6px 8px 0;padding:4px 10px;border-radius:999px;border:1px solid rgba(128,128,128,.3);background:rgba(128,128,128,.08);color:inherit;text-decoration:none;white-space:nowrap}' +
    '.tnav-rd{display:flex;flex-wrap:wrap;gap:6px;padding:4px 14px 6px}' +
    '.tnav-rd a{font-size:12.5px;padding:3px 9px;border-radius:999px;background:rgba(0,0,0,.05);color:inherit;text-decoration:none}' +
    '@media (prefers-color-scheme: dark){.tnav-rd a{background:rgba(255,255,255,.08)}}' +
    '.tnav-tab{position:fixed;left:0;z-index:29;width:24px;height:44px;border:0;padding:0 1px 0 0;border-radius:0 22px 22px 0;background:rgba(28,28,30,.45);color:#fff;font-size:15px;line-height:44px;text-align:center;box-shadow:0 2px 10px rgba(0,0,0,.18);-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);opacity:.65;touch-action:none;cursor:pointer;-webkit-tap-highlight-color:transparent;transition:opacity .2s,width .15s}' +
    '.tnav-tab:hover,.tnav-tab.drag{opacity:1;width:34px}' +
    '@media (prefers-color-scheme: dark){.tnav-tab{background:rgba(255,255,255,.2)}}' +
    '.tnav-bg{position:fixed;inset:0;left:0;top:0;right:0;bottom:0;z-index:2147483000;background:linear-gradient(90deg,rgba(0,0,0,.52) 0%,rgba(0,0,0,.34) 45%,rgba(0,0,0,.14) 100%);-webkit-backdrop-filter:blur(2px);backdrop-filter:blur(2px);opacity:0;pointer-events:none;transition:opacity .26s ease;touch-action:none}' +
    '.tnav-bg.on{opacity:1;pointer-events:auto}' +
    '.tnav-dr{position:fixed;left:0;top:0;bottom:0;z-index:2147483001;width:300px;max-width:84vw;background:#FBFAF7;color:#1C1B19;box-shadow:1px 0 4px rgba(0,0,0,.08),10px 0 40px rgba(0,0,0,.22);transform:translateX(calc(-100% - 48px));transition:transform .26s cubic-bezier(.2,.8,.2,1);touch-action:pan-y;overflow-y:auto;-webkit-overflow-scrolling:touch;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif;font-size:15px;line-height:1.4;padding-bottom:24px}' +
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
    '.tnav-th{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:2px 14px 4px}' +
    '.tnav-th button{border:1px solid #E3DED4;background:none;border-radius:12px;padding:6px 4px 5px;font-size:11.5px;color:inherit;display:flex;flex-direction:column;align-items:center;gap:4px;cursor:pointer;font-family:inherit}' +
    '.tnav-th i{width:100%;height:30px;border-radius:8px;display:block;position:relative;overflow:hidden}' +
    '.tnav-th i:after{content:"";position:absolute;right:6px;bottom:6px;width:9px;height:9px;border-radius:50%;background:var(--d)}' +
    '.tnav-th button.on{border-color:#C8553D;box-shadow:0 0 0 1px #C8553D;font-weight:700}' +
    '.tnav-home{margin:14px 16px 0;display:block;text-align:center;padding:10px;border-radius:12px;border:1px solid #E3DED4;color:inherit;text-decoration:none}' +
    '.tnav-tip{font-size:11.5px;color:#9C958A;text-align:center;margin-top:10px}' +
    '.tnav-off{position:fixed;left:50%;top:max(8px,env(safe-area-inset-top));transform:translate(-50%,-160%);z-index:2147482999;max-width:92vw;padding:7px 14px;border-radius:999px;background:#3A3A3C;color:#fff;font:13px/1.3 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;box-shadow:0 4px 14px rgba(0,0,0,.2);transition:transform .25s,visibility 0s .25s;visibility:hidden;pointer-events:none;white-space:nowrap}' +
    '.tnav-off.on{transform:translate(-50%,0);visibility:visible;transition:transform .25s}' +
    // 点开时列表依次淡入；只用 backwards，结束后不覆盖「当前」那一项的半透明
    '.tnav-dr.anim .tnav-back,.tnav-dr.anim .tnav-g,.tnav-dr.anim .tnav-a,.tnav-dr.anim .tnav-home{animation:tnavIn .24s ease backwards;animation-delay:calc(var(--i,0) * 14ms + 40ms)}' +
    '@keyframes tnavIn{from{opacity:0;transform:translateX(-12px)}to{opacity:1;transform:none}}' +
    '@media (prefers-reduced-motion: reduce){.tnav-dr,.tnav-bg{transition-duration:.01s}.tnav-dr.anim *{animation:none!important}}' +
    '@media (prefers-color-scheme: dark){.tnav-bg{background:linear-gradient(90deg,rgba(0,0,0,.66) 0%,rgba(0,0,0,.46) 45%,rgba(0,0,0,.24) 100%)}}' +
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
    if (window.THEME) {   // 🎨 全站主题（theme.js）
      var tk = window.THEME.get();
      h += '<div class="tnav-g">🎨 主题 · 全站一起换</div><div class="tnav-th"><button type="button" data-th=""' + (tk ? '' : ' class="on"') + '><i style="background:linear-gradient(135deg,#F4F1EA 50%,#1F1D19 50%);--d:#8A847A"></i>原样</button>' +
        window.THEME.list().map(function (t) { return '<button type="button" data-th="' + t.k + '"' + (tk === t.k ? ' class="on"' : '') + ' title="' + esc(t.desc) + '"><i style="background:linear-gradient(180deg,' + t.sky + ' 0%,' + t.bg + ' 55%,' + t.sil + ' 56%,' + t.sil + ' 100%);--d:' + t.ac + '"></i>' + t.icon + ' ' + esc(t.name) + '</button>'; }).join('') + '</div>';
    }
    if (prev && ALL[prev] && prev !== cur) h += '<a class="tnav-back" href="' + esc(prev) + '">↩️ 回到刚才：' + ALL[prev][1] + ' ' + esc(ALL[prev][2]) + '</a>';
    if (rel.length) h += '<div class="tnav-g">🔗 跟这页相关</div>' + relHTML('tnav-rd');
    for (g = 0; g < GROUPS.length; g++) {
      h += '<div class="tnav-g">' + GROUPS[g][0] + '</div>';
      for (i = 0; i < GROUPS[g][1].length; i++) {
        var p = GROUPS[g][1][i];
        h += '<a class="tnav-a' + (p[0] === cur ? ' cur' : '') + '" href="' + esc(p[0]) + '"><i>' + p[1] + '</i><span>' + esc(p[2]) + (p[3] ? '<small>' + esc(p[3]) + '</small>' : '') + '</span></a>';
      }
    }
    h += '<a class="tnav-home" href="./">🏠 回主页</a><div class="tnav-tip">🌀 上下拖能挪位置，往右拉能拉出这里；往左滑关上</div>';
    dr.innerHTML = h;
    var seq = dr.querySelectorAll('.tnav-back,.tnav-g,.tnav-a,.tnav-home');
    for (i = 0; i < seq.length; i++) seq[i].style.setProperty('--i', Math.min(i, 14));
    if (rel.length && !window.NO_REL && !document.getElementById('tnav-rel')) { var rb = document.createElement('div'); rb.innerHTML = relHTML('tnav-rel').replace('<div class="tnav-rel">', '<div class="tnav-rel" id="tnav-rel"><b>🔗 相关</b>'); document.body.appendChild(rb.firstChild); }
    document.body.appendChild(tab); document.body.appendChild(bg); document.body.appendChild(dr);
    dr.addEventListener('click', function (e) {
      var b = e.target.closest && e.target.closest('[data-th]'); if (!b || !window.THEME) return;
      window.THEME.set(b.getAttribute('data-th'));
      var bs = dr.querySelectorAll('[data-th]'); for (var j = 0; j < bs.length; j++) bs[j].className = bs[j] === b ? 'on' : '';
    });

    var isOpen = false, pushed = false, animT = 0;
    var open = function (anim) {
      isOpen = true; bg.className = 'tnav-bg on'; dr.className = 'tnav-dr on' + (anim ? ' anim' : '');
      clearTimeout(animT); if (anim) animT = setTimeout(function () { dr.className = 'tnav-dr on'; }, 700);
      try { window.history.pushState({ tnav: 1 }, ''); pushed = true; } catch (e) { pushed = false; }
    };
    // 跟手：f = 0 收起，1 完全打开；拖动时关掉过渡，抽屉和遮罩深浅都跟着手指
    var W = function () { return dr.offsetWidth || 300; };
    var follow = function (f) {
      f = Math.max(0, Math.min(1, f));
      dr.style.transition = bg.style.transition = 'none';
      dr.style.transform = 'translateX(' + Math.round((f - 1) * (W() + 48)) + 'px)';
      bg.style.opacity = f; bg.style.pointerEvents = 'none';
      return f;
    };
    // 松手：恢复过渡，从当前位置滑到开或关
    var settle = function (toOpen) {
      dr.style.transition = bg.style.transition = '';
      void dr.offsetWidth;
      dr.style.transform = ''; bg.style.opacity = ''; bg.style.pointerEvents = '';
      if (toOpen) { if (!isOpen) open(false); }
      else if (isOpen) close(); else { bg.className = 'tnav-bg'; dr.className = 'tnav-dr'; }
    };
    // 速度：最近一小段的 px/ms
    var vel = { x: 0, t: 0, v: 0 };
    var track = function (x) { var t = Date.now(), dt = t - vel.t; if (dt > 0) vel.v = 0.6 * ((x - vel.x) / dt) + 0.4 * vel.v; vel.x = x; vel.t = t; };
    var close = function (fromPop) {
      if (!isOpen) return;
      isOpen = false; bg.className = 'tnav-bg'; dr.className = 'tnav-dr';
      if (pushed && !fromPop) { pushed = false; try { window.history.back(); } catch (e) { } }
      pushed = false;
    };
    window.addEventListener('popstate', function () { if (isOpen) { pushed = false; close(true); } });
    var swiped = false;
    bg.onclick = function () { if (swiped) { swiped = false; return; } close(); };
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
    // 按钮：点一下打开；上下拖挪位置；往右拉就把抽屉跟着手指拉出来
    var startY = 0, startX = 0, startF = 0, moved = false, down = false, mode = '', pullF = 0;
    var pt = function (e) { return e.touches && e.touches.length ? e.touches[0].clientY : e.clientY; };
    var px = function (e) { return e.touches && e.touches.length ? e.touches[0].clientX : e.clientX; };
    var onDown = function (e) { down = true; moved = false; mode = ''; startY = pt(e); startX = px(e); startF = y; vel = { x: startX, t: Date.now(), v: 0 }; };
    var onMove = function (e) {
      if (!down) return;
      var dy = pt(e) - startY, dx = px(e) - startX;
      if (!mode && (Math.abs(dy) > 6 || Math.abs(dx) > 6)) {
        mode = dx > 0 && Math.abs(dx) > Math.abs(dy) ? 'pull' : 'move'; moved = true;
        if (mode === 'move') tab.className = 'tnav-tab drag';
      }
      if (mode === 'move') { y = place(startF + dy / (window.innerHeight || 600)); if (e.cancelable) e.preventDefault(); }
      else if (mode === 'pull') { track(px(e)); pullF = follow(dx / W()); if (e.cancelable) e.preventDefault(); }
    };
    var onUp = function () {
      if (!down) return;
      down = false; tab.className = 'tnav-tab';
      if (mode === 'move') put('y', y);
      else if (mode === 'pull') settle(pullF > 0.3 || vel.v > 0.4);
      mode = '';
    };

    // 抽屉打开时：在抽屉或遮罩上往左滑就跟着手指关上；滑不到七成、也不够快就弹回去
    var ds = null;
    var dStart = function (e) { if (!isOpen || !e.touches || e.touches.length !== 1) return; ds = { x: e.touches[0].clientX, y: e.touches[0].clientY, m: '', f: 1 }; vel = { x: ds.x, t: Date.now(), v: 0 }; };
    var dMove = function (e) {
      if (!ds) return;
      var dx = e.touches[0].clientX - ds.x, dy = e.touches[0].clientY - ds.y;
      if (!ds.m && (Math.abs(dx) > 8 || Math.abs(dy) > 8)) ds.m = dx < 0 && Math.abs(dx) > Math.abs(dy) ? 'h' : 'v';
      if (ds.m !== 'h') return;
      if (e.cancelable) e.preventDefault();
      track(e.touches[0].clientX); ds.f = follow(1 + Math.min(0, dx) / W());
    };
    var dEnd = function () {
      if (!ds) return;
      if (ds.m === 'h') { swiped = true; setTimeout(function () { swiped = false; }, 400); settle(!(ds.f < 0.7 || vel.v < -0.4)); }
      ds = null;
    };
    [dr, bg].forEach(function (el) {
      el.addEventListener('touchstart', dStart, { passive: true });
      el.addEventListener('touchmove', dMove, { passive: false });
      el.addEventListener('touchend', dEnd); el.addEventListener('touchcancel', dEnd);
    });
    tab.addEventListener('touchstart', onDown, { passive: true });
    tab.addEventListener('touchmove', onMove, { passive: false });
    tab.addEventListener('touchend', onUp);
    tab.addEventListener('mousedown', onDown);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    tab.addEventListener('click', function () { if (moved) { moved = false; return; } open(true); });
    window.addEventListener('resize', function () { place(y); });

    // 没网时顶部一条提示：现在看到的是上次存下的内容
    var off = document.createElement('div'); off.className = 'tnav-off'; off.setAttribute('role', 'status');
    off.textContent = '📵 没网，显示的是上次存下的内容';
    document.body.appendChild(off);
    var net = function () { off.className = 'tnav-off' + (navigator.onLine === false ? ' on' : ''); };
    window.addEventListener('online', net); window.addEventListener('offline', net); net();
  }
  if (document.body) build(); else document.addEventListener('DOMContentLoaded', build);

  // 装到手机桌面 + 离线：每页都挂上 manifest，注册 sw.js（先上网，没网用缓存）
  try {
    if (!document.querySelector('link[rel=manifest]')) {
      var mf = document.createElement('link'); mf.rel = 'manifest'; mf.href = 'tools.webmanifest'; document.head.appendChild(mf);
    }
    if (!document.querySelector('link[rel=apple-touch-icon]')) {
      var ai = document.createElement('link'); ai.rel = 'apple-touch-icon'; ai.href = 'icons/apple.png'; document.head.appendChild(ai);
    }
    if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1')) {
      window.addEventListener('load', function () { navigator.serviceWorker.register('sw.js').then(null, function () { }); });
    }
  } catch (e) { }
})();
