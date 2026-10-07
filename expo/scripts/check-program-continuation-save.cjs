const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const filename = path.resolve(__dirname, '../src/services/smart-tools.ts');
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const writes = [];
let previous = { id: 42, sequence_group_id: 'spanish-adult-abc', sequence_order: null, subject: 'spanish', custom_subject_name: null, learner_stage: 'adult_stage', level_or_band: 'A2', status: 'active' };
const client = {
  auth: { getUser: async () => ({ data: { user: { id: 'owner-id', email: 'teacher@example.com' } }, error: null }) },
  from: (table) => ({
    select: () => ({ eq() { return this; }, maybeSingle: async () => ({ data: table === 'learning_programs' ? previous : null, error: null }) }),
    insert: (payload) => { writes.push({ table, payload }); return { select: () => ({ single: async () => ({ data: { id: 99 }, error: null }) }) }; },
  }),
};
const localModule = { exports: {} };
new Function('module', 'exports', 'require', compiled)(localModule, localModule.exports, (specifier) => {
  if (specifier === '@/lib/supabase') return { requireSupabase: () => client };
  if (specifier === './program-storage') return { programTopicRow: () => ({}), programUnitRow: () => ({}) };
  if (specifier === '../shared/program-structure') return { nextProgramSequenceOrder: (level, order) => (order || ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'].indexOf(level) + 1) + 1 };
  throw new Error(`Unexpected import ${specifier}`);
});
const input = { kind: 'program', subject: 'Spanish', topic: 'Travel', stage: 'adult_stage', level: 'B1', language: 'es', planLanguage: 'en', previousProgramId: '42', generationMode: 'template', duration: '', notes: '' };
const document = { title: 'Spanish B1', units: [] };
(async () => {
  await localModule.exports.saveGeneratedMaterial(input, document);
  assert.equal(writes[0].payload.parent_program_id, 42);
  assert.equal(writes[0].payload.sequence_group_id, 'spanish-adult-abc');
  assert.equal(writes[0].payload.sequence_order, 3);
  assert.equal(writes[0].payload.source_type, 'template');
  assert.equal(writes[0].payload.builder_config.generation_path, 'next_level');
  previous = null;
  await assert.rejects(() => localModule.exports.saveGeneratedMaterial(input, document), /previous program is unavailable/i);
  assert.equal(writes.length, 1);
  process.stdout.write('Program continuation save fixture passed.\n');
})().catch((error) => { console.error(error); process.exitCode = 1; });
