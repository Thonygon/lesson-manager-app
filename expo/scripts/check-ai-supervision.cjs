const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const load = (name) => {
  const source = fs.readFileSync(path.join(__dirname, '../src/server', name), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const module = { exports: {} };
  new Function('module', 'exports', 'require', compiled)(module, module.exports, require);
  return module.exports;
};
const { approvedAiProviders } = load('ai-runtime-approval.ts');
const { recordAiFallback } = load('ai-fallback-telemetry.ts');
const candidates = [
  { provider: 'gemini', model: 'approved-model', key: 'secret' },
  { provider: 'openrouter', model: 'unapproved-model', key: 'secret' },
];

(async () => {
  const fetcher = async (url, options) => {
    assert.equal(new URL(url).searchParams.get('surface'), 'eq.expo_text');
    assert.equal(options.headers.apikey, 'service-key');
    return Response.json([{ provider: 'gemini', model: 'approved-model' }]);
  };
  assert.deepEqual(await approvedAiProviders(candidates, 'expo_text', 'v1', 'https://example.supabase.co', 'service-key', fetcher), candidates.slice(0, 1));
  assert.deepEqual(await approvedAiProviders(candidates, 'expo_text', 'v1', 'https://example.supabase.co', 'service-key', async () => Response.json([])), []);
  await assert.rejects(approvedAiProviders(candidates, 'expo_text', 'v1', 'https://example.supabase.co', 'service-key', async () => new Response(null, { status: 503 })), /unavailable/);
  await assert.rejects(approvedAiProviders(candidates, 'expo_text', 'v1', 'https://example.supabase.co', '', fetcher), /unavailable/);
  const recorded = await recordAiFallback('https://example.supabase.co', 'service-key', 'generate_plan', 'template', 'provider_failed', async (_url, options) => {
    const body = JSON.parse(options.body);
    assert.deepEqual(body, { source: 'expo', feature_name: 'generate_plan', requested_mode: 'ai', effective_mode: 'template', reason: 'provider_failed' });
    return new Response(null, { status: 201 });
  });
  assert.equal(recorded, true);
  console.log('AI supervision fixtures passed.');
})().catch((error) => { console.error(error); process.exitCode = 1; });
