const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
function load(file) {
  const source = fs.readFileSync(path.join(__dirname, '../src/lib', file), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const moduleRef = { exports: {} };
  new Function('module', 'exports', 'require', code)(moduleRef, moduleRef.exports, require);
  return moduleRef.exports;
}
const { convertPlanningAmount, recommendedRange } = load('income-planner.ts');
assert.equal(convertPlanningAmount(50000, 'USD', 'EUR'), 46000);
assert.equal(convertPlanningAmount(46000, 'EUR', 'USD'), 50000);
assert.equal(convertPlanningAmount(50000, 'USD', 'TRY'), 1900000);
assert.deepEqual(recommendedRange('English', ['Online'], ['Adults'], 'Master’s', 'USD'), [25, 40, 80]);
assert.deepEqual(recommendedRange('English', ['Online'], ['Kids'], 'Master’s', 'USD'), [19, 30, 60]);
assert.deepEqual(recommendedRange('English', ['Online'], ['Adults'], 'Bachelor’s', 'USD'), [23, 36, 72]);
assert.deepEqual(recommendedRange('English', ['Online', 'In person'], ['Adults'], 'Master’s', 'USD'), [25, 45, 90]);
assert.deepEqual(recommendedRange('English', ['Online'], ['Adults'], 'Master’s', 'EUR'), [23, 37, 74]);
console.log('Income goal currency and rate parity fixtures passed');
