// tools-api — 工具箱在 Cloudflare 上的小后端（由 .github/workflows/cf-worker.yml 自动部署）
//
//  POST /ocr     拍照识别柜号 / 封条号（Workers AI 视觉模型 + ISO 6346 校验）。需要请求头 X-Tools-Key：
//                网站首页解锁后存在浏览器里的那串密钥（sha256 后等于 CHECK），或部署时生成的测试密钥。
//  GET  /health  看看活着没有、配了哪些东西
//  POST /tg/<密钥> Telegram 机器人（照片认柜号 / 单据、语音翻译、/提醒 /股价 /简报），见下面「Telegram 双向机器人」
//  定时任务      美股交易时间每 5 分钟：检查「股价提醒」（stocks/data/alerts.json 里的规则）和大盘异动，触发就推送到 Telegram。
//
// 环境：AI（Workers AI 绑定）、KV（去重 / 状态）、CHECK、SITE、TEST_KEY、TG_BOT_TOKEN、TG_CHAT_ID

const ORIGINS = [/^https:\/\/boliunew\.github\.io$/, /^http:\/\/localhost(:\d+)?$/, /^https?:\/\/[a-z0-9-]+\.ts\.net$/];
const VISION = ['@cf/meta/llama-4-scout-17b-16e-instruct', '@cf/google/gemma-3-12b-it', '@cf/meta/llama-3.2-11b-vision-instruct'];

// ---------------------------------------------------------------------------- ISO 6346
const LV = (() => { const m = {}; let v = 10; for (const c of 'ABCDEFGHIJKLMNOPQRSTUVWXYZ') { if (v % 11 === 0) v++; m[c] = v++; } return m; })();
function cd(s10) { let t = 0; for (let i = 0; i < 10; i++) { const c = s10[i]; t += (/\d/.test(c) ? +c : LV[c]) * 2 ** i; } return t % 11 % 10; }
const TO_L = { 0: 'O', 1: 'I', 2: 'Z', 5: 'S', 6: 'G', 8: 'B' }, TO_D = { O: '0', Q: '0', D: '0', I: '1', L: '1', Z: '2', S: '5', G: '6', B: '8', T: '7' };
function fixShape(raw) {   // 4 字母 + 7 数字，把放错位置的 O/0、I/1 等换过来；最多改 2 个字符
  const s = raw.toUpperCase().replace(/[^A-Z0-9]/g, '');
  if (s.length !== 11) return null;
  if ((s.slice(0, 4).match(/[A-Z]/g) || []).length < 3 || (s.slice(4).match(/\d/g) || []).length < 5) return null;
  let a = '', n = 0;
  for (let i = 0; i < 11; i++) {
    const c = s[i];
    const d = i < 4 ? (/\d/.test(c) ? (TO_L[c] || c) : c) : (/[A-Z]/.test(c) ? (TO_D[c] || c) : c);
    if (d !== c) n++;
    a += d;
  }
  return n <= 2 && /^[A-Z]{4}\d{7}$/.test(a) ? a : null;
}
function containerCandidates(texts) {
  const out = new Map();
  for (const t of texts) {
    const src = String(t || '').toUpperCase();
    // 只看「像柜号」的一段：4 个字符 + 6–7 个字符（中间可以有空格、横线、换行），不跨单词乱拼
    for (const m of src.matchAll(/(?<![A-Z0-9])[A-Z0-9]{4}[\s\-\.\/]{0,3}[A-Z0-9]{3}[\s\-\.]{0,2}[A-Z0-9]{3}[\s\-\.\[\(]{0,3}[A-Z0-9]?(?![A-Z0-9])/g)) {
      const p = m[0].replace(/[^A-Z0-9]/g, '');
      const tries = p.length === 11 ? [p] : p.length === 10 ? [] : [];
      if (p.length === 10) {   // 没拍到校验位：按前 10 位算出来，标成「补算」
        const f10 = fixShape(p + '0');
        if (f10) { const f = f10.slice(0, 10) + cd(f10.slice(0, 10)); if (!out.has(f)) out.set(f, { no: f, ok: true, fixed: true, calc: true, cd: +f[10] }); }
      }
      for (const raw of tries) {
        const f = fixShape(raw);
        if (!f) continue;
        const ok = cd(f) === +f[10], fixed = f !== raw;
        const prev = out.get(f);
        if (!prev || (ok && !prev.ok)) out.set(f, { no: f, ok, fixed, cd: cd(f) });
      }
    }
  }
  return [...out.values()].sort((a, b) => (b.ok - a.ok) || (!!a.calc - !!b.calc) || (a.fixed - b.fixed));
}

// ---------------------------------------------------------------------------- 工具
async function sha256hex(s) { const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)); return [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join(''); }
function cors(req) {
  const o = req.headers.get('Origin') || '';
  return ORIGINS.some(r => r.test(o)) ? { 'Access-Control-Allow-Origin': o, 'Access-Control-Allow-Headers': 'Content-Type, X-Tools-Key', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS', 'Vary': 'Origin' } : {};
}
function json(req, obj, status = 200) { return new Response(JSON.stringify(obj), { status, headers: { 'Content-Type': 'application/json; charset=utf-8', ...cors(req) } }); }
async function authed(req, env) {
  const k = (req.headers.get('X-Tools-Key') || '').trim();
  if (!k) return false;
  if (env.TEST_KEY && k === env.TEST_KEY) return true;
  return !!env.CHECK && (await sha256hex(k)) === env.CHECK;
}
function aiText(r) {
  if (!r) return '';
  if (typeof r === 'string') return r;
  if (typeof r.response === 'string') return r.response;
  if (r.response && typeof r.response === 'object') return JSON.stringify(r.response);
  const ch = r.choices && r.choices[0];
  if (ch) return (ch.message && ch.message.content) || ch.text || '';
  for (const o of r.output || []) if (o.type === 'message') return (o.content || []).map(c => c.text || '').join('');
  return '';
}
function parseJSON(t) { const i = t.indexOf('{'), j = t.lastIndexOf('}'); if (i < 0 || j <= i) return null; try { return JSON.parse(t.slice(i, j + 1)); } catch (e) { return null; } }
function b64(bytes) { let s = ''; for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000)); return btoa(s); }

// ---------------------------------------------------------------------------- /ocr
const OCR_PROMPT = 'This photo was taken in a freight / container yard. Read every identification code painted or printed on the container, trailer, chassis or seal. ' +
  'Container numbers look like 4 letters + 6 digits + 1 check digit (e.g. CSQU 305438 3), often stacked vertically or split across lines; the check digit is usually in a box. ' +
  'Seal numbers are on the bolt seal at the door handle. Copy characters exactly as you see them; do not guess or invent. ' +
  'Reply with JSON only: {"containers":["…"],"seals":["…"],"others":["other codes: trailer / chassis / plate numbers"],"text":"all other text you can read"}';

async function runVision(env, bytes, mime, prompt = OCR_PROMPT, maxTokens = 600) {
  const errs = [];
  const dataUri = `data:${mime};base64,${b64(bytes)}`;
  for (const model of VISION) {
    try {
      let input;
      if (model.includes('llama-3.2')) input = { messages: [{ role: 'user', content: prompt }], image: [...bytes], max_tokens: maxTokens };
      else input = { messages: [{ role: 'user', content: [{ type: 'text', text: prompt }, { type: 'image_url', image_url: { url: dataUri } }] }], max_tokens: maxTokens, temperature: 0 };
      let r;
      try { r = await env.AI.run(model, input); }
      catch (e) {
        if (model.includes('llama-3.2') && /agree/i.test(String(e))) { await env.AI.run(model, { prompt: 'agree' }); r = await env.AI.run(model, input); }
        else throw e;
      }
      const text = aiText(r);
      if (text) return { model, text };
      errs.push(model + ': empty');
    } catch (e) { errs.push(model + ': ' + String(e).slice(0, 160)); }
  }
  return { model: null, text: '', errs };
}

