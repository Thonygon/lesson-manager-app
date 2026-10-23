const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/server/ai-economic-events.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const loaded = { exports: {} };
new Function('module', 'exports', compiled)(loaded, loaded.exports);
const { beginAiOperation, beginProviderAttempt, finishAiOperation, finishProviderAttempt, extractProviderUsage } = loaded.exports;

async function main() {
  const originalFetch = global.fetch;
  const writes = [];
  const context = { base: 'https://supabase.test', serverKey: 'server-secret', actorUserId: '00000000-0000-4000-8000-000000000001', source: 'expo' };
  try {
    global.fetch = async (url, options) => {
      writes.push({ table: new URL(url).pathname.split('/').pop(), method: options.method, body: JSON.parse(options.body) });
      assert.equal(options.headers.Authorization, 'Bearer server-secret');
      return options.method === 'PATCH' ? Response.json([{ id: 1 }]) : new Response(null, { status: 201 });
    };
    const operationId = await beginAiOperation(context, 'generate_plan', 'text');
    const first = await beginProviderAttempt(context, operationId, 1, 'openrouter', 'free-model', 'text');
    await finishProviderAttempt(context, first, { status: 'failed', errorKind: 'transport_error' });
    const second = await beginProviderAttempt(context, operationId, 2, 'gemini', 'gemini-model', 'text');
    const usage = extractProviderUsage('gemini', { usageMetadata: { promptTokenCount: 123, candidatesTokenCount: 45, cachedContentTokenCount: 12, prompt: 'never-store' } });
    await finishProviderAttempt(context, second, { status: 'success', modelReported: 'gemini-model', ...usage });
    await finishAiOperation(context, operationId, 'success');
    assert.equal(writes.length, 6);
    assert.deepEqual(writes.map((write) => `${write.table}:${write.method}`), [
      'classio_ai_operations:POST', 'classio_provider_attempts:POST', 'classio_provider_attempts:PATCH',
      'classio_provider_attempts:POST', 'classio_provider_attempts:PATCH', 'classio_ai_operations:PATCH',
    ]);
    assert.equal(writes[1].body.operation_id, operationId);
    assert.equal(writes[3].body.operation_id, operationId);
    assert.equal(writes[2].body.input_tokens, null);
    assert.equal(writes[4].body.input_tokens, 123);
    assert.equal(writes[4].body.output_tokens, 45);
    assert.equal(writes[4].body.cached_input_tokens, 12);
    assert.equal(writes[4].body.usage_json.prompt, undefined);
    assert.equal(writes[5].body.status, 'success');
    assert.doesNotMatch(JSON.stringify(writes), /never-store|prompt_text|student_name|teacher_ledger_payments/);
    assert.equal(extractProviderUsage('openai', {}).output_tokens, null);
    global.fetch = async () => new Response(null, { status: 503 });
    await assert.rejects(beginAiOperation(context, 'generate_plan', 'text'), /write failed/);
  } finally { global.fetch = originalFetch; }
  console.log('AI economic operation and retry attempts are separate, correlated and metadata-only.');
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
