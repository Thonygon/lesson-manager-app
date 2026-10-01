const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/student-practice.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleObject = { exports: {} };
new Function('module', 'exports', 'require', compiled)(moduleObject, moduleObject.exports, () => ({}));
const evaluateExpo = moduleObject.exports.evaluateWritingPrompt;

const model = 'The lesson explains how plants absorb sunlight and water. Students describe photosynthesis and compare plant growth in light and shade.';
const cases = [
  { student: '', expected: model },
  { student: 'Plants need sunlight and water.', expected: model },
  { student: 'Plants absorb sunlight and water. Photosynthesis supports plant growth. Light and shade change the result.', expected: model },
  { student: 'I will explain plants. They absorb sunlight and water. I can compare growth in light and shade with examples from the lesson.', expected: model },
];
const python = path.join(__dirname, '../../.venv/bin/python3');
const oracle = spawnSync(python, ['-c', `import json,sys\nfrom helpers.practice_engine import _writing_prompt_feedback\ncases=json.load(sys.stdin)\nprint(json.dumps([_writing_prompt_feedback(c['student'], c['expected']) for c in cases]))`], {
  input: JSON.stringify(cases), encoding: 'utf8', env: { ...process.env, PYTHONPATH: path.join(__dirname, '../../streamlit') },
});
if (oracle.status !== 0) throw new Error(oracle.stderr || `Python oracle exited ${oracle.status}`);
const expected = JSON.parse(oracle.stdout.trim().split('\n').at(-1));
cases.forEach((item, index) => {
  const actual = evaluateExpo(item.student, item.expected);
  assert.equal(actual.isCorrect, expected[index].is_correct, `case ${index} correctness`);
  assert.equal(actual.score, expected[index].score, `case ${index} rubric score`);
});
console.log(`${cases.length} writing-prompt scores match Streamlit.`);
