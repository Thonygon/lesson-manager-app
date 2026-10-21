const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/app/api/admin-actions+api.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
let failIntent = false;
let failRpc = false;
let effects = [];
let clients = 0;
function query(table) {
  let selected = '';
  let id = '';
  return {
    select(value) { selected = value; return this; },
    eq(column, value) { if (column === 'user_id' || column === 'id') id = value; return this; },
    in() { return this; },
    async limit() { return { data: [] }; },
    async maybeSingle() {
      if (table === 'profiles' && selected === 'role') return { data: { role: 'admin' } };
      if (table === 'profiles' && id === 'target-1') return { data: { user_id: id } };
      return { data: null };
    },
    async insert(payload) {
      effects.push({ table, payload });
      return { error: table === 'admin_overrides' && failIntent ? new Error('audit unavailable') : null };
    },
  };
}
function createClient() {
  clients += 1;
  return clients % 2
    ? { auth: { getUser: async () => ({ data: { user: { id: 'admin-1' } }, error: null }) } }
    : { from: query, async rpc(name, args) { assert.ok(['classio_admin_change_staff', 'classio_admin_account_control'].includes(name)); effects.push({ table: name, args }); return failRpc ? { data: null, error: new Error('fixture rollback') } : { data: name === 'classio_admin_change_staff' ? { assignment_id: 1 } : true, error: null }; } };
}
const moduleRef = { exports: {} };
new Function('module', 'exports', 'require', compiled)(moduleRef, moduleRef.exports, () => ({ createClient }));
const oldError = console.error;
const oldEnv = { url: process.env.EXPO_PUBLIC_SUPABASE_URL, publicKey: process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY, serverKey: process.env.SUPABASE_SERVICE_ROLE_KEY };
const request = (action = 'staff_assign') => new Request('https://classio.test/api/admin-actions', { method: 'POST', headers: { Authorization: 'Bearer fixture-token', 'Content-Type': 'application/json' }, body: JSON.stringify({ action, userId: 'target-1', role: 'developer', status: 'suspended', reason: 'fixture' }) });
async function main() {
  process.env.EXPO_PUBLIC_SUPABASE_URL = 'https://fixture.invalid';
  process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY = 'fixture-public';
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'fixture-server';
  console.error = () => {};
  try {
    failIntent = true;
    assert.equal((await moduleRef.exports.POST(request())).status, 502);
    assert.deepEqual(effects.map((effect) => effect.table), ['admin_overrides']);
    effects = [];
    failIntent = false;
    assert.equal((await moduleRef.exports.POST(request())).status, 200);
    assert.deepEqual(effects.map((effect) => effect.table), ['admin_overrides', 'classio_admin_change_staff']);
    assert.equal(effects[0].payload.override_type, 'admin_action_attempt');
    effects = [];
    failRpc = true;
    assert.equal((await moduleRef.exports.POST(request())).status, 502);
    assert.deepEqual(effects.map((effect) => effect.table), ['admin_overrides', 'classio_admin_change_staff']);
    failRpc = false;
    effects = [];
    assert.equal((await moduleRef.exports.POST(request('account_status'))).status, 200);
    assert.deepEqual(effects.map((effect) => effect.table), ['admin_overrides', 'classio_admin_account_control']);
    assert.equal(effects[1].args.p_status, 'suspended');
    effects = [];
    assert.equal((await moduleRef.exports.POST(request('reset_usage'))).status, 200);
    assert.deepEqual(effects.map((effect) => effect.table), ['admin_overrides', 'classio_admin_account_control']);
    process.stdout.write('Admin action intent fixtures passed.\n');
  } finally {
    console.error = oldError;
    for (const [key, value] of [['EXPO_PUBLIC_SUPABASE_URL', oldEnv.url], ['EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY', oldEnv.publicKey], ['SUPABASE_SERVICE_ROLE_KEY', oldEnv.serverKey]]) {
      if (value === undefined) delete process.env[key]; else process.env[key] = value;
    }
  }
}
void main();
