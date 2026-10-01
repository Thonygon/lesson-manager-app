const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/app/api/admin-ai+api.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
let role = 'admin';
const selected = [];
const server = {
  from(table) {
    selected.push(table);
    const result = table === 'profiles' ? { data: { role }, error: null } :
      ['ml_experiments', 'ml_experiment_runs', 'system_jobs'].includes(table) ? { data: [{ id: 1 }], error: null } : { count: 2, error: null };
    const query = { select() { return query; }, eq() { return query; }, order() { return query; }, limit() { return query; }, maybeSingle: async () => result, then(resolve) { return Promise.resolve(result).then(resolve); } };
    return query;
  },
};
const moduleObject = { exports: {} };
new Function('module', 'exports', 'require', compiled)(moduleObject, moduleObject.exports, (name) => {
  if (name !== '@supabase/supabase-js') return require(name);
  return { createClient: (_url, key) => key === 'server-key' ? server : { auth: { getUser: async () => ({ data: { user: { id: 'user-id' } }, error: null }) } } };
});
const { GET } = moduleObject.exports;
const request = (token) => new Request('https://classio.test/api/admin-ai', { headers: token ? { Authorization: `Bearer ${token}` } : {} });

async function main() {
  const original = { url: process.env.SUPABASE_URL, anon: process.env.SUPABASE_ANON_KEY, secret: process.env.SUPABASE_SECRET_KEY };
  try {
    assert.equal((await GET(request())).status, 401);
    process.env.SUPABASE_URL = 'https://supabase.test'; process.env.SUPABASE_ANON_KEY = 'anon-key'; delete process.env.SUPABASE_SECRET_KEY;
    assert.equal((await GET(request('signed-in'))).status, 503);
    process.env.SUPABASE_SECRET_KEY = 'server-key';
    role = 'student'; selected.length = 0;
    assert.equal((await GET(request('signed-in'))).status, 403);
    assert.deepEqual(selected, ['profiles']);
    role = 'admin'; selected.length = 0;
    const response = await GET(request('signed-in'));
    assert.equal(response.status, 200);
    assert.equal(response.headers.get('cache-control'), 'private, no-store');
    const payload = await response.json();
    assert.equal(payload.contentCounts.quick_exams, 2);
    assert.equal(payload.countMethod, 'planned');
    assert.equal(payload.recentRuns.length, 1);
    assert.equal(selected.length, 9);
  } finally {
    for (const [name, value] of Object.entries({ SUPABASE_URL: original.url, SUPABASE_ANON_KEY: original.anon, SUPABASE_SECRET_KEY: original.secret })) {
      if (value === undefined) delete process.env[name]; else process.env[name] = value;
    }
  }
  process.stdout.write('Protected admin AI API fixtures passed.\n');
}
void main();
