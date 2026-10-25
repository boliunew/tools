// Cloudflare 后端：柜号校验位和候选提取（node --test tests/worker.test.mjs）
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const src = fs.readFileSync(new URL('../cf/worker.js', import.meta.url), 'utf8').replace(/export default[\s\S]*$/, '') + '\nexport { cd, containerCandidates };';
const tmp = new URL('./.worker_under_test.mjs', import.meta.url);
fs.writeFileSync(tmp, src);
const { cd, containerCandidates } = await import(tmp.href);
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
