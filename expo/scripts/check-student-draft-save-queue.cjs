const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/student-draft-save-queue.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleRef = { exports: {} };
new Function('module', 'exports', compiled)(moduleRef, moduleRef.exports);
const { createStudentDraftSaveQueue } = moduleRef.exports;

async function main() {
  const calls = [];
  let finishFirst;
  const queue = createStudentDraftSaveQueue((material, answers, sessionId) => {
    calls.push({ material, answers, sessionId });
    if (calls.length === 1) return new Promise((resolve) => { finishFirst = resolve; });
    return Promise.resolve(sessionId || 'unexpected-insert');
  });
  queue.reset('worksheet:7');
  const first = queue.enqueue('worksheet:7', { id: 7 }, { '0': 'a' });
  assert.equal(queue.enqueue('worksheet:7', { id: 7 }, { '0': 'a' }), null);
  const second = queue.enqueue('worksheet:7', { id: 7 }, { '0': 'ab' });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(calls.length, 1);
  assert.equal(calls[0].sessionId, undefined);
  finishFirst('draft-41');
  assert.equal(await first, 'draft-41');
  assert.equal(await second, 'draft-41');
  assert.equal(await queue.flush(), 'draft-41');
  assert.equal(calls.length, 2);
  assert.equal(calls[1].sessionId, 'draft-41');
  queue.reset('exam:9', 'draft-92', { '0': 'saved' });
  assert.equal(queue.enqueue('exam:9', { id: 9 }, { '0': 'saved' }), null);
  assert.equal(await queue.flush(), 'draft-92');
  assert.equal(queue.enqueue('worksheet:7', { id: 7 }, { '0': 'wrong-key' }), null);

  let attempts = 0;
  const recovery = createStudentDraftSaveQueue(async (_material, _answers, sessionId) => {
    attempts += 1;
    if (attempts === 1) throw new Error('transient');
    return sessionId || 'draft-77';
  });
  recovery.reset('worksheet:1');
  await assert.rejects(recovery.enqueue('worksheet:1', {}, { '0': 'first' }));
  assert.equal(await recovery.enqueue('worksheet:1', {}, { '0': 'second' }), 'draft-77');
  assert.equal(await recovery.flush(), 'draft-77');
  process.stdout.write('Student draft save serialization fixtures passed.\n');
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
