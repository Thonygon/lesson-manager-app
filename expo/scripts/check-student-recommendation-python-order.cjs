const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const ts = require('typescript');

function load(relativePath, aliases = {}) {
  const source = fs.readFileSync(path.join(__dirname, '..', relativePath), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const loaded = { exports: {} };
  new Function('module', 'exports', 'require', compiled)(loaded, loaded.exports, (name) => aliases[name] || require(name));
  return loaded.exports;
}
const subjects = load('src/lib/subjects.ts');
const programs = load('src/services/student-recommendation-programs.ts', { '@/lib/subjects': subjects });
const assignments = load('src/services/student-recommendation-assignments.ts', { '@/services/student-recommendation-programs': programs });
const ranking = load('src/services/student-recommendation-ranking.ts', {
  '@/lib/subjects': subjects,
  '@/services/student-recommendation-programs': programs,
  '@/services/student-recommendation-need': {},
  '@/services/student-recommendation-assignments': assignments,
  '@/services/student-recommendation-assignment-behavior': {},
  '@/services/student-recommendation-semantic': {},
  '@/services/student-recommendation-safety': {},
  '@/services/student-recommendation-topic-alignment': {},
  '@/services/student-recommendation-ml': {},
});
const selection = load('src/services/student-recommendation-selection.ts', {
  '@/lib/subjects': subjects,
  '@/services/student-recommendation-programs': programs,
  '@/services/student-recommendation-assignments': assignments,
  '@/services/student-recommendation-ranking': ranking,
});
const workspace = {
  programs: [
    { id: 11, program_id: 101, teacher_id: 'teacher-a', program: { subject: 'english', level_or_band: 'A1' } },
    { id: 12, program_id: 102, teacher_id: 'teacher-b', program: { subject: 'english', level_or_band: 'A1' } },
  ],
  topics: [
    { id: 201, program_id: 101, unit_number: 1, topic_number: 1, title: 'Fractions' },
    { id: 202, program_id: 102, unit_number: 1, topic_number: 1, title: 'Grammar' },
  ], progress: [], assignments: [],
};
const source = [
  ['1', 'Fractions', 'Fractions practice', 0.82],
  ['2', 'Grammar', 'Grammar practice', 0.8],
  ['3', 'Review', 'General review', 0.79],
  ['4', 'Culture', 'Zulu', 0.7],
  ['5', 'Culture', 'Álgebra', 0.7],
];
const candidates = source.map(([id, topic, title, score]) => ({
  resource: { id, kind: 'worksheet', subject: 'english', topic, title, level: 'A1', stage: '', author: '', description: '', imageUrl: '', createdAt: '', raw: { worksheet_type: `type_${id}` } }, score,
}));
const signals = programs.buildStudentProgramSignals(workspace);
const programScopes = Object.fromEntries(Object.entries(signals.programScopes).map(([subject, scopes]) => [subject, scopes.map((scope) => ({
  learning_program_assignment_id: scope.learningProgramAssignmentId,
  program_id: scope.programId,
  teacher_id: scope.teacherId,
  level: scope.level,
  topics: scope.topics.map((topic) => ({ topic_id: topic.topicId, tokens: [...topic.tokens], is_complete: topic.isComplete, position: topic.position })),
}))]));
const input = {
  candidates: candidates.map(({ resource, score }) => ({ kind: resource.kind, score, row: { id: resource.id, title: resource.title, subject: resource.subject, topic: resource.topic, level_or_band: resource.level, worksheet_type: resource.raw.worksheet_type } })),
  program_scopes: programScopes,
  active_scope_keys: Object.values(programScopes).flat().map((scope) => `assignment:${scope.learning_program_assignment_id}`),
  limit: 5,
};
const python = path.join(__dirname, '../../.venv/bin/python');
const expected = JSON.parse(execFileSync(python, [path.join(__dirname, 'python-student-selection-reference.py')], { input: JSON.stringify(input), encoding: 'utf8', maxBuffer: 1024 * 1024 }));
const actual = selection.selectScoredStudentRecommendations(candidates, workspace, 5).map((row) => [row.id, row.learningProgramAssignmentId || 0, row.learningProgramTopicId || 0, row.recommendationScore]);
assert.deepEqual(actual, expected);
process.stdout.write('Student recommendation Python/Expo ordered selection fixture passed.\n');
