const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const source = path.resolve(__dirname, '../src/shared/oral-presentation.ts');
const javascript = ts.transpileModule(fs.readFileSync(source, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: true, target: ts.ScriptTarget.ES2022 },
}).outputText;
const moduleRecord = { exports: {} };
vm.runInNewContext(javascript, {
  exports: moduleRecord.exports,
  module: moduleRecord,
  require: (name) => {
    assert.equal(name, './oral-exercises.json');
    return require('../src/shared/oral-exercises.json');
  },
  Set,
  Number,
  Error,
});
const oral = moduleRecord.exports;

assert.equal(oral.oralFamily('English'), 'language');
assert.equal(oral.oralFamily('Mathematics'), 'mathematics');
assert.equal(oral.oralFamily('Science'), 'science');
assert.ok(oral.oralExercises('language').includes('read_aloud'));
assert.ok(!oral.oralExercises('mathematics').includes('read_aloud'));
assert.equal(oral.oralTemplateAvailable('read_aloud'), false);
assert.equal(oral.oralTemplateAvailable('monologue'), true);

const document = oral.oralTemplate({ subject: 'English', topic: 'Travel', objective: 'Explain a travel plan', exerciseType: 'monologue', maxDurationSeconds: 180, planLanguage: 'en', studentLanguage: 'es' });
assert.equal(document.student_material_language, 'es');
assert.equal(document.rubric.length, 5);
assert.equal(oral.oralDocumentIssues(document, 'language', 'monologue').length, 0);
assert.ok(oral.oralDocumentIssues({ ...document, rubric: [{ ...document.rubric[0], id: document.rubric[1].id }, ...document.rubric.slice(1)] }, 'language', 'monologue').some((issue) => issue.includes('unique')));
assert.ok(oral.oralDocumentIssues({ ...document, max_duration_seconds: 601 }, 'language', 'monologue').some((issue) => issue.includes('duration')));
assert.throws(() => oral.oralTemplate({ subject: 'Mathematics', topic: 'Fractions', objective: 'Explain', exerciseType: 'read_aloud', maxDurationSeconds: 180, planLanguage: 'en', studentLanguage: 'en' }));

const expirySource = path.resolve(__dirname, '../src/lib/oral-audio-expiry.ts');
const expiryModule = { exports: {} };
vm.runInNewContext(ts.transpileModule(fs.readFileSync(expirySource, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, { exports: expiryModule.exports, module: expiryModule, Date, Number });
const now = Date.parse('2026-11-21T12:00:00Z');
const expires = (days) => new Date(now + days * 86400000).toISOString();
assert.equal(expiryModule.exports.oralAudioExpiresSoon(expires(5), now), true);
assert.equal(expiryModule.exports.oralAudioExpiresSoon(expires(5.01), now), false);
assert.equal(expiryModule.exports.oralAudioExpiresSoon(expires(-1), now), false);
assert.equal(expiryModule.exports.oralAudioExpiresSoon('invalid', now), false);

process.stdout.write('Oral taxonomy, template, validation, and expiry checks passed.\n');
