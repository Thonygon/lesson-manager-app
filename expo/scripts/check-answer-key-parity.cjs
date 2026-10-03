const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const { spawnSync } = require('node:child_process');

const filename = path.join(__dirname, '../src/server/answer-key.ts');
const code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const loaded = { exports: {} };
new Function('module', 'exports', code)(loaded, loaded.exports);
const cases = [
  ['1. Red; 2. Blue; 3. Green', 3],
  ['1. Red\n2. Blue\n3. Green', 3],
  ['["Red", "Blue", "Green"]', 3],
  ["['Red', 'Blue', 'Green']", 3],
  ["['It\\'s red', 'Blue']", 2],
  ['A) Red B) Blue C) Green', 3],
  ['Red; Blue; Green', 3],
  ['1. Red', 3],
  [['1. Red', '2. Blue'], 2],
];
const python = spawnSync('python3', ['-c', `import importlib.util, json, sys
spec = importlib.util.spec_from_file_location('answer_key_utils', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
cases = json.load(sys.stdin)
print(json.dumps([module.split_answer_key_items(raw, expected_count=count) for raw, count in cases]))`, path.join(__dirname, '../../streamlit/helpers/answer_key_utils.py')], { input: JSON.stringify(cases), encoding: 'utf8' });
if (python.status !== 0) throw new Error(python.stderr);
const expected = JSON.parse(python.stdout);
cases.forEach(([raw, count], index) => assert.deepEqual(loaded.exports.splitAnswerKeyItems(raw, count), expected[index], `Case ${index}: ${JSON.stringify(raw)}`));
const repaired = loaded.exports.repairExamAnswerKey({ sections: [{ type: 'multiple_choice', title: 'Words', questions: [{ stem: 'A?', correct_answer: 'Blue' }, { stem: 'B?', answer: 'Red' }], answers: [] }, { type: 'matching', title: 'Pairs', questions: [{ left: 'uno', right: 'one' }, { left: 'dos', right: 'two' }], answers: ['B', 'A'] }] });
assert.deepEqual(repaired.answer_key.sections[0].answers, ['Blue', 'Red']);
assert.deepEqual(repaired.answer_key.sections[1].answers, ['two', 'one']);
const withBlanks = loaded.exports.repairExamAnswerKey({ sections: [{ type: 'multiple_choice', title: 'Recovered', questions: [{ stem: 'A?', answer: 'A' }, { stem: 'B?', answer: 'B' }], answers: ['', 'B'] }, { type: 'matching', title: 'Pairs', questions: [{ left: 'uno', right: 'one' }, { left: 'dos', right: 'two' }], answers: [{ marker: '2' }, '1'] }] });
assert.deepEqual(withBlanks.answer_key.sections[0].answers, ['B', 'B']);
assert.deepEqual(withBlanks.answer_key.sections[1].answers, ['two', 'one']);
process.stdout.write('Python/Expo answer-key parity fixtures passed.\n');
