const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/help-center.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const serviceExports = {};
let fakeClient = null;
vm.runInNewContext(compiled, { exports: serviceExports, require: () => ({ requireSupabase: () => fakeClient }), Uint8Array });

async function check() {
  const png = Uint8Array.from([137, 80, 78, 71, 13, 10, 26, 10, 0]);
  const jpeg = Uint8Array.from([255, 216, 255, 224, 0, 0, 255, 217]);
  assert.equal((await serviceExports.checkedHelpScreenshot({ name: 'capture.png', type: 'image/png', size: png.length, data: png })).mime, 'image/png');
  assert.equal((await serviceExports.checkedHelpScreenshot({ name: 'capture.jpg', type: 'image/jpeg', size: jpeg.length, data: jpeg })).mime, 'image/jpeg');
  await assert.rejects(serviceExports.checkedHelpScreenshot({ name: 'fake.png', type: 'image/png', size: jpeg.length, data: jpeg }), /help.invalidImage/);
  await assert.rejects(serviceExports.checkedHelpScreenshot({ name: 'large.png', type: 'image/png', size: 5 * 1024 * 1024 + 1, data: png }), /help.invalidImage/);
  await assert.rejects(serviceExports.checkedHelpScreenshot({ name: 'mismatch.png', type: 'image/png', size: png.length + 1, data: png }), /help.invalidImage/);
  const inserted = [];
  fakeClient = {
    auth: { getUser: async () => ({ data: { user: { id: 'owner' } }, error: null }) },
    from: () => ({ insert(row) { inserted.push(row); return this; }, select() { return this; }, single: async () => ({ data: { id: 'ticket', ticket_number: 1, reporter_id: 'owner', screenshot_mime: null }, error: null }) }),
  };
  const input = { title: 'My records', description: 'Please provide my data.', pagePath: '/help' };
  await assert.rejects(serviceExports.submitHelpTicket({ ...input, kind: 'privacy_rights' }), /help.privacyScopeRequired/);
  await serviceExports.submitHelpTicket({ ...input, kind: 'privacy_rights', privacyScope: 'access' });
  assert.equal(inserted[0].privacy_scope, 'access');
  await serviceExports.submitHelpTicket({ ...input, kind: 'security_incident', privacyScope: 'erasure' });
  assert.equal(inserted[1].privacy_scope, null);
  const newest = Array.from({ length: 30 }, (_, index) => ({ id: `new-${index}` }));
  const older = { id: 'older-notified' };
  const removed = [];
  let lists = 0;
  fakeClient = {
    auth: { getUser: async () => ({ data: { user: { id: 'owner' } } }) },
    from: () => {
      const query = {
        select() { return this; }, eq() { return this; }, order() { return this; },
        limit: async () => ({ data: newest, error: null }),
        maybeSingle: async () => ({ data: older, error: null }),
      };
      return query;
    },
    storage: { from: () => ({
      list: async () => ({ data: lists++ ? [] : [{ id: 'image', name: 'older-notified.png' }], error: null }),
      remove: async (paths) => { removed.push(...paths); return { error: null }; },
    }) },
  };
  const reports = await serviceExports.myHelpTickets('older-notified');
  assert.equal(reports.length, 31);
  assert.equal(reports[0].id, 'older-notified');
  await serviceExports.purgeOwnHelpScreenshots('owner');
  assert.deepEqual(removed, ['owner/older-notified.png']);
  process.stdout.write('Help screenshot validation passed.\n');
}

check().catch((error) => { console.error(error); process.exitCode = 1; });
