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

const alignment = load('src/services/student-recommendation-topic-alignment.ts');
const semantic = load('src/services/student-recommendation-semantic.ts');
const calls = [];
const events = [{ resource_kind: 'worksheet', resource_record_id: 7, learning_program_topic_id: 42, recommendation_bucket: 'next_topic', recommendation_focus_kind: 'stretch', event_type: 'student_improved', created_at: new Date().toISOString() }];
const assignments = [{ assignment_type: 'worksheet', source_record_id: 7, learning_program_topic_id: 42, score_pct: 95, status: 'completed', updated_at: new Date().toISOString() }];
const videos = [{ video_id: 9, topic_id: 42, created_at: new Date().toISOString() }];
const dataFor = { learning_program_recommendation_events: events, teacher_assignments: assignments, learning_program_topic_videos: videos };
let eventReadError = false;
const client = {
  auth: { getUser: async () => ({ data: { user: { id: 'teacher-1' } }, error: null }) },
  from(table) {
    calls.push(table);
    const query = { select: () => query, eq: () => query, not: () => query, neq: () => query, gte: () => query, order: () => query, limit: async () => ({ data: dataFor[table], error: table === 'learning_program_recommendation_events' && eventReadError ? new Error('temporary read failure') : null }) };
    return query;
  },
};
const { loadTeacherRecommendationModel, rankTeacherResources } = load('src/services/teacher-recommendations.ts', {
  '@/lib/supabase': { requireSupabase: () => client },
  '@/services/resource-library': { getResourceLibrary: async () => ({ resources: [], unavailable: [] }) },
  '@/services/student-recommendation-topic-alignment': alignment,
  '@/services/student-recommendation-semantic': semantic,
});
const resource = (id, kind = 'worksheet') => ({ id: String(id), kind, title: `Resource ${id}`, subject: 'Math', topic: 'Fractions', stage: '', level: '', description: '', raw: { user_id: 'teacher-1', title: `Resource ${id}`, topic: 'Fractions', subject: 'Math' } });

(async () => {
  const model = await loadTeacherRecommendationModel();
  assert.deepEqual(calls, ['learning_program_recommendation_events', 'teacher_assignments', 'learning_program_recommendation_events', 'learning_program_topic_videos']);
  assert.ok(model.alignment('worksheet', 7, [42]).explicitTopicMatch > 0.8);
  assert.equal(model.alignment('video', 9, [42]).directTopicLink, 1);
  const ranked = rankTeacherResources([resource(8), resource(7)], { id: 'program-42', subject: 'Math', topic: 'Fractions', priority: 'next', topicId: 42 }, model);
  assert.equal(ranked[0].resource.id, '7');
  assert.equal(ranked.length, 1, 'only the strongest Python affinity bucket is displayed');
  assert.deepEqual(rankTeacherResources([resource(8), { ...resource(9), subject: 'Science', raw: { ...resource(9).raw, subject: 'Science' } }], { id: 'topic', subject: 'Math', topic: 'Fractions', priority: 'high' }, model).map((item) => item.resource.id), ['8']);
  assert.deepEqual(rankTeacherResources([{ ...resource(8), stage: 'Primary' }], { id: 'stage', subject: 'Math', topic: 'Fractions', stage: 'Adults', priority: 'high' }, model), [], 'incompatible learner stages must not be recommended');
  assert.deepEqual(rankTeacherResources([{ ...resource(8), title: 'Unrelated', topic: '', raw: { ...resource(8).raw, title: 'Unrelated', topic: '' } }], { id: 'irrelevant', subject: 'Math', topic: 'Fractions', priority: 'high' }, model), [], 'an unrelated resource must not be rescued by its subject score');
  calls.length = 0;
  dataFor.learning_program_recommendation_events = [];
  const baseline = await loadTeacherRecommendationModel();
  assert.deepEqual(calls, ['learning_program_recommendation_events']);
  assert.equal(baseline.weights.bias, -0.2);
  const ordered = rankTeacherResources([resource(1, 'exam'), resource(2, 'worksheet'), resource(3, 'video'), resource(4, 'plan')], { id: 'order', subject: 'Math', topic: 'Fractions', priority: 'high' }, baseline);
  assert.deepEqual(ordered.map((item) => item.resource.kind), ['plan', 'video', 'worksheet', 'exam'], 'present each ML-ranked resource family in teaching order');
  calls.length = 0;
  eventReadError = true;
  const unavailable = await loadTeacherRecommendationModel();
  assert.deepEqual(calls, ['learning_program_recommendation_events']);
  assert.equal(unavailable.weights.bias, -0.2);
  process.stdout.write('Teacher recommendation topic evidence fixture passed.\n');
})().catch((error) => { console.error(error); process.exitCode = 1; });
