const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

function load(relative, aliases = {}) {
  const source = fs.readFileSync(path.join(__dirname, '..', relative), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const module = { exports: {} };
  new Function('module', 'exports', 'require', compiled)(module, module.exports, (name) => aliases[name] || require(name));
  return module.exports;
}

const subjects = load('src/lib/subjects.ts');
const { groupPracticeRows } = load('src/services/student-practice-groups.ts', { '@/lib/subjects': subjects });
const rows = [
  { id: 1, subject: 'English', teacher: 'a' },
  { id: 2, subject: 'Inglés', teacher: 'a' },
  { id: 3, subject: 'English', teacher: 'b' },
  { id: 4, subject: 'Spanish', teacher: '' },
  { id: 5, subject: '', teacher: '' },
];
const groups = groupPracticeRows(rows, (row) => ({ teacherId: row.teacher, teacherName: row.teacher === 'a' ? 'Ada' : row.teacher === 'b' ? 'Ben' : '' }));
assert.deepEqual(groups.map((group) => group.rows.map((row) => row.id)), [[1, 2], [3], [4]]);
assert.deepEqual(groups.map((group) => group.label), ['📚 English · Ada', '📚 English · Ben', '📚 Spanish']);
assert.deepEqual(groupPracticeRows(rows.slice(0, 1), (row) => ({ teacherId: row.teacher }))[0].rows.map((row) => row.id), [1]);
process.stdout.write('Student practice grouping fixtures passed.\n');
