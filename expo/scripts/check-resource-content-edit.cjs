const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const file = path.resolve(__dirname, '../src/services/resource-library.ts');
const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const writes = [];
let owner = { id: 'teacher-id' };
let saved = { id: 7 };
const client = {
  auth: { getUser: async () => ({ data: { user: owner }, error: null }) },
  from(table) {
    return { update(payload) {
      const filters = {};
      return { eq(column, value) { filters[column] = value; return this; }, select() { return { maybeSingle: async () => { writes.push({ table, payload, filters }); return { data: saved, error: null }; } }; } };
    } };
  },
};
const loaded = { exports: {} };
new Function('module', 'exports', 'require', code)(loaded, loaded.exports, (name) => {
  if (name === '@/lib/supabase') return { requireSupabase: () => client };
  if (name === '@/lib/subjects') return { canonicalSubjectKey: String, canonicalSubjectLabel: String };
  if (name === '@/services/public-data') return { extractResourceImageUrl: () => '' };
  throw new Error(`Unexpected import ${name}`);
});

(async () => {
  await loaded.exports.updateResourceContent('plan', '7', { objective: 'Updated goal' });
  assert.equal(writes[0].table, 'lesson_plans');
  assert.deepEqual(writes[0].filters, { id: '7', user_id: 'teacher-id' });
  assert.deepEqual(writes[0].payload.plan_json, { objective: 'Updated goal' });
  assert.equal('updated_at' in writes[0].payload, false, 'legacy plan saves must not require updated_at');
  await loaded.exports.updateResourceContent('exam', '8', { exam_data: { sections: [{ questions: ['Prompt'] }] }, answer_key: { sections: [{ answers: ['Answer'] }] } });
  assert.equal(writes[1].table, 'quick_exams');
  assert.deepEqual(writes[1].payload.answer_key.sections[0].answers, ['Answer']);
  assert.ok(writes[1].payload.updated_at, 'exam saves retain their update timestamp');
  await assert.rejects(() => loaded.exports.updateResourceContent('exam', '8', { exam_data: { sections: [] }, answer_key: {} }), /questions or student instructions/);
  await assert.rejects(() => loaded.exports.updateResourceContent('worksheet', '9', { questions: [] }), /Keep the learning content/);
  saved = null;
  await assert.rejects(() => loaded.exports.updateResourceContent('worksheet', '9', { questions: ['Prompt'] }), /unavailable/);
  owner = null;
  await assert.rejects(() => loaded.exports.updateResourceContent('plan', '7', { objective: 'No owner' }), /session has expired/);
  process.stdout.write('Owner-scoped saved resource editing fixture passed.\n');
})().catch((error) => { console.error(error); process.exitCode = 1; });
