const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/app/api/admin-workspace+api.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
let role = 'student';
let validToken = true;
const reads = [];
const server = {
  from(table) {
    reads.push(table);
    const query = {
      select() { return query; },
      eq() { return query; },
      order() { return query; },
      limit() { return query; },
      async maybeSingle() { return { data: { role }, error: null }; },
      then(resolve) { return Promise.resolve({ data: [], error: null }).then(resolve); },
    };
    return query;
  },
};
const moduleRef = { exports: {} };
new Function('module', 'exports', 'require', compiled)(moduleRef, moduleRef.exports, (name) => {
  if (name === '@supabase/supabase-js') return { createClient: (_url, key) => key === 'server-key' ? server : { auth: { getUser: async () => validToken ? { data: { user: { id: 'actor' } }, error: null } : { data: { user: null }, error: new Error('expired') } } } };
  return require(name);
});
const request = (token) => new Request('https://classio.test/api/admin-workspace?section=staff', { headers: token ? { Authorization: `Bearer ${token}` } : {} });

async function main() {
  const names = ['SUPABASE_URL', 'SUPABASE_ANON_KEY', 'SUPABASE_SECRET_KEY'];
  const previous = Object.fromEntries(names.map((name) => [name, process.env[name]]));
  try {
    process.env.SUPABASE_URL = 'https://fixture.invalid';
    process.env.SUPABASE_ANON_KEY = 'public-key';
    process.env.SUPABASE_SECRET_KEY = 'server-key';
    const { GET } = moduleRef.exports;
    assert.equal((await GET(request())).status, 401);
    assert.deepEqual(reads, []);
    validToken = false;
    assert.equal((await GET(request('expired'))).status, 401);
    assert.deepEqual(reads, []);
    validToken = true;
    for (role of ['student', 'teacher', 'developer', 'data_scientist']) {
      reads.length = 0;
      assert.equal((await GET(request('valid'))).status, 403, `${role} must not read Admin`);
      assert.deepEqual(reads, ['profiles'], `${role} must not reach staff data`);
    }
    role = 'admin';
    reads.length = 0;
    const response = await GET(request('valid'));
    assert.equal(response.status, 200);
    assert.equal(response.headers.get('cache-control'), 'private, no-store');
    assert.deepEqual(reads, ['profiles', 'user_staff_roles']);
    process.stdout.write('Admin workspace role and expired-token matrix passed.\n');
  } finally {
    for (const name of names) previous[name] === undefined ? delete process.env[name] : process.env[name] = previous[name];
  }
}
void main().catch((error) => { console.error(error); process.exitCode = 1; });
