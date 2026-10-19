const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/teacher-history-pagination.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleRef = { exports: {} };
new Function('module', 'exports', 'require', compiled)(moduleRef, moduleRef.exports, require);
const history = Array.from({ length: 1001 }, (_, id) => ({ id }));
const calls = [];
const client = { from(table) { assert.equal(table, 'payments'); return { select(columns) { assert.equal(columns, 'id,payment_date'); return { eq(key, value) { assert.equal(key, 'user_id'); assert.equal(value, 'teacher-1'); return { order() { return this; }, async range(start, end) { calls.push([start, end]); return { data: history.slice(start, end + 1), error: null }; } }; } }; } }; } };
(async () => {
  const rows = await moduleRef.exports.readTeacherHistory(client, 'teacher-1', 'payments', 'id,payment_date', 'payment_date');
  assert.equal(rows.length, 1001);
  assert.deepEqual(calls, [[0, 499], [500, 999], [1000, 1499], [1001, 1500]]);
  const filters = [];
  const scopedQuery = { eq(key, value) { filters.push([key, value]); return this; }, order() { return this; }, async range() { return { data: [], error: null }; } };
  const scopedClient = { from() { return { select() { return scopedQuery; } }; } };
  await moduleRef.exports.readTeacherHistory(scopedClient, 'teacher-1', 'classes', 'id,student,lesson_date', 'lesson_date', 'Emre Altan');
  assert.deepEqual(filters, [['user_id', 'teacher-1'], ['student', 'Emre Altan']]);
  const capped = { from() { return { select() { return { eq() { return { order() { return this; }, async range(start, end) { return { data: history.slice(start, Math.min(end + 1, start + 200)), error: null }; } }; } }; } }; } };
  assert.equal((await moduleRef.exports.readTeacherHistory(capped, 'teacher-1', 'payments', 'id', 'payment_date')).length, 1001);
  const failing = { from() { return { select() { return { eq() { return { order() { return this; }, async range() { return { data: null, error: Error('database unavailable') }; } }; } }; } }; } };
  await assert.rejects(moduleRef.exports.readTeacherHistory(failing, 'teacher-1', 'payments', 'id', 'payment_date'), /database unavailable/);
  process.stdout.write('Teacher history pagination reads all pages and rejects incomplete data.\n');
})().catch((error) => { process.stderr.write(`${error.stack}\n`); process.exitCode = 1; });
