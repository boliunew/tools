// Cloudflare 后端：柜号校验位和候选提取（node --test tests/worker.test.mjs）
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const src = fs.readFileSync(new URL('../cf/worker.js', import.meta.url), 'utf8').replace(/export default[\s\S]*$/, '') + '\nexport { cd, containerCandidates, placeOf, osmDigest, localClean, localApi };';
const tmp = new URL('./.worker_under_test.mjs', import.meta.url);
fs.writeFileSync(tmp, src);
const { cd, containerCandidates, placeOf, osmDigest, localClean, localApi } = await import(tmp.href);
fs.unlinkSync(tmp);

test('ISO 6346 check digit', () => {
  assert.equal(cd('CSQU305438'), 3);
  assert.equal(cd('MSKU123456'), 5);
});

test('candidates: spacing, O/0 mix-ups, missing check digit, junk', () => {
  const one = s => containerCandidates([s])[0];
  assert.deepEqual([one('CSQU 305438 3').no, one('CSQU 305438 3').ok], ['CSQU3054383', true]);
  assert.equal(one('C5QU 3O5438 3').no, 'CSQU3054383');
  assert.equal(one('CSQU\n305438\n[3]').no, 'CSQU3054383');
  assert.equal(one('CSQU 305438').calc, true);
  assert.equal(one('TGHU 876543 2').ok, false);
  assert.deepEqual(containerCandidates(['seals 12345678 and SEAL SL1234567 text HELLO WORLD 1234567']), []);
});

// ---------------------------------------------------------------- 📍 本地通
const NOMI = { lat: '34.0975', lon: '-117.6484', name: 'Upland', addresstype: 'city',
  address: { city: 'Upland', county: 'San Bernardino County', state: 'California', country: 'United States', country_code: 'us' },
  namedetails: { name: 'Upland', 'name:zh': '阿普兰' }, extratags: { population: '79,040', wikipedia: 'en:Upland, California' } };

test('placeOf: city name, Chinese name, population, wiki title', () => {
  const p = placeOf(NOMI);
  assert.equal(p.en, 'Upland'); assert.equal(p.zh, '阿普兰'); assert.equal(p.state, 'California');
  assert.equal(p.cc, 'us'); assert.equal(p.pop, 79040); assert.equal(p.wiki, 'en:Upland, California');
  assert.equal(placeOf({}), null);
});

test('osmDigest: drops chains and duplicates, rotates cuisines, sorts kinds', () => {
  const tags = [
    { name: 'Starbucks', amenity: 'cafe' }, { name: "McDonald's", amenity: 'fast_food' },
    { name: 'Pho Ha', amenity: 'restaurant', cuisine: 'vietnamese' }, { name: 'Pho Ha', amenity: 'restaurant', cuisine: 'vietnamese' },
    { name: 'Taqueria Uno', amenity: 'restaurant', cuisine: 'mexican' }, { name: 'Taqueria Dos', amenity: 'restaurant', cuisine: 'mexican' },
    { name: 'Upland Memorial Park', leisure: 'park' }, { name: 'Upland', railway: 'station', network: 'Metrolink' },
    { name: 'Ontario International Airport', aeroway: 'aerodrome', iata: 'ONT' }, { name: 'Old Town', place: 'neighbourhood' }
  ];
  const d = osmDigest(tags);
  assert.deepEqual(d.eat, ['Taqueria Uno [mexican]', 'Pho Ha [vietnamese]', 'Taqueria Dos [mexican]']);
  assert.match(d.cuisines, /mexican×2/);
  assert.match(d.text, /公园 \/ 自然：Upland Memorial Park \[park\]/);
  assert.match(d.text, /火车 \/ 地铁站：Upland \[Metrolink\]/);
  assert.match(d.text, /机场：Ontario International Airport \[ONT\]/);
  assert.doesNotMatch(d.text, /Starbucks|McDonald/);
});

