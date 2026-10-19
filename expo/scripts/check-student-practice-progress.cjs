const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/student-practice-progress.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleRef = { exports: {} };
new Function('module', 'exports', compiled)(moduleRef, moduleRef.exports);
const { aggregatePracticeProgress, practiceAccuracyPct, practiceSessionScorePct } = moduleRef.exports;

assert.deepEqual(aggregatePracticeProgress([
  { exerciseType: 'word_search_vocab', isCorrect: false },
  { exerciseType: 'multiple_choice', isCorrect: true },
  { exerciseType: 'multiple_choice', isCorrect: false },
], 15), [
  { exerciseType: 'word_search_vocab', attempted: 1, correct: 0, xp: 0 },
  { exerciseType: 'multiple_choice', attempted: 2, correct: 1, xp: 15 },
]);
assert.deepEqual(aggregatePracticeProgress([
  { exerciseType: 'matching', isCorrect: false },
  { exerciseType: 'writing_prompt', isCorrect: false },
], 5).map((row) => row.xp), [2, 2]);
assert.deepEqual(aggregatePracticeProgress([], 10), []);
assert.equal(practiceAccuracyPct(1, 8), 12.5);
assert.equal(practiceAccuracyPct(0, 0), 0);
assert.equal(practiceSessionScorePct(1, 8), 12);
assert.equal(practiceSessionScorePct(3, 8), 38);
assert.equal(practiceSessionScorePct(2, 3), 67);
assert.equal(practiceSessionScorePct(0, 0), 0);
const normalizationSource = fs.readFileSync(path.join(__dirname, '../src/services/student-practice-answer-normalization.ts'), 'utf8');
const normalizationModule = { exports: {} };
new Function('module', 'exports', ts.transpileModule(normalizationSource, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText)(normalizationModule, normalizationModule.exports);
const { normalizePracticeAnswer } = normalizationModule.exports;
assert.equal(normalizePracticeAnswer('“Café” — résumé'), 'cafe - resume');
assert.equal(normalizePracticeAnswer('l’école'), "l'ecole");
assert.equal(normalizePracticeAnswer('A_B'), 'a_b');
process.stdout.write('Student practice progress parity fixtures passed.\n');
