const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const ts = require('typescript');

const fixture = require('./fixtures/teacher-ledger.json');
const source = fs.readFileSync(path.join(__dirname, '../src/services/teacher-insights.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleRef = { exports: {} };
const localRequire = (name) => {
  if (name === 'react-native') return { Platform: { OS: 'web' } };
  if (name === '@/lib/subjects') return { canonicalSubjectLabel: (value) => value };
  if (name === '@/lib/supabase') return { requireSupabase: () => { throw Error('fixture must not query Supabase'); } };
  if (name === '@/services/teacher-history-pagination') return { readTeacherHistory: () => { throw Error('fixture must not query teacher history'); } };
  if (name === '@/services/teacher-currency') return { ANALYTICS_CURRENCIES: [] };
  return require(name);
};
new Function('module', 'exports', 'require', compiled)(moduleRef, moduleRef.exports, localRequire);
const RealDate = Date;
global.Date = class extends RealDate { constructor(...args) { super(...(args.length ? args : ['2026-10-12T00:00:00'])); } static now() { return new RealDate('2026-10-12T00:00:00').valueOf(); } };
let actual;
try { actual = moduleRef.exports.buildPackageInsights({ students: [], payments: fixture.payments, lessons: fixture.lessons }).map((row) => ({ student: row.student, purchased: row.purchased, delivered: row.delivered, remaining: row.remaining, status: row.dashboardStatus })); }
finally { global.Date = RealDate; }
const expected = JSON.parse(execFileSync(path.join(__dirname, '../../.venv/bin/python'), [path.join(__dirname, 'python-teacher-ledger-reference.py')], { encoding: 'utf8' }));
assert.deepEqual(actual.sort((a, b) => a.student.localeCompare(b.student)), expected.sort((a, b) => a.student.localeCompare(b.student)));
process.stdout.write('Teacher package ledger matches Streamlit frozen reference.\n');
