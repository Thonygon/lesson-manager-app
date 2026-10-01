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
const { buildStudentNeedProfile, fitStudentNeedWeights } = loadSource('src/services/student-recommendation-need.ts', {
  '@/lib/subjects': subjects,
});
const now = Date.parse('2026-09-26T00:00:00Z');
const rows = [
  { subject: 'english', topic: 'Fractions', exercise_type: 'multiple_choice', accuracy_pct: 50, total_attempted: 4, last_practiced: '2026-09-20T00:00:00+00:00', level: 'A1', learner_stage: 'early_primary' },
  { subject: 'english', topic: 'Fractions', exercise_type: 'short_answer', accuracy_pct: 90, total_attempted: 2, last_practiced: '2026-09-25T00:00:00+00:00', level: 'A2', learner_stage: 'upper_primary' },
];

// Expected weights are from Streamlit's _fit_need_weights on these rows with the same frozen clock.
const pythonWeights = [-1.5086316731394416, 3.795406245834025, 1.2095069766217488, 1.510657866373675];
fitStudentNeedWeights(rows, now).forEach((value, index) => assert.ok(Math.abs(value - pythonWeights[index]) < 1e-10));
assert.deepEqual(fitStudentNeedWeights([], now), [-0.1, 2.2, 0.7, 0.9]);

const profile = buildStudentNeedProfile(rows, ['English'], '', now);
assert.equal(profile.subjectAttempts.english, 6);
assert.ok(Math.abs(profile.overallAccuracy.english - (3.8 / 6)) < 1e-12);
assert.equal(profile.subjectLevel.english, 'A1');
assert.equal(profile.subjectStage.english, 'early_primary');
assert.ok(profile.topicNeed.fractions > 0 && profile.topicNeed.fractions < 1);
assert.ok(profile.exerciseNeed.multiple_choice > 0);
assert.ok(profile.exerciseNeed.short_answer > 0);
assert.deepEqual(profile.primarySubjects, ['english']);
process.stdout.write('Student need-profile parity fixtures passed.\n');
