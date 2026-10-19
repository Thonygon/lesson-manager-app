const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

function compile(file, imports = {}) {
  const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, file), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const module = { exports: {} };
  new Function('module', 'exports', 'require', code)(module, module.exports, (name) => imports[name] || {});
  return module.exports;
}

const normalization = compile('../src/services/student-practice-answer-normalization.ts');
const practice = compile('../src/services/student-practice.ts', {
  '@/services/student-practice-answer-normalization': normalization,
  '@/services/student-practice-progress': { practiceSessionScorePct: (correct, total) => Math.round(correct / total * 100) },
  '@/services/public-data': { extractResourceImageUrl: () => '' },
});

const worksheet = practice.materialFromAssignment({
  id: 31, assignment_type: 'worksheet', source_record_id: 7,
  content_snapshot: { worksheet_json: { worksheet_type: 'multiple_choice', multiple_choice_items: [{ stem: 'Choose', options: ['A) old', 'B) new'], answer: 'A' }], answer_key: '1. B' } },
});
assert.equal(worksheet.questions[0].answer, 'B) new', 'edited worksheet answer key must override stale inline answers');
assert.equal(practice.gradePractice(worksheet, { 0: 'B) new' }).score, 100);

const exam = practice.materialFromAssignment({
  id: 32, assignment_type: 'exam', source_record_id: 8,
  content_snapshot: { exam_data: { sections: [{ type: 'true_false', questions: [{ text: 'Statement', answer: 'F' }], answers: ['F'] }] }, answer_key: { sections: [{ answers: ['V'] }] } },
});
assert.equal(exam.questions[0].answer, 'V', 'edited exam key must override stale section and question answers');
assert.equal(practice.gradePractice(exam, { 0: 'Verdadero' }).score, 100);

console.log('Edited resource answer precedence and rescoring: OK');
