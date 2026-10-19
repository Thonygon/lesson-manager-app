const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/teacher-objective-recommendations.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleRef = { exports: {} };
let mockClient;
new Function('module', 'exports', 'require', compiled)(moduleRef, moduleRef.exports, (name) => {
  if (name === '@/lib/subjects') return { canonicalSubjectKey: (value) => String(value).toLowerCase(), canonicalSubjectLabel: (value) => String(value) };
  if (name === '@/lib/learning-program-topics') return { programTopics: (_program, rows) => rows };
  if (name === '@/lib/supabase') return { requireSupabase: () => mockClient };
  throw new Error(`Unexpected import: ${name}`);
});
const { buildTeacherObjectiveRecommendations } = moduleRef.exports;

const workspace = {
  assignments: [{ id: 10, subject_key: 'English', title: 'Food preferences', topic: 'Food preferences', status: 'completed', score_pct: 45, assignment_type: 'worksheet' }],
  attempts: [{ id: 11, assignment_id: 10, score_pct: 45, attempt_number: 2, created_at: new Date().toISOString() }], reviews: [],
  programs: [{ id: 20, program_id: 30, status: 'active', program: { id: 30, subject: 'English', title: 'English A2' } }],
  topics: [
    { id: 1, program_id: 30, unit_number: 1, topic_number: 1, title: 'Food preferences' },
    { id: 2, program_id: 30, unit_number: 1, topic_number: 2, title: 'At a restaurant' },
  ],
  progress: [{ assignment_id: 20, topic_id: 1, teacher_done: true, student_done: true }],
  recommendationEvents: [],
};
const result = buildTeacherObjectiveRecommendations(workspace);
assert.equal(result.length, 2);
assert.equal(result[0].bucket, 'review', 'a request for more practice is the first teacher action');
assert.equal(result[0].focus, 'needs_practice');
assert.equal(result[0].recentScore, 45);
assert.equal(result[1].bucket, 'next_topic');
assert.equal(result[1].topicId, 2);
const fallback = buildTeacherObjectiveRecommendations({ ...workspace, programs: [], topics: [], progress: [] });
assert.equal(fallback[0].bucket, 'assignment');
assert.equal(fallback[0].recentScore, 45);
const resolved = buildTeacherObjectiveRecommendations({ ...workspace, recommendationEvents: [{ learning_program_assignment_id: 20, learning_program_topic_id: 1, recommendation_bucket: 'review', event_type: 'teacher_marked_done', metadata: { resolved_low_score_signature: 'assignment_attempt:10:11' } }] });
assert.equal(resolved.some((item) => item.bucket === 'review'), true, 'a direct request for practice remains actionable after a score is resolved');
assert.equal(resolved.find((item) => item.bucket === 'review').recentScore, null, 'resolved low scores do not remain a new low-score signal');
const calls = [];
const fixtures = {
  learning_program_assignments: [{ id: 20, program_id: 30, student_user_id: 'student-1', status: 'assigned', updated_at: new Date().toISOString() }],
  teacher_assignments: [{ ...workspace.assignments[0], student_id: 'student-1', created_at: new Date().toISOString() }],
  teacher_assignment_attempts: workspace.attempts,
  learning_program_recommendation_events: [],
  learning_programs: [{ id: 30, subject: 'English', title: 'English A2', program_data: {} }],
  learning_program_topics: workspace.topics,
  learning_program_progress: workspace.progress,
};
mockClient = {
  auth: { getUser: async () => ({ data: { user: { id: 'teacher-1' } }, error: null }) },
  from(table) {
    calls.push({ table, filters: [] });
    const call = calls[calls.length - 1];
    const query = { select: () => query, eq: (key, value) => { call.filters.push([key, value]); return query; }, neq: () => query, gte: () => query, order: () => query, limit: () => query, in: () => query, then: (resolve, reject) => Promise.resolve({ data: fixtures[table], error: null }).then(resolve, reject) };
    return query;
  },
};
(async () => {
  const model = await moduleRef.exports.loadTeacherObjectiveModel();
  assert.equal(model.bias, -0.18, 'small samples use the same Python base weights');
  assert.deepEqual(calls.map((call) => call.table), ['learning_program_assignments', 'teacher_assignments', 'teacher_assignment_attempts', 'learning_program_recommendation_events', 'learning_programs', 'learning_program_topics', 'learning_program_progress']);
  assert.ok(calls.slice(0, 4).every((call) => call.filters.some(([key, value]) => key === 'teacher_id' && value === 'teacher-1')), 'teacher-wide training reads remain teacher scoped');
  await moduleRef.exports.loadTeacherObjectiveModel();
  assert.equal(calls.length, 7, 'the ten-minute cache prevents repeated training reads');
  process.stdout.write('Teacher objective recommendation fixture passed.\n');
})().catch((error) => { console.error(error); process.exitCode = 1; });
