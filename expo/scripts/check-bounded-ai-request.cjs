const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/server/bounded-ai-request.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const loaded = { exports: {} };
new Function('module', 'exports', compiled)(loaded, loaded.exports);
const { fetchBoundedAiJson } = loaded.exports;
const readRoute = (name) => fs.readFileSync(path.join(__dirname, '../src/app/api', name), 'utf8');

async function main() {
  const limits = { timeoutMs: 100, maxResponseBytes: 64 };
  const valid = await fetchBoundedAiJson('https://provider.test', { method: 'POST' }, limits, async () => Response.json({ ok: true }));
  assert.deepEqual(valid.body, { ok: true });
  assert.equal(valid.status, 200);
  const unavailable = await fetchBoundedAiJson('https://provider.test', {}, limits, async () => new Response(null, { status: 503 }));
  assert.equal(unavailable.status, 503);
  await assert.rejects(fetchBoundedAiJson('https://provider.test', {}, limits, async () => Response.json({ text: 'a'.repeat(100) })), /size limit/);
  const streamed = new Response(new ReadableStream({ start(controller) { controller.enqueue(new Uint8Array(40)); controller.enqueue(new Uint8Array(40)); controller.close(); } }));
  await assert.rejects(fetchBoundedAiJson('https://provider.test', {}, limits, async () => streamed), /size limit/);
  await assert.rejects(fetchBoundedAiJson('https://provider.test', {}, { ...limits, timeoutMs: 10 }, async (_url, init) => new Promise((_resolve, reject) => init.signal.addEventListener('abort', () => reject(new Error('aborted'))))), /timed out/);
  assert.equal((readRoute('resource-refine+api.ts').match(/providers\.slice\(0, 2\)/g) || []).length, 2);
  assert.match(readRoute('generate+api.ts'), /providerCalls >= 2/);
  assert.match(readRoute('lesson-plan-cover+api.ts'), /fetchBoundedAiJson/);
  console.log('Bounded AI requests enforce status, response size and timeout.');
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
