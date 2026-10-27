const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const source = fs.readFileSync(path.join(__dirname, '../src/lib/income-goal-handoff.ts'), 'utf8');
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
const store = new Map();
const storage = { getItem: async (key) => store.get(key) ?? null, setItem: async (key, value) => { store.set(key, value); }, removeItem: async (key) => { store.delete(key); } };
const moduleRef = { exports: {} };
new Function('module', 'exports', 'require', code)(moduleRef, moduleRef.exports, (name) => {
  if (name === '@react-native-async-storage/async-storage') return { __esModule: true, default: storage };
  if (name === '@/lib/income-planner') return { CURRENCY_FACTORS: { USD: 1, EUR: .92 } };
  throw new Error(name);
});
const { savePendingIncomeGoal, getPendingIncomeGoal, clearPendingIncomeGoal, parsePendingIncomeGoal } = moduleRef.exports;
(async () => {
  const now = Date.now();
  await savePendingIncomeGoal(46000, 'EUR');
  assert.equal((await getPendingIncomeGoal()).amount, 46000);
  assert.equal((await getPendingIncomeGoal()).currency, 'EUR');
  assert.equal(parsePendingIncomeGoal(JSON.stringify({ amount: 1, currency: 'EUR', year: new Date(now).getFullYear(), createdAt: now - 8 * 86400000 }), now), null);
  assert.equal(parsePendingIncomeGoal(JSON.stringify({ amount: 1, currency: 'EUR', year: new Date(now).getFullYear() - 1, createdAt: now }), now), null);
  assert.equal(parsePendingIncomeGoal(JSON.stringify({ amount: 1, currency: 'XXX', year: new Date(now).getFullYear(), createdAt: now }), now), null);
  await clearPendingIncomeGoal();
  assert.equal(await getPendingIncomeGoal(), null);
  console.log('Income goal handoff fixtures passed');
})().catch((error) => { console.error(error); process.exitCode = 1; });
