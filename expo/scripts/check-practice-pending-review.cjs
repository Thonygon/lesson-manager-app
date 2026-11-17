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
  if (name.endsWith('/public-data')) return { extractResourceImageUrl: () => '' };
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
const artwork = `data:image/png;base64,${'A'.repeat(1_060_000)}`;
const illustrated = { ...material('teacher'), questions: Array.from({ length: 9 }, (_, index) => ({
  prompt: `Question ${index + 1}`, options: [], answer: 'His name is Alex',
  exerciseIndex: 0, questionIndex: index, exerciseType: 'reading_comprehension',
  sectionTitle: 'Reading', instructions: 'Read and answer', sourceText: 'Alex is a learner.', visualSupportUrl: artwork,
})) };
const illustratedGrade = practice.gradePractice(illustrated, Object.fromEntries(illustrated.questions.map((_, index) => [String(index), 'His name is Alex'])));
const compact = practice.compactPracticeGrade(illustratedGrade);
assert.ok(JSON.stringify(illustratedGrade).length > 9_000_000);
assert.ok(JSON.stringify(compact).length < 20_000);
assert.equal(compact.rows.length, 9);
assert.equal(compact.rows[0].exerciseType, 'reading_comprehension');
assert.equal(compact.rows[0].correctCount, 1);
assert.ok(practice.exerciseDataForMaterial(illustrated).exercises[0].visual_support.image_url === artwork);
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
const reading = { ...material('teacher'), questions: [{ prompt: '¿A qué hora se levanta Elena?', options: [], answer: 'A las siete de la mañana', exerciseIndex: 0, questionIndex: 0, exerciseType: 'short_answer', sectionTitle: '', instructions: '', sourceText: '' }] };
assert.equal(practice.gradePractice(reading, { 0: 'Elena se levanta a las siete de la mañana.' }).evaluationStatus, 'final');
assert.equal(practice.gradePractice(reading, { 0: 'Elena no se levanta a las siete de la mañana.' }).evaluationStatus, 'pending_teacher');
assert.equal(practice.gradePractice(reading, { 0: 'Elena se levanta a las ocho, pero también a las siete de la mañana.' }).evaluationStatus, 'pending_teacher');
assert.equal(practice.gradePractice(reading, { 0: 'Elena se levanta.' }).evaluationStatus, 'pending_teacher');
assert.equal(practice.gradePractice(reading, { 0: 'A las siete de la mañana is wrong.' }).evaluationStatus, 'pending_teacher');
const weeklyRoutine = { ...material('teacher'), questions: [
  { prompt: '¿A qué hora se levanta Elena de lunes a viernes?', options: [], answer: 'Elena se levanta a las siete de la mañana de lunes a viernes.', exerciseIndex: 0, questionIndex: 0, exerciseType: 'short_answer', sectionTitle: '', instructions: '', sourceText: '' },
  { prompt: '¿Qué hace Elena después de trabajar por la tarde?', options: [], answer: 'Después de trabajar por la tarde, Elena va al gimnasio o estudia español.', exerciseIndex: 0, questionIndex: 1, exerciseType: 'short_answer', sectionTitle: '', instructions: '', sourceText: '' },
] };
const weeklyGrade = practice.gradePractice(weeklyRoutine, { 0: 'Elena se levanta a las siete de la mañana.', 1: 'Elena va al gimnasio o estudia español.' });
assert.equal(weeklyGrade.evaluationStatus, 'final');
assert.equal(weeklyGrade.correct, 2);
assert.equal(practice.gradePractice(weeklyRoutine, { 0: 'Elena se levanta a las siete de la mañana.', 1: 'Elena va al gimnasio o estudia español.' }, { allowExpandedModelMatch: false }).evaluationStatus, 'pending_teacher');
const correctedMixed = { ...weeklyRoutine, questions: [...weeklyRoutine.questions, { prompt: 'True or false?', options: ['True', 'False'], answer: 'False', exerciseIndex: 1, questionIndex: 0, exerciseType: 'true_false', sectionTitle: '', instructions: '', sourceText: '' }] };
const priorVerdict = (question, studentAnswer, isCorrect) => ({ studentAnswer, correctAnswer: question.answer, exerciseType: question.exerciseType, acceptedAnswers: question.acceptedAnswers || [], prompt: question.prompt, sourceText: question.sourceText, instructions: question.instructions, isCorrect });
const savedOpen = {
  '0:0': priorVerdict(weeklyRoutine.questions[0], 'Elena se levanta a las siete de la mañana.', true),
  '0:1': priorVerdict(weeklyRoutine.questions[1], 'Elena va al gimnasio o estudia español.', true),
};
const historical = practice.gradePractice(correctedMixed, { 0: 'Elena se levanta a las siete de la mañana.', 1: 'Elena va al gimnasio o estudia español.', 2: 'True' }, {
  allowExpandedModelMatch: false,
  preserveFinalVerdicts: savedOpen,
});
assert.equal(historical.evaluationStatus, 'final');
assert.equal(historical.correct, 2);
assert.equal(historical.rows[2].evaluationStatus, 'auto_incorrect');
const changedPrompt = { ...weeklyRoutine, questions: [{ ...weeklyRoutine.questions[0], prompt: '¿Cuándo se levanta Elena?' }, weeklyRoutine.questions[1]] };
assert.equal(practice.gradePractice(changedPrompt, { 0: 'Elena se levanta a las siete de la mañana.', 1: 'Elena va al gimnasio o estudia español.' }, { allowExpandedModelMatch: false, preserveFinalVerdicts: savedOpen }).evaluationStatus, 'pending_teacher');
const unchangedWrong = practice.gradePractice(weeklyRoutine, { 0: 'Elena se levanta a las siete de la mañana.', 1: 'Elena va al gimnasio o estudia español.' }, {
  allowExpandedModelMatch: false,
  preserveFinalVerdicts: { ...savedOpen, '0:0': { ...savedOpen['0:0'], isCorrect: false } },
});
assert.equal(unchangedWrong.evaluationStatus, 'final');
assert.equal(unchangedWrong.correct, 1);
assert.equal(practice.gradePractice(weeklyRoutine, { 0: 'Elena no se levanta a las siete de la mañana.', 1: 'Elena va al gimnasio o estudia español.' }).evaluationStatus, 'pending_teacher');
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
const oldAssignedSnapshot = practice.exerciseDataForMaterial({ ...wordSearch, teacherId: undefined });
const replay = practice.materialFromSession({ id: 643, source_type: 'worksheet', source_id: '624', title: 'Furniture', exercise_data: oldAssignedSnapshot });
assert.equal(replay.assignmentId, '42');
assert.equal(replay.teacherId, undefined);
const recentReplay = practice.materialFromSession({ id: 644, source_type: 'worksheet', source_id: '624', title: 'Furniture', exercise_data: practice.exerciseDataForMaterial(wordSearch) });
assert.equal(recentReplay.teacherId, 'teacher');
let lookedUpAssignment = '';
const assignmentClient = { from(table) {
  assert.equal(table, 'teacher_assignments');
  return { select(column) { assert.equal(column, 'teacher_id'); return { eq(key, id) { assert.equal(key, 'id'); lookedUpAssignment = id; return { maybeSingle: async () => ({ data: { teacher_id: 'authoritative-teacher' }, error: null }) }; } }; } };
} };
let completionPayload;
const completionClient = {
  auth: { getUser: async () => ({ data: { user: { id: 'learner' } } }) },
  rpc: async (name, args) => { assert.equal(name, 'classio_complete_student_practice'); completionPayload = args.p_result; return { data: 671, error: null }; },
  from: (name) => { assert.equal(name, 'practice_sessions'); return { select: () => { const query = { eq: () => query, single: async () => ({ data: { id: 671, status: 'completed', total_questions: 9, correct_count: 9, score_pct: 100, xp_earned: 69, best_streak: 9, evaluated_count: 9, pending_count: 0, evaluation_status: 'final' }, error: null }) }; return query; } }; },
};
const practiceWithClient = compiled('student-practice.ts', (name) => {
  if (name.endsWith('/student-practice-progress')) return progress;
  if (name.endsWith('/student-practice-answer-normalization')) return normalization;
  if (name.endsWith('/public-data')) return { extractResourceImageUrl: () => '' };
  if (name.endsWith('/lib/supabase')) return { requireSupabase: () => completionClient };
  return {};
});
practice.teacherIdForPractice(replay, assignmentClient).then(async (teacherId) => {
  assert.equal(lookedUpAssignment, '42');
  assert.equal(teacherId, 'authoritative-teacher');
  await practiceWithClient.savePractice({ ...illustrated, assignmentId: undefined, teacherId: undefined }, Object.fromEntries(illustrated.questions.map((_, index) => [String(index), 'His name is Alex'])), '671');
  assert.equal(completionPayload.exercise_data, undefined);
  assert.ok(JSON.stringify(completionPayload).length < 30_000);
  assert.equal(completionPayload.graded.rows.length, 9);
  console.log('Practice answer-key match, retry owner recovery, and pending-review boundaries: OK');
}).catch((error) => { console.error(error); process.exitCode = 1; });
