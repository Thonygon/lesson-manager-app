const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/lib/explorer-draft-handoff.ts'), 'utf8');
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
const store = new Map();
const storage = { getItem: async (key) => store.get(key) ?? null, setItem: async (key, value) => { store.set(key, value); }, removeItem: async (key) => { store.delete(key); } };
const mod = { exports: {} };
new Function('module', 'exports', 'require', code)(mod, mod.exports, (name) => {
  if (name === '@react-native-async-storage/async-storage') return { __esModule: true, default: storage };
  throw new Error(name);
});
const { saveExplorerDraft, getExplorerDraft, clearExplorerDraft, parseExplorerDraft } = mod.exports;

async function main() {
  const input = { kind: 'worksheet', subject: 'Spanish', topic: 'Saludos', stage: 'adult_stage', level: 'A2', language: 'es', notes: '', duration: '45 minutes' };
  const document = { title: 'Saludos', questions: [{ prompt: '¿Cómo estás?' }], answer_key: { 1: 'Bien' } };
  await saveExplorerDraft(input, document);
  assert.deepEqual((await getExplorerDraft()).document, document, 'the generated document must survive the sign-in boundary');
  assert.equal((await getExplorerDraft()).input.topic, 'Saludos');
  const raw = [...store.values()][0];
  assert.equal(parseExplorerDraft(raw, Date.now() + 25 * 60 * 60 * 1000), null, 'a draft must expire');
  assert.equal(parseExplorerDraft(raw.replace('worksheet', 'video')), null, 'unsupported kinds must be rejected');
  await assert.rejects(saveExplorerDraft(input, { text: 'x'.repeat(250_000) }), /too large/);
  await clearExplorerDraft();
  assert.equal(await getExplorerDraft(), null);
  process.stdout.write('Explorer draft handoff fixtures passed.\n');
}
void main().catch((error) => { console.error(error); process.exitCode = 1; });
