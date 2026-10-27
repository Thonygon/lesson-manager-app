const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/lib/hosting-api-url.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleRef = { exports: {} };
new Function('module', 'exports', 'require', compiled)(moduleRef, moduleRef.exports, () => ({ Platform: { OS: 'web' } }));
const { hostingApiUrl } = moduleRef.exports;

assert.equal(hostingApiUrl('/api/choose-role', 'web'), '/api/choose-role');
assert.equal(hostingApiUrl('/api/choose-role', 'ios', 'https://app.masterclassio.com/'), 'https://app.masterclassio.com/api/choose-role');
assert.equal(hostingApiUrl('/api/program-topic-videos?programId=7', 'android', 'https://beta.example/'), 'https://beta.example/api/program-topic-videos?programId=7');
assert.equal(hostingApiUrl('/api/public-exams?page=2', 'ios', ''), 'https://app.masterclassio.com/api/public-exams?page=2');
console.log('Hosting API URL fixtures passed');
