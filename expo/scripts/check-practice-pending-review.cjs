const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

function compiled(relative, requireModule = require) {
  const source = fs.readFileSync(path.join(__dirname, '../src/services', relative), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const moduleRef = { exports: {} };
  new Function('module', 'exports', 'require', code)(moduleRef, moduleRef.exports, requireModule);
  return moduleRef.exports;
}
const progress = compiled('student-practice-progress.ts');
const normalization = compiled('student-practice-answer-normalization.ts');
const practice = compiled('student-practice.ts', (name) => {
  if (name.endsWith('/student-practice-progress')) return progress;
  if (name.endsWith('/student-practice-answer-normalization')) return normalization;
  return {};
});
const material = (teacherId) => ({ title: 'Names', sourceType: 'exam', sourceId: '7', assignmentId: teacherId ? '42' : undefined, teacherId,
  subject: 'English', topic: 'Introductions', stage: 'secondary', level: 'A2', raw: {}, questions: [
    { prompt: 'Choose true', options: ['True', 'False'], answer: 'True', exerciseIndex: 0, questionIndex: 0, exerciseType: 'true_false', sectionTitle: '', instructions: '', sourceText: '' },
    { prompt: 'Who is he?', options: [], answer: 'His name is Alex', acceptedAnswers: ['Alex is his name'], exerciseIndex: 1, questionIndex: 0, exerciseType: 'short_answer', sectionTitle: '', instructions: '', sourceText: '' },
  ] });
const exact = practice.gradePractice(material('teacher'), { 0: 'True', 1: 'His name is Alex.' });
assert.equal(exact.evaluationStatus, 'final');
assert.equal(exact.correct, 2);
assert.equal(exact.pendingCount, 0);
const variant = practice.gradePractice(material('teacher'), { 0: 'True', 1: 'Alex is his name' });
assert.equal(variant.evaluationStatus, 'final');
assert.equal(variant.correct, 2);
const alternate = practice.gradePractice(material('teacher'), { 0: 'True', 1: 'He is Alex' });
assert.equal(alternate.evaluationStatus, 'pending_teacher');
assert.equal(alternate.pendingCount, 1);
assert.equal(alternate.evaluatedCount, 1);
assert.equal(alternate.score, 0);
assert.equal(alternate.rows[1].evaluationStatus, 'pending_review');
assert.deepEqual(progress.aggregatePracticeProgress(alternate.rows, alternate.xp).map((row) => row.exerciseType), ['true_false']);
const independent = practice.gradePractice(material(undefined), { 0: 'True', 1: 'His name is not Alex' });
assert.equal(independent.evaluationStatus, 'unassessed');
assert.equal(independent.rows[1].evaluationStatus, 'unassessed');
assert.equal(independent.correct, 1);
const closedWrong = practice.gradePractice(material('teacher'), { 0: 'False', 1: 'His name is Alex' });
assert.equal(closedWrong.rows[0].evaluationStatus, 'auto_incorrect');
assert.equal(closedWrong.pendingCount, 0);
const vocabulary = { ...material(undefined), questions: [{ prompt: 'Translate casa', options: [], answer: 'house', exerciseIndex: 0, questionIndex: 0, exerciseType: 'vocabulary', sectionTitle: '', instructions: '', sourceText: '' }] };
assert.equal(practice.gradePractice(vocabulary, { 0: 'home' }).rows[0].evaluationStatus, 'unassessed');
const correction = { ...material('teacher'), questions: [{ prompt: 'Correct the sentence', options: [], answer: 'He is Alex', acceptedAnswers: ['Alex is here'], exerciseIndex: 0, questionIndex: 0, exerciseType: 'error_correction', sectionTitle: '', instructions: '', sourceText: '' }] };
assert.equal(practice.gradePractice(correction, { 0: 'Alex is here.' }).evaluationStatus, 'final');
const wordSearch = { ...material('teacher'), questions: [
  { prompt: 'Find the words', options: [], answer: '["APPLE","PEAR","PLUM"]', words: ['APPLE', 'PEAR', 'PLUM'], placements: [{ word: 'APPLE' }, { word: 'PEAR' }, { word: 'PLUM' }], exerciseIndex: 0, questionIndex: 0, exerciseType: 'word_search_vocab', sectionTitle: '', instructions: '', sourceText: '' },
  material('teacher').questions[1],
] };
const weighted = practice.gradePractice(wordSearch, { 0: '["APPLE","PEAR"]', 1: 'He is Alex' });
assert.equal(weighted.total, 4);
assert.equal(weighted.correct, 2);
assert.equal(weighted.rows[0].totalCount, 3);
assert.equal(weighted.rows[0].correctCount, 2);
assert.equal(weighted.evaluationStatus, 'pending_teacher');
console.log('Practice answer-key match and pending-review boundaries: OK');
