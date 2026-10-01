const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/app/api/student-connection+api.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
let link = { id: 7, student_id: 'student-1', status: 'active' };
const writes = [];
const publicClient = { auth: { getUser: async (token) => ({ data: { user: token === 'valid' ? { id: 'student-1' } : null }, error: null }) } };
const serverClient = { from(table) {
  const filters = {};
  const chain = {
    select: () => chain, update: (payload) => { writes.push({ table, payload, filters }); return chain; },
    eq: (field, value) => { filters[field] = value; return chain; }, limit: () => chain,
    maybeSingle: async () => ({ data: link && filters.id === link.id && filters.student_id === link.student_id ? link : null, error: null }),
    then: (resolve) => resolve({ error: null }),
  };
  return chain;
} };
const moduleObject = { exports: {} };
new Function('module', 'exports', 'require', compiled)(moduleObject, moduleObject.exports, () => ({ createClient: (_url, key) => key === 'public' ? publicClient : serverClient }));
const { POST } = moduleObject.exports;
process.env.SUPABASE_URL = 'https://example.invalid';
process.env.SUPABASE_ANON_KEY = 'public';
process.env.SUPABASE_SECRET_KEY = 'server';
const request = (token, linkId) => new Request('https://example.invalid/api/student-connection', { method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ linkId }) });

(async () => {
  assert.equal((await POST(request('invalid', 7))).status, 401);
  assert.equal((await POST(request('valid', 0))).status, 400);
  assert.equal((await POST(request('valid', 8))).status, 404);
  assert.equal(writes.length, 0);
  const response = await POST(request('valid', 7));
  assert.equal(response.status, 200);
  assert.equal(writes.length, 2);
  assert.deepEqual(writes.map((item) => item.table), ['teacher_student_links', 'teacher_student_subjects']);
  assert.equal(writes[0].filters.student_id, 'student-1');
  assert.equal(writes[1].filters.student_id, 'student-1');
  assert.equal(writes[1].payload.status, 'archived');
  link = { ...link, status: 'archived' };
  writes.length = 0;
  assert.equal((await POST(request('valid', 7))).status, 200);
  assert.deepEqual(writes.map((item) => item.table), ['teacher_student_subjects']);
  console.log('Student connection route authorization, two-table archive, and retry pass.');
})().catch((error) => { console.error(error); process.exitCode = 1; });
