const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/student-recommendation-semantic.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleObject = { exports: {} };
new Function('module', 'exports', 'require', compiled)(moduleObject, moduleObject.exports, require);
const { semanticTextAffinity } = moduleObject.exports;
const near = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-10, `${actual} != ${expected}`);

near(semanticTextAffinity(['Grammar verbs'], ['Grammar verbs']), 1);
near(semanticTextAffinity(['Fractions review'], ['Fractions']), 0.82);
near(semanticTextAffinity(['Animal habitats'], ['Verb conjugation']), 0.1664516129032258);
near(semanticTextAffinity(['Linear equations practice'], ['Equation practice']), 0.6961904761904761);
near(semanticTextAffinity([''], ['Equation practice']), 0);
process.stdout.write('Student recommendation semantic affinity fixtures passed.\n');
