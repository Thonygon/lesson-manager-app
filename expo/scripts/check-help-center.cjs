const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/help-center.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const serviceExports = {};
vm.runInNewContext(compiled, { exports: serviceExports, require: () => ({ requireSupabase: () => { throw new Error('Network access is not part of this test'); } }), Uint8Array });

async function check() {
  const png = Uint8Array.from([137, 80, 78, 71, 13, 10, 26, 10, 0]);
  const jpeg = Uint8Array.from([255, 216, 255, 224, 0, 0, 255, 217]);
  assert.equal((await serviceExports.checkedHelpScreenshot({ name: 'capture.png', type: 'image/png', size: png.length, data: png })).mime, 'image/png');
  assert.equal((await serviceExports.checkedHelpScreenshot({ name: 'capture.jpg', type: 'image/jpeg', size: jpeg.length, data: jpeg })).mime, 'image/jpeg');
  await assert.rejects(serviceExports.checkedHelpScreenshot({ name: 'fake.png', type: 'image/png', size: jpeg.length, data: jpeg }), /help.invalidImage/);
  await assert.rejects(serviceExports.checkedHelpScreenshot({ name: 'large.png', type: 'image/png', size: 5 * 1024 * 1024 + 1, data: png }), /help.invalidImage/);
  await assert.rejects(serviceExports.checkedHelpScreenshot({ name: 'mismatch.png', type: 'image/png', size: png.length + 1, data: png }), /help.invalidImage/);
  process.stdout.write('Help screenshot validation passed.\n');
}

check().catch((error) => { console.error(error); process.exitCode = 1; });
