const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/privileged-workspaces.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const calls = [];
let staffRoles = [];
const client = {
  auth: { getUser: async () => ({ data: { user: { id: 'admin-user' } } }) },
  from(table) {
    calls.push(table);
    const query = {
      select: () => query,
      eq: () => query,
      order: () => query,
      limit: async () => ({ data: [] }),
      then(resolve) { return Promise.resolve({ data: table === 'user_staff_roles' ? staffRoles : [], error: null }).then(resolve); },
    };
    return query;
  },
};
const moduleRef = { exports: {} };
new Function('module', 'exports', 'require', compiled)(moduleRef, moduleRef.exports, (name) => {
  if (name === '@/lib/supabase') return { requireSupabase: () => client };
  return require(name);
});

(async () => {
  await assert.rejects(moduleRef.exports.loadDeveloperWorkspace(), /Developer or data scientist access/);
  assert.deepEqual(calls, ['user_staff_roles'], 'a product admin alone cannot read the ML workspace');
  calls.length = 0;
  staffRoles = [{ role_key: 'data_scientist' }];
  const workspace = await moduleRef.exports.loadDeveloperWorkspace();
  assert.ok(workspace.experiments && workspace.runs && workspace.artifacts);
  assert.ok(calls.includes('ml_experiments'));
  process.stdout.write('Developer workspace staff-role access fixture passed.\n');
})().catch((error) => { console.error(error); process.exitCode = 1; });
