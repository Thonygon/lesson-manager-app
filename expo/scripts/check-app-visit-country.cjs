const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/server/app-visit-country.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleRef = { exports: {} };
new Function('module', 'exports', compiled)(moduleRef, moduleRef.exports);
const { appVisitCountry } = moduleRef.exports;
const request = (country, cfCountry) => Object.assign(new Request('https://classio.test/api/app-visit', { headers: country ? { 'eas-ip-country': country } : {} }), cfCountry ? { cf: { country: cfCountry } } : {});

assert.equal(appVisitCountry(request('TR')), 'TR');
assert.equal(appVisitCountry(request('us')), 'US');
assert.equal(appVisitCountry(request('', 'GB')), 'GB');
assert.equal(appVisitCountry(request('XX')), 'ZZ');
assert.equal(appVisitCountry(request('T1')), 'ZZ');
assert.equal(appVisitCountry(request('BAD')), 'ZZ');
assert.equal(appVisitCountry(request('')), 'ZZ');
process.stdout.write('App visit country extraction passed.\n');
