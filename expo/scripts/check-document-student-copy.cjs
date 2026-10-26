const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/document-exports.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const loaded = { exports: {} };
new Function('module', 'exports', 'require', compiled)(loaded, loaded.exports, (name) => {
  if (name === 'react-native') return { Platform: { OS: 'web' } };
  if (name === '@/services/branding') return { getBrandingSettings: () => ({}) };
  if (name === '@/services/document-export-events') return { recordedDocumentExport: async () => {} };
  if (name === '@/lib/subjects') return { canonicalSubjectKey: (value) => value };
  if (name === '@/lib/learner-stages') return { canonicalLearnerStageKey: (value) => value };
  if (name === '@/lib/lesson-purpose') return { lessonPurposeKey: (value) => value };
  if (name === '@/lib/supabase') return { requireSupabase() { throw new Error('Not needed by this fixture'); } };
  if (name === './source-document-labels.json') return require('../src/services/source-document-labels.json');
  if (name === './word-search-grid') {
    const source = fs.readFileSync(path.join(__dirname, '../src/services/word-search-grid.ts'), 'utf8');
    const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
    const loadedGrid = { exports: {} };
    new Function('module', 'exports', compiled)(loadedGrid, loadedGrid.exports);
    return loadedGrid.exports;
  }
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
const responseSpace = loaded.exports.resourceSections({ exam_data: { duration_minutes: 45, sections: [{ type: 'short_answer', title: 'Short response', questions: ['Explain the result.'] }, { type: 'writing_prompt', title: 'Writing', questions: ['Write a paragraph.'] }, { type: 'fill_in_blank', title: 'Complete', questions: ['The result is ___.'] }] } }, 'student');
assert.equal(responseSpace[0].lines.filter((line) => line === '_'.repeat(50)).length, 2);
assert.equal(responseSpace[1].lines.filter((line) => line === '_'.repeat(50)).length, 5);
assert.ok(responseSpace[2].lines.includes('1. The result is ______________.'));

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
assert.ok(matchingStudent.some((section) => section.table?.some((row) => row.includes('a) Goodbye'))));
assert.ok(!JSON.stringify(matchingStudent).includes('Hola → Hello'));
assert.ok(JSON.stringify(matchingTeacher).includes('Hola → Hello'));
assert.deepEqual(matchingStudent.find((section) => section.heading === 'Match the items').table[0], ['1. Hola', '[   ]', 'a) Goodbye']);
const mappedMatching = loaded.exports.resourceSections({ worksheet_json: { worksheet_type: 'matching', matching_pairs: [{ left: { Cat: 'Gato' }, right: { value: 'Animal' } }, { left: '{"key":"Dog"}', right: { value: 'Pet' } }] } }, 'student');
assert.deepEqual(mappedMatching.find((section) => section.heading === 'Match the items').table[0], ['1. Cat', '[   ]', 'a) Pet']);
const mappedExam = loaded.exports.resourceSections({ exam_data: { sections: [{ type: 'matching', title: 'Match', questions: [{ left: { key: 'A' }, right: { value: 'One' } }, { left: { key: 'B' }, right: { value: 'Two' } }] }] } }, 'student');
assert.deepEqual(mappedExam.find((section) => section.heading === 'Match').table[0], ['1. A', '[   ]', 'a) Two']);
const directExam = loaded.exports.resourceSections({ sections: [{ type: 'matching', title: 'Direct exam', questions: [{ left: { key: 'A' }, right: { value: 'One' } }] }] }, 'student');
assert.deepEqual(directExam.find((section) => section.heading === 'Direct exam').table[0], ['1. A', '[   ]', 'a) One']);
const trueFalse = loaded.exports.resourceSections({ worksheet_json: { worksheet_type: 'true_false', source_text: 'Water can freeze.', true_false_statements: ['Water can become ice.'], answer_key: '1. True' } }, 'student');
assert.deepEqual(trueFalse.find((section) => section.heading === 'Questions').table[0], ['1. Water can become ice.', '[ ] T  [ ] F']);
const dialogue = loaded.exports.resourceSections({ worksheet_json: { worksheet_type: 'reading_comprehension', reading_passage: 'Ana: Hello.\nBen: Welcome.', text_kind: 'dialogue', text_blocks: [{ type: 'turn', speaker: 'Ana', text: 'Hello.' }, { type: 'turn', speaker: 'Ben', text: 'Welcome.' }], questions: ['Who speaks first?'], answer_key: 'Ana' } }, 'student');
assert.deepEqual(dialogue.find((section) => section.heading === 'Reading passage').lines, ['Ana: Hello.', 'Ben: Welcome.']);
const wordSearch = loaded.exports.resourceSections({ worksheet_json: { worksheet_type: 'word_search_vocab', vocabulary_bank: ['CLASS', 'LEARN'], instructions: 'Find the words.' } }, 'student');
assert.ok(wordSearch.some((section) => section.heading === 'Word search' && section.lines.length >= 10));
assert.equal(wordSearch.find((section) => section.heading === 'Word search').grid.length, 10);
const art = `data:image/png;base64,${fs.readFileSync(path.join(__dirname, '../public/logo_classio_light.png')).toString('base64')}`;
const watermarkedSearch = loaded.exports.resourceSections({ worksheet_json: { worksheet_type: 'word_search_vocab', vocabulary_bank: ['CLASS'], visual_supports: [{ status: 'ready', image_data_url: art }, { status: 'failed', image_data_url: art }] } }, 'student');
assert.equal(watermarkedSearch.find((section) => section.grid).watermark, art);
assert.equal(watermarkedSearch.flatMap((section) => section.visuals || []).length, 0);
const examSearch = loaded.exports.resourceSections({ exam_data: { sections: [{ type: 'word_search', title: 'Find the words', vocabulary_bank: ['CLASS', 'LEARN'], visual_support: { status: 'ready', image_data_url: art } }] } }, 'student');
assert.equal(examSearch[0].grid.length, 10);
assert.equal(examSearch[0].watermark, art);
assert.ok(examSearch[0].lines.some((line) => line.includes('CLASS')));
assert.equal(loaded.exports.resourceSections({ exam_data: { sections: [{ type: 'word_search', grid: [['A', 'B'], ['C', 'D']] }] } }, 'student')[0].grid[1][1], 'D');
const illustratedWorksheet = loaded.exports.resourceSections({ worksheet_json: { worksheet_type: 'reading_comprehension', instructions: 'Look at the picture.', visual_supports: [{ status: 'ready', image_data_url: art }, { status: 'failed', image_data_url: art }] } }, 'student');
assert.deepEqual(illustratedWorksheet.flatMap((section) => section.visuals || []), [art]);
const illustratedExam = loaded.exports.resourceSections({ exam_data: { sections: [{ type: 'diagram_questions', title: 'Diagram', visual_support: { status: 'ready', image_data_url: art }, questions: ['Name the part.'] }] } }, 'student');
assert.deepEqual(illustratedExam[0].visuals, [art]);
assert.equal(loaded.exports.resourceSections({ exam_data: { sections: [{ type: 'diagram_questions', visual_support: { status: 'ready', image_data_url: art }, questions: ['Name the part.'] }] } }, 'answers').flatMap((section) => section.visuals || []).length, 0);
assert.equal(loaded.exports.resourceSections({ exam_data: { sections: [{ type: 'word_search', visual_support: { status: 'ready', image_data_url: art }, questions: ['Find CAT'] }] } }, 'student')[0].visuals, undefined);

const cvSections = loaded.exports.resourceSections({ full_name: 'Ada Teacher', role: 'teacher', email: 'ada@example.test', professional_summary: 'Experienced educator.', subjects: ['Spanish'], education: ['BA Education'] }, 'full', 'es');
assert.deepEqual(cvSections.map((section) => section.heading).filter(Boolean), ['Resumen profesional', 'Asignaturas', 'Formación']);
assert.ok(cvSections.some((section) => section.lines.includes('ada@example.test')));
const letterSections = loaded.exports.resourceSections({ cover_letter: 'Dear school,\n\nI teach Spanish.\n\nSincerely, Ada', target_employer: 'Colegio Norte' }, 'full', 'en');
assert.deepEqual(letterSections[0].lines, ['Dear school,', 'I teach Spanish.', 'Sincerely, Ada']);
process.stdout.write('Student document answer-exclusion fixture passed.\n');
