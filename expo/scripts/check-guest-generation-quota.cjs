const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const source = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/server/guest-generation-quota.ts'), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const mod = { exports: {} };
new Function('module', 'exports', source)(mod, mod.exports);
const { reserveGuestGeneration } = mod.exports;
const originalFetch = global.fetch;
const reservations = new Map();
global.fetch = async (url, options) => {
  assert.match(String(url), /classio_reserve_guest_generation$/);
  const { p_ip_hash, p_cookie_hash } = JSON.parse(options.body);
  assert.match(p_ip_hash, /^[a-f0-9]{64}$/);
  assert.match(p_cookie_hash, /^[a-f0-9]{64}$/);
  const ipUsed = reservations.get(p_ip_hash) || 0;
  const cookieUsed = reservations.get(p_cookie_hash) || 0;
  const used = Math.max(ipUsed, cookieUsed);
  if (used >= 3) return Response.json({ allowed: false, used });
  reservations.set(p_ip_hash, ipUsed + 1);
  reservations.set(p_cookie_hash, cookieUsed + 1);
  return Response.json({ allowed: true, used: used + 1 });
};
async function main() {
  try {
    const config = { base: 'https://supabase.test', serverKey: 'fixture-key', secret: 'fixture-secret' };
    const request = (ip, cookie = '') => new Request('https://classio.test/api/generate', { headers: { 'x-real-ip': ip, cookie } });
    const first = await reserveGuestGeneration(request('192.0.2.42'), config);
    assert.equal(first.allowed, true);
    for (let i = 0; i < 2; i += 1) assert.equal((await reserveGuestGeneration(request('192.0.2.42'), config)).allowed, true);
    assert.equal((await reserveGuestGeneration(request('192.0.2.42'), config)).allowed, false, 'clearing the cookie must not reset an IP');
    const cookie = first.cookie.split(';')[0];
    assert.equal((await reserveGuestGeneration(request('198.51.100.3', cookie), config)).allowed, true);
    assert.equal((await reserveGuestGeneration(request('198.51.100.3', cookie), config)).allowed, true);
    assert.equal((await reserveGuestGeneration(request('198.51.100.3', cookie), config)).allowed, false, 'a cookie must survive network changes');
    await assert.rejects(reserveGuestGeneration(request(''), config), /Client IP is unavailable/);
    const migration = fs.readFileSync(path.join(__dirname, '../../streamlit/migrations/guest_generation_daily_quota.sql'), 'utf8');
    assert.match(migration, /created_at < now\(\) - interval '48 hours'/);
    assert.match(migration, /cron\.schedule\(/);
    process.stdout.write('Guest quota fixtures passed.\n');
  } finally { global.fetch = originalFetch; }
}
void main();
