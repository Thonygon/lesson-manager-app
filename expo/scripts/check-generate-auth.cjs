const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/app/api/generate+api.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const generated = { exports: {} };
new Function('module', 'exports', compiled)(generated, generated.exports);
const { POST } = generated.exports;
const originalFetch = global.fetch;
const originalEnv = {
  EXPO_PUBLIC_SUPABASE_URL: process.env.EXPO_PUBLIC_SUPABASE_URL,
  EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY: process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
  OPENROUTER_API_KEY: process.env.OPENROUTER_API_KEY,
};
let profile = { role: 'student', primary_role: 'student', can_teach: false };
let profileStatus = 200;
let providerCalls = 0;
let providerDocument = { title: 'Greetings', objectives: ['Greet a peer'], instruction: [{ minutes: 10, activity: 'Role play' }], assessment: ['Use a greeting'] };
const request = (token = 'valid-token', kind = 'plan') => new Request('https://classio.test/api/generate', {
  method: 'POST',
  headers: token ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' },
  body: JSON.stringify({ kind, subject: 'Spanish', topic: 'Greetings', stage: 'Adult', level: 'A2' }),
});

async function main() {
  try {
    process.env.EXPO_PUBLIC_SUPABASE_URL = 'https://supabase.test';
    process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY = 'anon-key';
    process.env.OPENROUTER_API_KEY = 'server-only-key';
    global.fetch = async (url, options) => {
      const target = String(url);
      if (target.endsWith('/auth/v1/user')) return Response.json({ id: 'owner-id' });
      if (target.includes('/rest/v1/profiles')) {
        const parsed = new URL(target);
        assert.equal(parsed.searchParams.get('user_id'), 'eq.owner-id');
        assert.equal(options.headers.Authorization, 'Bearer valid-token');
        return Response.json([profile], { status: profileStatus });
      }
      if (target.includes('openrouter.ai')) {
        providerCalls += 1;
        return Response.json({ choices: [{ message: { content: JSON.stringify(providerDocument) } }], model: 'fixture-model' });
      }
      throw new Error(`Unexpected request: ${target}`);
    };
    assert.equal((await POST(request(''))).status, 401);
    const denied = await POST(request());
    assert.equal(denied.status, 403);
    assert.equal(denied.headers.get('cache-control'), 'private, no-store');
    assert.equal(providerCalls, 0);
    profile = { role: 'student', primary_role: 'student', can_teach: true };
    assert.equal((await POST(request())).status, 200);
    assert.equal((await POST(new Request('https://classio.test/api/generate', { method: 'POST', headers: { Authorization: 'Bearer valid-token' }, body: '[' }))).status, 400);
    profile = { role: 'teacher', primary_role: 'teacher', can_teach: false };
    assert.equal((await POST(request())).status, 403);
    profile = { role: 'teacher', primary_role: 'teacher', can_teach: null };
    assert.equal((await POST(request())).status, 200);
    providerDocument = { title: 'Incomplete plan' };
    assert.equal((await POST(request())).status, 502);
    providerDocument = { title: 'Practice', sections: [{ questions: [{ id: 1, prompt: 'A?' }, { id: 2, prompt: 'B?' }] }], answer_key: [{ id: 1, answer: 'A' }] };
    assert.equal((await POST(request('valid-token', 'worksheet'))).status, 502);
    providerDocument.answer_key.push({ id: 2, answer: 'B' });
    assert.equal((await POST(request('valid-token', 'worksheet'))).status, 200);
    profileStatus = 503;
    assert.equal((await POST(request())).status, 503);
    assert.equal(providerCalls, 5);
  } finally {
    global.fetch = originalFetch;
    for (const [name, value] of Object.entries(originalEnv)) {
      if (value === undefined) delete process.env[name]; else process.env[name] = value;
    }
  }
  process.stdout.write('Protected teaching generation fixtures passed.\n');
}
void main();
