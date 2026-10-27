const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/lib/public-resource-handoff.ts'), 'utf8');
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
const store = new Map();
const storage = { getItem: async (key) => store.get(key) ?? null, setItem: async (key, value) => { store.set(key, value); }, removeItem: async (key) => { store.delete(key); } };
const mod = { exports: {} };
new Function('module', 'exports', 'require', code)(mod, mod.exports, (name) => {
  if (name === '@react-native-async-storage/async-storage') return { __esModule: true, default: storage };
  throw new Error(name);
});

async function main() {
  const { savePublicResourceHandoff, getPublicResourceHandoff, clearPublicResourceHandoff, parsePublicResourceHandoff } = mod.exports;
  await savePublicResourceHandoff({ kind: 'worksheet', id: '42', title: 'Spanish practice' });
  assert.deepEqual(((await getPublicResourceHandoff()) || {}).title, 'Spanish practice');
  const raw = [...store.values()][0];
  assert.equal(parsePublicResourceHandoff(raw, Date.now() + 25 * 60 * 60 * 1000), null);
  assert.equal(parsePublicResourceHandoff(raw.replace('worksheet', 'invalid')), null);
  await assert.rejects(savePublicResourceHandoff({ kind: 'worksheet', id: 'abc', title: 'Invalid' }), /Invalid/);
  await clearPublicResourceHandoff();
  assert.equal(await getPublicResourceHandoff(), null);
  process.stdout.write('Public resource handoff fixtures passed.\n');
}
void main().catch((error) => { console.error(error); process.exitCode = 1; });
