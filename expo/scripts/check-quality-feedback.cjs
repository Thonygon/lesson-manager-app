const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const generationId = '11111111-1111-4111-8111-111111111111';
const rows = {
  lesson_plans: [{ id: '8', user_id: 'teacher-1', is_public: false, status: 'active', created_at: '2026-10-23T00:01:00Z' }],
  classio_ai_operations: [{ operation_id: generationId, actor_user_id: 'teacher-1', source: 'expo', status: 'success', feature_name: 'generate_plan', modality: 'text', started_at: '2026-10-23T00:00:00Z', finished_at: '2026-10-23T00:00:50Z' }],
  classio_provider_attempts: [{ operation_id: generationId, status: 'success', model_reported: 'fixture-model' }],
  classio_generation_resources: [{ generation_id: generationId, actor_user_id: 'teacher-1', resource_type: 'plan', resource_id: '8', edited_at: null }],
  classio_generation_intent_feedback: [],
  resource_exposures: [{ exposure_id: 'exposure-1', teacher_id: 'teacher-1', viewer_user_id: 'teacher-1', student_id: 'student-1', resource_type: 'plan', resource_id: '8', exposure_type: 'teacher_resource_recommendation', learning_program_topic_id: 4, context_json: { recommendation_id: 'need-1' } }],
  classio_teacher_relevance_feedback: [],
};
const written = [];
const helper = {
  authorizeQualityFeedback: async () => ({ base: 'test', serverKey: 'test', userId: 'teacher-1' }),
  feedbackJson: (value, status = 200) => Response.json(value, { status }),
  readRows: async (_base, _key, table, filters = {}) => (rows[table] || []).filter((row) => Object.entries(filters).every(([key, value]) => !value.startsWith('eq.') || String(row[key]) === value.slice(3))),
  upsertRow: async (_base, _key, table, _conflict, value) => { written.push({ table, value }); return { id: 7, ...value }; },
  insertRow: async (_base, _key, table, value) => { written.push({ table, value }); },
};
function load(route) {
  const source = fs.readFileSync(path.join(__dirname, '../src/app/api', route), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const moduleRef = { exports: {} };
  new Function('module', 'exports', 'require', compiled)(moduleRef, moduleRef.exports, () => helper);
  return moduleRef.exports;
}
const generation = load('generation-feedback+api.ts');
const relevance = load('teacher-relevance-feedback+api.ts');
const post = (body) => new Request('https://classio.test/api/quality', { method: 'POST', body: JSON.stringify(body) });

async function main() {
  let result = await generation.GET(new Request('https://classio.test/api/generation-feedback?resourceType=plan&resourceId=8'));
  assert.deepEqual(await result.json(), { eligible: true, generationId, satisfied: null, reason: null });
  result = await generation.POST(post({ generationId, satisfied: false, surface: 'resource_page', reason: 'level' }));
  assert.equal(result.status, 200);
  assert.equal(written.find((item) => item.table === 'classio_generation_intent_feedback').value.feedback_surface, 'resource_page');
  assert.equal(written.find((item) => item.table === 'classio_generation_intent_feedback_events').value.reason, 'level');
  rows.classio_generation_resources[0].edited_at = '2026-10-23T00:05:00Z';
  assert.deepEqual(await (await generation.GET(new Request('https://classio.test/api/generation-feedback?resourceType=plan&resourceId=8'))).json(), { eligible: false });
  assert.equal((await generation.POST(post({ generationId, satisfied: true, surface: 'generation_preview' }))).status, 409);
  rows.classio_generation_resources[0].edited_at = null;
  assert.equal((await generation.POST(post({ action: 'bind', generationId, resourceType: 'plan', resourceId: '8' }))).status, 200);
  result = await relevance.POST(post({ exposureId: 'exposure-1', action: 'reject', reason: 'wrong_topic' }));
  assert.equal(result.status, 200);
  const feedback = written.find((item) => item.table === 'classio_teacher_relevance_feedback').value;
  assert.equal(feedback.context_key, 'student-1:topic:4:plan:8');
  assert.equal(feedback.reason, 'wrong_topic');
  assert.equal(written.find((item) => item.table === 'classio_teacher_relevance_feedback_events').value.action, 'rejected');
  console.log('Quality feedback route fixtures passed.');
}
void main();
