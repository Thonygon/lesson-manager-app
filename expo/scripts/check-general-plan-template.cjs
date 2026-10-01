const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const filename = path.join(__dirname, '../src/server/general-plan-template.ts');
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, resolveJsonModule: true } }).outputText;
const mod = { exports: {} };
new Function('module', 'exports', 'require', compiled)(mod, mod.exports, (name) => require(path.resolve(path.dirname(filename), name)));
const fixtures = require('./fixtures/general-plan-expected.json');
for (const fixture of fixtures) assert.deepEqual(mod.exports.generalPlanTemplate(fixture.input), fixture.expected);
process.stdout.write('General lesson-plan templates match Python fixtures.\n');
