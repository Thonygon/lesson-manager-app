const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

function load(relativePath, aliases = {}) {
  const source = fs.readFileSync(path.join(__dirname, '..', relativePath), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const module = { exports: {} };
  new Function('module', 'exports', 'require', compiled)(module, module.exports, (name) => aliases[name] || require(name));
  return module.exports;
}

const subjects = load('src/lib/subjects.ts');
const programs = load('src/services/student-recommendation-programs.ts', { '@/lib/subjects': subjects });
const assignments = load('src/services/student-recommendation-assignments.ts', { '@/services/student-recommendation-programs': programs });
const { selectStudentRecommendationSubjects: select, resolveStudentRecommendationScopes: resolveScopes } = load('src/services/student-recommendation-selection.ts', {
  '@/lib/subjects': subjects, '@/services/student-recommendation-programs': programs,
  '@/services/student-recommendation-assignments': assignments,
  '@/services/student-recommendation-ranking': { scopeAdjustedStudentRecommendationScore: (_row, score, scope) => score + (scope.learningProgramAssignmentId === 11 ? 0.2 : 0.1) },
});
const { selectScoredStudentRecommendations: selectScored } = load('src/services/student-recommendation-selection.ts', {
  '@/lib/subjects': subjects, '@/services/student-recommendation-programs': programs,
  '@/services/student-recommendation-assignments': assignments,
  '@/services/student-recommendation-ranking': { scopeAdjustedStudentRecommendationScore: (_row, score, scope) => score + (scope.learningProgramAssignmentId === 11 ? 0.2 : 0.1) },
});
const rows = Array.from({ length: 7 }, (_, index) => ({ kind: 'worksheet', subject: 'english', id: index + 1 })).concat([{ kind: 'worksheet', subject: 'spanish', id: 8 }]);
const workspace = { programs: [
  { id: 1, program_id: 1, teacher_id: 'a', program: { subject: 'english' } },
  { id: 2, program_id: 2, teacher_id: 'b', program: { subject: 'spanish' } },
], topics: [], progress: [], assignments: [] };
assert.deepEqual(select(rows, null).map((row) => row.id), [1, 2, 3, 4, 5, 6]);
assert.deepEqual(select(rows, workspace).map((row) => row.id), [1, 2, 3, 4, 5, 8]);
assert.deepEqual(select(rows.slice(0, 2), workspace).map((row) => row.id), [1, 2]);
const scopedWorkspace = { programs: [
  { id: 11, program_id: 11, teacher_id: 'teacher-a', program: { subject: 'english' } },
  { id: 12, program_id: 12, teacher_id: 'teacher-b', program: { subject: 'english' } },
], topics: [
  { id: 101, program_id: 11, title: 'Algebra equations', unit_number: 1, topic_number: 1 },
  { id: 102, program_id: 12, title: 'Grammar verbs', unit_number: 1, topic_number: 1 },
], progress: [], assignments: [] };
const scopedRows = [
  { id: 1, kind: 'worksheet', subject: 'english', title: 'General review', topic: '' },
  { id: 2, kind: 'worksheet', subject: 'english', title: 'Grammar verbs practice', topic: 'Grammar verbs' },
  { id: 3, kind: 'worksheet', subject: 'english', title: 'Algebra equations practice', topic: 'Algebra equations' },
  { id: 4, kind: 'worksheet', subject: 'english', title: 'Extra review', topic: '' },
];
assert.deepEqual(select(scopedRows, scopedWorkspace, 2).map((row) => row.id), [2, 3]);
assert.deepEqual(select(scopedRows, scopedWorkspace, 2).map((row) => [row.learningProgramAssignmentId, row.learningProgramTopicId]), [[12, 102], [11, 101]]);
assert.deepEqual(select(scopedRows, scopedWorkspace, 3).map((row) => row.id), [1, 2, 3]);
assert.equal(new Set(select(scopedRows, scopedWorkspace, 3).map((row) => row.id)).size, 3);
const scopes = programs.buildStudentProgramSignals(scopedWorkspace).programScopes.english;
assert.deepEqual(resolveScopes(scopedRows[1], scopes, { learningProgramAssignmentId: 99, learningProgramTopicId: 88 }), [
  { learningProgramAssignmentId: 99, learningProgramTopicId: 88, programId: 0, programTeacherId: '' },
]);
const pinnedWorkspace = { ...scopedWorkspace, assignments: [{
  id: 50, assignment_type: 'worksheet', source_record_id: 2, status: 'assigned',
  learning_program_assignment_id: 11, learning_program_topic_id: 101,
}] };
assert.equal(select([scopedRows[1]], pinnedWorkspace, 2)[0].learningProgramAssignmentId, 11);
const shared = select([scopedRows[0]], scopedWorkspace, 2);
assert.deepEqual(shared.map((row) => row.id), [1, 1]);
assert.deepEqual(shared.map((row) => row.learningProgramAssignmentId), [11, 12]);
assert.deepEqual(shared.map((row) => row.learningProgramTopicId), [101, 102]);
assert.equal(select([scopedRows[1]], pinnedWorkspace, 2).length, 1);
const full = (row) => ({ ...row, id: String(row.id), stage: '', level: '', author: '', description: '', imageUrl: '', createdAt: '', raw: {} });
const scored = selectScored([
  { resource: full(scopedRows[0]), score: 0.9, reasons: [{ key: 'student.materialReason.revisitTopic', params: { topic: 'Review' } }, { key: 'student.materialReason.levelFit', params: { level: 'A1' } }] },
  { resource: full(scopedRows[1]), score: 0.8 },
  { resource: full(scopedRows[2]), score: 0.7 },
], scopedWorkspace, 2);
assert.deepEqual(scored.map((row) => [row.id, row.learningProgramAssignmentId]), [['1', 11], ['1', 12]]);
assert.deepEqual(scored.map((row) => row.learningProgramTopicId), [101, 102]);
assert.deepEqual(scored.map((row) => row.recommendationReason), [
  { key: 'student.materialReason.revisitTopic', params: { topic: 'Review' } },
  { key: 'student.materialReason.revisitTopic', params: { topic: 'Review' } },
]);
assert.deepEqual(scored.map((row) => row.recommendationReasons.map((reason) => reason.key)), [
  ['student.materialReason.revisitTopic', 'student.materialReason.levelFit'],
  ['student.materialReason.revisitTopic', 'student.materialReason.levelFit'],
]);
const pinnedScored = selectScored([{ resource: full(scopedRows[1]), score: 0.8 }], pinnedWorkspace, 2);
assert.deepEqual(pinnedScored.map((row) => row.learningProgramAssignmentId), [11]);
const unscopedWorkspace = { programs: [], topics: [], progress: [], assignments: [] };
const unicodeTies = selectScored([
  { resource: { ...full(scopedRows[0]), id: 'z', title: 'Zulu', topic: 'Grammar', raw: { worksheet_type: 'one' } }, score: 0.8 },
  { resource: { ...full(scopedRows[0]), id: 'a', title: 'Álgebra', topic: 'Grammar', raw: { worksheet_type: 'two' } }, score: 0.8 },
], unscopedWorkspace, 2);
assert.deepEqual(unicodeTies.map((row) => row.id), ['z', 'a']); // Python casefold/code-point sort.
const casefoldDedup = selectScored([
  { resource: { ...full(scopedRows[0]), id: 'ss', title: 'Straße', topic: 'Straße', raw: { worksheet_type: 'gap_fill' } }, score: 0.8 },
  { resource: { ...full(scopedRows[0]), id: 'ss2', title: 'Strasse', topic: 'Strasse', raw: { worksheet_type: 'gap_fill' } }, score: 0.7 },
], unscopedWorkspace, 2);
assert.deepEqual(casefoldDedup.map((row) => row.id), ['ss']);
process.stdout.write('Student recommendation assignment-scope selection fixtures passed.\n');