test('localClean: caps sizes, drops untitled cards, keeps only known fields', () => {
  const G = localClean({ intro: ['a', 'b', 'c', 'd'], facts: [['人口', '约 8 万'], ['bad']], hoods: [{ t: 'Old Town', s: 'x', d: 'y', evil: '<script>' }, { s: 'no title' }],
    eat: Array.from({ length: 30 }, (_, i) => ({ t: 'E' + i })), trivia: ['x'] });
  assert.equal(G.intro.length, 3); assert.deepEqual(G.facts, [['人口', '约 8 万']]);
  assert.equal(G.hoods.length, 1); assert.equal(G.hoods[0].evil, undefined); assert.equal(G.hoods[0].e, '📍');
  assert.equal(G.eat.length, 18); assert.deepEqual(G.fun, []);
});

test('localApi: auth, resolve, generate once, then serve from cache', async () => {
  const kv = new Map(), calls = { ai: 0, fetch: [] };
  const env = { TEST_KEY: 'k', KV: { get: async k => kv.get(k) ?? null, put: async (k, v) => { kv.set(k, v); }, delete: async k => { kv.delete(k); } },
    AI: { run: async (model, input) => {
      calls.ai++;
      const ask = input.input;
      if (/"intro":\[/.test(ask) && /"hoods"/.test(ask)) return { output: [{ type: 'message', content: [{ text: JSON.stringify({ intro: ['阿普兰在…', '历史…', '看点…'], facts: [['人口', '约 8 万']], hoods: [{ e: '🏘️', t: '老城 Old Town', s: 's', d: 'd' }], stories: [{ t: '柑橘', y: '1900', s: 's', d: 'd' }], trivia: ['冷知识'] }) }] }] };
      if (/输出：\{"eat"/.test(ask)) return { output: [{ type: 'message', content: [{ text: JSON.stringify({ eat: [{ t: '越南粉', s: 's', d: 'Pho Ha' }, { t: '墨西哥卷饼', s: 's', d: 'd' }], fun: [{ t: '纪念公园 Upland Memorial Park', s: 's', d: 'd', tag: ['免费'] }, { t: 'f2', s: 's', d: 'd' }, { t: 'f3', s: 's', d: 'd' }] }) }] }] };
      return { output: [{ type: 'message', content: [{ text: '好的 ' + JSON.stringify({ tips: [{ t: '图书馆卡', s: 's', d: 'd' }], go: [{ t: '怎么去', s: 's', d: 'd' }], work: [{ t: '行业', s: 's', d: 'd' }] }) }] }] };
    } } };
  globalThis.fetch = async (url, opt) => {
    calls.fetch.push(String(url));
    const J = o => ({ ok: true, json: async () => o });
    if (/nominatim.*reverse/.test(url)) return J(NOMI);
    if (/list=search/.test(url)) return J({ query: { search: [{ title: 'Upland, California' }] } });
    if (/en\.wikipedia.*prop=extracts/.test(url)) return J({ query: { pages: [{ title: 'Upland, California', extract: 'Upland is a city in San Bernardino County.', langlinks: [{ title: '阿普兰' }] }] } });
    if (/zh\.wikipedia/.test(url)) return J({ query: { pages: [{ title: '阿普兰', extract: '阿普兰是加州的一座城市。' }] } });
    if (/geosearch/.test(url)) return J({ query: { pages: [{ title: 'Upland Memorial Park', description: 'park' }] } });
    if (/overpass/.test(url)) return J({ elements: [{ tags: { name: 'Pho Ha', amenity: 'restaurant', cuisine: 'vietnamese' } }, { tags: { name: 'Upland Memorial Park', leisure: 'park' } }] });
    return { ok: false, json: async () => null };
  };
  const mk = (body, key = 'k') => new Request('https://x/local', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Tools-Key': key, Origin: 'https://boliunew.github.io' }, body: JSON.stringify(body) });

  assert.equal((await localApi(mk({ lat: 34.1, lon: -117.6 }, 'wrong'), env)).status, 401);

  const r1 = await (await localApi(mk({ lat: 34.09812, lon: -117.64811 }), env)).json();
  assert.equal(r1.place.en, 'Upland'); assert.equal(r1.place.zh, '阿普兰');
  assert.equal(r1.guide.intro.length, 3); assert.equal(r1.guide.eat.length, 2); assert.equal(r1.guide.tips[0].t, '图书馆卡');
  assert.equal(r1.guide.sources.length, 3); assert.equal(calls.ai, 3); assert.ok(!r1.cached);
  assert.ok(calls.fetch.some(u => /lat=34\.10&lon=-117\.65/.test(u)), 'coordinates are rounded to ~1 km before leaving the worker');
  assert.ok(![...kv.keys()].some(k => k.startsWith('lock:')), 'lock released');

  const r2 = await (await localApi(mk({ lat: 34.1, lon: -117.65 }), env)).json();
  assert.equal(r2.cached, true); assert.equal(calls.ai, 3);

  globalThis.fetch = async () => ({ ok: true, json: async () => [] });
  const r3 = await localApi(mk({ q: 'Nowhereville' }), env);
  assert.equal(r3.status, 404);
});

test('placeOf: keeps only the first of multi-language values', () => {
  const p = placeOf({ ...NOMI, address: { ...NOMI.address, state: '加利福尼亚州;加利福尼亞州', country: '美国;美國' } });
  assert.equal(p.state, '加利福尼亚州'); assert.equal(p.country, '美国');
});

test('localApi: a section that comes back empty is retried, and a still-incomplete guide is cached briefly', async () => {
  const kv = new Map(), ttl = {}; let eatTries = 0, calls = 0;
  const msg = o => ({ output: [{ type: 'message', content: [{ text: JSON.stringify(o) }] }] });
  const card = t => ({ t, s: 's', d: 'd' });
  const env = { TEST_KEY: 'k', KV: { get: async k => kv.get(k) ?? null, put: async (k, v, o) => { kv.set(k, v); ttl[k] = o && o.expirationTtl; }, delete: async k => { kv.delete(k); } },
    AI: { run: async (m, input) => {
      calls++;
      const ask = input.input || (input.messages || [])[1]?.content || '';
      if (/输出：\{"eat"/.test(ask)) { eatTries++; return msg(eatTries === 1 ? { eat: [], fun: [] } : { eat: [card('e1'), card('e2')], fun: [card('f1'), card('f2')] }); }
      if (/"hoods"/.test(ask)) return msg({ intro: ['a'], hoods: [card('h1'), card('h2')], stories: [card('s1')] });
      return msg({ tips: [card('t1')], go: [] });   // go 一直缺
    } } };
  globalThis.fetch = async (url) => {
    const J = o => ({ ok: true, status: 200, json: async () => o, text: async () => JSON.stringify(o) });
    if (/reverse/.test(url)) return J(NOMI);
    if (/overpass|kumi|coffee|mail\.ru/.test(url)) return { ok: false, status: 429, json: async () => null, text: async () => 'rate_limited' };
    return J({ query: { pages: [], search: [] } });
  };
  const req = new Request('https://x/local', { method: 'POST', headers: { 'X-Tools-Key': 'k' }, body: JSON.stringify({ lat: 34.1, lon: -117.65 }) });
  const r = await (await localApi(req, env)).json();
  assert.equal(eatTries, 2, 'eat/fun retried once');
  assert.equal(r.guide.eat.length, 2); assert.equal(r.guide.go.length, 0); assert.equal(r.stats.full, false);
  assert.ok(r.diag.some(d => /missing eat\/fun/.test(d)), r.diag.join(' | '));
  assert.ok(r.diag.some(d => /overpass-api\.de 429/.test(d)), r.diag.join(' | '));
  const k = [...kv.keys()].find(k => k.startsWith('local1:'));
  assert.equal(ttl[k], 6 * 3600);
});
