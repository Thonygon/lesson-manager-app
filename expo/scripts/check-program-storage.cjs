const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const root = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(root, 'expo/src/services/program-storage.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleExports = {};
vm.runInNewContext(compiled, { exports: moduleExports });

const unit = moduleExports.programUnitRow({ title: 'Unit', overview: 'Scope', unit_objectives: ['Understand text'], recommended_lesson_purposes: ['practice_skill'], recommended_worksheet_types: ['reading_comprehension'], recommended_exam_exercise_types: ['short_answer'], topics: [{}, {}] }, 0);
const topic = moduleExports.programTopicRow({ title: 'Reading', subtopic: 'Evidence', lesson_focus: 'Find supporting details', lesson_purpose: 'practice_skill', learning_objectives: ['Find evidence'], success_criteria: ['Cites a sentence'], student_can_do: ['Explain an answer'], suggested_worksheet_types: ['reading_comprehension'], suggested_exam_exercise_types: ['short_answer'], homework_idea: 'Annotate a paragraph', teacher_notes: 'Model first', student_summary: 'Find clues', estimated_lessons: 2 }, 0, 1);
assert.equal(unit.estimated_lessons, 2);
assert.equal(unit.recommended_worksheet_types[0], 'reading_comprehension');
assert.equal(topic.lesson_focus, 'Find supporting details');
assert.equal(topic.lesson_purpose, 'practice_skill');
assert.equal(topic.success_criteria[0], 'Cites a sentence');
assert.equal(topic.suggested_exam_exercise_types[0], 'short_answer');
assert.equal(topic.homework_idea, 'Annotate a paragraph');

const schema = fs.readFileSync(path.join(root, 'streamlit/migrations/learning_programs.sql'), 'utf8');
for (const [table, row] of [['learning_program_units', unit], ['learning_program_topics', topic]]) {
  const definition = schema.match(new RegExp(`create table if not exists ${table} \\(([\\s\\S]*?)\\n\\);`, 'i'))?.[1];
  assert.ok(definition, `${table} schema found`);
  for (const column of Object.keys(row)) assert.match(definition, new RegExp(`\\b${column}\\s+`), `${table}.${column} exists`);
}
console.log('Program storage preserves linked-resource fields in source schema columns.');
