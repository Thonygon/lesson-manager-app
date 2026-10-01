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
const { buildStudentProgramSignals } = loadSource('src/services/student-recommendation-programs.ts', {
  '@/lib/subjects': subjects,
});
const workspace = {
  programs: [
    { id: 1, program_id: 10, teacher_id: 'teacher-a', updated_at: '2026-09-26', program: { subject: 'English', sequence_order: 1 } },
    { id: 2, program_id: 20, teacher_id: 'teacher-a', updated_at: '2026-09-25', program: { subject: 'English', level_or_band: 'A2', sequence_order: 2 } },
    { id: 3, program_id: 30, teacher_id: 'teacher-b', updated_at: '2026-09-24', program: { subject: 'English', learner_stage: 'upper_primary', sequence_order: 1 } },
    { id: 4, program_id: 40, teacher_id: 'teacher-c', program: { subject: 'General' } },
    { id: 5, program_id: 50, teacher_id: 'teacher-d', program: { subject: '' } },
  ],
  topics: [
    { id: 11, program_id: 10, unit_number: 1, topic_number: 1, title: 'Old sequence' },
    { id: 21, program_id: 20, unit_number: 1, topic_number: 1, title: 'Fractions', student_summary: 'Numerator basics' },
    { id: 22, program_id: 20, unit_number: 1, topic_number: 2, title: 'Pending decimals' },
    { id: 23, program_id: 20, unit_number: 1, topic_number: 3, title: 'Completed ratios' },
    { id: 24, program_id: 20, unit_number: 2, topic_number: 1, title: 'Percent practice', suggested_worksheet_types: ['gap_fill'], suggested_exam_exercise_types: ['short_answer'] },
    { id: 31, program_id: 30, unit_number: 1, topic_number: 1, title: 'Grammar review' },
    { id: 41, program_id: 40, unit_number: 1, topic_number: 1, title: 'General study' },
  ],
  progress: [
    { assignment_id: 2, topic_id: 21, teacher_done: true, student_done: true },
    { assignment_id: 2, topic_id: 23, teacher_done: true, student_done: false },
  ],
};
const signals = buildStudentProgramSignals(workspace);
assert.deepEqual([...signals.subjects].sort(), ['english', 'general']);
assert.equal(signals.subjectLevels.english, 'A2');
assert.equal(signals.subjectStages.english, 'upper_primary');
assert.deepEqual([...signals.activeTopicIds].sort(), [22, 24, 31, 41]);
assert.deepEqual([...signals.pendingTopicIds], [22]);
assert.deepEqual([...signals.reviewTopicIds], [21]);
assert.deepEqual([...signals.nextTopicIds].sort(), [22, 31, 41]);
assert.ok(signals.pendingTopicTokens.has('decimals'));
assert.ok(signals.reviewTopicTokens.has('numerator'));
assert.ok(signals.topicTokens.has('percent'));
assert.deepEqual([...signals.worksheetTypes], ['gap_fill']);
assert.deepEqual([...signals.examTypes], ['short_answer']);
assert.deepEqual(signals.programScopes.english.map((scope) => scope.learningProgramAssignmentId), [2, 3]);
assert.equal(signals.programScopes.english[0].topics[1].position, 2);
process.stdout.write('Student program-signal parity fixtures passed.\n');