async function ocr(req, env) {
  if (!(await authed(req, env))) return json(req, { error: 'key', msg: '需要先在工具箱首页输入密码解锁（并勾选「记住我」）' }, 401);
  let bytes, mime = 'image/jpeg';
  const ct = req.headers.get('Content-Type') || '';
  if (ct.startsWith('image/')) { bytes = new Uint8Array(await req.arrayBuffer()); mime = ct.split(';')[0]; }
  else {
    const body = await req.json().catch(() => ({}));
    const m = /^data:(image\/[a-z+]+);base64,(.+)$/.exec(body.image || '');
    if (!m) return json(req, { error: 'image', msg: '没有收到图片' }, 400);
    mime = m[1]; bytes = Uint8Array.from(atob(m[2]), c => c.charCodeAt(0));
  }
  if (bytes.length > 4.5e6) return json(req, { error: 'size', msg: '图片太大（超过 4.5 MB）' }, 413);
  const t0 = Date.now();
  await track(env, 'vision');
  const v = await runVision(env, bytes, mime);
  if (!v.text) return json(req, { error: 'ai', msg: 'AI 没读出来', detail: v.errs }, 502);
  const J = parseJSON(v.text) || {};
  const arr = x => (Array.isArray(x) ? x : x ? [x] : []).map(s => String(s).trim()).filter(Boolean);
  let containers = containerCandidates(arr(J.containers));
  if (!containers.length) containers = containerCandidates([...arr(J.others), J.text || '', Object.keys(J).length ? '' : v.text]);
  const seals = arr(J.seals).map(s => s.toUpperCase().replace(/\s+/g, '')).filter(s => /\d{4,}/.test(s)).slice(0, 4);
  return json(req, { containers: containers.slice(0, 5), seals, others: arr(J.others).slice(0, 6), text: String(J.text || '').slice(0, 300), model: v.model, ms: Date.now() - t0 });
}

// ---------------------------------------------------------------------------- 行情
async function quotes(symbols) {
  const out = {};
  await Promise.all(symbols.map(async s => {
    try {
      const r = await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(s)}?interval=5m&range=1d`, { headers: { 'User-Agent': 'Mozilla/5.0' }, cf: { cacheTtl: 60 } });
      if (r.ok) {
        const m = (await r.json()).chart.result[0].meta;
        if (m && m.regularMarketPrice) { out[s] = { p: m.regularMarketPrice, prev: m.chartPreviousClose || m.previousClose, src: 'yahoo' }; return; }
      }
    } catch (e) { /* 换 Stooq */ }
    try {
      const r = await fetch(`https://stooq.com/q/l/?s=${encodeURIComponent(s.toLowerCase().replace(/^\^/, ''))}.us&f=sd2t2ohlcv&h&e=csv`);
      const line = (await r.text()).trim().split('\n')[1] || '';
      const c = line.split(',');
      if (+c[6] > 0) out[s] = { p: +c[6], prev: null, src: 'stooq' };
    } catch (e) { /* 拿不到就算了 */ }
  }));
  return out;
}

function etNow() {
  const p = Object.fromEntries(new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', weekday: 'short', hour12: false }).formatToParts(new Date()).map(x => [x.type, x.value]));
  return { date: `${p.year}-${p.month}-${p.day}`, mins: (+p.hour % 24) * 60 + +p.minute, wd: p.weekday };
}

async function tg(env, text) {
  // 盘中提醒、大盘异动：同时推到 App（Firebase）和 Telegram
  const plain = text.replace(/<a href="([^"]+)">[^<]*<\/a>/g, '').replace(/<[^>]+>/g, '').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&').trim();
  const link = (/<a href="([^"]+)"/.exec(text) || [])[1];
  const lines = plain.split('\n').filter(Boolean);
  try { await fcmSend(env, { title: lines[0] || '工具箱', body: lines.slice(1).join('\n'), url: link }); } catch (e) { /* App 推送失败不影响 Telegram */ }
  if (!env.TG_BOT_TOKEN || !env.TG_CHAT_ID) return false;
  const r = await fetch(`https://api.telegram.org/bot${env.TG_BOT_TOKEN}/sendMessage`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: env.TG_CHAT_ID, text, parse_mode: 'HTML', disable_web_page_preview: true })
  });
  return r.ok;
}

// ---------------------------------------------------------------------------- App 推送（Firebase Cloud Messaging）
// App 解锁后把自己的推送地址（token）登记到 /push/register；GitHub 上的自动任务通过 /push/send 发（用 Telegram 令牌派生的密钥认证）。
// 需要 Worker 密钥 FCM_SERVICE_ACCOUNT（Firebase 服务账号 JSON）。
function pemToDer(pem) { const b = atob(pem.replace(/-----[^-]+-----/g, '').replace(/\s+/g, '')); return Uint8Array.from(b, c => c.charCodeAt(0)); }
const b64url = x => btoa(typeof x === 'string' ? unescape(encodeURIComponent(x)) : String.fromCharCode(...new Uint8Array(x))).replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_');
async function fcmAccess(env) {
  const cached = await env.KV.get('fcm:access');
  if (cached) return cached;
  const sa = JSON.parse(env.FCM_SERVICE_ACCOUNT);
  const now = Math.floor(Date.now() / 1000);
  const unsigned = b64url(JSON.stringify({ alg: 'RS256', typ: 'JWT' })) + '.' + b64url(JSON.stringify({
    iss: sa.client_email, scope: 'https://www.googleapis.com/auth/firebase.messaging', aud: 'https://oauth2.googleapis.com/token', iat: now, exp: now + 3600 }));
  const key = await crypto.subtle.importKey('pkcs8', pemToDer(sa.private_key), { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign('RSASSA-PKCS1-v1_5', key, new TextEncoder().encode(unsigned));
  const r = await fetch('https://oauth2.googleapis.com/token', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: 'grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer&assertion=' + unsigned + '.' + b64url(sig) });
  const j = await r.json();
  if (!j.access_token) throw new Error('Google 授权失败：' + JSON.stringify(j).slice(0, 200));
  await env.KV.put('fcm:access', j.access_token, { expirationTtl: 3000 });
  return j.access_token;
}
async function fcmSend(env, { title, body, url, kind }) {
  if (!env.FCM_SERVICE_ACCOUNT) return { sent: 0, why: '没有配置 FCM_SERVICE_ACCOUNT' };
  const tokens = JSON.parse((await env.KV.get('fcm:tokens')) || '[]');
  if (!tokens.length) return { sent: 0, why: 'App 还没登记（打开 App、首页解锁一次）' };
  const pid = JSON.parse(env.FCM_SERVICE_ACCOUNT).project_id, access = await fcmAccess(env);
  let sent = 0;
  const keep = [];
  for (const t of tokens) {
    const r = await fetch(`https://fcm.googleapis.com/v1/projects/${pid}/messages:send`, {
      method: 'POST', headers: { Authorization: 'Bearer ' + access, 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: { token: t.token, data: { title: String(title || '工具箱').slice(0, 120), body: String(body || '').slice(0, 1500), url: url || '', kind: kind || '' }, android: { priority: 'high' } } })
    });
    if (r.ok) { sent++; keep.push(t); }
    else if (![404, 400].includes(r.status)) keep.push(t);        // 404 / 400 = 这个 App 已卸载或地址失效，删掉
  }
  if (keep.length !== tokens.length) await env.KV.put('fcm:tokens', JSON.stringify(keep));
  return { sent, devices: tokens.length };
}
async function pushKey(env) { return env.TG_BOT_TOKEN ? (await sha256hex('push:' + env.TG_BOT_TOKEN)).slice(0, 32) : null; }

