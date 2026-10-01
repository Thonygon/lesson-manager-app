const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

function loadSource(relativePath, aliases = {}) {
  const source = fs.readFileSync(path.join(__dirname, '..', relativePath), 'utf8');
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const module = { exports: {} };
  new Function('module', 'exports', 'require', compiled)(module, module.exports, (name) => aliases[name] || require(name));
  return module.exports;
}

const subjects = loadSource('src/lib/subjects.ts');
const programs = loadSource('src/services/student-recommendation-programs.ts', { '@/lib/subjects': subjects });
const { buildStudentAssignmentBehavior } = loadSource('src/services/student-recommendation-assignment-behavior.ts', {
  '@/services/student-recommendation-programs': programs,
});
const profile = buildStudentAssignmentBehavior([
  { assignment_type: 'worksheet', topic: 'Fractions', status: 'assigned', score_pct: null },
  { assignment_type: 'worksheet', topic: 'Fractions', status: 'graded', score_pct: 80 },
  { assignment_type: 'exam', title: 'Decimals', status: 'completed', score_pct: 50 },
  { assignment_type: 'lesson_plan_topic', topic: 'Ratios', status: 'started', score_pct: null },
  { assignment_type: 'video', topic: 'Ignored', status: 'completed', score_pct: 100 },
]);
assert.deepEqual(profile.kindSuccess, { worksheet: 0.8, exam: 0.5, plan: 0 });
assert.deepEqual(profile.kindCompletion, { worksheet: 0.5, exam: 1, plan: 0 });
assert.deepEqual(profile.topicSuccess, { fractions: 0.8, decimals: 0.5, ratios: 0 });
assert.deepEqual([...profile.recentTeacherTopics].sort(), ['decimals', 'fractions', 'ratios']);
process.stdout.write('Student assignment-behavior parity fixtures passed.\n');
