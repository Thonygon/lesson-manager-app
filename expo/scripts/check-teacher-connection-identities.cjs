const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/app/api/teacher-connection-identities+api.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleRef = { exports: {} };
let owner = 'teacher-1';
const publicClient = { auth: { getUser: async () => ({ data: { user: { id: owner } }, error: null }) } };
const server = {
  from(table) {
    const filters = {};
    const query = {
      select: () => query,
      eq: (key, value) => { filters[key] = value; return query; },
      in: (key, values) => { filters[key] = values; return query; },
      then: (resolve, reject) => Promise.resolve(table === 'teacher_student_links'
        ? { data: filters.teacher_id === 'teacher-1' && filters.id.includes(19) ? [{ id: 19, student_id: 'student-1' }] : [], error: null }
        : { data: [{ user_id: 'student-1', display_name: 'Real Student', username: 'real', email: 'student@example.test', phone_number: '+905551234567' }], error: null }).then(resolve, reject),
    };
    return query;
  },
  auth: { admin: { getUserById: async () => { throw Error('unexpected auth fallback'); } } },
};
let calls = 0;
new Function('module', 'exports', 'require', 'process', compiled)(moduleRef, moduleRef.exports, (name) => {
  if (name === '@supabase/supabase-js') return { createClient: () => ++calls % 2 ? publicClient : server };
  return require(name);
}, { env: { SUPABASE_URL: 'https://example.supabase.co', SUPABASE_ANON_KEY: 'public', SUPABASE_SERVICE_ROLE_KEY: 'secret' } });

const request = (token, ids) => new Request('https://app.example.test/api/teacher-connection-identities', { method: 'POST', headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: JSON.stringify({ linkIds: ids }) });
(async () => {
  let response = await moduleRef.exports.POST(request('', [19]));
  assert.equal(response.status, 401);
  response = await moduleRef.exports.POST(request('valid', ['not-an-id']));
  assert.equal(response.status, 400);
  owner = 'different-teacher';
  response = await moduleRef.exports.POST(request('valid', [19]));
  assert.equal(response.status, 403);
  assert.equal((await response.json()).identities, undefined);
  owner = 'teacher-1';
  response = await moduleRef.exports.POST(request('valid', [19]));
  assert.equal(response.status, 200);
  assert.deepEqual((await response.json()).identities['19'], { name: 'Real Student', email: 'student@example.test', phone: '+905551234567' });
  console.log('Teacher connection identity route verifies request ownership before returning student data.');
})().catch((error) => { console.error(error); process.exitCode = 1; });