// ---------------------------------------------------------------------------- 盘中检查
const MARKET = [['SPY', '标普500 ETF'], ['QQQ', '纳指100 ETF']], MARKET_MOVE = 1.5;
const pctTxt = x => (x >= 0 ? '+' : '') + x.toFixed(2) + '%';

async function intraday(env, force = false) {
  const now = etNow();
  const open = !['Sat', 'Sun'].includes(now.wd) && now.mins >= 9 * 60 + 35 && now.mins <= 16 * 60 + 5;
  if (!open && !force) return { skipped: '不在交易时间', et: now };
  const site = env.SITE || 'https://boliunew.github.io/tools';
  const A = await fetch(`${site}/stocks/data/alerts.json?t=${Date.now()}`).then(r => r.json()).catch(() => ({ items: {} }));
  const snap = await fetch(`${site}/stocks/data/snap.json?t=${Math.floor(Date.now() / 36e5)}`, { cf: { cacheTtl: 3600 } }).then(r => r.json()).catch(() => ({ rows: {} }));
  const kvRules = JSON.parse((await env.KV.get('rules')) || '[]').map(r => ['k' + r.id, { ...r, url: null }]);
  const rules = [...Object.entries(A.items || {}), ...kvRules].filter(([, a]) => ['below', 'above', 'move', 'dd'].includes(a.kind) && a.t);
  const syms = [...new Set([...MARKET.map(m => m[0]), ...rules.map(([, a]) => a.t)])];
  const Q = await quotes(syms);
  const sent = [];
  // 大盘异动：一天一次（每个方向）
  for (const [s, name] of MARKET) {
    const q = Q[s];
    if (!q || !q.prev) continue;
    const chg = (q.p / q.prev - 1) * 100;
    if (Math.abs(chg) >= MARKET_MOVE) {
      const key = `mkt:${now.date}:${s}:${chg > 0 ? 'up' : 'dn'}`;
      if (!force && await env.KV.get(key)) continue;
      const ok = await tg(env, `📊 <b>大盘异动</b>：${name}（${s}）盘中 ${pctTxt(chg)}，现价 ${q.p.toFixed(2)}\n<a href="${site}/stocks.html">打开股票池</a>`);
      if (ok) { await env.KV.put(key, '1', { expirationTtl: 86400 * 2 }); sent.push(key); }
    }
  }
  // 股价提醒
  for (const [id, a] of rules) {
    const q = Q[a.t];
    if (!q) continue;
    const prev = q.prev || (snap.rows[a.t] || {}).c;
    let met = false, rearm = false, detail = '';
    if (a.kind === 'below') { met = q.p <= a.v; rearm = q.p >= a.v * 1.03; detail = `现价 ${q.p.toFixed(2)} ≤ ${a.v}`; }
    else if (a.kind === 'above') { met = q.p >= a.v; rearm = q.p <= a.v * 0.97; detail = `现价 ${q.p.toFixed(2)} ≥ ${a.v}`; }
    else if (a.kind === 'move' && prev) { const c = (q.p / prev - 1) * 100; met = Math.abs(c) >= a.v; detail = `盘中 ${pctTxt(c)}（现价 ${q.p.toFixed(2)}）`; }
    else if (a.kind === 'dd') {
      const r = snap.rows[a.t];
      if (r && r.h != null && r.c) { const hi = r.c / (1 + r.h), dd = (q.p / hi - 1) * 100; met = dd <= -a.v; rearm = dd > -(a.v - 3); detail = `距一年高点 ${pctTxt(dd)}（现价 ${q.p.toFixed(2)}）`; }
    }
    const level = a.kind !== 'move';
    const armKey = `arm:${id}:${a.kind}:${a.v}`, dayKey = `fired:${now.date}:${id}`;
    if (level) {
      const disarmed = await env.KV.get(armKey);
      if (disarmed && rearm) { await env.KV.delete(armKey); continue; }
      if (!met || disarmed) continue;
    } else if (!met || (!force && await env.KV.get(dayKey))) continue;
    const ok = await tg(env, `🔔 <b>股价提醒（盘中）</b>：<b>${a.t}</b> ${a.desc || ''}\n${detail}\n` + (a.url ? `<a href="${a.url}">查看提醒</a> · ` : `（Telegram 设的提醒 #${a.id}，/删除 ${a.id} 可以关掉）\n`) + `<a href="${site}/stocks.html">股票池</a>`);
    if (ok) {
      sent.push(id);
      if (level) await env.KV.put(armKey, now.date, { expirationTtl: 86400 * 60 });
      else await env.KV.put(dayKey, '1', { expirationTtl: 86400 * 2 });
    }
  }
  await env.KV.put('last-run', JSON.stringify({ at: new Date().toISOString(), rules: rules.length, quotes: Object.keys(Q).length, sent }), { expirationTtl: 86400 * 7 });
  return { et: now, rules: rules.length, quotes: Object.fromEntries(Object.entries(Q).map(([k, v]) => [k, v.p])), sent, telegram: !!(env.TG_BOT_TOKEN && env.TG_CHAT_ID) };
}

// ---------------------------------------------------------------------------- Telegram 双向机器人
// Telegram 把消息推到 /tg/<密钥>（部署时 setWebhook）。只理你自己（TG_CHAT_ID）发的消息。
//  照片            → 柜号 / 封条号（ISO 6346 校验）；像单据就整理提单号、件数、重量等字段。配文「单据」强制按单据读
//  语音            → Whisper 听写，中文翻成西班牙语 + 英语（附西语朗读），西语 / 英语翻成中文
//  直接打字        → 同上，中 ↔ 西 / 英翻译
//  /提醒 VOO 跌到 650 · /提醒列表 · /删除 3 · /股价 NVDA · /简报 · /帮助
const LLM = ['@cf/openai/gpt-oss-120b', '@cf/meta/llama-3.3-70b-instruct-fp8-fast'];
const WHISPER = ['@cf/openai/whisper-large-v3-turbo', '@cf/openai/whisper'];
const HELP = [
  '🤖 <b>我能做这些</b>',
  '📷 <b>发照片</b>：认柜号 / 封条号（自动校验）；拍的是提单、装箱单就整理关键字段。配文写「单据」强制按单据读',
  '🎙️ <b>发语音</b>：现场翻译——说中文 → 西班牙语 + 英语 + 朗读；说西语 / 英语 → 中文',
  '💬 <b>直接打中文</b>：问我任何事（问股市会参考实时行情和股票池）',
  '🌐 <b>翻译</b>：打「翻译 把柜子放到12号门」→ 西语 + 英语 + 朗读；收到西语 / 英语直接转发给我 → 中文',
  '🔔 <code>/提醒 VOO 跌到 650</code>（也可以：涨到 250、单日涨跌 5、回撤 10）',
  '📋 <code>/提醒列表</code> · <code>/删除 3</code>',
  '📈 <code>/q</code> 大盘 · <code>/q NVDA</code> 个股 · ☀️ <code>/简报</code> · 📊 <code>/用量</code>'
].join('\n');

