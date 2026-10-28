const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const source = fs.readFileSync(path.join(__dirname, '../src/server/ai-privacy-redaction.ts'), 'utf8');
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const loaded = { exports: {} };
new Function('module', 'exports', js)(loaded, loaded.exports);
const { redactDirectIdentifiers } = loaded.exports;
const input = 'Student name: Ana García. Email ana@example.com, phone +34 612 345 678. Address: 12 Main Street. Native language: Spanish. Learner ID: 1583928473928473928.';
const result = redactDirectIdentifiers(input);
for (const identifier of ['Ana García', 'ana@example.com', '+34 612 345 678', '12 Main Street']) assert.ok(!result.includes(identifier), identifier);
assert.match(result, /Native language: Spanish/);
assert.match(result, /1583928473928473928/);
assert.match(redactDirectIdentifiers('Calle Mayor 12, 3º B'), /\[address removed\]/);
assert.match(redactDirectIdentifiers('Calle Mayor 12, 3º B. Topic fractions'), /\[address removed\]\. Topic fractions/);
assert.match(redactDirectIdentifiers('Student: {"student_name":"Leyla Demir"}'), /\[student identifier removed\]/);
assert.match(redactDirectIdentifiers('Topic: fractions. Stage: upper_primary.'), /^Topic: fractions\. Stage: upper_primary\.$/);
for (const variant of ['Ana García necesita ayuda', 'ana garcia necesita ayuda', 'Anna Garcìa necesita ayuda', 'Αna Gаrcia necesita ayuda', 'Ana-Garcia necesita ayuda', 'Ana necesita ayuda']) {
  const cleaned = redactDirectIdentifiers(variant, ['Ana García']);
  assert.match(cleaned, /\[student name removed\]/, variant);
  assert.doesNotMatch(cleaned, /Ana|Anna|Garc/i, variant);
  assert.match(cleaned, /necesita ayuda/, variant);
}
assert.equal(redactDirectIdentifiers('Topic: Spanish grammar', ['Ana García']), 'Topic: Spanish grammar');
for (const value of ['TCKN: 10000000146', 'DNI: 12345678Z', 'Passport: A12345678', 'TR33 0006 1005 1978 6457 8413 26']) {
  assert.doesNotMatch(redactDirectIdentifiers(`Topic fractions. ${value}`), /10000000146|12345678Z|A12345678|TR33 0006/i);
}
assert.match(redactDirectIdentifiers('10000000146'), /\[identity number removed\]/);
assert.equal(redactDirectIdentifiers('Exercise: 12345678901 + 2'), 'Exercise: 12345678901 + 2');
assert.equal(redactDirectIdentifiers('Lesson topic: passport vocabulary and travel'), 'Lesson topic: passport vocabulary and travel');
assert.equal(redactDirectIdentifiers('Explain DNI vocabulary in Spanish'), 'Explain DNI vocabulary in Spanish');
process.stdout.write('AI direct-identifier redaction fixtures passed.\n');
