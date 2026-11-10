const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/server/admin-account-suspension.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const loaded = { exports: {} };
new Function('module', 'exports', 'require', source)(loaded, loaded.exports, require);

async function main() {
  const { changeAccountStatus } = loaded.exports;
  const events = [];
  let failBan = false;
  let failSave = false;
  const server = { auth: { admin: { async updateUserById(userId, attrs) {
    assert.equal(userId, 'target');
    events.push(attrs.ban_duration);
    return { error: failBan ? new Error('Auth unavailable') : null };
  } } } };
  const save = async () => { events.push('save'); if (failSave) throw new Error('DB unavailable'); };

  await changeAccountStatus(server, 'target', 'active', 'suspended', save);
  assert.deepEqual(events.splice(0), ['876000h', 'save']);
  await changeAccountStatus(server, 'target', 'suspended', 'active', save);
  assert.deepEqual(events.splice(0), ['none', 'save']);
  await changeAccountStatus(server, 'target', 'active', 'active', save);
  assert.deepEqual(events.splice(0), ['none', 'save']);
  await changeAccountStatus(server, 'target', 'suspended', 'suspended', save);
  assert.deepEqual(events.splice(0), ['876000h', 'save']);
  failBan = true;
  await assert.rejects(changeAccountStatus(server, 'target', 'active', 'suspended', save), /Auth unavailable/);
  assert.deepEqual(events.splice(0), ['876000h']);
  failBan = false; failSave = true;
  await assert.rejects(changeAccountStatus(server, 'target', 'active', 'suspended', save), /DB unavailable/);
  assert.deepEqual(events.splice(0), ['876000h', 'save', 'none']);
  process.stdout.write('Admin account suspension sequencing passed.\n');
}

void main();