// ---------- 用量统计（按公开价格粗估的神经元；免费额度每天 10,000，UTC 零点重置 = 太平洋时间下午 5 点 / 冬令时 4 点）
const COST = { chat: 100, vision: 100, whisper: 50, translate: 40, tts: 20 };
const COST_ZH = { chat: '💬 聊天', vision: '📷 认图', whisper: '🎙️ 听写', translate: '🌐 翻译', tts: '🔊 朗读' };
const AUTO_DAILY = 600;   // 每日简报 + 盘后解读（在 GitHub 上调用，这里按固定值估）
async function track(env, kind) {
  try {
    const key = 'use:' + new Date().toISOString().slice(0, 10);
    const u = JSON.parse((await env.KV.get(key)) || '{}');
    u[kind] = (u[kind] || 0) + 1;
    await env.KV.put(key, JSON.stringify(u), { expirationTtl: 86400 * 8 });
  } catch (e) { /* 统计失败不影响正常功能 */ }
}
async function cmdUsage(env, chat) {
  const today = new Date().toISOString().slice(0, 10);
  const u = JSON.parse((await env.KV.get('use:' + today)) || '{}');
  let used = AUTO_DAILY;
  const L = ['📊 <b>今天的 AI 用量</b>（估算）'];
  for (const k of Object.keys(COST)) if (u[k]) { used += u[k] * COST[k]; L.push(`${COST_ZH[k]} ${u[k]} 次 ≈ ${u[k] * COST[k]}`); }
  L.push(`⚙️ 自动任务（简报、盘后解读）≈ ${AUTO_DAILY}`);
  const pct = Math.min(100, Math.round(used / 100));
  const bar = '▓'.repeat(Math.round(pct / 10)) + '░'.repeat(10 - Math.round(pct / 10));
  L.push(`\n合计约 <b>${used}</b> / 10,000 神经元\n${bar} ${pct}%`);
  L.push(`还能再聊大约 <b>${Math.max(0, Math.floor((10000 - used) / COST.chat))}</b> 条（或拍 ${Math.max(0, Math.floor((10000 - used) / COST.vision))} 张照片）`);
  const reset = new Date(); reset.setUTCHours(24, 0, 0, 0);
  const hrs = Math.max(0, (reset - Date.now()) / 36e5);
  const at = new Intl.DateTimeFormat('zh-CN', { timeZone: 'America/Los_Angeles', hour: 'numeric', hour12: true }).format(reset);
  L.push(`额度在 ${Math.floor(hrs)} 小时 ${Math.round((hrs % 1) * 60)} 分后重置（太平洋时间${at}）`);
  const week = [];
  for (let i = 1; i <= 6; i++) {
    const d = new Date(Date.now() - i * 864e5).toISOString().slice(0, 10);
    const x = JSON.parse((await env.KV.get('use:' + d)) || 'null');
    if (x) week.push(`${d.slice(5)} ≈ ${AUTO_DAILY + Object.entries(x).reduce((a, [k, n]) => a + (COST[k] || 0) * n, 0)}`);
  }
  if (week.length) L.push('\n前几天：' + week.join('，'));
  L.push('\n<i>按公开价格粗估，准确数字看 Cloudflare 后台 AI → Workers AI</i>');
  return reply(env, chat, L.join('\n'));
}

const esc = s => String(s == null ? '' : s).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));

