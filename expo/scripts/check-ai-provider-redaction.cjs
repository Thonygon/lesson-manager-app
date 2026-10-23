const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const transpile = (name, requireFn = require) => {
  const source = fs.readFileSync(path.join(__dirname, '../src/server', name), 'utf8');
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const loaded = { exports: {} };
  new Function('module', 'exports', 'require', js)(loaded, loaded.exports, requireFn);
  return loaded.exports;
};
const privacy = transpile('ai-privacy-redaction.ts');
const bounded = transpile('bounded-ai-request.ts');
const economics = transpile('ai-economic-events.ts');
const { requestAiProvider } = transpile('ai-provider-chain.ts', (name) => name === './ai-privacy-redaction' ? privacy : name === './bounded-ai-request' ? bounded : name === './ai-economic-events' ? economics : require(name));
const prompt = 'Anna Garcìa necesita ayuda. Email ana@example.com. Phone +34 612 345 678. Address: 12 Main Street. Learner ID 1583928473928473928. Stage upper_primary. Native language Spanish. Level A2.';
(async () => {
  for (const provider of ['openrouter', 'gemini', 'openai']) {
    let body;
    const fetcher = async (_url, init) => {
      body = JSON.stringify(JSON.parse(init.body));
      return Response.json(provider === 'gemini' ? { candidates: [{ content: { parts: [{ text: '{}' }] } }] } : { choices: [{ message: { content: '{}' } }] });
    };
    await requestAiProvider({ provider, key: 'fixture-key', model: 'fixture-model' }, 'System instructions', prompt, fetcher, ['Ana García']);
    for (const identifier of ['Anna Garcìa', 'ana@example.com', '+34 612 345 678', '12 Main Street']) assert.ok(!body.includes(identifier), `${provider}: ${identifier}`);
    assert.match(body, /\[student name removed\]/);
    assert.match(body, /1583928473928473928/);
    assert.match(body, /upper_primary/);
    assert.match(body, /Native language Spanish/);
    assert.match(body, /Level A2/);
  }
  process.stdout.write('AI provider payload redaction passed for all configured providers.\n');
})().catch((error) => { console.error(error); process.exitCode = 1; });
