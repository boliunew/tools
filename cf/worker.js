// tools-api — 工具箱在 Cloudflare 上的小后端（由 .github/workflows/cf-worker.yml 自动部署）
//
//  POST /ocr     拍照识别柜号 / 封条号（Workers AI 视觉模型 + ISO 6346 校验）。需要请求头 X-Tools-Key：
//                网站首页解锁后存在浏览器里的那串密钥（sha256 后等于 CHECK），或部署时生成的测试密钥。
//  GET  /health  看看活着没有、配了哪些东西
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

async function runVision(env, bytes, mime) {
  const errs = [];
  const dataUri = `data:${mime};base64,${b64(bytes)}`;
  for (const model of VISION) {
    try {
      let input;
      if (model.includes('llama-3.2')) input = { messages: [{ role: 'user', content: OCR_PROMPT }], image: [...bytes], max_tokens: 600 };
      else input = { messages: [{ role: 'user', content: [{ type: 'text', text: OCR_PROMPT }, { type: 'image_url', image_url: { url: dataUri } }] }], max_tokens: 600, temperature: 0 };
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
  if (!env.TG_BOT_TOKEN || !env.TG_CHAT_ID) return false;
  const r = await fetch(`https://api.telegram.org/bot${env.TG_BOT_TOKEN}/sendMessage`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: env.TG_CHAT_ID, text, parse_mode: 'HTML', disable_web_page_preview: true })
  });
  return r.ok;
}

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
  const rules = Object.entries(A.items || {}).filter(([, a]) => ['below', 'above', 'move', 'dd'].includes(a.kind) && a.t);
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
    const ok = await tg(env, `🔔 <b>股价提醒（盘中）</b>：<b>${a.t}</b> ${a.desc || ''}\n${detail}\n<a href="${a.url || site + '/stocks.html'}">查看提醒</a> · <a href="${site}/stocks.html">股票池</a>`);
    if (ok) {
      sent.push(id);
      if (level) await env.KV.put(armKey, now.date, { expirationTtl: 86400 * 60 });
      else await env.KV.put(dayKey, '1', { expirationTtl: 86400 * 2 });
    }
  }
  await env.KV.put('last-run', JSON.stringify({ at: new Date().toISOString(), rules: rules.length, quotes: Object.keys(Q).length, sent }), { expirationTtl: 86400 * 7 });
  return { et: now, rules: rules.length, quotes: Object.fromEntries(Object.entries(Q).map(([k, v]) => [k, v.p])), sent, telegram: !!(env.TG_BOT_TOKEN && env.TG_CHAT_ID) };
}

// ---------------------------------------------------------------------------- 入口
export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors(req) });
    if (url.pathname === '/ocr' && req.method === 'POST') return ocr(req, env);
    if (url.pathname === '/health') {
      const last = await env.KV.get('last-run');
      return json(req, { ok: true, ai: !!env.AI, kv: !!env.KV, telegram: !!(env.TG_BOT_TOKEN && env.TG_CHAT_ID), check: !!env.CHECK, last: last ? JSON.parse(last) : null });
    }
    if (url.pathname === '/intraday' && req.method === 'POST') {   // 手动跑一次（测试用）
      if (!(await authed(req, env))) return json(req, { error: 'key' }, 401);
      return json(req, await intraday(env, url.searchParams.get('force') === '1'));
    }
    return json(req, { name: 'tools-api', endpoints: ['/health', 'POST /ocr'] });
  },
  async scheduled(event, env, ctx) { ctx.waitUntil(intraday(env)); }
};
