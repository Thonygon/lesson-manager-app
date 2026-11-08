const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/lib/teacher-record-copy.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const loaded = { exports: {} };
new Function('module', 'exports', compiled)(loaded, loaded.exports);
const copy = loaded.exports.teacherRecordTranslations;
const keys = Object.keys(copy.en).sort();
for (const language of ['es', 'tr']) {
  assert.deepEqual(Object.keys(copy[language]).sort(), keys, `${language} record translations are incomplete`);
  for (const key of keys) {
    assert.ok(copy[language][key].trim(), `${language} has an empty value for ${key}`);
    const placeholders = (value) => [...value.matchAll(/\{([^}]+)\}/g)].map((match) => match[1]).sort();
    assert.deepEqual(placeholders(copy[language][key]), placeholders(copy.en[key]), `${language} has different placeholders for ${key}`);
  }
}
process.stdout.write('Teacher record translations are complete in EN, ES and TR.\n');
