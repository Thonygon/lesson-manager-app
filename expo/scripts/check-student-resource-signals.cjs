const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/app/api/student-resource-signals+api.ts'), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
let connected = false;
let privateReads = 0;
const server = { from(table) {
  const query = { select: () => query, eq: () => query, in: () => table === 'teacher_assignment_attempts' ? Promise.resolve({ data: [{ practice_session_id: 10 }], error: null }) : query, order: () => query, limit: async () => {
    if (table === 'teacher_student_links') return { data: connected ? [{ id: 1 }] : [], error: null };
    privateReads += 1;
    if (table === 'practice_sessions') return { data: [{ id: 10, source_type: 'worksheet', source_id: 5 }, { id: 11, source_type: 'exam', source_id: 6 }], error: null };
    return { data: [{ practice_session_id: 10 }], error: null };
  } };
  return query;
} };
const createClient = (_url, key) => key === 'server-key' ? server : { auth: { getUser: async () => ({ data: { user: { id: 'teacher-id' } }, error: null }) } };
const moduleRef = { exports: {} };
new Function('module', 'exports', 'require', source)(moduleRef, moduleRef.exports, () => ({ createClient }));
const { POST } = moduleRef.exports;
process.env.EXPO_PUBLIC_SUPABASE_URL = 'https://supabase.test';
process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY = 'public-key';
process.env.SUPABASE_SERVICE_ROLE_KEY = 'server-key';
const studentId = '11111111-1111-4111-8111-111111111111';
const request = (authorized = true) => new Request('https://classio.expo.app/api/student-resource-signals', { method: 'POST', headers: { ...(authorized ? { Authorization: 'Bearer valid' } : {}), 'Content-Type': 'application/json' }, body: JSON.stringify({ studentId }) });
(async () => {
  assert.equal((await POST(request(false))).status, 401);
  assert.equal((await POST(request())).status, 403);
  assert.equal(privateReads, 0, 'student sessions must not be read before checking the teacher connection');
  connected = true;
  const response = await POST(request());
  assert.equal(response.status, 200);
  assert.deepEqual((await response.json()).completed, [{ kind: 'exam', id: '6' }]);
  process.stdout.write('Student resource signal authorization fixtures passed.\n');
})().catch((error) => { console.error(error); process.exitCode = 1; });
