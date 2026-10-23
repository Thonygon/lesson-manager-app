const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const source = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/app/api/admin-access+api.ts'), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
let clientNumber = 0;
let fail = false;
let rpcCalls = 0;
const queries = [];
function createClient() {
  clientNumber += 1;
  if (clientNumber % 2) return { auth: { getUser: async () => ({ data: { user: { id: 'admin-id' } }, error: null }) } };
  return {
    from(table) {
      if (!['profiles', 'plans'].includes(table)) throw new Error(`Unexpected write or table: ${table}`);
      queries.push(table);
      let selected = '';
      return { select(columns) { selected = columns; return this; }, eq() { return this; }, async maybeSingle() { return { data: table === 'profiles' ? selected === 'role' ? { role: 'admin' } : { user_id: 'target-id' } : { id: 'free', active: true }, error: null }; } };
    },
    async rpc(name, args) {
      rpcCalls += 1;
      assert.equal(name, 'classio_admin_set_access');
      assert.equal(args.p_actor_id, 'admin-id');
      assert.equal(args.p_target_id, 'target-id');
      assert.equal(args.p_plan_id, 'free');
      return fail ? { data: null, error: new Error('fixture rollback') } : { data: true, error: null };
    },
  };
}
const moduleRef = { exports: {} };
new Function('module', 'exports', 'require', source)(moduleRef, moduleRef.exports, () => ({ createClient }));
const request = () => new Request('https://classio.test/api/admin-access', { method: 'POST', headers: { Authorization: 'Bearer fixture-token', 'Content-Type': 'application/json' }, body: JSON.stringify({ userId: 'target-id', role: 'teacher', planId: 'free', subscriptionStatus: 'free', canTeach: true, canStudy: false, accountStatus: 'active', activeMode: 'teacher' }) });
async function main() {
  const old = { url: process.env.EXPO_PUBLIC_SUPABASE_URL, publicKey: process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY, serverKey: process.env.SUPABASE_SERVICE_ROLE_KEY };
  const oldError = console.error;
  process.env.EXPO_PUBLIC_SUPABASE_URL = 'https://fixture.invalid';
  process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY = 'fixture-public';
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'fixture-service';
  console.error = () => {};
  try {
    const success = await moduleRef.exports.POST(request());
    assert.equal(success.status, 200);
    assert.equal((await success.json()).audited, true);
    fail = true;
    assert.equal((await moduleRef.exports.POST(request())).status, 502);
    assert.equal(rpcCalls, 2);
    assert.deepEqual(queries, ['profiles', 'profiles', 'plans', 'profiles', 'profiles', 'plans']);
    const migration = fs.readFileSync(path.join(__dirname, '../../streamlit/migrations/admin_access_transaction.sql'), 'utf8');
    assert.match(migration, /insert into public\.admin_overrides/);
    assert.match(migration, /update public\.profiles/);
    process.stdout.write('Admin access transaction fixtures passed.\n');
  } finally {
    console.error = oldError;
    for (const [key, value] of [['EXPO_PUBLIC_SUPABASE_URL', old.url], ['EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY', old.publicKey], ['SUPABASE_SERVICE_ROLE_KEY', old.serverKey]]) {
      if (value === undefined) delete process.env[key]; else process.env[key] = value;
    }
  }
}
void main();
