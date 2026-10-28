const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/assignment-snapshot.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleUnderTest = { exports: {} };
new Function('module', 'exports', compiled)(moduleUnderTest, moduleUnderTest.exports);
const { buildAssignmentSnapshot } = moduleUnderTest.exports;

const resource = { worksheet_json: { sections: [{ exercises: [{ groups: [{ questions: [{ prompt: 'What food?', options: ['Bread', 'Milk'], answer: 'Bread' }] }] }] }] }, cover_image_data: 'data:image/png;base64,private' };
const saved = buildAssignmentSnapshot(resource);
assert.equal(saved.worksheet_json.sections[0].exercises[0].groups[0].questions[0].answer, 'Bread');
assert.equal(saved.cover_image_data, undefined);
console.log('Assigned activity snapshot preserves nested questions and omits embedded images.');
