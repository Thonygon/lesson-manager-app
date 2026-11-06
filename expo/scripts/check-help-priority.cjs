const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/privileged-workspaces.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const serviceExports = {};
const ordinary = Array.from({ length: 300 }, (_, index) => ({ id: `ordinary-${index}`, kind: 'bug', created_at: '2026-11-06T00:00:00Z' }));
const urgent = { id: 'sensitive-old', kind: 'privacy_rights', status: 'open', created_at: '2026-10-01T00:00:00Z' };
const client = {
  auth: { getUser: async () => ({ data: { user: { id: 'staff' } } }) },
  from(table) {
    const query = {
      sensitive: false,
      select() { return this; }, eq() { return this; }, order() { return this; },
      in(column) { if (column === 'kind') this.sensitive = true; return this; },
      maybeSingle: async () => ({ data: { role: 'developer' }, error: null }),
      async limit() { return { data: this.sensitive ? [urgent] : ordinary, error: null }; },
      then(resolve) { return Promise.resolve({ data: [{ role_key: 'developer' }], error: null }).then(resolve); },
    };
    assert.ok(['user_staff_roles', 'profiles', 'classio_help_tickets'].includes(table));
    return query;
  },
};
vm.runInNewContext(compiled, { exports: serviceExports, require: () => ({ requireSupabase: () => client }), Date, Map, Promise });

serviceExports.loadDeveloperWorkspace('support').then((workspace) => {
  assert.equal(workspace.helpTickets.rows.length, 301);
  assert.ok(workspace.helpTickets.rows.some((row) => row.id === urgent.id));
  process.stdout.write('Sensitive help tickets survive the recent-queue limit.\n');
}).catch((error) => { console.error(error); process.exitCode = 1; });
