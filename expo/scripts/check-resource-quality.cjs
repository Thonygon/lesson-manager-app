const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/server/resource-quality.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleRef = { exports: {} };
new Function('module', 'exports', compiled)(moduleRef, moduleRef.exports);
const { worksheetQualityIssues, examQualityIssues, programQualityIssues } = moduleRef.exports;

const worksheet = { worksheet_type: 'reading_comprehension', reading_passage: 'A short passage.', questions: ['Why?', 'How?'], answer_key: '1. Because of the weather.' };
assert.match(worksheetQualityIssues(worksheet).join(' '), /one answer per item/);
worksheet.answer_key = '1. Because of the weather.\n2. By walking.';
assert.deepEqual(worksheetQualityIssues(worksheet), []);
worksheet.reading_passage = '';
assert.match(worksheetQualityIssues(worksheet).join(' '), /reading_passage/);

const exam = { sections: [{ type: 'table_interpretation', questions: ['1', '2', '3', '4', '5'], table_data: { columns: ['Year'], rows: [['2025']] } }] };
assert.match(examQualityIssues(exam, 'medium').join(' '), /2 columns and 2 rows/);
exam.sections[0].table_data = { columns: ['Year', 'Count'], rows: [['2025', '4'], ['2026', '5']] };
assert.deepEqual(examQualityIssues(exam, 'medium'), []);

const program = { units: [{ title: 'Unit 1', topics: [{ title: 'Topic 1', student_summary: 'We will practice.' }] }] };
assert.match(programQualityIssues(program, 2, 2).join(' '), /2 units/);
assert.deepEqual(programQualityIssues(program, 1, 1), []);
process.stdout.write('Resource quality fixtures passed.\n');
