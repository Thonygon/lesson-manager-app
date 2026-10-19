const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

function loadTs(file) {
  const source = fs.readFileSync(file, 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const module = { exports: {} };
  new Function('module', 'exports', 'require', compiled)(module, module.exports, require);
  return module.exports;
}

const normalization = loadTs(path.join(__dirname, '../src/services/student-practice-answer-normalization.ts'));
for (const answer of ['V', 'T', 'Verdadero', 'Verdadera', 'TRUE', 'doğru']) assert.equal(normalization.canonicalTrueFalse(answer), 'true');
for (const answer of ['F', 'Falso', 'Falsa', 'FALSE', 'yanlış']) assert.equal(normalization.canonicalTrueFalse(answer), 'false');
const choices = ['A) Access', 'B) Adapt', 'C) Analyze', 'D) Apply'];
assert.equal(normalization.canonicalChoice('B', choices), normalization.canonicalChoice('B) Adapt', choices));
assert.equal(normalization.canonicalChoice('B', choices), normalization.canonicalChoice('Adapt', choices));
assert.equal(normalization.canonicalChoice('Option 3', choices), normalization.canonicalChoice('C) Analyze', choices));
assert.notEqual(normalization.canonicalChoice('A', choices), normalization.canonicalChoice('D) Apply', choices));

const grid = loadTs(path.join(__dirname, '../src/services/word-search-grid.ts'));
const puzzle = grid.makeWordSearchPuzzle(['LIBRO', 'LÁPIZ', 'MOCHILA']);
assert.equal(puzzle.placements.length, 3);
for (const placement of puzzle.placements) {
  const dr = Math.sign(placement.end[0] - placement.start[0]);
  const dc = Math.sign(placement.end[1] - placement.start[1]);
  const found = [...placement.word].map((_, index) => puzzle.grid[placement.start[0] + index * dr][placement.start[1] + index * dc]).join('');
  assert.equal(found, placement.word);
}
console.log('Practice answer keys and solved word-search placements: OK');
