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
const { buildStudentAssignmentSignals, resourceAssignmentKey } = loadSource('src/services/student-recommendation-assignments.ts', {
  '@/services/student-recommendation-programs': programs,
});
const signals = buildStudentAssignmentSignals([
  { id: 1, teacher_id: 't1', assignment_type: 'worksheet', source_record_id: 10, status: 'completed', topic: 'Fraction basics' },
  { id: 2, teacher_id: 't1', assignment_type: 'worksheet', source_record_id: 10, status: 'assigned', topic: 'Fraction practice', learning_program_assignment_id: 8, learning_program_topic_id: 9 },
  { id: 3, teacher_id: 't1', assignment_type: 'video', source_record_id: 11, status: 'assigned', title: 'Ratio introduction' },
  { id: 4, teacher_id: 't1', assignment_type: 'video', source_record_id: 12, status: 'assigned', attempt_count: 1, title: 'Seen video' },
  { id: 5, teacher_id: 't1', assignment_type: 'exam', source_record_id: 0, status: 'assigned', title: 'Ignore' },
], { t1: 'Teacher One' });
assert.equal(signals.resourceAssignments.size, 3);
assert.equal(signals.resourceAssignments.get(resourceAssignmentKey('worksheet', 10)).assignmentId, 2);
assert.equal(signals.resourceAssignments.get(resourceAssignmentKey('worksheet', 10)).teacherName, 'Teacher One');
assert.equal(signals.resourceAssignments.get(resourceAssignmentKey('worksheet', 10)).learningProgramTopicId, 9);
assert.equal(signals.resourceAssignments.get(resourceAssignmentKey('video', 11)).isUnseen, true);
assert.equal(signals.resourceAssignments.get(resourceAssignmentKey('video', 12)).isCompleted, true);
assert.ok(signals.activeAssignedTopicTokens.has('fraction'));
assert.ok(signals.unseenVideoTopicTokens.has('ratio'));
assert.ok(!signals.unseenVideoTopicTokens.has('seen'));
process.stdout.write('Student assignment-signal parity fixtures passed.\n');
