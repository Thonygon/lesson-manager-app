const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/student-resource-access.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleRef = { exports: {} };
const calls = [];
const planRows = [
  { id: 'free', active: true, features_json: { videos_access: true } },
  { id: 'no_video', active: true, features_json: { videos_access: false } },
];
const records = {
  plans: planRows,
  user_subscriptions: { plan_id: 'no_video', subscription_status: 'active', manual_override: false },
  profiles: { current_plan: 'free' },
};
const client = {
  auth: { getUser: async () => ({ data: { user: { id: 'student-1' } }, error: null }) },
  from(table) {
    calls.push(['table', table]);
    return {
      select() { return this; },
      eq(column, value) { calls.push(['filter', table, column, value]); return this; },
      limit(value) { calls.push(['limit', table, value]); return table === 'plans' ? Promise.resolve({ data: records[table], error: null }) : this; },
      async maybeSingle() { return { data: records[table], error: null }; },
    };
  },
};
const resourceLoads = [];
new Function('module', 'exports', 'require', compiled)(moduleRef, moduleRef.exports, (name) => {
  if (name === '@/lib/supabase') return { requireSupabase: () => client };
  if (name === '@/services/public-data') return { getPublicResources: async (kinds, limit) => { resourceLoads.push([kinds, limit]); return []; } };
  throw new Error(`Unexpected import: ${name}`);
});
const { studentVideoAccess, getStudentPublicPracticeResources } = moduleRef.exports;

assert.equal(studentVideoAccess(planRows, records.user_subscriptions, 'free'), false);
assert.equal(studentVideoAccess(planRows, { plan_id: 'no_video', subscription_status: 'expired' }, 'free'), true);
assert.equal(studentVideoAccess(planRows, { plan_id: 'no_video', manual_override: true }, 'free'), false);
assert.equal(studentVideoAccess([{ id: 'free', features_json: {} }], null, 'free'), true);
assert.equal(studentVideoAccess([{ id: 'free', features_json: { videos_access: false } }], null, 'free'), false);
assert.equal(studentVideoAccess(planRows, { plan_id: 'hidden_plan', subscription_status: 'active' }, 'free'), false);

getStudentPublicPracticeResources().then(() => {
  assert.deepEqual(resourceLoads, [[['worksheet', 'exam'], 120]]);
  assert.ok(calls.some((entry) => entry[0] === 'filter' && entry[1] === 'user_subscriptions' && entry[2] === 'user_id' && entry[3] === 'student-1'));
  assert.ok(calls.some((entry) => entry[0] === 'filter' && entry[1] === 'profiles' && entry[2] === 'user_id' && entry[3] === 'student-1'));
  console.log('Student resource access fixtures passed');
}).catch((error) => { console.error(error); process.exitCode = 1; });
