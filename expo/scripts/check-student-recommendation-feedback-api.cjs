const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const filename = path.join(__dirname, '../src/app/api/student-recommendation-feedback+api.ts');
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleRef = { exports: {} };
new Function('module', 'exports', compiled)(moduleRef, moduleRef.exports);
const { GET, POST } = moduleRef.exports;
const originalFetch = global.fetch;
const originalEnv = Object.fromEntries(['EXPO_PUBLIC_SUPABASE_URL', 'EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY', 'SUPABASE_SERVICE_ROLE_KEY'].map((key) => [key, process.env[key]]));
let recent = [];
let inserted = [];
const request = (events, token = 'valid-token') => new Request('https://classio.test/api/student-recommendation-feedback', { method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ events }) });

async function main() {
  try {
    process.env.EXPO_PUBLIC_SUPABASE_URL = 'https://supabase.test';
    process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY = 'anon';
    process.env.SUPABASE_SERVICE_ROLE_KEY = 'service';
    global.fetch = async (input, options) => {
      const url = new URL(String(input));
      if (url.pathname === '/auth/v1/user') return options.headers.Authorization === 'Bearer valid-token' ? Response.json({ id: 'student-1' }) : Response.json({}, { status: 401 });
      assert.equal(options.headers.Authorization, 'Bearer service');
      assert.equal(url.searchParams.get('user_id') || 'eq.student-1', 'eq.student-1');
      if (url.pathname === '/rest/v1/user_activity_log') {
        if (options.method === 'POST') { inserted = JSON.parse(options.body); assert(inserted.every((row) => row.user_id === 'student-1')); return new Response(null, { status: 201 }); }
        return Response.json(recent);
      }
      throw new Error(`Unexpected URL ${url}`);
    };
    assert.equal((await GET(new Request('https://classio.test/api/student-recommendation-feedback'))).status, 401);
    assert.equal((await GET(new Request('https://classio.test/api/student-recommendation-feedback', { headers: { Authorization: 'Bearer valid-token' } }))).status, 200);
    const event = { activityType: 'student_recommendation_impression', surface: 'student_home', resourceKind: 'worksheet', resourceId: 42, subject: 'Spanish', mlScore: 0.8 };
    assert.equal((await POST(request([event]))).status, 200);
    assert.equal(inserted.length, 1);
    assert.equal(inserted[0].meta_json.resource_id, 42);
    recent = [{ activity_type: 'student_recommendation_impression', meta_json: inserted[0].meta_json }];
    assert.deepEqual(await (await POST(request([event]))).json(), { inserted: 0 });
    assert.equal((await POST(request([{ ...event, resourceId: -1 }]))).status, 400);
    assert.equal((await POST(request([event], 'expired'))).status, 401);
  } finally {
    global.fetch = originalFetch;
    for (const [key, value] of Object.entries(originalEnv)) if (value === undefined) delete process.env[key]; else process.env[key] = value;
  }
  process.stdout.write('Student recommendation feedback API fixtures passed.\n');
}
void main();
