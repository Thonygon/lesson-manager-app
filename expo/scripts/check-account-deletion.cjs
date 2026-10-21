const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const filename = path.join(__dirname, '../src/services/profile.ts');
const source = ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
let fail = false;
let calls = 0;
const client = {
  auth: { getUser: async () => ({ data: { user: { id: '12345678-1234-1234-1234-123456789012' } }, error: null }) },
  async rpc(name, args) {
    calls += 1;
    assert.equal(name, 'classio_delete_account_data');
    assert.deepEqual(args, { p_user_id: '12345678-1234-1234-1234-123456789012' });
    return fail ? { data: null, error: new Error('fixture transaction rolled back') } : { data: true, error: null };
  },
  from() { throw new Error('Deletion must use one transaction RPC'); },
};
const moduleRef = { exports: {} };
new Function('module', 'exports', 'require', source)(moduleRef, moduleRef.exports, (name) => {
  if (name === '@/lib/supabase') return { requireSupabase: () => client };
  throw new Error(`Unexpected import: ${name}`);
});

async function main() {
  fail = true;
  await assert.rejects(moduleRef.exports.deleteCurrentUserData(), /fixture transaction rolled back/);
  fail = false;
  await moduleRef.exports.deleteCurrentUserData();
  assert.equal(calls, 2);
  const migration = fs.readFileSync(path.join(__dirname, '../../streamlit/migrations/delete_account_transaction.sql'), 'utf8');
  assert.match(migration, /is_public is distinct from true or status = ''archived''/);
  assert.match(migration, /author_name = ''Classio''/);
  assert.doesNotMatch(migration, /delete from public\.payments/i);
  assert.doesNotMatch(migration, /delete from public\.admin_overrides/i);
  process.stdout.write('Account deletion fixtures passed.\n');
}
void main();
