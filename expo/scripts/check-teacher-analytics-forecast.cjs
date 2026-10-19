const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/teacher-analytics-forecast.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleRef = { exports: {} };
new Function('module', 'exports', 'require', compiled)(moduleRef, moduleRef.exports, require);
const now = new Date(2026, 9, 12);
const packages = [
  { student: 'Ana', currency: 'TRY', remaining: 4, paymentDate: '2026-09-01', expiryDate: '', status: 'active' },
  { student: 'Bob', currency: 'TRY', remaining: 2, paymentDate: '2026-02-01', expiryDate: '2026-11-01', status: 'finishing_soon' },
  { student: 'Clara', currency: 'TRY', remaining: -1, paymentDate: '2026-10-01', expiryDate: '', status: 'overused' },
];
const lessons = [
  { student: 'Ana', lesson_date: '2026-09-20', number_of_lesson: 4, modality: 'Online', note: '' },
  { student: 'Zed', lesson_date: '2026-09-21', number_of_lesson: 8, modality: 'Online', note: '' },
  { student: 'Bob', lesson_date: '2026-09-19', number_of_lesson: 2, modality: 'Online', note: '[FREE]' },
];
const payments = [
  { student: 'Ana', payment_date: '2026-01-01', paid_amount: 100, number_of_lesson: 10, currency: 'TRY' },
  { student: 'Ana', payment_date: '2026-07-01', paid_amount: 120, number_of_lesson: 10, currency: 'TRY' },
  { student: 'Ana', payment_date: '2026-09-01', paid_amount: 140, number_of_lesson: 10, currency: 'TRY' },
  { student: 'Bob', payment_date: '2026-02-01', paid_amount: 200, number_of_lesson: 20, currency: 'TRY' },
  { student: 'Clara', payment_date: '2026-10-01', paid_amount: 50, number_of_lesson: 5, currency: 'TRY' },
];
const dataset = { lessons, payments };
const forecast = moduleRef.exports.buildAnalyticsForecast(dataset, packages, 7, now);
const actual = forecast.map((row) => ({ student: row.student, rate: row.unitsPerDay, days: row.daysToFinish, finish: row.estimatedFinishDate, reminder: row.reminderDate, due: row.dueNow }));
const python = path.join(__dirname, '../../.venv/bin/python');
const expected = JSON.parse(execFileSync(python, [path.join(__dirname, 'python-teacher-forecast-reference.py')], { encoding: 'utf8' }));
assert.deepEqual(actual, expected.forecast);
const projection = moduleRef.exports.buildAnnualRenewalProjection(dataset, forecast, 'TRY', now);
assert.deepEqual({ ytd: projection.ytd, expected_future: projection.expectedFuture, projected: projection.projected, counted: projection.counted, missing_baseline: projection.missingBaseline }, expected.projection);
const inactivePackage = { student: 'Inactive', currency: 'TRY', remaining: 6, paymentDate: '2025-01-01', expiryDate: '', status: 'active' };
const inactiveData = { lessons: [], payments: [{ student: 'Inactive', payment_date: '2025-01-01', paid_amount: 100, number_of_lesson: 6, currency: 'TRY' }] };
const inactiveForecast = moduleRef.exports.buildAnalyticsForecast(inactiveData, [inactivePackage], 0, now);
assert.equal(inactiveForecast[0].isActive, false);
assert.equal(moduleRef.exports.buildAnnualRenewalProjection(inactiveData, inactiveForecast, 'TRY', now).expectedFuture, 0);
const optimizerSource = fs.readFileSync(path.join(__dirname, '../src/services/teacher-goal-optimizer.ts'), 'utf8');
const optimizerModule = { exports: {} };
new Function('module', 'exports', 'require', ts.transpileModule(optimizerSource, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText)(optimizerModule, optimizerModule.exports, require);
const optimization = optimizerModule.exports.buildGoalOptimization(dataset, forecast, projection, 'TRY', 1500, now);
for (const [key, value] of Object.entries(expected.optimization)) {
  if (typeof value === 'number') assert.ok(Math.abs(optimization[key] - value) < 1e-7, `${key}: ${optimization[key]} != ${value}`);
  else if (key === 'scenarios') value.forEach((scenario, index) => { assert.equal(optimization.scenarios[index].key, scenario.key); assert.ok(Math.abs(optimization.scenarios[index].impact - scenario.impact) < 1e-7); assert.ok(Math.abs(optimization.scenarios[index].value - scenario.value) < 1e-7); });
  else assert.deepEqual(optimization[key], value);
}
process.stdout.write('Teacher Analytics forecast and goal optimizer match Streamlit frozen reference.\n');
