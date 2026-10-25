const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/lib/password-recovery-link.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleRef = { exports: {} };
new Function('module', 'exports', 'require', compiled)(moduleRef, moduleRef.exports, require);
const { parsePasswordRecoveryLink } = moduleRef.exports;

assert.deepEqual(parsePasswordRecoveryLink('classio:///reset-password#access_token=secret&refresh_token=refresh&type=recovery'), { kind: 'session', accessToken: 'secret', refreshToken: 'refresh' });
assert.deepEqual(parsePasswordRecoveryLink('classio://reset-password#access_token=secret&refresh_token=refresh&type=recovery'), { kind: 'session', accessToken: 'secret', refreshToken: 'refresh' });
assert.deepEqual(parsePasswordRecoveryLink('exp://127.0.0.1:8081/--/reset-password#access_token=secret&refresh_token=refresh&type=recovery'), { kind: 'session', accessToken: 'secret', refreshToken: 'refresh' });
assert.equal(parsePasswordRecoveryLink('classio:///reset-password#access_token=secret&refresh_token=refresh&type=magiclink').kind, 'none');
assert.equal(parsePasswordRecoveryLink('classio:///home#access_token=secret&refresh_token=refresh&type=recovery').kind, 'none');
assert.equal(parsePasswordRecoveryLink('classio:///reset-password#error=access_denied').kind, 'error');
assert.equal(parsePasswordRecoveryLink('classio:///reset-password#type=recovery&access_token=secret').kind, 'error');
console.log('Password recovery link fixtures passed');
