const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/document-exports.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const loaded = { exports: {} };
new Function('module', 'exports', 'require', compiled)(loaded, loaded.exports, (name) => {
  if (name === 'react-native') return { Platform: { OS: 'web' } };
  if (name === '@/lib/supabase') return { requireSupabase() { throw new Error('Not needed by this fixture'); } };
  return require(name);
});

const exam = {
  title: 'Science exam',
  exam_data: {
    sections: [{ title: 'Matter', questions: [{ id: 1, prompt: 'Name a solid.', correct_answer: 'Frozen water', is_correct: true, explanation: 'It holds its shape.', teacher_feedback: 'Accept snow.', marking_guide: 'One mark.', options: ['A solid', 'A gas'] }] }],
    answer_key: [{ id: 1, answer: 'Frozen water', rationale: 'It holds its shape.' }],
  },
  answer_key: { sections: [{ answers: ['Frozen water'] }] },
};
const student = JSON.stringify(loaded.exports.resourceSections(exam, 'student'));
const teacher = JSON.stringify(loaded.exports.resourceSections(exam, 'teacher'));
const keyOnly = JSON.stringify(loaded.exports.resourceSections(exam, 'answers'));
for (const answer of ['Frozen water', 'It holds its shape.', 'Accept snow.', 'One mark.']) {
  assert.ok(!student.includes(answer), `Student document exposed ${answer}`);
  assert.ok(teacher.includes(answer), `Teacher document lost ${answer}`);
}
assert.ok(student.includes('Name a solid.'));
assert.ok(student.includes('A gas'));
assert.ok(!student.includes('Is Correct'));
assert.ok(keyOnly.includes('Frozen water'));
assert.ok(!keyOnly.includes('Name a solid.'));
assert.ok(teacher.includes('Matter'));

const legacy = {
  exam_data: { instructions: 'Show your work.', sections: [{ type: 'multiple_choice', title: 'Vocabulary', questions: [{ stem: 'Choose the word.', options: ['A', 'B'] }] }] },
  answer_key: { sections: [{ title: 'Vocabulary', answers: ['B'] }] },
};
const legacyStudent = JSON.stringify(loaded.exports.resourceSections(legacy, 'student'));
const legacyTeacher = JSON.stringify(loaded.exports.resourceSections(legacy, 'teacher'));
const legacyAnswers = JSON.stringify(loaded.exports.resourceSections(legacy, 'answers'));
assert.ok(legacyStudent.includes('Choose the word.'));
assert.ok(!legacyStudent.includes('Answer key'));
assert.ok(legacyTeacher.includes('Answer key'));
assert.ok(legacyAnswers.includes('1. B'));
assert.ok(!legacyAnswers.includes('Choose the word.'));

const worksheet = { worksheet_json: { title: 'Practice', sections: [{ questions: [{ prompt: 'Write a greeting.', is_correct: true, feedback: 'Teacher hint' }] }], answer_key: 'Hello' } };
const worksheetStudent = JSON.stringify(loaded.exports.resourceSections(worksheet, 'student'));
const worksheetTeacher = JSON.stringify(loaded.exports.resourceSections(worksheet, 'teacher'));
assert.ok(worksheetStudent.includes('Write a greeting.'));
assert.ok(!worksheetStudent.includes('Teacher hint'));
assert.ok(!worksheetStudent.includes('Is Correct'));
assert.ok(!worksheetStudent.includes('Hello'));
assert.ok(worksheetTeacher.includes('Hello'));
const matching = { worksheet_json: { worksheet_type: 'matching', instructions: 'Connect each pair.', matching_pairs: [{ left: 'Hola', right: 'Hello' }, { left: 'Adiós', right: 'Goodbye' }], answer_key: '1. Hola → Hello\n2. Adiós → Goodbye' } };
const matchingStudent = loaded.exports.resourceSections(matching, 'student');
const matchingTeacher = loaded.exports.resourceSections(matching, 'teacher');
assert.ok(matchingStudent.some((section) => section.lines.includes('a) Goodbye')));
assert.ok(!JSON.stringify(matchingStudent).includes('Hola → Hello'));
assert.ok(JSON.stringify(matchingTeacher).includes('Hola → Hello'));

const cvSections = loaded.exports.resourceSections({ full_name: 'Ada Teacher', role: 'teacher', email: 'ada@example.test', professional_summary: 'Experienced educator.', subjects: ['Spanish'], education: ['BA Education'] }, 'full', 'es');
assert.deepEqual(cvSections.map((section) => section.heading), ['Contacto', 'Resumen profesional', 'Asignaturas', 'Formación']);
assert.ok(cvSections[0].lines.includes('ada@example.test'));
const letterSections = loaded.exports.resourceSections({ cover_letter: 'Dear school,\n\nI teach Spanish.\n\nSincerely, Ada', target_employer: 'Colegio Norte' }, 'full', 'en');
assert.equal(letterSections[0].lines.length, 4);
process.stdout.write('Student document answer-exclusion fixture passed.\n');
