const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

function load(relative, dependencies = {}) {
  const source = fs.readFileSync(path.join(__dirname, relative), 'utf8');
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const module = { exports: {} };
  new Function('module', 'exports', 'require', js)(module, module.exports, (name) => dependencies[name]);
  return module.exports;
}

const subjects = load('../src/lib/subjects.ts');
const redaction = load('../src/server/ai-privacy-redaction.ts');
const { summarizeMatchedGrades, gradeEvidencePrompt, loadMatchedGradeEvidence } = load('../src/server/student-generation-evidence.ts', { '../lib/subjects': subjects, './ai-privacy-redaction': redaction });
const rows = [
  { id: 1, subject_key: 'mathematics', topic: 'Adding fractions', title: 'Fraction vocabulary for Ana García', learning_program_topic_id: 42, assignment_type: 'worksheet', status: 'graded', score_pct: 55 },
  { id: 2, subject_key: 'math', topic: 'Adding unlike fractions', title: 'Adding unlike fractions exam', assignment_type: 'exam', status: 'completed', score_pct: 75 },
  { id: 3, subject_key: 'english', topic: 'Adding fractions', assignment_type: 'exam', status: 'graded', score_pct: 100 },
  { id: 4, subject_key: 'mathematics', topic: 'Long division', assignment_type: 'exam', status: 'graded', score_pct: 10 },
  { id: 5, subject_key: 'mathematics', topic: 'Adding fractions', assignment_type: 'exam', status: 'assigned', score_pct: 20 },
  { id: 6, subject_key: 'mathematics', topic: 'Adding fractions', assignment_type: 'exam', status: 'graded', score_pct: null },
  { id: 7, subject_key: 'mathematics', topic: 'Adding fractions', assignment_type: 'video', status: 'completed', score_pct: 100 },
];
const attempts = [
  { assignment_id: 1, submission_payload: { result: { rows: [
    { exerciseType: 'fill_in_blank', correctCount: 0, totalCount: 1, studentAnswer: 'Ana García' },
    { exerciseType: 'fill_in_blank', correctCount: 0, totalCount: 1, answer: '+34 612 345 678' },
    { exerciseType: 'multiple_choice', correctCount: 1, totalCount: 1 },
  ] } } },
  { assignment_id: 2, submission_payload: { result: { rows: [{ exerciseType: 'multiple_choice', correctCount: 1, totalCount: 1 }] } } },
  { assignment_id: 4, submission_payload: { result: { rows: [{ exerciseType: 'fill_in_blank', correctCount: 1, totalCount: 1 }] } } },
];
const summary = summarizeMatchedGrades(rows, 'Matemáticas', 'Adding fractions', 42, attempts);
assert.equal(summary.count, 2);
assert.equal(summary.scope, 'topic');
assert.equal(summary.average, 65);
assert.equal(summary.latest, 55);
assert.deepEqual(summary.resources.map((row) => [row.title, row.topic, row.score]), [['Fraction vocabulary for Ana García', 'Adding fractions', 55], ['Adding unlike fractions exam', 'Adding unlike fractions', 75]]);
assert.deepEqual(summary.exercises, [{ type: 'fill_in_blank', correct: 0, total: 2 }, { type: 'multiple_choice', correct: 2, total: 2 }]);
assert.equal(summarizeMatchedGrades(rows, 'science', 'Adding fractions'), null);
const programSummary = summarizeMatchedGrades(rows, 'mathematics', '');
assert.equal(programSummary.scope, 'subject');
assert.equal(programSummary.count, 3);
assert.match(gradeEvidencePrompt(programSummary), /matching subject:/);
assert.equal(summarizeMatchedGrades([{ subject_key: 'other', subject_label: 'Robotics', topic: 'Sensors and circuits', assignment_type: 'exam', status: 'graded', score_pct: 81 }], 'Robotics', 'Sensors and circuits').average, 81);
const prompt = gradeEvidencePrompt(summary, 'Ana García');
assert.match(prompt, /Fraction vocabulary/);
assert.match(prompt, /Adding fractions/);
assert.match(prompt, /fill in blank: 0\/2 correct/);
assert.match(prompt, /mean 65%/);
for (const personal of ['Ana García', '+34 612 345 678', 'Long division']) assert.ok(!prompt.includes(personal), personal);
assert.match(prompt, /\[student name removed\]/);

(async () => {
  const teacherId = '11111111-1111-4111-8111-111111111111';
  const studentId = '22222222-2222-4222-8222-222222222222';
  let calls = 0;
  const fetcher = async (url, options) => {
    calls += 1;
    assert.equal(url.searchParams.get('teacher_id'), `eq.${teacherId}`);
    assert.equal(url.searchParams.get('student_id'), `eq.${studentId}`);
    assert.equal(options.headers.Authorization, 'Bearer teacher-token');
    if (url.pathname.endsWith('/teacher_assignments')) {
      assert.equal(url.searchParams.get('limit'), '120');
      assert.equal(url.searchParams.get('assignment_type'), 'in.(worksheet,exam)');
      assert.equal(url.searchParams.get('order'), 'updated_at.desc');
      assert.match(url.searchParams.get('select'), /title/);
      return { ok: true, json: async () => rows };
    }
    assert.equal(url.pathname, '/rest/v1/teacher_assignment_attempts');
    assert.equal(url.searchParams.get('assignment_id'), 'in.(1,2)');
    assert.equal(url.searchParams.get('limit'), '30');
    return { ok: true, json: async () => attempts };
  };
  const loaded = await loadMatchedGradeEvidence('https://example.test', 'anon-key', 'teacher-token', teacherId, studentId, 'math', 'Adding fractions', 42, fetcher);
  assert.deepEqual(loaded, summary);
  assert.equal(calls, 2);
  await assert.rejects(loadMatchedGradeEvidence('https://example.test', 'anon-key', 'teacher-token', teacherId, 'invalid', 'math', 'Adding fractions', 42, fetcher));
  assert.equal(calls, 2);
  await assert.rejects(loadMatchedGradeEvidence('https://example.test', 'anon-key', 'teacher-token', teacherId, studentId, 'math', 'Adding fractions', 42, async () => ({ ok: false })));
  process.stdout.write('Student generation resource and exercise evidence fixtures passed.\n');
})().catch((error) => { console.error(error); process.exitCode = 1; });
