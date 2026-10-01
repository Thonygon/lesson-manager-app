const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const cache = new Map();
function loadTypeScript(filename) {
  if (cache.has(filename)) return cache.get(filename).exports;
  const generated = { exports: {} };
  cache.set(filename, generated);
  const source = fs.readFileSync(filename, 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, resolveJsonModule: true } }).outputText;
  const localRequire = (specifier) => {
    if (!specifier.startsWith('.')) return require(specifier);
    const resolved = path.resolve(path.dirname(filename), specifier);
    if (fs.existsSync(resolved) && resolved.endsWith('.json')) return require(resolved);
    if (fs.existsSync(`${resolved}.ts`)) return loadTypeScript(`${resolved}.ts`);
    if (fs.existsSync(`${resolved}.json`)) return require(`${resolved}.json`);
    throw new Error(`Unresolved fixture import: ${specifier}`);
  };
  new Function('module', 'exports', 'require', compiled)(generated, generated.exports, localRequire);
  return generated.exports;
}
const generated = { exports: loadTypeScript(path.join(__dirname, '../src/app/api/generate+api.ts')) };
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
let providerFailures = 0;
let providerDocuments = [];
let providerDocument = { title: 'Greetings', objective: 'Greet a peer', success_criteria: ['Use a greeting'], main_activity: ['Role play'], core_material: {} };
const request = (token = 'valid-token', kind = 'plan') => new Request('https://classio.test/api/generate', {
  method: 'POST',
  headers: token ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' },
  body: JSON.stringify({ kind, subject: 'Spanish', topic: 'Greetings', stage: 'Adult', level: 'A2', worksheetType: kind === 'worksheet' ? 'short_answer' : undefined }),
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
        if (providerFailures > 0) { providerFailures -= 1; return Response.json({ error: 'temporary failure' }, { status: 503 }); }
        return Response.json({ choices: [{ message: { content: JSON.stringify(providerDocuments.shift() || providerDocument) } }], model: 'fixture-model' });
      }
      throw new Error(`Unexpected request: ${target}`);
    };
    assert.equal((await POST(request(''))).status, 403);
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
    const templateRequest = new Request('https://classio.expo.app/api/generate', { method: 'POST', headers: { Authorization: 'Bearer valid-token', 'Content-Type': 'application/json' }, body: JSON.stringify({ kind: 'plan', subject: 'Other', customSubject: 'Philosophy', topic: 'Ethics', stage: 'adult_stage', level: 'intermediate_band', planLanguage: 'en', lessonPurpose: 'review_topic', generationMode: 'template' }) });
    const callsBeforeTemplate = providerCalls;
    const templateResult = await POST(templateRequest);
    assert.equal(templateResult.status, 200);
    const templatePayload = await templateResult.json();
    assert.equal(templatePayload.model, 'template');
    assert.equal(templatePayload.document.title, 'Ethics');
    assert.equal(providerCalls, callsBeforeTemplate);
    providerDocument = { title: 'Incomplete plan' };
    assert.equal((await POST(request())).status, 502);
    providerDocument = { title: 'Practice', worksheet_type: 'short_answer', instructions: 'Answer both questions.', questions: ['A?', 'B?'], answer_key: '' };
    assert.equal((await POST(request('valid-token', 'worksheet'))).status, 502);
    providerDocument.answer_key = '1. A; 2. B';
    assert.equal((await POST(request('valid-token', 'worksheet'))).status, 200);
    providerDocument = { title: 'Greetings', objective: 'Greet a peer', success_criteria: ['Use a greeting'], main_activity: ['Role play'], core_material: {} };
    providerDocuments = [{ title: 'Incomplete plan' }, providerDocument];
    assert.equal((await POST(request())).status, 200);
    providerFailures = 1;
    assert.equal((await POST(request())).status, 200);
    profileStatus = 503;
    assert.equal((await POST(request())).status, 503);
    assert.equal(providerCalls, 11);
  } finally {
    global.fetch = originalFetch;
    for (const [name, value] of Object.entries(originalEnv)) {
      if (value === undefined) delete process.env[name]; else process.env[name] = value;
    }
  }
  process.stdout.write('Protected teaching generation fixtures passed.\n');
}
void main();
