const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const cache = new Map();
function load(filename) {
  if (cache.has(filename)) return cache.get(filename).exports;
  const mod = { exports: {} };
  cache.set(filename, mod);
  const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, resolveJsonModule: true } }).outputText;
  new Function('module', 'exports', 'require', compiled)(mod, mod.exports, (name) => {
    const resolved = path.resolve(path.dirname(filename), name);
    if (fs.existsSync(resolved)) return require(resolved);
    if (fs.existsSync(`${resolved}.ts`)) return load(`${resolved}.ts`);
    throw new Error(`Unresolved import: ${name}`);
  });
  return mod.exports;
}

const render = load(path.join(__dirname, '../src/server/subject-plan-template.ts')).subjectPlanTemplate;
for (const fixture of require('./fixtures/subject-plan-expected.json')) assert.deepEqual(render(fixture.input), fixture.expected);
process.stdout.write('Subject lesson-plan templates match Python fixtures.\n');
