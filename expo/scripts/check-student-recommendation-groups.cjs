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
const { groupStudentRecommendations } = load('src/services/student-recommendation-groups.ts', { '@/lib/subjects': subjects });
const rows = [
  { id: 1, subject: 'English', learningProgramAssignmentId: 10, programTeacherId: 'a' },
  { id: 2, subject: 'Inglés', learningProgramAssignmentId: 20, programTeacherId: 'b' },
  { id: 3, subject: 'English', learningProgramAssignmentId: 10, programTeacherId: 'a' },
  { id: 4, subject: 'Spanish' },
];
const groups = groupStudentRecommendations(rows, { a: 'Ada', b: 'Ben' });
assert.deepEqual(groups.map((group) => group.key), ['assignment:10', 'assignment:20', 'subject:spanish']);
assert.deepEqual(groups.map((group) => group.rows.map((row) => row.id)), [[1, 3], [2], [4]]);
assert.deepEqual(groups.map((group) => group.label), ['English · Ada', 'English · Ben', 'Spanish']);
process.stdout.write('Student recommendation grouping fixtures passed.\n');
