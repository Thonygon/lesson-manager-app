const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const transpile = (name, requireFn = require) => {
  const source = fs.readFileSync(path.join(__dirname, '../src/server', name), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const loaded = { exports: {} };
  new Function('module', 'exports', 'require', compiled)(loaded, loaded.exports, requireFn);
  return loaded.exports;
};
const privacy = transpile('ai-privacy-redaction.ts');
const bounded = transpile('bounded-ai-request.ts');
const economics = transpile('ai-economic-events.ts');
const { configuredAiProviders, requestAiProvider } = transpile('ai-provider-chain.ts', (name) => name === './ai-privacy-redaction' ? privacy : name === './bounded-ai-request' ? bounded : name === './ai-economic-events' ? economics : require(name));

const providers = configuredAiProviders({ OPENROUTER_API_KEY: 'or-key', GEMINI_API_KEY: 'gem-key', OPENAI_API_KEY: 'oa-key' });
assert.deepEqual(providers.map((item) => item.provider), ['openrouter', 'gemini', 'openai']);
assert.deepEqual(providers.map((item) => item.model), ['google/gemma-4-31b-it:free', 'gemini-2.5-flash', 'gpt-4o-mini']);
assert.deepEqual(configuredAiProviders({ GEMINI_API_KEY: 'gem-key' }).map((item) => item.provider), ['gemini']);
assert.equal(configuredAiProviders({ OPENROUTER_API_KEY: 'or-key', OPENROUTER_MODEL: 'openrouter/free' })[0].model, 'google/gemma-4-31b-it:free');
const calls = [];
const fakeFetch = async (url, options) => {
  calls.push({ url, options });
  if (url.includes('generativelanguage')) return Response.json({ candidates: [{ content: { parts: [{ text: '{"title":"Gemini"}' }] } }] });
  return Response.json({ model: 'selected-model', choices: [{ message: { content: '{"title":"Chat"}' } }] });
};

(async () => {
  const openRouter = await requestAiProvider(providers[0], 'system', 'user', fakeFetch);
  const gemini = await requestAiProvider(providers[1], 'system', 'user', fakeFetch);
  const openAi = await requestAiProvider(providers[2], 'system', 'user', fakeFetch);
  assert.equal(openRouter.content, '{"title":"Chat"}');
  assert.equal(openRouter.model, 'selected-model');
  assert.equal(openRouter.usage.input_tokens, null);
  assert.equal(gemini.content, '{"title":"Gemini"}');
  assert.equal(gemini.model, 'gemini-2.5-flash');
  assert.equal(openAi.content, '{"title":"Chat"}');
  assert.equal(openAi.model, 'selected-model');
  assert.deepEqual(calls.map((call) => new URL(call.url).hostname), ['openrouter.ai', 'generativelanguage.googleapis.com', 'api.openai.com']);
  assert.equal(calls[1].options.headers['x-goog-api-key'], 'gem-key');
  assert.equal(calls[2].options.headers.Authorization, 'Bearer oa-key');
  assert.match(calls[1].options.body, /systemInstruction/);
  await assert.rejects(requestAiProvider(providers[0], 's', 'u', async () => new Response(null, { status: 503 })), /HTTP 503/);
  console.log('AI provider chain fixtures passed.');
})().catch((error) => { console.error(error); process.exitCode = 1; });
