const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/server/ai-provider-chain.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleRef = { exports: {} };
new Function('module', 'exports', compiled)(moduleRef, moduleRef.exports);
const { configuredAiProviders, requestAiProvider } = moduleRef.exports;

const providers = configuredAiProviders({ OPENROUTER_API_KEY: 'or-key', GEMINI_API_KEY: 'gem-key', OPENAI_API_KEY: 'oa-key' });
assert.deepEqual(providers.map((item) => item.provider), ['openrouter', 'gemini', 'openai']);
assert.deepEqual(providers.map((item) => item.model), ['openrouter/free', 'gemini-2.5-flash', 'gpt-4o-mini']);
assert.deepEqual(configuredAiProviders({ GEMINI_API_KEY: 'gem-key' }).map((item) => item.provider), ['gemini']);
const calls = [];
const fakeFetch = async (url, options) => {
  calls.push({ url, options });
  if (url.includes('generativelanguage')) return { ok: true, json: async () => ({ candidates: [{ content: { parts: [{ text: '{"title":"Gemini"}' }] } }] }) };
  return { ok: true, json: async () => ({ model: 'selected-model', choices: [{ message: { content: '{"title":"Chat"}' } }] }) };
};

(async () => {
  assert.deepEqual(await requestAiProvider(providers[0], 'system', 'user', fakeFetch), { content: '{"title":"Chat"}', model: 'selected-model' });
  assert.deepEqual(await requestAiProvider(providers[1], 'system', 'user', fakeFetch), { content: '{"title":"Gemini"}', model: 'gemini-2.5-flash' });
  assert.deepEqual(await requestAiProvider(providers[2], 'system', 'user', fakeFetch), { content: '{"title":"Chat"}', model: 'selected-model' });
  assert.deepEqual(calls.map((call) => new URL(call.url).hostname), ['openrouter.ai', 'generativelanguage.googleapis.com', 'api.openai.com']);
  assert.equal(calls[1].options.headers['x-goog-api-key'], 'gem-key');
  assert.equal(calls[2].options.headers.Authorization, 'Bearer oa-key');
  assert.match(calls[1].options.body, /systemInstruction/);
  await assert.rejects(requestAiProvider(providers[0], 's', 'u', async () => ({ ok: false, status: 503 })), /HTTP 503/);
  console.log('AI provider chain fixtures passed.');
})().catch((error) => { console.error(error); process.exitCode = 1; });
