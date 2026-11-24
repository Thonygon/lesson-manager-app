const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');

const source = fs.readFileSync('src/services/student-package-reports.ts', 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleExports = {};
vm.runInNewContext(compiled, { exports: moduleExports });

const payments = [
  { id: 1, payment_date: '2025-09-15', package_start_date: '2025-09-08', number_of_lesson: 18, subject: 'English', modality: 'Online' },
  { id: 2, payment_date: '2025-12-12', package_start_date: '2025-12-15', number_of_lesson: 44, subject: 'English', modality: 'Online' },
];
const lessons = [
  { id: 1, lesson_date: '2025-09-08', number_of_lesson: 1 },
  { id: 2, lesson_date: '2025-09-10', number_of_lesson: 1 },
  { id: 3, lesson_date: '2025-12-03', number_of_lesson: 1 },
  { id: 4, lesson_date: '2025-12-15', number_of_lesson: 1 },
  { id: 5, lesson_date: '2025-12-16', number_of_lesson: 1, note: '[FREE]' },
];
const reports = moduleExports.studentPackageReports(payments, lessons);
assert.equal(JSON.stringify(reports.map((report) => report.lessons.map((row) => row.id))), JSON.stringify([[1, 2, 3], [4, 5]]));
assert.equal(JSON.stringify(reports.map((report) => report.balance.delivered)), JSON.stringify([3, 1]));
assert.equal(reports[0].balance.remaining, 15);
assert.equal(reports[1].balance.remaining, 43);
assert.equal(JSON.stringify(moduleExports.studentPackageReports(payments, lessons.slice(0, 2)).map((report) => report.lessons.length)), JSON.stringify([2, 0]));
console.log('Student package report boundaries and balances passed.');