async function tgApi(env, method, body) {
  const r = await fetch(`https://api.telegram.org/bot${env.TG_BOT_TOKEN}/${method}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  return r.json().catch(() => ({}));
}
async function reply(env, chat, html, extra = {}) {
  const r = await tgApi(env, 'sendMessage', { chat_id: chat, text: html.slice(0, 4000), parse_mode: 'HTML', disable_web_page_preview: true, ...extra });
  if (!r.ok) await tgApi(env, 'sendMessage', { chat_id: chat, text: html.replace(/<[^>]+>/g, '').slice(0, 4000) });
}
async function tgFile(env, fileId) {
  const f = await tgApi(env, 'getFile', { file_id: fileId });
  if (!f.ok) throw new Error('getFile 失败');
  const r = await fetch(`https://api.telegram.org/file/bot${env.TG_BOT_TOKEN}/${f.result.file_path}`);
  return { bytes: new Uint8Array(await r.arrayBuffer()), path: f.result.file_path };
}

async function llm(env, system, user, maxTokens = 800) {
  for (const model of LLM) {
    try {
      const input = model.includes('gpt-oss')
        ? { instructions: system, input: user, reasoning: { effort: 'low' } }
        : { messages: [{ role: 'system', content: system }, { role: 'user', content: user }], max_tokens: maxTokens, temperature: 0.2 };
      const t = aiText(await env.AI.run(model, input));
      if (t) return t;
    } catch (e) { /* 换下一个模型 */ }
  }
  return '';
}

// ---------------------------------------------------------------------------- /explain：SubLingo「讲讲这句」
const EXPLAIN_SYS = `你是给中文母语者讲英语语法的老师。读者是在美国工作生活的成年人，英语中等水平。
只讲用户给的「要讲的句子」，上下文只用来帮你理解，不要讲上下文。用简体中文，简洁、口语化，不客套，不用表情符号。
只输出一个 JSON 对象，不要任何别的文字：
{"meaning":"这句话的意思：一两句自然的中文翻译",
 "trunk":"句子主干：主语 + 谓语（+ 宾语/表语），用原文的词，比如 analysts expect it to lay off workers",
 "parts":[{"text":"原文片段","role":"在句中的作用，如：主句 / 时间状语从句（since 引导）/ 条件状语从句（if 引导）/ 宾语从句 / 定语从句 / 宾语补足语 / 分词短语","note":"一句话说明"}],
 "verbs":[{"text":"原文里的动词部分","form":"形式，如：现在完成进行时 / 一般过去时 / 不定式 / 现在分词 / 过去分词 / 被动语态 / 情态动词","why":"为什么这里用这个形式，结合这句话说"}],
 "phrases":[{"text":"短语动词、习语或固定搭配","meaning":"在这句里的意思"}],
 "tip":"这句最值得注意的一点，一句话；没有就写空字符串"}
要求：parts 按句子顺序列 2 到 5 项（简单句可以只列 1 项）；verbs 列出所有谓语动词和非谓语动词，注意 to 后面的动词是不定式（比如 to lay off 是不定式，不是过去时）；phrases 只列真正的短语动词、习语和固定搭配，没有就给空数组。`;
async function explain(req, env) {
  if (!(await authed(req, env))) return json(req, { error: 'key', msg: '需要先在工具箱首页输入密码解锁（并勾选「记住我」）' }, 401);
  const b = await req.json().catch(() => ({}));
  const s = String(b.sentence || '').replace(/\s+/g, ' ').trim();
  if (!s) return json(req, { error: 'input', msg: '没有收到句子' }, 400);
  if (s.length > 600) return json(req, { error: 'input', msg: '句子太长了，分开来问' }, 400);
  const ctxText = String(b.context || '').replace(/\s+/g, ' ').trim().slice(0, 600);
  const ck = 'ex1:' + (await sha256hex(s)).slice(0, 40);
  if (env.KV && !b.nocache) { const hit = await env.KV.get(ck); if (hit) return json(req, { ...JSON.parse(hit), cached: true }); }
  await track(env, 'chat');
  const user = (ctxText && ctxText !== s ? '上下文（只供参考）：' + ctxText + '\n\n' : '') + '要讲的句子：' + s;
  const t0 = Date.now();
  const J = parseJSON(await llm(env, EXPLAIN_SYS, user, 1400));
  if (!J || !J.meaning) return json(req, { error: 'ai', msg: 'AI 这次没讲出来，再试一次' }, 502);
  const list = (x, keys) => (Array.isArray(x) ? x : []).slice(0, 8).map(o => { const r = {}; for (const k of keys) r[k] = String((o && o[k]) || '').slice(0, 300); return r; }).filter(o => o[keys[0]]);
  const out = { meaning: String(J.meaning).slice(0, 400), trunk: String(J.trunk || '').slice(0, 300), parts: list(J.parts, ['text', 'role', 'note']),
    verbs: list(J.verbs, ['text', 'form', 'why']), phrases: list(J.phrases, ['text', 'meaning']), tip: String(J.tip || '').slice(0, 300) };
  if (env.KV) await env.KV.put(ck, JSON.stringify(out), { expirationTtl: 60 * 60 * 24 * 90 });
  return json(req, { ...out, ms: Date.now() - t0 });
}

// ---------- 照片：柜号 / 单据
const DOC_PROMPT = 'This is a photo from a freight / container yard. First decide: is it mainly a DOCUMENT (bill of lading, delivery order, packing list, gate ticket, seal record, any printed form) or a CONTAINER / TRAILER / SEAL photo? ' +
  'Copy characters exactly; never guess. Reply with JSON only: ' +
  '{"type":"document" or "container","containers":["container numbers like CSQU 305438 3"],"seals":["seal numbers"],"others":["trailer / chassis / plate / booking numbers"],' +
  '"fields":{"bl":"B/L number","booking":"booking number","shipper":"","consignee":"","carrier":"","vessel":"vessel / voyage","pol":"port of loading","pod":"port of discharge","pieces":"packages / pieces with unit","weight":"gross weight with unit","volume":"CBM","description":"goods description, short","date":""},' +
  '"text":"other important text, short"}. Use empty strings for fields you cannot see.';
const FIELD_ZH = { bl: '提单号', booking: '订舱号', shipper: '发货人', consignee: '收货人', carrier: '船公司 / 承运人', vessel: '船名航次', pol: '装货港', pod: '卸货港', pieces: '件数', weight: '毛重', volume: '体积', description: '货物', date: '日期' };

async function onPhoto(env, chat, msg) {
  const ph = msg.photo ? msg.photo[msg.photo.length - 1] : msg.document;
  if (!ph) return;
  if ((ph.file_size || 0) > 9e6) return reply(env, chat, '照片太大了，用 Telegram 默认的压缩方式发（不要“按文件发送”）');
  await tgApi(env, 'sendChatAction', { chat_id: chat, action: 'typing' });
  const { bytes, path } = await tgFile(env, ph.file_id);
  const mime = /\.png$/i.test(path) ? 'image/png' : 'image/jpeg';
  const forceDoc = /单据|提单|文件|doc|bl\b/i.test(msg.caption || '');
  await track(env, 'vision');
  const v = await runVision(env, bytes, mime, forceDoc ? DOC_PROMPT.replace('First decide', 'It IS a document. Still') : DOC_PROMPT, 900);
  if (!v.text) return reply(env, chat, '😵 AI 没读出来，换个角度再拍一张试试');
  const J = parseJSON(v.text) || {};
  const arr = x => (Array.isArray(x) ? x : x ? [x] : []).map(s => String(s).trim()).filter(Boolean);
  let C = containerCandidates(arr(J.containers));
  if (!C.length) C = containerCandidates([...arr(J.others), J.text || '', Object.keys(J).length ? '' : v.text]);
  const S = arr(J.seals).map(s => s.toUpperCase().replace(/\s+/g, '')).filter(s => /\d{4,}/.test(s));
  const out = [];
  const isDoc = forceDoc || J.type === 'document';
  if (isDoc) {
    out.push('📄 <b>单据识别</b>');
    for (const [k, zh] of Object.entries(FIELD_ZH)) { const val = J.fields && String(J.fields[k] || '').trim(); if (val) out.push(`${zh}：<code>${esc(val)}</code>`); }
  }
  if (C.length) {
    out.push(isDoc ? '\n📦 <b>柜号</b>' : '📦 <b>柜号</b>');
    for (const c of C.slice(0, 6)) {
      const g = `${c.no.slice(0, 4)} ${c.no.slice(4, 10)} ${c.no.slice(10)}`;
      out.push(`<code>${c.no}</code>  ${esc(g)}  ${c.calc ? '（没拍到校验位，已补算）' : c.ok ? (c.fixed ? '✅ 校验通过（已纠正 O/0 之类）' : '✅ 校验通过') : `⚠️ 校验位不对（应为 ${c.cd}），再看一眼`}`);
    }
  }
  if (S.length) out.push('🔒 <b>封条号</b>：' + S.slice(0, 4).map(s => `<code>${esc(s)}</code>`).join('  '));
  const others = arr(J.others).filter(o => !C.some(c => o.replace(/\W/g, '').toUpperCase().includes(c.no.slice(0, 10)))).slice(0, 5);
  if (others.length) out.push('🔖 其他编号：' + others.map(o => `<code>${esc(o)}</code>`).join('  '));
  if (out.length <= (isDoc ? 1 : 0)) out.push('没认出编号。' + (J.text ? '读到的文字：' + esc(String(J.text).slice(0, 300)) : '靠近一点、正对着拍、避开反光再试。'));
  out.push('<i>点编号可以复制。AI 可能读错，请对一眼实物</i>');
  return reply(env, chat, out.join('\n'), { reply_to_message_id: msg.message_id });
}

// ---------- 翻译（文字 / 语音）
async function translate(env, text, lang) {
  const zh = /[一-鿿]/.test(text) || /^zh|chinese/i.test(lang || '');
  const system = '你是货运堆场现场的翻译，帮一位中文母语的现场主管和墨西哥 / 美国司机、工人沟通。翻译要口语、简短、准确，保留数字、柜号、门号、时间。只输出 JSON。';
  const user = zh
    ? `把这句中文翻成墨西哥口语西班牙语和美式英语，输出 {"es":"…","en":"…"}：\n${text}`
    : `把这句话（可能是西班牙语或英语）翻成中文，输出 {"src":"原文语言（中文写，如 西班牙语）","zh":"中文翻译"}：\n${text}`;
  const J = parseJSON(await llm(env, system, user)) || {};
  return { zh, J };
}

async function sendSpanishVoice(env, chat, text) {
  try {
    await track(env, 'tts');
    const r = await env.AI.run('@cf/myshell-ai/melotts', { prompt: text, lang: 'es' });
    const audio = typeof r === 'string' ? r : r && r.audio;
    if (!audio) return;
    const bytes = Uint8Array.from(atob(audio), c => c.charCodeAt(0));
    const fd = new FormData();
    fd.append('chat_id', String(chat));
    fd.append('title', text.slice(0, 60));
    fd.append('performer', '🇲🇽 西语朗读');
    fd.append('audio', new Blob([bytes], { type: 'audio/mpeg' }), 'espanol.mp3');
    await fetch(`https://api.telegram.org/bot${env.TG_BOT_TOKEN}/sendAudio`, { method: 'POST', body: fd });
  } catch (e) { /* 朗读失败就只发文字 */ }
}

async function doTranslate(env, chat, text, fromVoice = '', lang = '', speak = false) {
  await tgApi(env, 'sendChatAction', { chat_id: chat, action: 'typing' });
  const { zh, J } = await translate(env, text, lang);
  await track(env, 'translate');
  const head = fromVoice ? `🎙️ 听到：${esc(text)}\n\n` : '';
  if (zh) {
    if (!J.es && !J.en) return reply(env, chat, head + '😵 翻译失败，再发一次试试');
    await reply(env, chat, head + `🇲🇽 <b>${esc(J.es || '')}</b>\n\n🇺🇸 ${esc(J.en || '')}`);
    if (J.es && speak) await sendSpanishVoice(env, chat, J.es);
  } else {
    if (!J.zh) return reply(env, chat, head + '😵 翻译失败，再发一次试试');
    await reply(env, chat, head + `🇨🇳 <b>${esc(J.zh)}</b>` + (J.src ? `\n<i>（${esc(J.src)}）</i>` : ''));
  }
}

// 打字：中文 → AI 助手回答（带行情 / 股票池 / 简报数据）；「翻译 …」→ 翻出去（附西语朗读）；西语 / 英语 → 翻成中文
async function onText(env, chat, text) {
  const tr = /^\s*(翻译|翻一下|fy)\s*[:：,，]?\s*([\s\S]+)$/i.exec(text);
  if (tr) return doTranslate(env, chat, tr[2].trim(), '', '', true);
  if (!/[\u4e00-\u9fff]/.test(text)) return doTranslate(env, chat, text);
  return askAI(env, chat, text);
}

const TICK_STOP = new Set(['AI', 'ETF', 'RSI', 'VIX', 'CEO', 'IPO', 'EPS', 'GDP', 'CPI', 'PCE', 'FOMC', 'USD', 'OK', 'US', 'BL', 'TG']);
async function marketContext(env, question) {
  const site = env.SITE, h = Math.floor(Date.now() / 36e5);
  const getj = p => fetch(`${site}/${p}?t=${h}`).then(r => r.json()).catch(() => null);
  const named = [...new Set((question.toUpperCase().match(/\b[A-Z]{1,5}\b/g) || []).filter(t => !TICK_STOP.has(t)))].slice(0, 4);
  const [Q, pool, snap, ai, idx] = await Promise.all([quotes(['SPY', 'QQQ', '^VIX', ...named]), getj('stocks/data/latest.json'), getj('stocks/data/snap.json'), getj('stocks/data/ai.json'), getj('brief/data/index.json')]);
  const brief = idx && idx.dates && idx.dates[0] ? await getj(`brief/data/${idx.dates[0]}.json`) : null;
  const L = [];
  const now = etNow();
  L.push(`现在美东时间 ${now.date} ${String(Math.floor(now.mins / 60)).padStart(2, '0')}:${String(now.mins % 60).padStart(2, '0')}（${now.wd}）`);
  for (const s of ['SPY', 'QQQ', '^VIX']) { const q = Q[s]; if (q) L.push(`${s} 最新 ${q.p}` + (q.prev ? `（较前收 ${pctTxt((q.p / q.prev - 1) * 100)}）` : '')); }
  if (pool && pool.regime) L.push(`股票池大盘状态「${pool.regime.label}」：${pool.regime.desc || ''}；站上50日线的股票占 ${Math.round((pool.regime.breadth50 || 0) * 100)}%`);
  if (pool && pool.signals) L.push('各信号回测结论：' + Object.values(pool.signals).map(v => `${v.name}「${(v.stats || {}).verdict}」`).join('，'));
  if (pool && pool.candidates) L.push('股票池评分前 5：' + pool.candidates.slice().sort((a, b) => b.score - a.score).slice(0, 5).map(c => `${c.t}(${c.primary}, RSI ${c.rsi})`).join('、'));
  if (ai && ai.market) L.push(`AI 盘后解读（${ai.date}）：${ai.market} ${ai.sectors || ''}`);
  for (const t of named) {
    const q = Q[t], r = snap && snap.rows && snap.rows[t], c = pool && (pool.candidates || []).find(x => x.t === t);
    if (q || r) L.push(`${t}：` + (q ? `现价 ${q.p}` + (q.prev ? `（${pctTxt((q.p / q.prev - 1) * 100)}）` : '') : '') + (r ? `；${snap.date} 收盘 ${r.c}，RSI14 ${r.rsi}，${r.a50 ? '在' : '不在'}50日线上，${r.a200 ? '在' : '不在'}200日线上，距一年高点 ${pctTxt((r.h || 0) * 100)}，相对强度 ${r.rs}` : '') + (c ? `；在今日股票池（${c.primary}，止损 ${c.stop}，目标 ${c.target}${c.earn ? '，财报 ' + c.earn : ''}）` : ''));
  }
  if (brief) L.push(`今日简报（${brief.date}）：` + (brief.sections || []).map(s => s.title + '：' + (s.items || []).slice(0, 2).map(i => i.t).join('；')).join(' ｜ '));
  return L.join('\n');
}

async function askAI(env, chat, text) {
  await tgApi(env, 'sendChatAction', { chat_id: chat, action: 'typing' });
  const hist = JSON.parse((await env.KV.get('chat:' + chat)) || '[]');
  const ctx = await marketContext(env, text);
  const system = '你是用户的私人助理，用户是美国货运堆场的现场主管，也是用 Python 做量化波段交易的散户。用中文回答，简洁、口语、直接给结论，一般 3–6 句；' +
    '涉及股市时以【实时数据】为准，数字照抄不要编，数据里没有的就说不知道；不给买卖建议、不预测涨跌，可以解释数据说明了什么、有哪些风险。' +
    '其他问题（工作、生活、英语西语、常识）正常回答。不要用 Markdown 表格。';
  const convo = hist.map(m => (m.r === 'u' ? '用户：' : '助理：') + m.t).join('\n');
  const user = `【实时数据】\n${ctx}\n\n` + (convo ? `【之前的对话】\n${convo}\n\n` : '') + `【用户现在问】\n${text}`;
  const ans = (await llm(env, system, user, 900)).trim();
  await track(env, 'chat');
  if (!ans) return reply(env, chat, '😵 AI 没回上来，再问一次试试');
  hist.push({ r: 'u', t: text.slice(0, 300) }, { r: 'a', t: ans.slice(0, 500) });
  await env.KV.put('chat:' + chat, JSON.stringify(hist.slice(-8)), { expirationTtl: 6 * 3600 });
  const html = esc(ans).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/^#{1,6}\s*(.+)$/gm, '<b>$1</b>');
  return reply(env, chat, html);
}

async function onVoice(env, chat, msg) {
  const v = msg.voice || msg.audio;
  if ((v.duration || 0) > 120) return reply(env, chat, '语音太长了，2 分钟以内的我才听');
  await tgApi(env, 'sendChatAction', { chat_id: chat, action: 'typing' });
  const { bytes } = await tgFile(env, v.file_id);
  await track(env, 'whisper');
  let text = '', lang = '';
  for (const model of WHISPER) {
    try {
      const r = model.includes('turbo') ? await env.AI.run(model, { audio: b64(bytes) }) : await env.AI.run(model, { audio: [...bytes] });
      text = (r && (r.text || (r.segments || []).map(s => s.text).join(' '))) || '';
      lang = (r && r.transcription_info && r.transcription_info.language) || '';
      if (text.trim()) break;
    } catch (e) { /* 换下一个模型 */ }
  }
  if (!text.trim()) return reply(env, chat, '😵 没听清，靠近手机再说一次');
  return doTranslate(env, chat, text.trim(), '1', lang, true);
}

// ---------- 股价提醒（存在 KV，盘中检查见 intraday）
const KINDS_JS = [['dd', /回撤|回调|距.{0,4}高点/], ['move', /单日|涨跌幅|涨跌|异动/], ['above', /涨到|涨破|涨过|高于|突破|>/], ['below', /跌到|跌破|跌至|低于|</]];
const KIND_ZH = { below: '跌到', above: '涨到', move: '单日涨跌 ≥', dd: '距一年高点回撤 ≥' };
async function cmdAlert(env, chat, arg) {
  const m = /^\s*\$?([A-Za-z][A-Za-z0-9.\-]{0,6})\s*(.*)$/.exec(arg || '');
  if (!m) return reply(env, chat, '格式：<code>/提醒 VOO 跌到 650</code>（还可以：涨到 250、单日涨跌 5、回撤 10）');
  const t = m[1].toUpperCase().replace('.', '-'), rest = m[2];
  const k = (KINDS_JS.find(([, rx]) => rx.test(rest)) || [])[0];
  const n = /\d+(\.\d+)?/.exec(rest.replace(/,/g, ''));
  if (!k || !n) return reply(env, chat, '没看懂条件。写成：跌到 650 / 涨到 250 / 单日涨跌 5 / 回撤 10');
  const v = +n[0];
  const rules = JSON.parse((await env.KV.get('rules')) || '[]');
  const id = rules.reduce((a, r) => Math.max(a, r.id), 0) + 1;
  const desc = `${KIND_ZH[k]} ${v}${k === 'move' || k === 'dd' ? '%' : ''}`;
  rules.push({ id, t, kind: k, v, desc, created: new Date().toISOString() });
  await env.KV.put('rules', JSON.stringify(rules));
  const q = (await quotes([t]))[t];
  return reply(env, chat, `✅ 提醒 #${id}：<b>${t}</b> ${esc(desc)}` + (q ? `\n现价 ${q.p.toFixed(2)}` : '\n⚠️ 暂时查不到这个代码的行情，确认一下拼写') + '\n美股交易时间每 5 分钟检查一次，触发就推送。<code>/提醒列表</code> 查看全部');
}
async function cmdList(env, chat) {
  const rules = JSON.parse((await env.KV.get('rules')) || '[]');
  if (!rules.length) return reply(env, chat, '还没有用 Telegram 设的提醒。例：<code>/提醒 VOO 跌到 650</code>');
  const q = await quotes([...new Set(rules.map(r => r.t))]);
  return reply(env, chat, '📋 <b>我的提醒</b>（在 GitHub 开的提醒不在这里）\n' + rules.map(r => `#${r.id} <b>${r.t}</b> ${esc(r.desc)}` + (q[r.t] ? `  · 现价 ${q[r.t].p.toFixed(2)}` : '')).join('\n') + '\n\n删除：<code>/删除 编号</code>');
}
async function cmdDel(env, chat, arg) {
  const id = +((/\d+/.exec(arg || '') || [])[0]);
  const rules = JSON.parse((await env.KV.get('rules')) || '[]');
  const left = rules.filter(r => r.id !== id);
  if (left.length === rules.length) return reply(env, chat, '没有这个编号。<code>/提醒列表</code> 看看');
  await env.KV.put('rules', JSON.stringify(left));
  return reply(env, chat, `🗑️ 已删除提醒 #${id}`);
}

// ---------- 股价 / 简报
async function cmdMarket(env, chat) {
  const site = env.SITE;
  const [Q, pool] = await Promise.all([quotes(['SPY', 'QQQ', 'IWM', '^VIX']), fetch(`${site}/stocks/data/latest.json?t=${Math.floor(Date.now() / 36e5)}`).then(r => r.json()).catch(() => ({}))]);
  const name = { SPY: '标普500', QQQ: '纳指100', IWM: '罗素2000', '^VIX': 'VIX 恐慌指数' };
  const L = ['📊 <b>大盘</b>'];
  for (const s of ['SPY', 'QQQ', 'IWM', '^VIX']) { const q = Q[s]; if (q) L.push(`${name[s]}（${s.replace('^', '')}）<b>${q.p.toFixed(2)}</b>` + (q.prev ? ` ${pctTxt((q.p / q.prev - 1) * 100)}` : '')); }
  if (pool.regime && pool.regime.label) L.push(`\n股票池判断：「${esc(pool.regime.label)}」${esc(pool.regime.desc || '')}`);
  L.push('\n查个股：<code>/q NVDA</code> · 也可以直接打字问我');
  return reply(env, chat, L.join('\n'));
}
async function cmdQuote(env, chat, arg) {
  const t = (/[A-Za-z][A-Za-z0-9.\-]{0,6}/.exec(arg || '') || [])[0];
  if (!t) return cmdMarket(env, chat);
  const T = t.toUpperCase().replace('.', '-'), site = env.SITE;
  const [q, snap, pool] = await Promise.all([
    quotes([T]),
    fetch(`${site}/stocks/data/snap.json?t=${Math.floor(Date.now() / 36e5)}`).then(r => r.json()).catch(() => ({ rows: {} })),
    fetch(`${site}/stocks/data/latest.json?t=${Math.floor(Date.now() / 36e5)}`).then(r => r.json()).catch(() => ({}))
  ]);
  const p = q[T], r = (snap.rows || {})[T], c = (pool.candidates || []).find(x => x.t === T);
  if (!p && !r) return reply(env, chat, `查不到 ${esc(T)}，确认一下代码`);
  const L = [`📈 <b>${T}</b>${r && r.n ? ' ' + esc(r.n) : ''}`];
  if (p) L.push(`现价 <b>${p.p.toFixed(2)}</b>` + (p.prev ? `（${pctTxt((p.p / p.prev - 1) * 100)}）` : ''));
  if (r) {
    L.push(`${snap.date} 收盘 ${r.c} · RSI14 ${r.rsi} · ${r.a50 ? '站上' : '跌破'} 50 日线 · ${r.a200 ? '站上' : '跌破'} 200 日线`);
    if (r.h != null) L.push(`距一年高点 ${pctTxt(r.h * 100)} · 近 1 月 ${pctTxt((r.m1 || 0) * 100)} · 近 3 月 ${pctTxt((r.m3 || 0) * 100)} · 相对强度 ${r.rs}`);
  }
  if (c) L.push(`🎯 在今日股票池里：${esc(c.primary)} · 止损 ${c.stop} · 目标 ${c.target}${c.earn ? ` · 财报 ${c.earn}` : ''}`);
  if (pool.regime && pool.regime.label) L.push(`大盘状态：${esc(pool.regime.label)}`);
  L.push(`<a href="${site}/stocks.html">打开股票池</a>`);
  return reply(env, chat, L.join('\n'));
}
async function cmdBrief(env, chat) {
  const site = env.SITE;
  const idx = await fetch(`${site}/brief/data/index.json?t=${Date.now()}`).then(r => r.json()).catch(() => null);
  const d = idx && idx.dates && idx.dates[0];
  if (!d) return reply(env, chat, '今天的简报还没生成');
  const B = await fetch(`${site}/brief/data/${d}.json?t=${Date.now()}`).then(r => r.json()).catch(() => null);
  if (!B) return reply(env, chat, '简报读取失败');
  const L = [`☀️ <b>每日简报 ${d}</b>`];
  for (const s of B.sections || []) {
    if (!s.items || !s.items.length) continue;
    L.push(`\n<b>${esc(s.title)}</b>`);
    for (const it of s.items.slice(0, 3)) L.push(`• <b>${esc(it.t)}</b>\n  ${esc(it.d)}`);
  }
  if (B.pick && B.pick.t) L.push(`\n📌 <b>今日一件事</b>：${esc(B.pick.t)}`);
  L.push(`\n<a href="${site}/brief.html">网页版</a>`);
  return reply(env, chat, L.join('\n'));
}

// ---------- 入口
async function tgWebhook(req, env, ctx, url) {
  const want = env.TG_BOT_TOKEN ? (await sha256hex('tg-hook:' + env.TG_BOT_TOKEN)).slice(0, 32) : '';
  if (!want || url.pathname !== '/tg/' + want || req.headers.get('X-Telegram-Bot-Api-Secret-Token') !== want) return new Response('no', { status: 403 });
  const up = await req.json().catch(() => ({}));
  const msg = up.message || up.edited_message;
  if (!msg || String(msg.chat && msg.chat.id) !== String(env.TG_CHAT_ID)) return new Response('ok');   // 只理主人
  ctx.waitUntil(handle(env, msg).catch(e => reply(env, msg.chat.id, '😵 出错了：' + esc(String(e).slice(0, 200)))));
  return new Response('ok');
}
async function handle(env, msg) {
  const chat = msg.chat.id;
  if (msg.photo || (msg.document && /^image\//.test(msg.document.mime_type || ''))) return onPhoto(env, chat, msg);
  if (msg.voice || msg.audio) return onVoice(env, chat, msg);
  const text = (msg.text || '').trim();
  if (!text) return;
  const m = /^\/(\S+?)(?:@\w+)?(?:\s+([\s\S]*))?$/.exec(text);
  if (!m) return onText(env, chat, text);
  const [, cmd, arg = ''] = m;
  if (/^(提醒|alert|tx)$/i.test(cmd)) return arg.trim() ? cmdAlert(env, chat, arg) : cmdList(env, chat);
  if (/^(提醒列表|列表|list|alerts)$/i.test(cmd)) return cmdList(env, chat);
  if (/^(删除|del|rm)$/i.test(cmd)) return cmdDel(env, chat, arg);
  if (/^(股价|q|quote|gj)$/i.test(cmd)) return cmdQuote(env, chat, arg);
  if (/^(简报|brief|jb)$/i.test(cmd)) return cmdBrief(env, chat);
  if (/^(用量|usage|yl)$/i.test(cmd)) return cmdUsage(env, chat);
  if (/^(翻译|fy|tr)$/i.test(cmd)) return arg.trim() ? doTranslate(env, chat, arg.trim(), '', '', true) : reply(env, chat, '打「翻译 要翻的话」，或者直接发语音');
  return reply(env, chat, HELP);
}

// ---------------------------------------------------------------------------- 入口
export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors(req) });
    if (url.pathname === '/ocr' && req.method === 'POST') return ocr(req, env);
    if (url.pathname === '/explain' && req.method === 'POST') return explain(req, env);
    if (url.pathname.startsWith('/tg/') && req.method === 'POST') return tgWebhook(req, env, ctx, url);
    if (url.pathname === '/push/register' && req.method === 'POST') {   // App 登记推送地址（需要首页密码解锁过）
      if (!(await authed(req, env))) return json(req, { error: 'key' }, 401);
      const b = await req.json().catch(() => ({}));
      if (!b.token || String(b.token).length < 20) return json(req, { error: 'token' }, 400);
      const list = JSON.parse((await env.KV.get('fcm:tokens')) || '[]').filter(t => t.token !== b.token);
      list.push({ token: String(b.token), device: String(b.device || '').slice(0, 60), at: new Date().toISOString() });
      await env.KV.put('fcm:tokens', JSON.stringify(list.slice(-5)));
      return json(req, { ok: true, devices: list.slice(-5).length });
    }
    if (url.pathname === '/push/send' && req.method === 'POST') {      // GitHub 上的自动任务发推送
      const k = await pushKey(env);
      if (!k || req.headers.get('X-Push-Key') !== k) return json(req, { error: 'key' }, 401);
      const b = await req.json().catch(() => ({}));
      try { return json(req, await fcmSend(env, b)); } catch (e) { return json(req, { error: String(e).slice(0, 300) }, 500); }
    }
    if (url.pathname === '/health') {
      const last = await env.KV.get('last-run');
      const devices = JSON.parse((await env.KV.get('fcm:tokens')) || '[]').length;
      return json(req, { ok: true, ai: !!env.AI, kv: !!env.KV, telegram: !!(env.TG_BOT_TOKEN && env.TG_CHAT_ID), check: !!env.CHECK, fcm: !!env.FCM_SERVICE_ACCOUNT, app_devices: devices, last: last ? JSON.parse(last) : null });
    }
    if (url.pathname === '/selftest' && req.method === 'POST') {   // 部署后自检：翻译 → 西语朗读 → 再听写回来
      if (!(await authed(req, env))) return json(req, { error: 'key' }, 401);
      const out = {};
      try { out.translate = (await translate(env, '把这个柜子放到12号门', 'zh')).J; } catch (e) { out.translate = 'ERR ' + String(e).slice(0, 150); }
      let mp3 = null;
      try {
        const r = await env.AI.run('@cf/myshell-ai/melotts', { prompt: (out.translate && out.translate.es) || 'Pon este contenedor en la puerta doce', lang: 'es' });
        const a = typeof r === 'string' ? r : r && r.audio;
        mp3 = a ? Uint8Array.from(atob(a), c => c.charCodeAt(0)) : null;
        out.tts = mp3 ? mp3.length + ' bytes' : 'empty';
      } catch (e) { out.tts = 'ERR ' + String(e).slice(0, 150); }
      if (mp3) {
        for (const model of WHISPER) {
          try {
            const r = model.includes('turbo') ? await env.AI.run(model, { audio: b64(mp3) }) : await env.AI.run(model, { audio: [...mp3] });
            out.whisper = model + ': ' + ((r && r.text) || JSON.stringify(r).slice(0, 120));
            if (r && r.text) break;
          } catch (e) { out.whisper = model + ' ERR ' + String(e).slice(0, 150); }
        }
      }
      try { out.reverse = (await translate(env, 'Estoy esperando en la puerta tres', 'es')).J; } catch (e) { out.reverse = 'ERR ' + String(e).slice(0, 150); }
      return json(req, out);
    }
    if (url.pathname === '/intraday' && req.method === 'POST') {   // 手动跑一次（测试用）
      if (!(await authed(req, env))) return json(req, { error: 'key' }, 401);
      return json(req, await intraday(env, url.searchParams.get('force') === '1'));
    }
    return json(req, { name: 'tools-api', endpoints: ['/health', 'POST /ocr'] });
  },
  async scheduled(event, env, ctx) { ctx.waitUntil(intraday(env)); }
};
