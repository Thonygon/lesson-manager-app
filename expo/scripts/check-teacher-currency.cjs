const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/teacher-currency.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleRef = { exports: {} };
new Function('module', 'exports', 'require', compiled)(moduleRef, moduleRef.exports, require);

(async () => {
  const originalFetch = global.fetch;
  const calls = [];
  global.fetch = async (url) => { calls.push(url); return { ok: true, json: async () => ({ result: 'success', rates: { USD: .025, EUR: .021 } }) }; };
  try {
    assert.equal(await moduleRef.exports.getAnalyticsExchangeRate('TRY', 'TRY'), 1);
    assert.equal(await moduleRef.exports.getAnalyticsExchangeRate('TRY', 'USD'), .025);
    assert.equal(await moduleRef.exports.getAnalyticsExchangeRate('TRY', 'EUR'), .021);
    assert.deepEqual(calls, ['https://open.er-api.com/v6/latest/TRY']);
    await assert.rejects(moduleRef.exports.getAnalyticsExchangeRate('TRY', 'BAD'), /Unsupported currency/);
    global.fetch = async (url) => { calls.push(url); return { ok: true, json: async () => [{}, [{ date: '2025', value: 120 }, { date: '2026', value: 150 }, { date: '2024', value: null }]] }; };
    const cpi = await moduleRef.exports.getAnalyticsCpi('Turkey');
    assert.equal(cpi[2025], 120);
    assert.equal(cpi[2026], 150);
    assert.equal(cpi[2024], undefined);
    assert.equal(moduleRef.exports.inflateAnalyticsAmount(100, 2025, 2026, cpi), 125);
    assert.equal(moduleRef.exports.inflateAnalyticsAmount(100, 2024, 2026, cpi), 100);
    assert.ok(calls.at(-1).includes('country/TUR/indicator/FP.CPI.TOTL'));
    await assert.rejects(moduleRef.exports.getAnalyticsCpi('Neverland'), /Unsupported inflation country/);
  } finally { global.fetch = originalFetch; }
  process.stdout.write('Teacher currency conversion validates rates and reuses the one-hour base cache.\n');
})().catch((error) => { process.stderr.write(`${error.stack}\n`); process.exitCode = 1; });
